from math import floor

from enum import Enum, auto
from ..static import strings as s


class RoleEnum(Enum):
	SYSADMIN = "sys"
	MANAGER = "manager"
	REGION_MANAGER = "region_manager"
	INSTALLER = "installer"
	LAUNDRY = "owner"


class StationStatusEnum(Enum):
	AWAITING = "awaiting"
	WORKING = "working"
	MAINTENANCE = "maintenance"
	ERROR = "error"


class StationParamsEnum(Enum):
	GENERAL = "general"
	SETTINGS = "settings"
	CONTROL = "control"
	PROGRAMS = "programs"
	WASHING_MACHINES = "machines"
	WASHING_AGENTS = "agents"


class WashingServicesEnum(Enum):
	WASHING_MACHINES = "machines"
	WASHING_AGENTS = "agents"


class UserSortingEnum(Enum):
	NAME = "name"
	ROLE = "role"
	LAST_ACTION = "last_action"
	REGION = "region"


class LaundryStationSorting(Enum):
	NAME = "name"
	STATION_SERIAL = "station_serial"
	REGION = "region"


class RegionEnum(Enum):
	CENTRAL = "Центральный"
	NORTHWEST = "Северо-западный"
	SOUTH = "Южный"
	SIBERIA = "Сибирь"


class QueryFromEnum(Enum):
	USER = auto()
	STATION = auto()


class LogCaseEnum:
	data = {
		1: {
			"title": s.LOG_1,
			"sub": [s.LOG_1_1, s.LOG_1_2]
		},
		2: {
			"title": s.LOG_2,
			"sub": [s.LOG_2_1, s.LOG_2_2]
		},
		3: {
			"title": s.LOG_3,
			"sub": [s.LOG_3_1, s.LOG_3_2, s.LOG_3_3]
		},
		4: {
			"title": s.LOG_4,
			"sub": [s.LOG_4_1, s.LOG_4_2, s.LOG_4_3, s.LOG_4_4]
		},
		5: {
			"title": s.LOG_5,
			"sub": [s.LOG_5_1]
		},
		6: {
			"title": s.LOG_6,
			"sub": [s.LOG_6_1, s.LOG_6_2, s.LOG_6_3, s.LOG_6_4, s.LOG_6_5]
		},
		9: {
			"title": s.LOG_9
		}
	}

	def __init__(self, num: int | float):
		self.sub = None
		if isinstance(num, int):
			self.title = self.data[num]["title"]
		elif isinstance(num, float):
			type_num = floor(num)
			self.title = self.data[type_num]["title"]
			try:
				sub_num = int(str(num)[-1])
				if sub_num != 0:
					self.sub = self.data[type_num]["sub"][sub_num - 1]
			except (IndexError, KeyError):
				pass

	def __str__(self):
		base_string = f"<Тип события: \"{self.title}\">"
		if self.sub:
			return base_string + f" <Событие: \"{self.sub}\">"
		return base_string


class LogFromEnum(Enum):
	STATION = "station"
	SERVER = "server"


class ErrorTypeEnum(Enum):
	PUBLIC = "public"
	SERVICE = "service"
	ALL = "all"


class LogTypeEnum(Enum):
	LOG = "log"
	ERROR = "error"


class LogActionEnum(Enum):
	"""
	Действия для осуществления после добавления лога.
	"""
	ERROR_STATION_CONTROL_STATUS_START = "Установка статуса станции \"Ошибка\". Работа приостановлена"
	ERROR_STATION_CONTROL_STATUS_END = "Снятие статуса станции \"Ошибка\". Работа возобновлена"
	STATION_TURN_OFF = "Отключение станции"
	STATION_TURN_ON = "Включение станции"
	WASHING_MACHINE_TURN_ON = "Включение стиральной машины"
	WASHING_MACHINE_TURN_OFF = "Выключение стиральной машины"
	WASHING_AGENTS_CHANGE_VOLUME = "Изменение дозировок стиральных средств станции"
	STATION_SETTINGS_CHANGE = "Изменение настроек станции"
	STATION_START_MANUAL_WORKING = "Подача средства в \"ручном\" режиме"
	STATION_WORKING_PROCESS = "Работа станции"
	STATION_MAINTENANCE_START = "Начало обслуживания станции"
	STATION_MAINTENANCE_END = "Окончание обслуживания станции"
	STATION_ACTIVATE = "Активация станции"
