from app.static.enums import RoleEnum, ErrorTypeEnum, LogActionEnum

# SMTP ACCOUNT
# SMTP_HOST = os.getenv("SMTP_HOST")
# SMTP_PORT = os.getenv("SMTP_PORT")
# if SMTP_PORT:
# 	SMTP_PORT = int(SMTP_PORT)
# SMTP_USER = os.getenv("SMTP_USER")  # почта логин
# SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # почта пароль
#
# if any(
# 	(var == "null" for var in (SMTP_HOST, SMTP_PORT, SMTP_PASSWORD, SMTP_USER))
# ):
# 	raise RuntimeError("For testing app, write your SMTP data into .env-docker file")

# USERS PARAMS
USER_DEFAULT_ROLE = RoleEnum.LAUNDRY

# USER AUTHORIZATION PARAMS
ACCESS_TOKEN_EXPIRE_MINUTES = 20
REFRESH_TOKEN_EXPIRE_DAYS = 30

# EMAIL VERIFICATION PARAMS
CODE_LENGTH = 6
CODE_EXPIRING_IN_MINUTES = 5

# WASHING MACHINES PARAMS
DEFAULT_WASHING_MACHINES_VOLUME = 10  # объем стиральных машин по умолчанию
DEFAULT_WASHING_MACHINES_IS_ACTIVE = True  # активны или нет по умолчанию
DEFAULT_WASHING_MACHINES_TRACK_LENGTH = 10.0  # длина трассы по умолчанию
MIN_WASHING_MACHINE_VOLUME = 10  # минимальный объем
MAX_WASHING_MACHINE_VOLUME = 100  # максимальный объем
MIN_WASHING_MACHINE_TRACK_LENGTH = 1  # минимальная длина трассы
MAX_WASHING_MACHINE_TRACK_LENGTH = 10.0  # максимальная длина трассы

# WASHING AGENTS PARAMS
DEFAULT_WASHING_AGENTS_VOLUME = 10  # объем стиральных средств по умолчанию (если не указать при создании)
DEFAULT_WASHING_AGENTS_ROLLBACK = False  # откат средств по умолчанию
MIN_WASHING_AGENTS_VOLUME = 10  # минимальный объем средства
MAX_WASHING_AGENTS_VOLUME = 500  # максимальный объем средства

# STATIONS PARAMS
DEFAULT_STATION_POWER = False  # включена ли станция по умолчанию
DEFAULT_STATION_TEH_POWER = False  # включен ли тен по умолчанию
DEFAULT_STATION_IS_ACTIVE = False  # активна ли станция по умолчанию (если нет, то включение станции и тэна невозможно)
DEFAULT_STATION_WASHING_MACHINES_AMOUNT = 4  # количество стиральных машин у станции по умолчанию
DEFAULT_STATION_WASHING_AGENTS_AMOUNT = 5  # количество стиральных средств у станции по умолчанию
DEFAULT_STATION_IS_PROTECTED = False  # включена ли защита станции по умолчанию
DEFAULT_STATION_STATUS = None  # статус станции по умолчанию
MAX_STATION_COMMENT_LENGTH = 200  # максимальный размер комментария по станции
# (если выключена - статус только нулевой)
MIN_STATION_WASHING_AGENTS_AMOUNT = 1  # минимальное количество стиральных средств у станции
MIN_STATION_WASHING_MACHINES_AMOUNT = 1  # минимальное количество стиральных машин у станции
MAX_STATION_WASHING_MACHINES_AMOUNT = 7  # максимальное количество стиральных машин у станции
MAX_STATION_WASHING_AGENTS_AMOUNT = 8  # максимальное количество стиральных средств у станции

# STATION LOGS
DEFAULT_ERROR_SCOPE = ErrorTypeEnum.PUBLIC
LOG_ACTIONS = {
	9.2: LogActionEnum.STATION_TURN_OFF,
	9.1: LogActionEnum.STATION_TURN_ON,
	9.3: LogActionEnum.WASHING_MACHINE_TURN_ON,
	9.4: LogActionEnum.WASHING_MACHINE_TURN_OFF,
	9.9: LogActionEnum.WASHING_AGENTS_CHANGE_VOLUME,
	9.10: LogActionEnum.STATION_SETTINGS_CHANGE,
	9.11: LogActionEnum.STATION_ACTIVATE,
	9.12: LogActionEnum.STATION_START_MANUAL_WORKING,
	3.1: LogActionEnum.STATION_WORKING_PROCESS,
	9.16: LogActionEnum.STATION_MAINTENANCE_START,
	9.17: LogActionEnum.STATION_MAINTENANCE_END,
	9.18: LogActionEnum.ERROR_STATION_CONTROL_STATUS_END
}
ERROR_ACTIONS = {
	ErrorTypeEnum.PUBLIC: {
		3.3: LogActionEnum.ERROR_STATION_CONTROL_STATUS_START,
		9.4: LogActionEnum.STATION_TURN_OFF
	},
	ErrorTypeEnum.SERVICE: {}
}
LOG_EXPECTING_DATA = {
	9.3: {"washing_machine_number": int},
	9.4: {"washing_machine_number": int},
	9.9: {"washing_agent_number": int, "volume": int},
	9.10: {"teh_power": bool},
	9.12: {"washing_machine_number": int, "washing_agent_number": int, "volume": int},
	3.1: {"washing_machine_number": int, "program_step_number": int,
		  "program_number": int, "washing_machines_queue": list}
}
ERROR_EXPECTING_DATA = {
	ErrorTypeEnum.PUBLIC: {},
	ErrorTypeEnum.SERVICE: {}
}
