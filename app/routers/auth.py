import datetime
from typing import Annotated

import pytz
from fastapi import APIRouter, HTTPException, status, Depends, Body, BackgroundTasks, Header
from fastapi.responses import Response, JSONResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from .. import tasks
from ..dependencies import get_async_session, get_sync_session
from ..dependencies.users import get_current_user
from ..exceptions import CredentialsException
from ..models.auth import RegistrationCode, RefreshToken
from ..models.users import User
from ..schemas import schemas_users, schemas_token, schemas_email_code
from ..schemas.schemas_email_code import RegistrationCodeInDB
from ..static import openapi
from ..utils.general import create_token_response

router = APIRouter(
	prefix="/auth",
	tags=["authentication"]
)


@router.post("/login", responses=openapi.login_post,
			 response_model=schemas_token.LoginTokens)
async def login(
	email: Annotated[str, Body(title="Email пользователя")],
	password: Annotated[str, Body(title="Пароль пользователя")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Проверка логина и пароля (хэша) пользователя при авторизации.
	Если они верны, то создаются access_token и refresh_token (JWT token) и возвращаются.
	Refresh - в body, access - в body.
	"""
	user = await User.authenticate_user(
		db=db, email=email, password=password
	)
	if not user:
		raise CredentialsException(detail="Incorrect username or password")

	if user.disabled:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	token, refresh = await RefreshToken.generate(user, db)

	logger.info(f"User {email} (ID: {user.id}) was successfully authorized")

	response = create_token_response(token, refresh)
	response.headers["Authorization"] = f"{token.token_type} {token.access_token}"

	return response


@router.get("/refresh", response_model=schemas_token.LoginTokens, responses=openapi.refresh_access_token_get)
async def refresh_access_token(
	db: Annotated[AsyncSession, Depends(get_async_session)],
	refreshToken: Annotated[str, Header(title="Refresh токен")]
):
	"""
	Обновление токенов пользователя при истечении срока действия Access токена.
	"""
	if refreshToken is None:
		raise CredentialsException()

	user = await RefreshToken.validate(refreshToken, db)

	if not user:
		raise CredentialsException()
	if user.disabled:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	token, refresh = await RefreshToken.generate(user, db)

	logger.info(f"User {user.email} (ID: {user.id}) authorization was successfully refreshed")

	response = create_token_response(token, refresh)

	response.headers["Authorization"] = f"{token.token_type} {token.access_token}"

	return response


@router.get("/logout", responses=openapi.logout_get)
async def logout(
	current_user: Annotated[schemas_users.User, Depends(get_current_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Удаляет из кук и БД рефреш-токен.
	+ на стороне фронта нужно удалить access-токен из headers!
	"""
	if current_user.disabled:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	await RefreshToken.deactivate(current_user, db)

	response = JSONResponse(content={"logout": current_user.email})

	return response


@router.post(
	"/confirm_email",
	tags=["confirming_email"],
	responses=openapi.confirm_email_post_responses,
	response_model=dict[str, schemas_users.User | schemas_email_code.RegistrationCode]
)
async def confirm_user_email(
	current_user: Annotated[schemas_users.User, Depends(get_current_user)],
	code: Annotated[str, Body(title="Код подтверждения Email", embed=True)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Подтверждение Email пользователя.
	Для подтверждения пользователь должен быть авторизован (ожидается токен).

	Если email уже подтвержден или пользователь заблокирован - подтвердить нельзя.
	Если код в БД не найден по каким-то причинам или истек или не совпадает с полученным кодом - вернутся ошибки.
	"""
	if current_user.email_confirmed:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User email already confirmed")

	if current_user.disabled:  # дублируется из dependencies.get_current_active_user, чтобы не делать новую dependency
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	current_db_code: RegistrationCodeInDB = await RegistrationCode.get_user_last_code(user=current_user, db=db)

	if current_db_code is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User code not found")
	code_verifying = RegistrationCode.verify_code(code=code, hashed_code=current_db_code.hashed_code)
	if current_db_code.expires_at < datetime.datetime.utcnow().replace(tzinfo=pytz.UTC):
		raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Confirmation code expired")
	if not code_verifying:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid confirmation code")

	confirmed_code = await RegistrationCode.confirm_user_code(user=current_user, registration_code=current_db_code, db=db)
	confirmed_user = await User.confirm_user_email(user=current_user, db=db)

	logger.info(f"User email {current_user.email} was successfully confirmed.")

	return {
		"user": confirmed_user.dict(), "email_code": confirmed_code.dict()
	}


@router.get(
	"/confirm_email", tags=["confirming_email"],
	description="Ручной запрос отправки кода подтверждения.",
	responses=openapi.confirm_email_get_responses
)
async def request_confirmation_code(
	current_user: Annotated[schemas_users.User, Depends(get_current_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	send_email_confirmation_code: BackgroundTasks,
	sync_db: Annotated[Session, Depends(get_sync_session)]
):
	"""
	Используется, если код не дошел до пользователя/истек и т.д.

	Если пользователь заблокирован/подтвержден или неистекший код уже существует - вернутся ошибки.

	TODO: Можно ввести ограничение на общее количество кодов.
	"""
	last_user_confirmation_code = await RegistrationCode.get_user_last_code(user=current_user, db=db)

	if current_user.disabled:  # дублируется из dependencies.get_current_active_user, чтобы не делать новую dependency
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	if current_user.email_confirmed:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User email already confirmed")

	if not last_user_confirmation_code is None:
		if datetime.datetime.utcnow().replace(tzinfo=pytz.UTC) < last_user_confirmation_code.expires_at:
			raise HTTPException(status_code=status.HTTP_425_TOO_EARLY,
								detail="Active user confirmation code already exists")

	send_email_confirmation_code.add_task(tasks.send_verifying_email_code, current_user, sync_db)

	return Response(status_code=status.HTTP_200_OK)
