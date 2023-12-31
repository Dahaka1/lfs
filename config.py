import copy
import os

from dotenv import load_dotenv
from passlib.context import CryptContext

# GEOLOCATION
GEO_APP = "LFS-company server"

STARTING_APP_FROM_CMD_DEBUG_ARG = "--debug"

if not os.getenv("DOCKER"):
	load_dotenv()  # если docker, то окружение будет из файла .env-docker

DB_PARAMS = {"user": os.environ.get("DB_USER"), "password": os.environ.get("DB_PASSWORD"),
			 "host": os.environ.get("DB_HOST"), "port": os.environ.get("DB_PORT"), "dbname": os.environ.get("DB_NAME")}

DB_PARAMS_TEST = {"user": os.environ.get("DB_USER_TEST"), "password": os.environ.get("DB_PASSWORD_TEST"),
				  "host": os.environ.get("DB_HOST_TEST"), "port": os.environ.get("DB_PORT_TEST"),
				  "dbname": os.environ.get("DB_NAME_TEST")}

DATABASE_URL = "postgresql+asyncpg://%s:%s@%s:%s/%s" % tuple(DB_PARAMS.values())
DATABASE_URL_SYNC = "postgresql://%s:%s@%s:%s/%s" % tuple(DB_PARAMS.values())  # for alembic and sync SA
DATABASE_URL_TEST = "postgresql+asyncpg://%s:%s@%s:%s/%s" % tuple(DB_PARAMS_TEST.values())
DATABASE_URL_SYNC_TEST = "postgresql://%s:%s@%s:%s/%s" % tuple(DB_PARAMS_TEST.values())

API_DOCS_URL = "/v1/docs"
API_REDOC_URL = "/v1/redoc"
OPENAPI_URL = "/v1/openapi.json"

# response time logging
RESPONSE_TIME_LOGGING_PATH = "logs/processing_time.log"
RESPONSE_TIME_LOGGING_FORMAT = "{time} - {method} \"{url}\": {request_from} ID {request_from_id}, " \
							   "handling time result <{result} sec.>"

# loguru logger settings
LOGGING_OUTPUT = "logs/services.log"
LOGGING_PARAMS = {
	"sink": LOGGING_OUTPUT,
	"rotation": "1 MB",
	"compression": "zip"
}
CUSTOM_EXCEPTIONS_OUTPUT = "logs/services_errors.log"
CUSTOM_EXCEPTIONS_OUTPUT_PARAMS = copy.deepcopy(LOGGING_PARAMS)
CUSTOM_EXCEPTIONS_OUTPUT_PARAMS["sink"] = CUSTOM_EXCEPTIONS_OUTPUT
CUSTOM_EXCEPTIONS_OUTPUT_PARAMS["level"] = "ERROR"

# http logging params
STD_LOGS_GETTING_AMOUNT = 50
MAX_LOGS_GETTING_AMOUNT = 500

# alembic: commands for initializing migrations
ALEMBIC_MIGRATION_CMD = "alembic upgrade head"
ALEMBIC_MAKE_MIGRATIONS_CMD = "alembic revision --autogenerate"

# alembic: if parameter is True, alembic will check models changing in every server launching
# e.g. even if model field attributes was changed, it will automatically reflect in DB
DB_AUTO_UPDATING = False

# starting params
STARTING_APP_CMD_DEBUG_MODE = "uvicorn app.main:app"
STARTING_APP_CMD = "gunicorn app.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000"

# users passwords hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# jwt token params
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_SIGN_ALGORITHM = "HS256"

# redis params
REDIS_HOST = f"redis://{os.environ.get('REDIS_HOST')}"
REDIS_PORT = os.environ.get("REDIS_PORT")
REDIS_URL = f"{REDIS_HOST}:{REDIS_PORT}"
REDIS_CACHE_PREFIX = "lfs-cache"

# STATIC FILES DIR
STATIC_FILES_DIR = "app/static"
HTML_TEMPLATES_DIR = STATIC_FILES_DIR + "/templates"

# FERNET SECRET KEY (WIFI DATA ENCRYPTING)
FERNET_SECRET_KEY_STRING = os.getenv("FERNET_SECRET_KEY")
if FERNET_SECRET_KEY_STRING is not None:
	FERNET_SECRET_KEY = bytes(os.getenv("FERNET_SECRET_KEY"), "utf-8")


# SMTP SERVER
SMTP_SERVER_TIMEOUT = 10

# CORS
ORIGINS = [
    "http://localhost",
    "http://localhost:8080",
	"https://lfs-spb.ru"
]


class GoogleSheetTableQuery:
	_QUERY = "https://sheets.googleapis.com/v4/spreadsheets/{spreadsheetId}/values/{sheetName}!{range}?key={apiKey}"
	_PARAMS = dict(
		_station_default_programs_params={
			"spreadsheetId": os.getenv("GS_STATION_PROGRAMS_SHEET_ID"),
			"sheetName": "Main", "apiKey": os.getenv("GS_API_KEY"),
			"range": "A2:Z999"
		}
	)
	station_default_programs = _QUERY.format(**_PARAMS["_station_default_programs_params"])

