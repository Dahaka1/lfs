import datetime
from typing import Any
import random

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from sqlalchemy.orm import Session
from httpx import AsyncClient
from pydantic import BaseModel

import services
from app.static.enums import RoleEnum, RegionEnum
from app.models.users import User
from app.schemas import schemas_users
from app.utils.general import get_data_hash, sa_object_to_dict, sa_objects_dicts_list
from app.schemas.schemas_token import Token


class UserData(BaseModel):
	"""
	Набор данных пользователя для тестов.
	"""
	id: int
	email: str
	first_name: str
	last_name: str
	region: RegionEnum
	password: str
	role: RoleEnum
	disabled: bool
	email_confirmed: bool
	token: str
	headers: dict
	cookies: dict
	registered_at: datetime.datetime


async def get_user_token(email: str, password: str, ac: AsyncClient) -> tuple[Token, str]:
	"""
	Аутентификация пользователя.
	Без проверки на ошибки (это не тест, а побочная функция).
	"""
	data = {
		"email": email,
		"password": password
	}
	response = await ac.post(
		"/api/v1/auth/login",
		data=data
	)
	return Token(**response.json()), response.cookies.get("refreshToken")


def generate_user_data() -> dict[str, str]:
	"""
	Дополняет объект запроса для тестов нужными данными пользователя.
	"""
	data = {
		"email": f"autotest_{random.randrange(10_000_000)}@gmail.com",
		"password": str(random.randrange(10_000_000, 20_000_000)),
		"first_name": random.choice(("Andrew", "Petr", "Ivan")),
		"last_name": random.choice(("Petrov", "Sidorov", "Ivanov"))
	}
	return data


def create_user(sync_session: Session, role: RoleEnum | None = None, **kwargs) ->\
	dict[str, int | str | dict | RegionEnum | RoleEnum]:
	"""
	Создает пользователя напрямую в БД (чтобы избежать отправки
	 письма подтверждения).
	"""
	if role is None:
		role = services.USER_DEFAULT_ROLE

	user_data = generate_user_data()

	user = User(
		email=user_data.get("email"),
		first_name=user_data.get("first_name"),
		last_name=user_data.get("last_name"),
		hashed_password=get_data_hash(user_data.get("password")),
		region=RegionEnum.NORTHWEST,
		role=role,
		**kwargs
	)

	sync_session.add(user)

	sync_session.commit()
	sync_session.refresh(user)

	result = sa_object_to_dict(user)
	result.pop("hashed_password")
	result.setdefault("password", user_data.get("password"))

	return result


async def create_authorized_user(ac: AsyncClient, sync_session: Session, role: RoleEnum = None,
								 confirm_email: bool = False) -> tuple[UserData, schemas_users.User]:
	"""
	Создает авторизованного юзера.
	Без проверки на ошибки (это не тест, а побочная функция).
	"""
	params = dict(sync_session=sync_session, role=role)
	if confirm_email:
		params["email_confirmed"] = True
	user = create_user(**params)
	token, refresh = await get_user_token(user.get("email"), user.get("password"), ac)

	user.setdefault("token", token.access_token)
	user.pop("last_action_at")
	user["headers"] = {"Authorization": f"Bearer {token.access_token}"}
	user["cookies"] = {"refreshToken": refresh}

	return UserData(**user), schemas_users.User(**user)


async def create_multiple_users(ac: AsyncClient, sync_session: Session) -> list[UserData]:
	"""
	Создает авторизованных и подтвержденных пользователей по каждой роли.
	"""
	users = []
	for role in (RoleEnum.SYSADMIN, RoleEnum.MANAGER, RoleEnum.INSTALLER, RoleEnum.LAUNDRY):
		user, user_schema = await create_authorized_user(ac, sync_session, role, True)
		users.append(user)
	return users


async def change_user_data(user: Any | int, session: AsyncSession, **kwargs) -> None:
	"""
	Изменяет данные пользователя в БД.
	"""
	fields = [c.key for c in User.__table__.columns]
	if any(
		(arg not in fields for arg in kwargs)
	):
		raise ValueError

	user_id = user.id if not isinstance(user, int) else user

	await session.execute(
		update(User).where(User.id == user_id).values(**kwargs)
	)
	await session.commit()


async def get_user_by_id(id: int, session: AsyncSession) -> schemas_users.User:
	"""
	Поиск пользователя в БД.
	"""
	user = await session.execute(
		select(User).where(User.id == id)
	)
	return schemas_users.User(
		**sa_object_to_dict(user.scalar())
	)


async def get_all_users(session: AsyncSession) -> list[dict]:
	"""
	Список всех пользователей
	"""
	return sa_objects_dicts_list(
		(await session.execute(
			select(User)
		)).scalars().all()
	)