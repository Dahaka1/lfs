from typing import AsyncGenerator

from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session_maker, SyncSession

# dependency that expects for token from user
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
	"""
	SA-сессия.
	"""
	async with async_session_maker() as session:
		yield session


async def get_sync_session():
	"""
	Синхронная сессия.
	"""
	db = SyncSession()
	try:
		yield db
	finally:
		db.close()