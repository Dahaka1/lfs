from typing import Any
import random

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, update
from sqlalchemy.orm import Session
from httpx import AsyncClient

import config
import services
from app.static.enums import RoleEnum, RegionEnum
from app.models.users import User
from app.schemas import schemas_users
from app.utils.general import get_data_hash, sa_object_to_dict
from .auth import get_user_token


def generate_user_data(request) -> Any:
	"""
	Дополняет объект запроса для тестов нужными данными пользователя.
	"""
	request.cls.email = f"autotest_{random.randrange(10_000)}@gmail.com"
	request.cls.password = str(random.randrange(10_000_000, 20_000_000))
	request.cls.first_name = random.choice(
		("Andrew", "Petr", "Ivan")
	)
	request.cls.last_name = random.choice(
		("Petrov", "Sidorov", "Ivanov")
	)
	request.cls.region = "Северо-западный"  # ИЗ ЕНАМА РЕГИОНОВ

	return request


async def create_user(request, sync_session: Session,
					  role: RoleEnum = services.USER_DEFAULT_ROLE) -> schemas_users.User:
	"""
	Создает пользователя напрямую в БД (чтобы избежать отправки
	 письма подтверждения).
	"""

	user = User(
		email=request.cls.email,
		first_name=request.cls.first_name,
		last_name=request.cls.last_name,
		hashed_password=get_data_hash(request.cls.password),
		region=RegionEnum.NORTHWEST,
		role=role
	)

	sync_session.add(user)

	sync_session.commit()
	sync_session.refresh(user)

	return schemas_users.User(**sa_object_to_dict(user))


async def create_authorized_user(request, ac: AsyncClient, sync_session: Session) -> dict[str, Any]:
	"""
	Создает сисадмин-юзера.
	Без проверки на ошибки (это не тест, а побочная функция).
	"""
	user = await create_user(request, sync_session=sync_session)
	token = await get_user_token(user.email, request.cls.password, ac)
	result = dict()
	result["token"] = token.access_token
	result["headers"] = {
		"Authorization": f"Bearer {token.access_token}"
	}
	result["user_schema"] = user

	return {**result, **user.dict()}


async def change_user_data(user: Any, session: AsyncSession, **kwargs) -> None:
	"""
	Изменяет данные пользователя в БД.
	"""
	fields = [c.key for c in User.__table__.columns]
	if any(
		(arg not in fields for arg in kwargs)
	):
		raise ValueError

	user.id: int
	await session.execute(
		update(User).where(User.id == user.id).values(**kwargs)
	)
	await session.commit()
