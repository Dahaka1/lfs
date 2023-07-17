import os
import smtplib

import psycopg2
import redis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from loguru import logger
from redis import asyncio as aioredis

import config
import services
from .database import sync_db
from .static.sql_queries import GET_ALL_TABLES


def database_init() -> None:
	"""
	Создание таблиц в БД по умолчанию.
	"""
	with sync_db.cursor() as cursor:
		cursor.execute(GET_ALL_TABLES)
		all_tables = cursor.fetchall()
	if not sync_db.closed:
		sync_db.close()
	if not any(all_tables):
		os.system(config.ALEMBIC_MIGRATION_CMD)
		logger.info(f"There are default DB tables was successfully created")
	if config.DB_AUTO_UPDATING:
		for cmd in (config.ALEMBIC_MAKE_MIGRATIONS_CMD, config.ALEMBIC_MIGRATION_CMD):
			os.system(cmd)
		logger.info(f"SQLAlchemy models changes was automatically checked and applied if exists.\n"
					f"You can set it in config.db_auto_updating param.")
		# можно добавить проверку на то, что создался новый файл миграции


def execute_from_command_line(*args):
	"""
	Определение параметров запуска приложения.
	"""
	params = {}
	for arg in args:
		match arg:
			case config.STARTING_APP_FROM_CMD_DEBUG_ARG:
				params.setdefault("debug", True)
	return params


def start_app(**kwargs) -> None:
	"""
	Запуск сервера.

	Если debug == True, то запускается uvicorn-локальный сервер.

	Если запуск в "продакшн" (debug = False), то запускается gunicorn-сервер.
	"""
	# debug = kwargs.get("debug")
	# if debug:
	os.system(config.STARTING_APP_CMD_DEBUG_MODE)
	# else:
	# 	os.system(config.STARTING_APP_CMD)


async def fastapi_cache_init() -> None:
	"""
	Используется при старте сервера, а также при начале тестирования.
	Redis должен быть активен!
	"""
	redis = aioredis.from_url(config.REDIS_URL)
	FastAPICache.init(RedisBackend(redis), prefix=config.REDIS_CACHE_PREFIX)


async def check_connections() -> None:
	await check_redis_connection()
	await check_db_connection()
	await check_smtp_connection()


async def check_smtp_connection() -> None:
	"""
	Проверка соединения с SMTP-сервером.
	"""
	try:
		with smtplib.SMTP(host=services.SMTP_HOST, port=services.SMTP_PORT) as conn:
			status = conn.noop()[0]
	except smtplib.SMTPServerDisconnected:
		status = -1
	if status != 250:
		logger.error("Can't establish the connection to SMTP server.\n"
					 "Please make sure that SMTP params in 'services' was defined right.")
		exit()


async def check_redis_connection() -> None:
	"""
	Redis при инициализации кэширования может и не быть активным - при этом нет ошибки.
	Делаю доп. проверку.
	"""
	r = await aioredis.from_url(config.REDIS_URL)
	try:
		await r.ping()
	except (OSError, redis.exceptions.ConnectionError):
		error_text = "Can't establish the connection to Redis.\nPlease make sure that Redis " \
					 "is running on url that defined in 'config.py' file."
		logger.error(error_text)
		exit()
	finally:
		await r.close()


async def check_db_connection() -> None:
	"""
	Проверка соединения с БД.
	"""
	try:
		with sync_db.cursor() as cursor:
			cursor.execute("SELECT 1")
	except psycopg2.OperationalError:
		error_text = "Can't establish the connection to PostgreSQL Database.\nPlease make sure that PSQL DB " \
					 "is running on url that defined in 'config.py' file."
		logger.error(error_text)
		exit()
