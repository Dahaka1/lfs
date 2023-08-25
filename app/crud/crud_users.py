from loguru import logger
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

import services
from ..models.users import User
from ..schemas import schemas_users
from ..static.enums import RoleEnum, UserSortingEnum
from ..utils.general import sa_objects_dicts_list, get_data_hash
from ..exceptions import UpdatingError


async def get_users(db: AsyncSession, user: schemas_users.User,
					order_by: UserSortingEnum, desc: bool):
	"""
	:return: Возвращает список всех пользователей (pydantic-модели)
	"""
	query = select(User)
	if user.role == RoleEnum.REGION_MANAGER:
		query = query.where(User.region == user.region)
	query = query.where(User.id != user.id)
	if order_by not in (UserSortingEnum.REGION, UserSortingEnum.ROLE):
		# SA не сортирует по Enum'у... не смог разобраться
		ordering = {UserSortingEnum.NAME: User.last_name, UserSortingEnum.LAST_ACTION: User.last_action_at}
		order = ordering[order_by]
		if desc:
			order = order.desc()
		query = query.order_by(order)
	result = await db.execute(query)
	users = sa_objects_dicts_list(result.scalars().all())
	if order_by in (UserSortingEnum.REGION, UserSortingEnum.ROLE):
		sorting_params = {"key": None, "reverse": desc}
		match order_by:
			case UserSortingEnum.ROLE:
				sorting_params["key"] = lambda u: u["role"].value
			case UserSortingEnum.REGION:
				sorting_params["key"] = lambda u: u["region"].value
		users = sorted(users, **sorting_params)
	return users


async def create_user(user: schemas_users.UserCreate, db: AsyncSession,
					role: RoleEnum = None):
	"""
	:return: Возвращает словарь с данными созданного юзера.
	"""
	hashed_password = get_data_hash(user.password)
	user_params = dict(
		email=user.email,
		first_name=user.first_name,
		last_name=user.last_name,
		hashed_password=hashed_password,
		region=user.region
	)
	if role:
		user_params["role"] = role
		if role not in (RoleEnum.REGION_MANAGER, RoleEnum.INSTALLER):
			user_params["region"] = None  # остальным регион не нужен

	query = insert(User).values(**user_params)

	await db.execute(query)
	await db.commit()

	inserted_user = await User.get_user_by_email(db=db, email=user.email)

	logger.info(f"User {user.email} ({user.first_name} {user.last_name}) was successfully registered")

	return inserted_user


async def update_user(user_update: schemas_users.UserUpdate, user: schemas_users.User,
					  action_by: schemas_users.User, db: AsyncSession):
	"""
	:return: Возвращает словарь с данными обновленного пользователя.
	"""
	if action_by.role < user.role:
		raise PermissionError  # более низкая роль не может изменить юзера с ролью выше
	if action_by.role in (RoleEnum.INSTALLER, RoleEnum.LAUNDRY):
		for key, val in user_update.dict().items():
			if val and key not in services.USER_UPDATE_BY_SELF_AVAILABLE_FIELDS:
				raise PermissionError  # запрещено для не менеджеров и не админов
	else:
		if user_update.password:
			if user.id != action_by.id:
				raise PermissionError  # поменять чужой пароль никто не может
	if user_update.email and user_update.email != user.email:
		user_exists = await User.get_user_by_email(db, user_update.email)
		if user_exists:
			raise UpdatingError(f"User updating error: email {user_update.email} already exists")
	if user_update.password:
		user_update.password = get_data_hash(user_update.password)
	if user_update.role and user_update.role != user.role and user.id == action_by.id:
		raise PermissionError  # сам себе роль не поменяет
	params = user_update.dict(exclude_unset=True)
	new_pass = params.get("password")
	if new_pass:
		params["hashed_password"] = new_pass
		del params["password"]
	query = update(User).where(User.id == user.id).values(**params)
	await db.execute(query)
	await db.commit()

	for key in params:
		val = params[key]
		setattr(user, key, val)

	return user


async def delete_user(user: schemas_users.User, action_by: schemas_users.User, db: AsyncSession) -> dict[str, int]:
	"""
	:return: Возвращает ИД удаленного пользователя.
	"""
	if action_by.role < user.role:
		raise PermissionError
	query = delete(User).where(User.id == user.id)
	await db.execute(query)
	await db.commit()

	logger.info(f"User ID: {user.id} '{user.email}' was successfully deleted by user {action_by.email} with ID "
				f"{action_by.id}")

	return {"deleted_user_id": user.id}
