from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_user_token, confirm_user_email


async def create_user(
	email: str,
	password: str,
	firstname: str,
	lastname: str,
	async_client: AsyncClient,
	raise_error: bool = False,
	confirm_email: bool = False,
	session: AsyncSession = None
) -> dict[str, Any]:
	"""
	Создание пользователя для тестов и получение его токена авторизации.

	Функция использует для создания юзера Post-метод, который тестируется непосредственно в тестах.
	Поэтому здесь добавил дополнительное тестирование: если raise_error = True (это нужно в позитивных тестах),
	 то при неудачном создании объекта рейзится ошибка на уровне этой функции.
	"""
	user_data = dict(user={
		"email": email,
		"password": password,
		"first_name": firstname,
		"last_name": lastname
	})

	response = await async_client.post(
		"/api/v1/users/",
		json=user_data
	)

	if raise_error is True:
		if response.status_code != 201:
			raise AssertionError(f"Can't create a new user: server response status code is {response.status_code}")

	result: dict[str, Any] = {
		** response.json(),
		"token": await get_user_token(email, password, async_client)
	}

	if confirm_email:
		if session:
			await confirm_user_email(session=session, user_id=result.get("id"))
		else:
			raise RuntimeError("Needs for async SA session for auto email confirming")
		result.setdefault("email_confirmed", True)

	return result
