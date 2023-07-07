from loguru import logger
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

import services
from ..schemas import schemas_users
from ..models.users import User
from ..utils import get_data_hash
from ..utils import sa_objects_dicts_list, sa_object_to_dict


async def get_users(db: AsyncSession):
	"""
	:return: Возвращает список всех пользователей (pydantic-модели)
	"""
	query = select(User).order_by(User.registered_at)
	result = await db.execute(query)
	return sa_objects_dicts_list(result.scalars().all())


async def create_user(user: schemas_users.UserCreate, db: AsyncSession):
	"""
	:return: Возвращает словарь с данными созданного юзера.
	"""
	hashed_password = get_data_hash(user.password)
	query = insert(User).values(
		email=user.email,
		first_name=user.first_name,
		last_name=user.last_name,
		hashed_password=hashed_password
	)

	await db.execute(query)
	await db.commit()

	inserted_user = await User.get_user_by_email(db=db, email=user.email)

	logger.info(f"User {user.email} ({user.first_name} {user.last_name}) was successfully registered")

	return inserted_user


async def update_user(user: schemas_users.UserUpdate, user_id: int, action_by: schemas_users.User, db: AsyncSession):
	"""
	:return: Возвращает словарь с данными обновленного пользователя.
	"""
	query = select(User).where(User.id == user_id)
	result = await db.execute(query)
	user_db = sa_object_to_dict(result.scalar())
	for key, val in user.dict().items():
		if not val is None:
			if key == "password":
				if action_by.id != user_id:
					pass  # only user can set a new password, not staff
				else:
					hashed_password = get_data_hash(val)
					user_db["hashed_password"] = hashed_password
			else:
				user_db[key] = val
	query = update(User).where(User.id == user_id).values(**user_db)
	await db.execute(query)
	await db.commit()

	logger.info(f"User {user_db['email']} (ID: {user_id}) was successfully updated by user "
				f"{action_by.email} with ID {action_by.id}")

	return user_db


async def delete_user(user_id: int, action_by: schemas_users.User, db: AsyncSession) -> dict[str, int]:
	"""
	:return: Возвращает ИД удаленного пользователя.
	"""
	query = delete(User).where(User.id == user_id)
	await db.execute(query)
	await db.commit()

	logger.info(f"User ID: {user_id} was successfully deleted by user {action_by.email} with ID "
				f"{action_by.id}")

	return {"deleted_user_id": user_id}
