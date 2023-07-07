from typing import Optional, Any

from sqlalchemy import Column, Integer, String, Boolean, DateTime, select, Enum, func, update
from sqlalchemy.ext.asyncio import AsyncSession

import services
from .. import utils
from ..schemas import schemas_users, schemas_email_code
from ..database import Base
from ..utils import sa_object_to_dict
from ..static.enums import RoleEnum
from .auth import RegistrationCode


class User(Base):
	"""
	 Модель пользователя

	 Role - права пользователя.
	 Disabled - заблокирован или нет.
	 Email_confirmed - подтвержден ли email.
	"""
	__tablename__ = "user"

	id = Column(Integer, primary_key=True, index=True)
	email = Column(String(length=50), unique=True, index=True)
	first_name = Column(String(length=50))
	last_name = Column(String(length=50))
	role = Column(Enum(RoleEnum), default=services.USER_DEFAULT_ROLE)
	disabled = Column(Boolean, default=False)
	hashed_password = Column(String)
	registered_at = Column(DateTime(timezone=True), server_default=func.now())
	last_action_at = Column(DateTime(timezone=True))
	email_confirmed = Column(Boolean, default=False)

	@staticmethod
	async def get_user_by_email(db: AsyncSession, email: str) -> Optional[schemas_users.UserInDB]:
		"""
		Поиск пользователя по email.
		"""
		query = select(User).where(User.email == email)
		result = await db.execute(query)
		user: User | None = result.scalar()
		if isinstance(user, User):
			user_dict: dict[str, Any] = sa_object_to_dict(user)
			return schemas_users.UserInDB(**user_dict)

	@staticmethod
	async def authenticate_user(db: AsyncSession, email: str, password: str) -> None | schemas_users.UserInDB:
		"""
		Аутентификация пользователя: если пользователя с таким email не существует или
		был введен неправильный пароль - возвращает False; иначе возвращает pydantic-модель пользователя
		с хеш-паролем.
		"""
		user = await User.get_user_by_email(db=db, email=email)
		if not user:
			return
		if not utils.verify_data_hash(password, user.hashed_password):
			return
		return user

	@staticmethod
	async def confirm_user_email(
		db: AsyncSession, user: schemas_users.User, email_code: schemas_email_code.RegistrationCodeInDB
	) -> tuple[schemas_users.User, schemas_email_code.RegistrationCode]:
		"""
		Подтвердить Email пользователя.
		Изменяются:
		- Пользователь в БД (email_confirmed);
		- Запись об отправленном коде пользователю в БД.
		"""
		confirmed_user_code = await RegistrationCode.confirm_user_code(
			user=user, registration_code=email_code, db=db
		)
		query = update(User).where(
			User.id == user.id
		).values(email_confirmed=True)

		await db.execute(query)
		await db.commit()

		return await User.get_user_by_email(email=user.email, db=db), confirmed_user_code

