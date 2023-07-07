from httpx import AsyncClient


async def get_user_token(
	email: str,
	password: str,
	async_client: AsyncClient
) -> str:
	"""
	Авторизация пользователя для тестов.
	"""
	auth_response = await async_client.post(
		"/api/v1/token/",
		data={"email": email,
			  "password": password}
	)

	return auth_response.json()["access_token"]
