# import os
#
# import pytest
# from httpx import AsyncClient
#
#
# @pytest.mark.usefixtures("generate_user", "get_jwt_token_params")
# class TestAuth:
# 	async def test_create_user(self, async_test_client: AsyncClient):
# 		"""
# 		Тест создания нового пользователя.
#
# 		Дату/время регистрации форматирую в местные (без нужды, но мб как-то можно после применить).
# 		"""
# 		user_data = dict(user={
# 			"email": self.email,
# 			"password": self.password,
# 			"first_name": self.first_name,
# 			"last_name": self.last_name
# 		})
#
# 		response = await async_test_client.post(
# 			"/api/v1/users/",
# 			json=user_data
# 		)
#
# 		assert response.status_code == 201
#
# 		created_user_data = response.json()
#
# 		user_id = created_user_data.get("id")
# 		os.environ.setdefault("TEST_AUTH_USER_ID", str(user_id))  # для использования в тестах далее
#
# 		assert "registered_at" in created_user_data
#
# 		local_reg_datetime = convert_obj_creating_time(obj_json=created_user_data, obj_type="user")
#
# 		created_user_data["registered_at"] = local_reg_datetime
#
# 		assert created_user_data == {
# 			'email': user_data["user"].get("email"), 'first_name': user_data["user"].get("first_name"),
# 			'last_name': None,
# 			'registered_at': local_reg_datetime, 'id': user_id, 'is_staff': False, 'disabled': False
# 		}
#
# 	async def test_create_user_errors(self, async_test_client: AsyncClient):
# 		"""
# 		Получение ошибок при создании нового пользователя.
# 		Если email уже существует - статус-код 409.
# 		"""
# 		user_data = dict(user={
# 			"email": self.email,
# 			"password": self.password,
# 			"first_name": self.first_name
# 		})
#
# 		response = await async_test_client.post(
# 			"/api/v1/users/",
# 			json=user_data
# 		)
#
# 		assert response.status_code == 409
#
# 	async def test_login_for_access_token(self, async_test_client: AsyncClient):
# 		"""
# 		Получение JWT-токена. Проверка его содержания.
# 		По ключу 'sub' в токене содержится email пользователя.
# 		"""
# 		form_data = {
# 			"email": self.email,
# 			"password": self.password
# 		}
# 		response = await async_test_client.post(
# 			"/api/v1/token/",
# 			data=form_data
# 		)
#
# 		assert response.status_code == 200
#
# 		token = response.json().get("access_token")
#
# 		assert token
#
# 		payload = jwt.decode(token=token, key=self.jwt_secret_key, algorithms=[self.jwt_algorithm])
#
# 		user_email = payload.get("sub")
#
# 		assert user_email and user_email == self.email
#
# 	async def test_login_for_access_token_errors(self, async_test_client: AsyncClient, session: AsyncSession):
# 		"""
# 		Получение ответа 401 в случае, если email или password не подходят.
# 		Получение ответа 403 в случае, если пользователь заблокирован.
# 		"""
# 		form_data = {
# 			"email": "qwerty_qwerty_qwerty@hotmail.com",
# 			"password": self.password
# 		}
#
# 		response = await async_test_client.post(
# 			"/api/v1/token/",
# 			data=form_data
# 		)
#
# 		assert response.status_code == 401
#
# 		form_data["email"] = self.email
# 		form_data["password"] = "qwerty_qwerty_qwerty"
#
# 		response = await async_test_client.post(
# 			"/api/v1/token/",
# 			data=form_data
# 		)
#
# 		assert response.status_code == 401
#
# 		user_id = int(os.environ.get("TEST_AUTH_USER_ID"))
#
# 		await change_user_params(disabled=True, user_id=user_id, sa_session=session)
#
# 		response_for_disabled_user = await async_test_client.post(
# 			"/api/v1/token/",
# 			data={
# 				"email": self.email,
# 				"password": self.password
# 			}
# 		)
#
# 		assert response_for_disabled_user.status_code == 403
#
#
# @pytest.mark.usefixtures("generate_user_with_token")
# class TestDisabledUserOrBadToken:
# 	"""
# 	Выношу ошибки по причине невалидного токена или заблокированного пользователя сюда,
# 	 чтобы не повторяться в каждом тесте.
# 	"""
# 	async def test_disabled_or_bad_token_user(self, async_test_client: AsyncClient, session: AsyncSession):
# 		"""
# 		Urls_and_methods - эндпоинты.
# 		"""
# 		urls_and_methods = {
# 			"get": ("/api/v1/users/", "/api/v1/users/me", "/api/v1/notes/", "/api/v1/notes/me",
# 					"/api/v1/notes/123", "/api/v1/day_ratings/", "/api/v1/day_ratings/me",
# 					f"/api/v1/day_ratings/user/{self.id}?date=2023-06-27"),
# 			"post": ("/api/v1/notes/", "/api/v1/day_ratings/"),
# 			"put": (f"/api/v1/users/{self.id}", "/api/v1/notes/123",
# 					f"/api/v1/day_ratings/user/{self.id}?date=2023-06-27"),
# 			"delete": (f"/api/v1/users/{self.id}", "/api/v1/notes/123",
# 					   f"/api/v1/day_ratings/user/{self.id}?date=2023-06-27")
# 		}  # может быть, через роутеры фастапи можно сразу получить все урлы и методы апи сразу,
# 		# но я написал вручную - не нашел такой функции
#
# 		for method in urls_and_methods:
# 			urls_list = urls_and_methods.get(method)
# 			for url in urls_list:
# 				data = {
# 					"url": url,
# 					"headers": self.headers,
# 					"user_id": self.id,
# 					"sa_session": session,
# 					"async_test_client": async_test_client
# 				}
#
# 				match method:
# 					case "get":
# 						data.setdefault("method", "get")
# 					case "post":
# 						data.setdefault("method", "post")
# 					case "put":
# 						data.setdefault("method", "put")
# 					case "delete":
# 						data.setdefault("method", "delete")
#
# 				response_bad_token, response_disabled_user = await endpoint_autotest(data=data)
#
# 				assert response_disabled_user.status_code == 403
# 				assert response_bad_token.status_code == 401