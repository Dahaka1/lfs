from typing import Annotated

from fastapi import Depends, status, HTTPException, Path
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from ..schemas import schemas_users, schemas_token
from ..exceptions import CredentialsException
from ..models.users import User
from . import oauth2_scheme, get_async_session


async def get_current_user(
	token: Annotated[str, Depends(oauth2_scheme)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> schemas_users.UserInDB:
	"""
	Функция для декодирования получаемого от пользователя токена.
	Если токен не содержит email или не поддается декодированию, поднимается ошибка авторизации.
	Если токен корректный, но нет пользователя с указанным email - тоже.
	Эта функция в dependency, потому что будет по дефолту срабатывать при каждом запросе от пользователей.
	"""
	try:
		payload = jwt.decode(token=token, key=config.JWT_SECRET_KEY, algorithms=[config.JWT_SIGN_ALGORITHM])
		email: str = payload.get("sub")  # sub is std jwt token data param
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
	current_user: Annotated[schemas_users.User, Depends(get_current_user)]
) -> schemas_users.User:
	"""
	Функция проверяет, заблокирован ли пользователь, сделавший запрос.
	+ Подтвержден ли Email.
	"""
	if current_user.disabled:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Disabled user")
	if not current_user.email_confirmed:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User email is not confirmed")
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


