from typing import Literal

from ..database import Base
from ..models.logs import ErrorsLog, WashingAgentsUsingLog, StationProgramsLog, ChangesLog, StationMaintenanceLog
from ..static.enums import CreateLogByStationEnum, LogTypeEnum
import config


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


def log_request_handling_time(**kwargs) -> None:
	"""
	Логирует время выполнения запроса от станции/пользователя/...
	"""
	try:
		result = config.RESPONSE_TIME_LOGGING_FORMAT.format(**kwargs)
	except KeyError as e:
		raise ValueError("Logging arguments getting error: ", str(e))

	def log(mode: Literal["a", "w"]):
		with open(config.RESPONSE_TIME_LOGGING_PATH, mode, encoding="utf-8") as log_output:
			log_output.write(result + "\n")

	try:
		log("a")
	except FileNotFoundError:
		log("w")
