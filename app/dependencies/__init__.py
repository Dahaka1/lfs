from fastapi.security import OAuth2PasswordBearer
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import async_session_maker


# dependency that expects for token from user
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
	"""
	SA-сессия.
	"""
	async with async_session_maker() as session:
		yield session

