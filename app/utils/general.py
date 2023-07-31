import asyncio
import json
import random
from datetime import timedelta, datetime, timezone
from string import ascii_letters
from typing import Any, Sequence

import geopy
from geopy.geocoders import Nominatim
from geopy.adapters import AioHTTPAdapter
from cryptography.fernet import Fernet
from fastapi.responses import JSONResponse
from jose import jwt

import config
from ..database import Base
from ..schemas.schemas_token import Token, RefreshToken


def verify_data_hash(data, hashed_data) -> bool:
	"""
	Сравнение хешей данных (паролей, email-кодов, ...).
	"""
	return config.pwd_context.verify(data, hashed_data)


def get_data_hash(data: str) -> str:
	"""
	Хеширование данных (пароль, email-код, ...).
	"""
	return config.pwd_context.hash(data)


def create_jwt_token(data: dict, expires_at: timedelta) -> str:
	"""
	Создание JWT-токена. "Живет" в течение переданного времени. По умолчанию время указывается в конфиге.
	В data должен содержаться обязательный для JWT-токена параметр: "sub" (субъект - имя пользователя/email/...).
	:param expires_at: через сколько истекает
	:param data: содержание payload
	"""
	expire = datetime.utcnow() + expires_at
	data.update({"exp": expire})  # std jwt data param
	encoded_jwt = jwt.encode(claims=data, key=config.JWT_SECRET_KEY, algorithm=config.JWT_SIGN_ALGORITHM)

	return encoded_jwt


def create_token_response(token: Token, refresh: RefreshToken) -> JSONResponse:
	"""
	Создать ответ сервера с токенами (refresh - cookie, access - body).
	"""
	response = JSONResponse(content=token.dict())
	exp_at = refresh.expires_at.timestamp()
	refresh.expires_at = datetime.fromtimestamp(exp_at, tz=timezone.utc)
	response.set_cookie(key="refreshToken", value=refresh.refresh_token, expires=refresh.expires_at, httponly=True,
						secure=True)

	return response


def decode_jwt(token: str) -> dict[str, Any]:
	"""
	Расшифровать JWT
	"""
	return jwt.decode(token=token, key=config.JWT_SECRET_KEY, algorithms=[config.JWT_SIGN_ALGORITHM])


def generate_refresh_token(length: int = 20) -> str:
	"""
	Генерирует рефреш-токен.
	"""
	return ''.join(
		(random.choice(ascii_letters) for _ in range(length))
	)


def sa_object_to_dict(sa_object: Base) -> dict[str, Any]:
	"""
	Использую AsyncSession из SQLAlchemy.
	Она возвращает из БД не словарь с данными, а объект ORM-модели.
	Для использования, например, с pydantic-схемами, нужна эта функция.

	P.S. МОЖНО И НЕ ИСПОЛЬЗОВАТЬ, pydantic все равно не будет никак ссылаться на SA-object или использовать его.
	Но делаю для чистоты =)
	"""
	obj_dict = sa_object.__dict__
	del obj_dict["_sa_instance_state"]
	return obj_dict


def sa_objects_dicts_list(objects_list: Sequence[Base]) -> list[dict[str, Any]]:
	"""
	Возвращает pydantic-модели (словари) списка SA-объектов.
	"""
	return [sa_object_to_dict(obj) for obj in objects_list]


def encrypt_data(data: str | dict) -> str:
	"""
	Шифрует строку с помощью Fernet.
	Можно зашифровать json-строку =)
	"""
	fernet = Fernet(config.FERNET_SECRET_KEY)
	if isinstance(data, dict):
		data = json.dumps(data)
	return str(
		fernet.encrypt(data.encode()), 'utf-8'
	)


def decrypt_data(data: str) -> str | dict:
	"""
	Расшифровывает строку.
	"""
	fernet = Fernet(config.FERNET_SECRET_KEY)
	decrypted_data = str(
		fernet.decrypt(data), 'utf-8'
	)
	try:
		decrypted_data = json.loads(decrypted_data)
	except json.decoder.JSONDecodeError:
		pass
	return decrypted_data


async def read_location(address: str) -> geopy.Location:
	"""
	Чтение адреса.
	"""
	while True:
		async with Nominatim(user_agent=config.GEO_APP, adapter_factory=AioHTTPAdapter, timeout=10) as geolocator:
			location = await geolocator.geocode(address)
		return location

