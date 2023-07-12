from datetime import timedelta, datetime
from typing import Any, Sequence
import json

from jose import jwt
from cryptography.fernet import Fernet

import config, services
from ..database import Base


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


def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=services.ACCESS_TOKEN_EXPIRE_MINUTES)):
	"""
	Создание JWT-токена. "Живет" в течение переданного времени. По умолчанию время указывается в конфиге.
	В data должен содержаться обязательный для JWT-токена параметр: "sub" (субъект - имя пользователя/email/...).
	"""
	expire = datetime.utcnow() + expires_delta
	data.update({"exp": expire})  # std jwt data param
	encoded_jwt = jwt.encode(claims=data, key=config.JWT_SECRET_KEY, algorithm=config.JWT_SIGN_ALGORITHM)
	return encoded_jwt


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
