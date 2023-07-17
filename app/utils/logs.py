from ..models.logs import ErrorsLog, WashingAgentsUsingLog, StationProgramsLog, ChangesLog, StationMaintenanceLog
from ..database import Base
from ..static.enums import LogTypeEnum


def parse_log_class(log_type: LogTypeEnum) -> Base:
	"""
	Определяет класс лога.
	Сделал для избежания повторения)
	"""
	match log_type:
		case LogTypeEnum.ERRORS:
			log_cls = ErrorsLog
		case LogTypeEnum.PROGRAMS_USING:
			log_cls = StationProgramsLog
		case LogTypeEnum.WASHING_AGENTS_USING:
			log_cls = WashingAgentsUsingLog
		case LogTypeEnum.CHANGES:
			log_cls = ChangesLog,
		case LogTypeEnum.MAINTENANCE:
			log_cls = StationMaintenanceLog
	return log_cls
