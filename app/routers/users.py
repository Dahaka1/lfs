from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status, Depends, BackgroundTasks
from fastapi_cache.decorator import cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from .config import CACHE_EXPIRING_DEFAULT
from .. import tasks
from ..crud import crud_users
from ..dependencies import get_async_session, get_sync_session
from ..dependencies.roles import get_sysadmin_user
from ..dependencies.users import get_current_active_user, get_user_id
from ..exceptions import PermissionsError
from ..models.users import User
from ..schemas import schemas_users
from ..static import openapi

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
	current_user: Annotated[schemas_users.User, Depends(get_sysadmin_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение списка всех пользователей.
	Доступно для SYSADMIN-пользователей.
	"""
	return await crud_users.get_users(db=db)


@router.post("/", responses=openapi.create_user_post, status_code=status.HTTP_201_CREATED,
			 response_model=schemas_users.User)
async def create_user(
	user: Annotated[schemas_users.UserCreate, Body(embed=True, title="Параметры пользователя")],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	sync_db: Annotated[Session, Depends(get_sync_session)],
	send_verification_email_code: BackgroundTasks
):
	"""
	Регистрация пользователя по email.
	Отправка кода подтверждения email.

	По умолчанию роль пользователя: LAUNDRY (прачечная).
	"""
	query = select(User).where(User.email == user.email)
	result = await db.execute(query)
	existing_user = result.scalar()
	if existing_user:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	created_user = await crud_users.create_user(user, db=db)

	send_verification_email_code.add_task(tasks.send_verifying_email_code, created_user, sync_db)

	return created_user


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
	user_id: Annotated[int, Depends(get_user_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение данных аккаунта пользователем.

	Получить данные могут:
	- Сам пользователь;
	- SYSADMIN-пользователь.
	"""
	if not User.check_user_permissions(action_by_user=current_user, user_id=user_id):
		raise PermissionsError()
	return await crud_users.get_user(user_id=user_id, db=db)


@router.put("/{user_id}", responses=openapi.update_user_put, response_model=schemas_users.User)
async def update_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user: Annotated[schemas_users.UserUpdate, Body(embed=True, title="Обновленные данные пользователя")],
	user_id: Annotated[int, Depends(get_user_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Обновление данных пользователя. Обновить данные могут:
	- сам пользователь;
	- SYSADMIN-пользователь.

	Изменить роль пользователя и его блокировку может только пользователь с ролью SYSADMIN.

	Если изменился EMail - нужно заново его подтверждать.
	"""
	# Права проверяются методом check_user_permissions + в crud_users.
	if not User.check_user_permissions(action_by_user=current_user, user_id=user_id):
		raise PermissionsError()
	if any(user.dict().values()):
		return await crud_users.update_user(user=user, user_id=user_id, action_by=current_user, db=db)
	else:
		return current_user


@router.delete("/{user_id}", responses=openapi.delete_user_delete)
async def delete_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user_id: Annotated[int, Depends(get_user_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Удаление пользователя.
	Удалить могут только:
	- сам пользователь;
	- SYSADMIN-пользователь.
	"""
	if not User.check_user_permissions(action_by_user=current_user, user_id=user_id):
		raise PermissionsError()
	return await crud_users.delete_user(user_id=user_id, action_by=current_user, db=db)
