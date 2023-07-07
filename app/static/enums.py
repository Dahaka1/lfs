from enum import Enum


class RoleEnum(Enum):
	SYSADMIN = "Сисадмин"
	MANAGER = "Управляющий"
	INSTALLER = "Установщик"
	LAUNDRY = "Прачечная"


class StationStatusEnum(Enum):
	AWAITING = "Ожидание"
	WORKING = "Подача"
