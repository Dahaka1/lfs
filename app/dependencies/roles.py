from typing import Annotated

from fastapi import Depends

from .users import get_current_active_user
from ..exceptions import PermissionsError
from ..schemas.schemas_users import User
from ..static.enums import RoleEnum


def get_sysadmin_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка SYSADMIN-прав пользователя.
	"""
	if current_user.role.value != RoleEnum.SYSADMIN.value:
		raise PermissionsError()
	return current_user


def get_manager_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка MANAGER-прав пользователя.
	"""
	if current_user.role.value not in (RoleEnum.MANAGER.value, RoleEnum.SYSADMIN.value):
		raise PermissionsError()
	return current_user


def get_installer_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка INSTALLER-прав пользователя.
	"""
	if current_user.role.value not in (RoleEnum.MANAGER.value, RoleEnum.SYSADMIN.value, RoleEnum.INSTALLER.value):
		raise PermissionsError()
	return current_user


def get_laundry_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка LAUNDRY-прав пользователя.
	"""
	if current_user.role.value not in (RoleEnum.MANAGER.value, RoleEnum.SYSADMIN.value,
								 RoleEnum.INSTALLER.value, RoleEnum.LAUNDRY.value):
		raise PermissionsError()
	return current_user

