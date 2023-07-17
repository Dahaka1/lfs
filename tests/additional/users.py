from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.static.enums import RoleEnum
from app.classes.users import User


async def change_user_role(user_id: int, needed_role: RoleEnum, session: AsyncSession) -> None:
	"""
	Вручную изменить права пользователя.
	"""
	query = update(User).where(
		User.id == user_id
	).values(role=needed_role)

	await session.execute(query)
	await session.commit()
