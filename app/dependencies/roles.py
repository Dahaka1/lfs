from typing import Annotated

from fastapi import Depends

from .users import get_current_active_user
from ..exceptions import PermissionsError
from ..schemas.schemas_users import User
from ..static.enums import RoleEnum


roles = {
	RoleEnum.MANAGER: (RoleEnum.MANAGER, RoleEnum.SYSADMIN),
	RoleEnum.REGION_MANAGER: (RoleEnum.REGION_MANAGER, RoleEnum.MANAGER, RoleEnum.SYSADMIN),
	RoleEnum.INSTALLER: (RoleEnum.INSTALLER, RoleEnum.REGION_MANAGER,
						 RoleEnum.MANAGER, RoleEnum.SYSADMIN)
}


def get_sysadmin_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка SYSADMIN-прав пользователя.
	"""
	if current_user.role != RoleEnum.SYSADMIN:
		raise PermissionsError()
	return current_user


def get_manager_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка MANAGER-прав пользователя.
	"""
	if current_user.role not in roles[RoleEnum.MANAGER]:
		raise PermissionsError()
	return current_user


def get_region_manager_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка REGION_MANAGER-прав пользователя.
	"""
	if current_user.role not in roles[RoleEnum.REGION_MANAGER]:
		raise PermissionsError()
	return current_user


def get_installer_user(
	current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
	"""
	Проверка INSTALLER-прав пользователя.
	"""
	if current_user.role not in roles[RoleEnum.INSTALLER]:
		raise PermissionsError()
	return current_user


