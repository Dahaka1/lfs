from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logs import ChangesLog
from app.utils.general import sa_object_to_dict
from .users import UserData


async def get_user_last_changes_log(user: UserData, session: AsyncSession) -> dict[str, Any] | None:
	"""
	Поиск последнего лога пользователя типа CHANGES
	"""
	log = (await session.execute(
		select(ChangesLog).where(ChangesLog.user_id == user.id)
	)).scalar()
	if log:
		return sa_object_to_dict(log)


async def check_user_log_exists(user: UserData, session: AsyncSession) -> None:
	"""
	Проверяет наличие созданного лога у пользователя
	"""
	assert (await get_user_last_changes_log(user, session)) is not None

