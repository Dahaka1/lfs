from __future__ import annotations

import datetime
import os.path
import random
from email.message import EmailMessage
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, \
	func, Boolean, PrimaryKeyConstraint, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from loguru import logger

import services, config
from ..database import Base
from ..schemas.schemas_users import User
from ..schemas.schemas_email_code import RegistrationCodeInDB
from ..utils.general import get_data_hash, sa_object_to_dict, verify_data_hash


class RegistrationCode(Base):
	"""
	Email-коды для регистрации пользователей.

	Sended_to - Email, куда был отправлен код.
	Sended_from - EMail, откуда был отправлен код.
	Sended_at - время отправки кода пользователю.
	Is_confirmed - подтвержден ли код пользователем.
	Confirmed_at - когда подтвержден (если подтвержден).
	Expires_at - когда истекает срок действия.
	"""
	CODE_LENGTH = services.CODE_LENGTH

	__tablename__ = "registration_code"
	__table_args__ = (
		PrimaryKeyConstraint("user_id", "sended_at"),
	)

	user_id = Column(Integer, ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"), index=True)
	sended_to = Column(String)
	sended_from = Column(String)
	hashed_code = Column(String)
	sended_at = Column(DateTime(timezone=True), server_default=func.now())
	is_confirmed = Column(Boolean, default=False)
	confirmed_at = Column(DateTime(timezone=True), onupdate=func.now(), default=None)
	expires_at = Column(DateTime(timezone=True))

	@staticmethod
	def create_obj(
		email_message: EmailMessage, verification_code: str, user: User, db: Session,
		expires_at=datetime.datetime.now() + datetime.timedelta(minutes=services.CODE_EXPIRING_IN_MINUTES)
	) -> None:
		"""
		Создать запись об отправленном коде напрямую в БД.
		Думаю, не нужно делать для этого отдельные CRUD-методы.
		"""
		verification_code_hash = get_data_hash(data=verification_code)

		code = RegistrationCode(
			user_id=user.id,
			hashed_code=verification_code_hash,
			sended_to=user.email,
			sended_from=email_message["From"],
			expires_at=expires_at
		)

		db.add(code)
		db.commit()

	@staticmethod
	async def get_user_last_code(
		user: User, db: AsyncSession
	) -> RegistrationCodeInDB | None:
		"""
		Получить запись о последнем отправленном коде пользователю.
		Если их нет - возвращает None.
		"""
		query = select(RegistrationCode).where(
			RegistrationCode.user_id == user.id
		).order_by(RegistrationCode.sended_at.desc()).limit(1)
		result = await db.execute(query)
		user_code = result.scalar()

		if user_code:
			return RegistrationCodeInDB(
				**sa_object_to_dict(user_code)
			)

	@staticmethod
	async def confirm_user_code(
		user: User,
		registration_code: RegistrationCodeInDB,
		db: AsyncSession
	) -> Optional[RegistrationCodeInDB]:
		"""
		Подтверждает код пользователя.
		Возвращает обновленный код.
		"""
		query = update(RegistrationCode).where(
			(RegistrationCode.user_id == user.id) &
			(RegistrationCode.sended_at == registration_code.sended_at)
		).values(is_confirmed=True)

		await db.execute(query)
		await db.commit()

		query = select(RegistrationCode).where(
			(RegistrationCode.user_id == user.id) &
			(RegistrationCode.sended_at == registration_code.sended_at)
		)

		result = await db.execute(query)
		updated_code = result.scalar()

		if updated_code:
			return RegistrationCodeInDB(
				**sa_object_to_dict(updated_code)
			)

	@classmethod
	def verify_code(cls, code: str, hashed_code: str) -> bool:
		"""
		Проверяет код на валидность.
		"""
		if len(code) != cls.CODE_LENGTH or not verify_data_hash(data=code, hashed_data=hashed_code):
			return False
		return True

	@classmethod
	def generate_code(cls) -> str:
		"""
		Генерирует код верификации с указанной длиной строки.
		В будущем можно добавить больше параметров.
		"""
		return ''.join(
			[str(random.randint(0, 9)) for _ in range(cls.CODE_LENGTH)]
		)

	@staticmethod
	def generate_message_template(user: User, code: str) -> str:
		"""
		Генерация шаблона для сообщения с кодом верификации.

		Пока сделаю самый примитивный вариант.
		"""
		filepath = config.HTML_TEMPLATES_DIR + "/sending_verification_code.html"
		if not os.path.exists(filepath):
			logger.warning("Can't generate template for sending Email-verification code. "
						 f"HTML template not found by path {filepath}")
			return f"""
			<div><h1>Здравствуйте, {user.first_name}!</h1><br>Ваш код для подтверждения Email: {code}</div>
			"""
		else:
			with open(config.HTML_TEMPLATES_DIR + "/sending_verification_code.html", encoding='utf-8') as template:
				html = template.read()
				return html.format(username=user.first_name, code=code)
