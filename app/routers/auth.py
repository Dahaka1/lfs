import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status, Form, Depends, Body, BackgroundTasks
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from ..schemas import schemas_token, schemas_users, schemas_email_code
from .. import utils
from ..dependencies import get_async_session
from ..dependencies.users import get_current_user
from ..exceptions import CredentialsException
from ..models.users import User
from ..models.auth import RegistrationCode
from ..schemas.schemas_email_code import RegistrationCodeInDB
from .. import tasks

router = APIRouter(
	prefix="/auth",
	tags=["authentication"]
)


@router.post("/token", tags=["token"], response_model=schemas_token.Token)
async def login_for_access_token(
	email: Annotated[str, Form()],
	password: Annotated[str, Form()],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Метод проверяет логин и пароль пользователя при авторизации.
	Если они верны, то создает access_token (JWT token) и возвращает его.
	"""
	user = await User.authenticate_user(
		db=db, email=email, password=password
	)
	if not user:
		raise CredentialsException(detail="Incorrect username or password")

	if user.disabled:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")

	access_token = utils.create_access_token(
		data={"sub": user.email}
	)

	logger.info(f"User {email} (ID: {user.id}) was successfully authorized")

	return {"access_token": access_token, "token_type": "bearer"}


@router.post(
	"/confirm_email",
	tags=["confirming_email"],
	response_model=dict[str, schemas_users.User | schemas_email_code.RegistrationCode],
	response_description="Пользователь с подтвержденным Email и измененная запись в registration_code"
)
async def confirm_user_email(
	current_user: Annotated[schemas_users.User, Depends(get_current_user)],
	code: Annotated[str, Body(title="Код подтверждения Email", embed=True)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Подтверждение Email пользователя.
	Для подтверждения пользователь должен быть авторизован (ожидается токен).
	"""
	if current_user.email_confirmed:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User email already confirmed")

	current_db_code: RegistrationCodeInDB = await RegistrationCode.get_user_last_code(user=current_user, db=db)

	if current_db_code is None:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User code in DB not found")
	code_verifying = RegistrationCode.verify_code(code=code, hashed_code=current_db_code.hashed_code)
	if not code_verifying:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid confirmation code")
	if current_db_code.expires_at < datetime.datetime.now(tz=pytz.UTC):
		# pytz.UTC -  конвертация текущего времени в UTC-формат
		raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Confirmation code expired")

	confirmed_user, confirmed_code = await User.confirm_user_email(user=current_user, email_code=current_db_code, db=db)

	logger.info(f"User email {current_user.email} was successfully confirmed.")

	return {
		"user": confirmed_user.dict(), "email_code": confirmed_code.dict()
	}


@router.get(
	"/confirm_email", tags=["confirming_email_request_code_manually"],
	description="Ручной запрос отправки кода подтверждения."
)
async def request_confirmation_code(
	current_user: Annotated[schemas_users.User, Depends(get_current_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	send_email_confirmation_code: BackgroundTasks
):
	"""
	Используется, если код не дошел до пользователя/истек и т.д.

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

	send_email_confirmation_code.add_task(tasks.send_verifying_email_code, current_user, db)

	return Response(status_code=200)
