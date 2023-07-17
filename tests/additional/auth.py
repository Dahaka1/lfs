from typing import Any
import random
from httpx import AsyncClient

from app.static.enums import RegionEnum
from app.schemas.schemas_token import Token
from app.schemas.schemas_users import User


async def get_user_token(email: str, password: str, ac: AsyncClient) -> Token:
	"""
	Аутентификация пользователя.
	Без проверки на ошибки (это не тест, а побочная функция).
	"""
	data = {
		"email": email,
		"password": password
	}
	response = await ac.post(
		"/api/v1/auth/token",
		data=data
	)

	return Token(**response.json())
