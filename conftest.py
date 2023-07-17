"""
ВАЖНО: ПЕРЕД ЗАПУСКОМ УБЕДИТЬСЯ, ЧТО ТЕСТОВАЯ БД И РЕДИС АКТИВНЫ.
TODO: РЕШИТЬ, КАК ТЕСТИРОВАТЬ АВТОМАТИЧЕСКУЮ ОТПРАВКУ EMAIL-КОДОВ ПРИ РЕГИСТРАЦИИ ПОЛЬЗОВАТЕЛЯ
TODO: и вообще как протестировать положительную отправку кода по email и проверку валидности введенного
 пользователем - ведь сравниваются хэши кодов... думаю, в целом структура отправки кодов при регистрации
 не подходит для тестов - никак не "достать" даже объект письма.
По вышеуказанным причинам проверяю только лишь создание записи в БД об отправленном коде.
"""

import dotenv

dotenv.load_dotenv()  # load env vars for safe importing

import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from config import DATABASE_URL_TEST, JWT_SIGN_ALGORITHM, JWT_SECRET_KEY, DATABASE_URL_SYNC_TEST
from sqlalchemy.pool import NullPool
from app.database import Base
from app.models.logs import ErrorsLog, ChangesLog, StationProgramsLog, WashingAgentsUsingLog, StationMaintenanceLog
from app.models.users import User
from app.models.washing import WashingAgent, WashingMachine
from app.models.stations import Station, StationSettings, StationProgram, StationControl
from app.models.auth import RegistrationCode
from app.dependencies import get_async_session, get_sync_session
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
import pytest
from app.main import app
from typing import AsyncGenerator
import asyncio
from app import fastapi_cache_init
from tests.additional.users import create_authorized_user, generate_user_data, create_user

engine_test = create_async_engine(DATABASE_URL_TEST, poolclass=NullPool)
async_session_maker = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)
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
	generated_data = generate_user_data(request)
	for _ in generated_data.cls.__dict__:
		setattr(generated_data.cls, _, generated_data.cls.__dict__.get(_))


@pytest.fixture(scope="class")
async def generate_user(request):
	"""
	Генерация зарегистрированного (неавторизованного) пользователя.
	"""
	generated_data = generate_user_data(request)

	with SyncSession() as sync_session:
		user_data = await create_user(generated_data, sync_session=sync_session)

	for _ in user_data.dict():
		setattr(request.cls, _, getattr(user_data, _))

	request.cls.password = generated_data.cls.password
	request.cls.token = None
	request.cls.headers = None


@pytest.fixture(scope="function")
async def generate_authorized_user(request):
	"""
	Генерация пользователя с готовым токеном авторизации для тестов,
	где не проверяется получение токена.

	В каждом тесте (функции) можно менять свободно данные, ибо scope='function'.
	"""
	generated_data = generate_user_data(request)

	with SyncSession() as session:
		async with AsyncClient(app=app, base_url="http://test") as ac:
			authorized_user_data = await create_authorized_user(generated_data, ac, sync_session=session)
	for k, v in authorized_user_data.items():
		setattr(request.cls, k, v)


@pytest.fixture
async def get_jwt_token_params(request):
	"""
	Определяет секретный ключ и алгоритм JWT для тестирования токена.
	"""
	request.cls.jwt_secret_key = JWT_SECRET_KEY
	request.cls.jwt_algorithm = JWT_SIGN_ALGORITHM
