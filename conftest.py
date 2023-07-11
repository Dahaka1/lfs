import dotenv

dotenv.load_dotenv()  # load env vars for safe importing

import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from config import DATABASE_URL_TEST, JWT_SIGN_ALGORITHM, JWT_SECRET_KEY
from sqlalchemy.pool import NullPool
from app.database import Base
from app.models.logs import ErrorsLog, ChangesLog, StationProgramsLog, WashingAgentsUsingLog
from app.models.users import User
from app.models.washing import WashingAgent, WashingMachine
from app.models.stations import Station, StationSettings, StationProgram, StationControl
from app.models.auth import RegistrationCode
from app.dependencies import get_async_session
from sqlalchemy.orm import sessionmaker
import pytest
from app.main import app
from typing import AsyncGenerator
import asyncio
from tests.additional.fills import create_user
from app import fastapi_cache_init


engine_test = create_async_engine(DATABASE_URL_TEST, poolclass=NullPool)
async_session_maker = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)
Base.metadata.bind = engine_test


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
	"""
	Перезапись сессии БД в проекте.
	Нужно для корректной работы тестов (иначе БД будет использоваться не тестовая).
	"""
	async with async_session_maker() as session:
		yield session

app.dependency_overrides[get_async_session] = override_get_async_session
# перезапись зависимости, возвращающей сессию SA, для корректной работы БД-функций


@pytest.fixture  # для ручного использования SA-сессии в тестах
async def session() -> AsyncGenerator[AsyncSession, None]:
	async with async_session_maker() as session:
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
async def async_test_client() -> AsyncGenerator[AsyncClient, None]:
	"""
	Сессия подключения к БД для тестов
	"""
	async with AsyncClient(app=app, base_url="http://test") as ac:
		yield ac


@pytest.fixture(scope="class")
async def generate_user(request):
	"""
	Генерирует новые данные пользователя для каждого класса тестов (scope='class').
	"""
	request.cls.email = f"autotest_{random.randrange(10_000)}@gmail.com"
	request.cls.password = str(random.randrange(10_000_000, 20_000_000))
	request.cls.first_name = random.choice(
		("Andrew", "Petr", "Ivan")
	)
	request.cls.last_name = random.choice(
		("Petrov", "Sidorov", "Ivanov")
	)


@pytest.fixture(scope="function")
async def generate_confirmed_user_with_token(request):
	"""
	Генерация пользователя с готовым токеном авторизации для тестов,
	где не проверяется получение токена.
	Делаю так, потому что при получении токена внутри теста почему-то не получается
	 никаким образом сохранить токен для использования в нескольких тестах.

	В каждом тесте (функции) можно менять свободно данные, ибо scope='function'.
	"""
	request.cls.email = f"autotest_{random.randrange(10_000)}@gmail.com"
	request.cls.password = str(random.randrange(10_000_000, 20_000_000))
	request.cls.first_name = random.choice(
		("Andrew", "Petr", "Ivan")
	)
	request.cls.last_name = random.choice(
		("Petrov", "Sidorov", "Ivanov")
	)
	async with AsyncClient(app=app, base_url="http://test") as ac:
		user_and_token_data = await create_user(
			request.cls.email,
			request.cls.password,
			request.cls.first_name,
			request.cls.last_name,
			async_client=ac,
			raise_error=True,
			confirm_email=True,
			session=session
		)
	token = user_and_token_data.get("token")
	user_id = user_and_token_data.get("id")
	registered_at = user_and_token_data.get("registered_at")

	request.cls.token = token
	request.cls.id = user_id
	request.cls.headers = {
		"Authorization": f"Bearer {token}"
	}
	request.cls.registered_at = registered_at

	request.cls.dict = user_and_token_data
	request.cls.dict.pop("token")


@pytest.fixture
async def get_jwt_token_params(request):
	"""
	Определяет секретный ключ и алгоритм JWT для тестирования относительно токена.
	"""
	request.cls.jwt_secret_key = JWT_SECRET_KEY
	request.cls.jwt_algorithm = JWT_SIGN_ALGORITHM
