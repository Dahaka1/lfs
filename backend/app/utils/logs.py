from ..database import Base
from ..models.logs import ErrorsLog, WashingAgentsUsingLog, StationProgramsLog, ChangesLog, StationMaintenanceLog
from ..static.enums import CreateLogByStationEnum, LogTypeEnum


def parse_log_class(log_type: CreateLogByStationEnum | LogTypeEnum) -> Base:
	"""
	Определяет класс лога.
	Сделал для избежания повторения)
	"""
	match log_type:
		case CreateLogByStationEnum.ERRORS | LogTypeEnum.ERRORS:
			log_cls = ErrorsLog
		case CreateLogByStationEnum.PROGRAMS_USING | LogTypeEnum.PROGRAMS_USING:
			log_cls = StationProgramsLog
		case CreateLogByStationEnum.WASHING_AGENTS_USING | LogTypeEnum.WASHING_AGENTS_USING:
			log_cls = WashingAgentsUsingLog
		case LogTypeEnum.CHANGES:
			log_cls = ChangesLog
		case LogTypeEnum.MAINTENANCE:
			log_cls = StationMaintenanceLog
	return log_cls
