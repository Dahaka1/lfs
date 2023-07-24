import enum
from enum import Enum


class RoleEnum(Enum):
	SYSADMIN = "sys"
	MANAGER = "manager"
	INSTALLER = "installer"
	LAUNDRY = "laundry"


class StationStatusEnum(Enum):
	AWAITING = "awaiting"
	WORKING = "working"
	MAINTENANCE = "maintenance"


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


class RegionEnum(Enum):
	CENTRAL = "Центральный"
	NORTHWEST = "Северо-западный"
	SOUTH = "Южный"
	SIBERIA = "Сибирь"


class QueryFromEnum(Enum):
	USER = enum.auto()
	STATION = enum.auto()


class CreateLogByStationEnum(Enum):
	ERRORS = "errors"
	WASHING_AGENTS_USING = "washing_agents_using"
	PROGRAMS_USING = "programs_using"


class LogTypeEnum(Enum):
	ERRORS = "errors"
	WASHING_AGENTS_USING = "washing_agents_using"
	PROGRAMS_USING = "programs_using"
	CHANGES = "changes"
	MAINTENANCE = "maintenance"
