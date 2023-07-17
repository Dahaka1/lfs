from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.classes.users import User


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


async def confirm_user_email(
	session: AsyncSession,
	user_id: int
):
	"""
	Ручное подтверждение email для пользователя.
	"""
	query = update(User).where(
		User.id == user_id
	).values(email_confirmed=True)

	await session.execute(query)
	await session.commit()
