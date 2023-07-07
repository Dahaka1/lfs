from typing import Any

from httpx import AsyncClient

from .auth import get_user_token


async def create_user(
	email: str,
	password: str,
	firstname: str,
	async_client: AsyncClient,
	raise_error: bool = False
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
		"first_name": firstname
	})

	response = await async_client.post(
		"/api/v1/users/",
		json=user_data
	)
	if raise_error is True:
		if response.status_code != 201:
			raise AssertionError(f"Can't create a new user: server response status code is {response.status_code}")
	result = {
		** response.json(),
		"token": await get_user_token(email, password, async_client)
	}

	return result
