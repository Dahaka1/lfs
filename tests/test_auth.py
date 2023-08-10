import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import RegistrationCode
from app.schemas.schemas_token import LoginTokens
from app.schemas.schemas_users import User
from app.utils.general import decode_jwt
from tests.additional import auth
from tests.additional.auth import url_auth_test
from tests.additional.users import change_user_data, get_user_token


@pytest.mark.usefixtures("generate_user")
class TestAuth:
	id: int
	email: str
	password: str
	headers: dict
	token: str | None
	"""
	Тестирование аутентификации пользователя.
	"""
	async def test_login(self, ac: AsyncClient, session: AsyncSession):
		"""
		Проверка получения пары токенов.
		В 'sub' токена должен содержаться email пользователя.
		Токен должен быть рабочим.
		"""
		data = {"email": self.email, "password": self.password}
		response = await ac.post(
			"/v1/auth/login",
			json=data
		)
		assert response.status_code == 200

		tokens = LoginTokens(**response.json())
		payload = decode_jwt(tokens.access_token)
		email: str = payload.get("sub")

		assert email == self.email

		assert tokens.refresh_token
		assert tokens.refresh_token[-6:] == tokens.access_token[-6:]

		refresh_token_in_db = await auth.user_refresh_token_in_db(self.id, session)
		assert refresh_token_in_db and refresh_token_in_db == tokens.refresh_token

		self.token = tokens.access_token
		self.headers = {
			"Authorization": f"Bearer {self.token}",
			"refreshToken": tokens.refresh_token
		}

		await change_user_data(self, session, email_confirmed=True)

		response = await ac.get(
			"/v1/users/me",
			headers=self.headers
		)
		assert response.status_code == 200

	async def test_login_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Некорректные email/password;
		- Заблокированный пользователь.
		"""
		correct_data = {"email": self.email, "password": self.password}
		invalid_data = {"email": self.email, "password": self.password + "qwerty"}

		invalid_data_response = await ac.post(
			"/v1/auth/login",
			json=invalid_data
		)

		assert invalid_data_response.status_code == 401

		await change_user_data(self, session, disabled=True)
		disabled_user_response = await ac.post(
			"/v1/auth/login",
			json=correct_data
		)
		assert disabled_user_response.status_code == 403

	async def test_refresh_access_token(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление пары токенов пользователя.
		"""
		tokens = await get_user_token(self.email, self.password, ac)
		headers = {"refreshToken": tokens.refresh_token}

		response = await ac.get(
			"/v1/auth/token",
			headers=headers
		)

		assert response.status_code == 200
		updated_refresh = response.json().get("refresh_token")
		assert updated_refresh and updated_refresh != tokens.refresh_token

		refresh_token_in_db = await auth.user_refresh_token_in_db(self.id, session)
		assert refresh_token_in_db == updated_refresh

		access_token = response.json().get("access_token")
		assert access_token
		access_payload = decode_jwt(access_token)
		assert access_payload.get("sub") == self.email

	async def test_refresh_access_token_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Токен должен быть валидным;
		- Должен быть в БД.
		"""
		def headers(data: str | None) -> dict:
			return {"refreshToken": data}

		# ___________________________________________________________________________________

		valid_refresh = (await get_user_token(self.email, self.password, ac)).refresh_token
		invalid_refresh = valid_refresh + "qwerty"

		invalid_token_r = await ac.get(
			"/v1/auth/token",
			headers=headers(invalid_refresh)
		)
		assert invalid_token_r.status_code == 401

		# ___________________________________________________________________________________

		await auth.delete_user_refresh_token_in_db(self.id, session)

		non_existing_token_in_db_r = await ac.get(
			"/v1/auth/token",
			headers=headers(valid_refresh)
		)

		assert non_existing_token_in_db_r.status_code == 401

	async def test_logout(self, ac: AsyncClient, session: AsyncSession):
		"""
		Выход пользователя
		"""
		tokens = await get_user_token(self.email, self.password, ac)
		headers = {"Authorization": f"Bearer {tokens.access_token}",
				   "refreshToken": tokens.refresh_token}

		response = await ac.get(
			"/v1/auth/logout",
			headers=headers
		)
		assert response.status_code == 200
		user_refresh_in_db = await auth.user_refresh_token_in_db(self.id, session)
		assert user_refresh_in_db is None

	async def test_logout_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Юзер не должен быть заблокированным;
		- Токены должны быть валидными.
		"""
		tokens = await get_user_token(self.email, self.password, ac)
		headers = {"Authorization": "Bearer " + tokens.access_token,
				   "refreshToken": tokens.refresh_token}
		await change_user_data(self.id, session, disabled=True)

		disabled_user_r = await ac.get(
			"/v1/auth/logout",
			headers=headers
		)

		assert disabled_user_r.status_code == 403

		await change_user_data(self.id, session, disabled=False)

		headers["Authorization"] += "qwerty"

		invalid_tokens_r = await ac.get(
			"/v1/auth/logout",
			headers=headers
		)

		assert invalid_tokens_r.status_code == 401


@pytest.mark.usefixtures("generate_authorized_user")
class TestRegistrationCode:
	id: int
	email: str
	password: str
	headers: dict
	token: str | None
	user_schema: User
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
			"/v1/auth/confirm_email",
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
				"/v1/auth/confirm_email",
				headers=self.headers
			)
		assert response.status_code == 425

		await auth.delete_user_code(self, session)
		await url_auth_test("/v1/auth/confirm_email",
							"get", self,  ac, session)

	async def test_confirm_email_post_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Код пользователя не найден;
		- Неправильный введенный код;
		- Срок действия кода истек;
		- users auth auto test.
		"""
		code_not_found_r = await ac.post(
			"/v1/auth/confirm_email",
			headers=self.headers,
			json={"code": "123456"}
		)
		assert code_not_found_r.status_code == 404

		await ac.get(
			"/v1/auth/confirm_email",
			headers=self.headers
		)

		invalid_code_r = await ac.post(
			"/v1/auth/confirm_email",
			headers=self.headers,
			json={"code": "123456"}
		)

		assert invalid_code_r.status_code == 403

		await auth.do_code_expired(self, session)

		expired_code_r = await ac.post(
			"/v1/auth/confirm_email",
			headers=self.headers,
			json={"code": "123456"}
		)

		assert expired_code_r.status_code == 408

		await url_auth_test("/v1/auth/confirm_email", 'post', self, ac, session, json={"code": "123456"})
