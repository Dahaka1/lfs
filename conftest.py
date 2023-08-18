"""
ВАЖНО: ПЕРЕД ЗАПУСКОМ УБЕДИТЬСЯ, ЧТО ТЕСТОВАЯ БД И РЕДИС АКТИВНЫ.
TODO: РЕШИТЬ, КАК ТЕСТИРОВАТЬ АВТОМАТИЧЕСКУЮ ОТПРАВКУ EMAIL-КОДОВ ПРИ РЕГИСТРАЦИИ ПОЛЬЗОВАТЕЛЯ
TODO: и вообще как протестировать положительную отправку кода по email и проверку валидности введенного
 пользователем - ведь сравниваются хэши кодов... думаю, в целом структура отправки кодов при регистрации
 не подходит для тестов - никак не "достать" даже объект письма.
По вышеуказанным причинам проверяю только лишь создание записи в БД об отправленном коде.

ВАЖНО: в конце каждого негативного теста не забывать вызывать функцию тестирования аутентификации по маршруту.
 Она - в additional.auth. Есть функция для юзеров, есть - для станции.

TODO: скорее всего, переписать генерацию тестовых данных/объектов, а то очень запутанно вышло (не в фикстурах,
 а под капотом).
"""

import dotenv
from typing import AsyncGenerator
import asyncio

dotenv.load_dotenv()  # load env vars for safe importing

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, Session
import pytest
from sqlalchemy import create_engine

from app.database import Base
from app.models.users import User
from app.models.washing import WashingAgent, WashingMachine
from app.models.stations import Station, StationSettings, StationProgram, StationControl
from app.models.auth import RegistrationCode, RefreshToken
from app.models.logs import Log, Error
from config import DATABASE_URL_TEST, DATABASE_URL_SYNC_TEST
from app.dependencies import get_async_session, get_sync_session
from app.main import app
from app import fastapi_cache_init
from tests.additional.users import create_authorized_user, generate_user_data, create_user, create_multiple_users
from tests.additional.stations import generate_station

engine_test = create_async_engine(DATABASE_URL_TEST, poolclass=NullPool)
async_session_maker = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False, autoflush=False)
Base.metadata.bind = engine_test

sync_engine_test = create_engine(DATABASE_URL_SYNC_TEST)
SyncSession = sessionmaker(sync_engine_test)


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
	"""
	Перезапись сессии БД в проекте.
	Нужно для корректной работы тестов (иначе БД будет использоваться не тестовая).
	"""
	async with async_session_maker() as session:
		yield session


def override_get_sync_session():
	"""
	Перезапись получения синхронной сессии БД.
	:return:
	"""
	try:
		db = SyncSession()
		yield db
	finally:
		db.close()


app.dependency_overrides[get_async_session] = override_get_async_session
app.dependency_overrides[get_sync_session] = override_get_sync_session


# перезапись зависимости, возвращающей сессию SA, для корректной работы БД-функций


@pytest.fixture  # для ручного использования SA-сессии в тестах
async def session() -> AsyncGenerator[AsyncSession, None]:
	async with async_session_maker() as session:
		yield session


@pytest.fixture
def sync_session() -> Session:
	"""
	Синхронная сессия SA.
	"""
	with SyncSession() as session:
		yield session


@pytest.fixture(autouse=True, scope='session')
async def prepare_app():
	"""
	Перед запуском тестов создает сущности в БД. После тестов - удаляет
	 (yield - специальный разделитель действий для фикстур pytest).

	 + инициализирует кэш и заливает нужные данные.
	"""
	async with engine_test.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	await fastapi_cache_init()  # для работы кеширования при тестах

	yield

	async with engine_test.begin() as conn:
		await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope='session')
def event_loop(request):
	"""
	Из asyncio документации (рекомендация).
	"""
	loop = asyncio.get_event_loop_policy().new_event_loop()
	yield loop
	loop.close()


@pytest.fixture(scope='session')
async def ac() -> AsyncGenerator[AsyncClient, None]:
	"""
	Сессия подключения к БД для тестов
	"""
	async with AsyncClient(app=app, base_url="http://test") as ac:
		yield ac


@pytest.fixture(scope="class")
async def generate_user_random_data(request):
	"""
	Генерирует новые данные пользователя.
	"""
	for k, v in generate_user_data().items():
		setattr(request.cls, k, v)


@pytest.fixture(scope="function")
async def generate_user(request):
	"""
	Генерация зарегистрированного (неавторизованного) пользователя.
	"""
	with SyncSession() as sync_session:
		user: dict[str, int | str | dict] = create_user(sync_session=sync_session)

	for k, v in user.items():
		setattr(request.cls, k, v)

	request.cls.token = None
	request.cls.headers = None


@pytest.fixture(scope="function")
async def generate_authorized_user(request):
	"""
	Генерация пользователя с готовым токеном авторизации для тестов,
	где не проверяется получение токена.

	В каждом тесте (функции) можно менять свободно данные, ибо scope='function'.
	"""

	with SyncSession() as session:
		async with AsyncClient(app=app, base_url="http://test") as ac:
			user, user_schema = await create_authorized_user(ac, sync_session=session)

	for k, v in user.__dict__.items():
		setattr(request.cls, k, v)

	request.cls.user_schema = user_schema


@pytest.fixture(scope="function")
async def generate_users(request):
	"""
	Генерация подтвержденных и авторизованных пользователей со всеми ролями.
	"""

	with SyncSession() as session:
		async with AsyncClient(app=app, base_url="http://test") as ac:
			users = await create_multiple_users(ac, session)
	sysadmin, manager, installer, laundry = users

	request.cls.sysadmin = sysadmin
	request.cls.manager = manager
	request.cls.installer = installer
	request.cls.laundry = laundry


@pytest.fixture(scope="function")
async def generate_default_station(request):
	"""
	Генерация станции с дефолтными параметрами (и парочкой программ для тестов).
	"""
	with SyncSession() as session:
		async with AsyncClient(app=app, base_url="http://test") as ac:
			station = await generate_station(ac, session)

	request.cls.station = station
