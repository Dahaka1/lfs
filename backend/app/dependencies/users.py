from typing import Annotated

from fastapi import Depends, status, HTTPException, Path, Cookie
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import oauth2_scheme, get_async_session
from ..exceptions import CredentialsException, PermissionsError
from ..models.users import User
from ..schemas import schemas_users, schemas_token
from ..utils.general import decode_jwt


async def get_current_user(
	token: Annotated[str, Depends(oauth2_scheme)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	refreshToken: str | None = Cookie(default=None, title="Refresh токен")
) -> schemas_users.UserInDB:
	"""
	Функция для декодирования получаемого от пользователя токена (access и refresh).
	Если токен не содержит email или не поддается декодированию, поднимается ошибка авторизации.
	Если токен корректный, но нет пользователя с указанным email - тоже.
	Эта функция в dependency, потому что будет по дефолту срабатывать при каждом запросе от пользователей.
	"""
	if not refreshToken:
		raise CredentialsException()
	if refreshToken[-6:] != token[-6:]:
		raise CredentialsException()
	try:
		access_payload = decode_jwt(token)
		email: str = access_payload.get("sub")  # sub is std jwt token data param
		if email is None:
			raise CredentialsException()
		token_data = schemas_token.TokenData(email=email)
	except JWTError:
		raise CredentialsException()
	user = await User.get_user_by_email(db=db, email=token_data.email)
	if user is None:
		raise CredentialsException()

	return user


async def get_current_active_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> schemas_users.User:
	"""
	Функция проверяет, заблокирован ли пользователь, сделавший запрос.
	+ Подтвержден ли Email.

	И обновляет время последнего действия пользователя.
	"""
	if current_user.disabled:
		raise PermissionsError("Disabled user")
	if not current_user.email_confirmed:
		raise PermissionsError("User email is not confirmed")

	await User.update_user_last_action(user=current_user, db=db)

	return current_user


async def get_user_id(
	user_id: Annotated[int, Path(ge=1)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> int:
	"""
	Функция проверяет, существует ли пользователь с переданным ИД в URL'е (пути запроса).
	Возвращает ИД.
	"""
	result = await db.execute(
		select(User).where(User.id == user_id)
	)
	user_db = result.scalar()
	if user_db is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
	return user_id


