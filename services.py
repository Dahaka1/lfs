import os

from app.static.enums import RoleEnum, StationStatusEnum

# SMTP ACCOUNT
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT")
if SMTP_PORT:
	SMTP_PORT = int(SMTP_PORT)
SMTP_USER = os.getenv("SMTP_USER")  # почта логин
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # почта пароль

if any(
	(var == "null" for var in (SMTP_HOST, SMTP_PORT, SMTP_PASSWORD, SMTP_USER))
):
	raise RuntimeError("For testing app, write your SMTP data into .env-docker file")

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
DEFAULT_STATION_POWER = True  # включена ли станция по умолчанию
DEFAULT_STATION_TEH_POWER = False  # включен ли тен по умолчанию
DEFAULT_STATION_IS_ACTIVE = True  # активна ли станция по умолчанию (если нет, то включение станции и тэна невозможно)
DEFAULT_STATION_WASHING_MACHINES_AMOUNT = 4  # количество стиральных машин у станции по умолчанию
DEFAULT_STATION_WASHING_AGENTS_AMOUNT = 5  # количество стиральных средств у станции по умолчанию
DEFAULT_STATION_IS_PROTECTED = True  # включена ли защита станции по умолчанию
DEFAULT_STATION_STATUS = StationStatusEnum.AWAITING  # статус станции по умолчанию
# (если выключена - статус только нулевой)
MIN_STATION_WASHING_AGENTS_AMOUNT = 1  # минимальное количество стиральных средств у станции
MIN_STATION_WASHING_MACHINES_AMOUNT = 1  # минимальное количество стиральных машин у станции
MAX_STATION_WASHING_MACHINES_AMOUNT = 7  # максимальное количество стиральных машин у станции
MAX_STATION_WASHING_AGENTS_AMOUNT = 8  # максимальное количество стиральных средств у станции
