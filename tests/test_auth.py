from httpx import AsyncClient
import pytest
from jose import jwt

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas_token import Token
from app.models.auth import RegistrationCode
from tests.additional.users import change_user_data
import config


@pytest.mark.usefixtures("generate_user")
class TestAuth:
	"""
	Тестирование аутентификации пользователя.
	"""
	async def test_get_valid_token(self, ac: AsyncClient, session: AsyncSession):
		"""
		Проверка получения access-токена.
		В 'sub' токена должен содержаться email пользователя.
		Токен должен быть рабочим.
		"""
		data = {"email": self.email, "password": self.password}
		response = await ac.post(
			"/api/v1/auth/token",
			data=data
		)
		assert response.status_code == 200

		token = Token(**response.json())

		payload = jwt.decode(token=token.access_token,
							 key=config.JWT_SECRET_KEY,
							 algorithms=[config.JWT_SIGN_ALGORITHM])

		email: str = payload.get("sub")

		assert email == self.email

		self.token = token.access_token
		self.headers = {
			"Authorization": f"Bearer {self.token}"
		}

		await change_user_data(self, session, email_confirmed=True)

		response = await ac.get(
			"/api/v1/users/me",
			headers=self.headers
		)
		assert response.status_code == 200

	async def test_get_token_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Некорректные email/password;
		- Заблокированный пользователь.
		"""
		correct_data = {"email": self.email, "password": self.password}
		invalid_data = {"email": self.email, "password": self.password + "qwerty"}

		invalid_data_response = await ac.post(
			"/api/v1/auth/token",
			data=invalid_data
		)

		assert invalid_data_response.status_code == 401

		await change_user_data(self, session, disabled=True)

		disabled_user_response = await ac.post(
			"/api/v1/auth/token",
			data=correct_data
		)
		assert disabled_user_response.status_code == 403


@pytest.mark.usefixtures("generate_authorized_user")
class TestRegistrationCode:
	"""
	Тестирование кодов подтверждения email.
	Ограниченное - см. описание проблемы в conftest.
	"""
	async def test_request_confirmation_code(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание в БД записи об отправленном коде подтверждения регистрации.
		Мб, придется подождать в течение таймаута SMTP, пока письмо точно отправится.
		"""
		response = await ac.get(
			"/api/v1/auth/confirm_email",
			headers=self.headers
		)

		assert response.status_code == 200

		code = await RegistrationCode.get_user_last_code(user=self.user_schema, db=session)

		assert code is not None

	async def test_request_confirmation_code_codes_duplicate_error(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Нельзя получить код, если предыдущий еще не истек.
		"""
		for _ in range(2):
			response = await ac.get(
				"/api/v1/auth/confirm_email",
				headers=self.headers
			)
		assert response.status_code == 425

	async def test_confirmation_codes_user_disabled_or_confirmed_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Заблокированный пользователь;
		- Уже подтвержденный пользователь.
		"""
		await change_user_data(self, session, disabled=True)
		r_1 = await ac.post(
			"/api/v1/auth/confirm_email",
			headers=self.headers,
			json={"code": "123456"}
		)

		r_2 = await ac.get(
			"/api/v1/auth/confirm_email",
			headers=self.headers
		)

		assert r_1.status_code == 403 and r_2.status_code == 403

		await change_user_data(self, session, disabled=False, email_confirmed=True)

		r_1 = await ac.post(
			"/api/v1/auth/confirm_email",
			headers=self.headers,
			json={"code": "123456"}
		)
		r_2 = await ac.get(
			"/api/v1/auth/confirm_email",
			headers=self.headers
		)

		assert r_1.status_code == 403 and r_2.status_code == 403

	async def test_auth_without_bad_token_error(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Некорректный токен от пользователя.
		"""
		self.headers["Authorization"] = self.headers.get("Authorization") + "qwerty"

		r_1 = await ac.post(
			"/api/v1/auth/confirm_email",
			headers=self.headers
		)
		r_2 = await ac.get(
			"/api/v1/auth/confirm_email",
			headers=self.headers
		)
		assert r_1.status_code == 401 and r_2.status_code == 401
