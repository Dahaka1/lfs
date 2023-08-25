from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from .config import CACHE_EXPIRING_DEFAULT
from ..crud import crud_users
from ..dependencies import get_async_session
from ..dependencies.roles import get_sysadmin_user, get_region_manager_user
from ..dependencies.users import get_current_active_user, get_user_by_id
from ..exceptions import PermissionsError
from ..models.users import User
from ..schemas import schemas_users
from ..static import openapi, enums
from ..exceptions import UpdatingError

router = APIRouter(
	prefix="/users",
	tags=["users"]
)

special_router = APIRouter(
	prefix="/auth",
	tags=["users", "authentication"]
)


@router.get("/", responses=openapi.read_users_get, response_model=list[schemas_users.User])
@cache(expire=CACHE_EXPIRING_DEFAULT)
async def read_users(
	current_user: Annotated[schemas_users.User, Depends(get_region_manager_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	order_by: Annotated[enums.UserSortingEnum, Query(title="Сортировка списка пользователей")] =
		enums.UserSortingEnum.NAME,
	desc: Annotated[bool, Query(title="В обратном порядке или нет")] = False
):
	"""
	Получение списка пользователей.
	Доступно для REGION_MANAGER-пользователей и выше.
	"""
	return await crud_users.get_users(db, current_user, order_by, desc)


@router.post("/", responses=openapi.create_user_post, status_code=status.HTTP_201_CREATED,
			 response_model=schemas_users.User, deprecated=True)
async def create_user(
	user: Annotated[schemas_users.UserCreate, Body(embed=True, title="Параметры пользователя")],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	# sync_db: Annotated[Session, Depends(get_sync_session)],
	# send_verification_email_code: BackgroundTasks
):
	"""
	Регистрация пользователя по email.

	По умолчанию роль пользователя: LAUNDRY (прачечная).
	Сделать SYSADMIN-пользователя можно только напрямую из БД.
	Далее он может создавать пользователей с нужными ролями (по другому методу).

	Этот метод использовать нужно только для создания первого пользователя и назначения ему прав сисадмина в БД.
	Дальше он самостоятельно создаст пользователей.
	"""
	existing_user = await User.get_user_by_email(db, user.email)
	if existing_user:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
	user.region = None  # у сисадмина не должно быть региона
	created_user = await crud_users.create_user(user, db=db)

	# send_verification_email_code.add_task(tasks.send_verifying_email_code, created_user, sync_db)

	return created_user


@router.post("/user", response_model=schemas_users.User,
			 responses=openapi.create_user_by_sysadmin_post, status_code=status.HTTP_201_CREATED)
async def create_user_by_sysadmin(
	current_user: Annotated[schemas_users.User, Depends(get_sysadmin_user)],
	user: Annotated[schemas_users.UserCreateBySysadmin, Body(embed=True, title="Параметры пользователя")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Создание пользователя SYSADMIN-пользователем.
	Метод отличается от основного тем, что можно выбрать роль пользователя.

	Регион, даже если выбран, установится только для REGION_MANAGER и INSTALLER.
	Для остальных он будет пустым (выводить в таком случае его как "Все регионы").
	"""
	existing_user = await User.get_user_by_email(db, user.email)
	if existing_user:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	return await crud_users.create_user(user, db, role=user.role)


@special_router.get("/user", responses=openapi.read_users_me_get, response_model=schemas_users.User)
@cache(expire=CACHE_EXPIRING_DEFAULT)
async def read_users_me(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)]
):
	"""
	Получение данных пользователя самим пользователем.
	"""
	return current_user


@router.get("/{user_id}", responses=openapi.read_user_get, response_model=schemas_users.User)
@cache(expire=CACHE_EXPIRING_DEFAULT)
async def read_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user: Annotated[schemas_users.User, Depends(get_user_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение данных аккаунта пользователя.

	Получить данные могут:
	- Сам пользователь;
	- REGION_MANAGER-пользователь и выше.
	Для REGION_MANAGER доступ есть только к пользователям его региона.
	Для тех, кто выше - ко всем.
	"""
	if not User.check_user_permissions(action_by_user=current_user, user=user):
		raise PermissionsError()
	return user


@router.put("/{user_id}", responses=openapi.update_user_put, response_model=schemas_users.User)
async def update_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user_update: Annotated[schemas_users.UserUpdate, Body(embed=True, title="Обновленные данные пользователя")],
	user: Annotated[schemas_users.User, Depends(get_user_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Обновление данных пользователя. Обновить данные могут:
	- сам пользователь;
	- REGION_MANAGER и старше.

	Изменить любые данные юзера (кроме пароля) пользователи REGION_MANAGER (если
	 он менеджер по региону пользователя) и старше.
	Пароль может изменить только сам пользователь (и только пароль, если
	 роль пользователя меньше REGION_MANAGER).
	Изменить роль пользователя могут только SYS, MANAGER или REGION_MANAGER, если
	 их роль выше его роли. Собственно, и изменить свою роль сам пользователь не может.
	"""
	# Права проверяются методом check_user_permissions + в crud_users.
	if not User.check_user_permissions(action_by_user=current_user, user=user):
		raise PermissionsError()
	if any(user.dict().values()):
		try:
			return await crud_users.update_user(user_update=user_update, user=user, action_by=current_user, db=db)
		except PermissionError:  # если по правам не сходится
			raise PermissionsError()
		except UpdatingError as err:
			raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
	else:
		return current_user


@router.delete("/{user_id}", responses=openapi.delete_user_delete)
async def delete_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user: Annotated[schemas_users.User, Depends(get_user_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Удаление пользователя.
	Удалить может только REGION_MANAGER (только пользователя своего региона) и выше.
	И только в случае, если роль выше роли удаляемого пользователя.
	"""
	if not User.check_user_permissions(action_by_user=current_user, user=user):
		raise PermissionsError()
	if current_user.id == user.id:  # противоречие, чтоб проверку не переписывать всю
		raise PermissionsError()
	try:
		return await crud_users.delete_user(user=user, action_by=current_user, db=db)
	except PermissionError:
		raise PermissionsError()
