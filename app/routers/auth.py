import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status, Form, Depends, Body, BackgroundTasks
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import pytz

import services
from ..schemas import schemas_users, schemas_token, schemas_email_code
from ..dependencies import get_async_session,get_sync_session
from ..dependencies.users import get_current_user
from ..exceptions import CredentialsException
from ..models.users import User
from ..models.auth import RegistrationCode
from ..schemas.schemas_email_code import RegistrationCodeInDB
from .. import tasks
from ..utils.general import create_jwt_token
from ..static import openapi

router = APIRouter(
	prefix="/auth",
	tags=["authentication"]
)


@router.post("/token", tags=["token"], responses=openapi.token_post_responses, response_model=schemas_token.Token)
async def login_for_access_token(
	email: Annotated[str, Form(title="Email пользователя")],
	password: Annotated[str, Form(title="Пароль пользователя")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Проверка логина и пароля (хэша) пользователя при авторизации.
	Если они верны, то создается access_token (JWT token) и возвращается.
	"""
	user = await User.authenticate_user(
		db=db, email=email, password=password
	)
	if not user:
		raise CredentialsException(detail="Incorrect username or password")

	if user.disabled:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	access_token = create_jwt_token(
		data={"sub": user.email}, expires_at_hours=services.ACCESS_TOKEN_EXPIRE_HOURS
	)

	logger.info(f"User {email} (ID: {user.id}) was successfully authorized")

	return {"access_token": access_token, "token_type": "bearer"}


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
	if current_db_code.expires_at < datetime.datetime.now(tz=pytz.UTC):
		# pytz.UTC -  конвертация текущего времени в UTC-формат
		raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Confirmation code expired")
	if not code_verifying:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid confirmation code")

	confirmed_user, confirmed_code = await User.confirm_user_email(user=current_user, email_code=current_db_code, db=db)

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
		if datetime.datetime.now(tz=pytz.UTC) < last_user_confirmation_code.expires_at:
			# pytz.UTC -  конвертация текущего времени в UTC-формат
			raise HTTPException(status_code=status.HTTP_425_TOO_EARLY,
								detail="Active user confirmation code already exists")

	send_email_confirmation_code.add_task(tasks.send_verifying_email_code, current_user, sync_db)

	return Response(status_code=status.HTTP_200_OK)
