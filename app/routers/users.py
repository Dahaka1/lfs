from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import schemas_users
from ..crud import crud_users
from ..dependencies import get_async_session
from ..dependencies.users import get_current_active_user, get_user_id
from ..exceptions import PermissionsError
from ..models.users import User
from ..static.enums import RoleEnum
from .. import tasks

router = APIRouter(
	prefix="/users",
	tags=["users"]
)

# TODO: user retrieve by id (not by himself)


@router.get("/", response_model=list[schemas_users.User])
async def read_users(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение списка всех пользователей
	"""
	if current_user.role == RoleEnum.SYSADMIN.value:
		return await crud_users.get_users(db=db)
	raise PermissionsError()


@router.post("/", response_model=schemas_users.User, status_code=status.HTTP_201_CREATED)
async def create_user(
	user: Annotated[schemas_users.UserCreate, Body(embed=True, title="Параметры пользователя")],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	send_verification_email_code: BackgroundTasks
):
	"""
	Регистрация пользователя по email.
	Отправка кода подтверждения email.
	"""
	query = select(User).where(User.email == user.email)
	result = await db.execute(query)
	existing_user = result.scalar()
	if existing_user:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	created_user = await crud_users.create_user(user, db=db)

	send_verification_email_code.add_task(tasks.send_verifying_email_code, created_user, db)

	return created_user


@router.get("/me", response_model=schemas_users.User)
async def read_users_me(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение данных аккаунта пользователем после проверки его токена.
	"""

	return current_user


@router.put("/{user_id}", response_model=schemas_users.User)
async def update_user(
	user: Annotated[schemas_users.UserUpdate, Body(embed=True, title="User updated params dict")],
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user_id: Annotated[int, Depends(get_user_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Обновление данных пользователя. Обновить данные могут:
	- сам пользователь;
	- стафф-пользователь.
	Права проверяются функцией check_user_permissions.
	"""

	if not User.check_user_permissions(current_user=current_user, user_id=user_id):
		raise PermissionsError()
	if any(user.dict().values()):
		return await crud_users.update_user(user=user, user_id=user_id, action_by=current_user, db=db)
	else:
		return current_user


@router.delete("/{user_id}")
async def delete_user(
	current_user: Annotated[schemas_users.User, Depends(get_current_active_user)],
	user_id: Annotated[int, Depends(get_user_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> dict[str, int]:
	"""
	см. update_user
	"""
	if not User.check_user_permissions(current_user=current_user, user_id=user_id):
		raise PermissionsError()
	return await crud_users.delete_user(user_id=user_id, action_by=current_user, db=db)
