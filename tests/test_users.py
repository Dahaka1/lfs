import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from httpx import AsyncClient

from app.schemas import schemas_users as users
from app.models.users import User
from tests.additional import auth, users as users_funcs
from app.static.enums import RoleEnum, RegionEnum
from app.utils.general import sa_object_to_dict, sa_objects_dicts_list


@pytest.mark.usefixtures("generate_users")
class TestUsers:
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	"""
	Тестирование функционала пользователей.
	"""

	async def test_read_users(self, ac: AsyncClient):
		"""
		Получение списка всех пользователей.
		"""
		response = await ac.get(
			"/api/v1/users/",
			headers=self.sysadmin.headers
		)

		assert response.status_code == 200
		users_list = response.json()
		assert len(users_list) > 0
		map(lambda u: users.User(**u), users_list)  # здесь поднимется ValidationError, если что-то не так

	async def test_read_users_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- user roles auto test;
		- users auth auto test.
		"""
		await auth.url_auth_roles_test(
			"/api/v1/users/",
			"get", RoleEnum.SYSADMIN, self.sysadmin, session, ac
		)

		await auth.url_auth_test(
			"/api/v1/users/",
			"get", self.sysadmin, ac, session
		)

	async def test_create_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание пользователя.
		"""
		user_data = dict(user={
			"first_name": "Test",
			"last_name": "Test",
			"region": RegionEnum.NORTHWEST.value,
			"email": "test_123@gmail.com",
			"password": "qwerty123"
		})

		response = await ac.post(
			"/api/v1/users/",
			json=user_data
		)

		assert response.status_code == 201
		created_user = response.json()

		for k, v in user_data["user"].items():
			if k in created_user:  # пароль, например, не возвращается
				assert created_user[k] == v

		user_in_db = await session.execute(
			select(User).where(User.email == user_data["user"]["email"])
		)
		assert user_in_db.scalar()

	async def test_create_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Нельзя создать пользователя с уже существующим email.
		"""
		user_data = dict(user={
			"first_name": "Test",
			"last_name": "Test",
			"region": RegionEnum.NORTHWEST.value,
			"email": "test_123456@gmail.com",
			"password": "qwerty123"
		})
		for _ in range(2):
			existing_email_r = await ac.post(
				"/api/v1/users/",
				json=user_data
			)
		assert existing_email_r.status_code == 409

	async def test_read_users_me(self, ac: AsyncClient):
		"""
		Получение пользователем своих данных
		"""
		response = await ac.get(
			"/api/v1/users/me",
			headers=self.laundry.headers
		)

		assert response.status_code == 200

		assert response.json().get("email") == self.laundry.email

	async def test_read_users_me_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- users auth auto test
		"""
		await auth.url_auth_test(
			"/api/v1/users/me", "get",
			self.sysadmin, ac, session
		)

	async def test_read_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение данных пользователя
		"""
		r_1 = await ac.get(
			f"/api/v1/users/{self.laundry.id}",
			headers=self.laundry.headers
		)

		assert r_1.status_code == 200
		assert r_1.json().get("email") == self.laundry.email

		r_2 = await ac.get(
			f"/api/v1/users/{self.laundry.id}",
			headers=self.sysadmin.headers
		)

		assert r_2.status_code == 200
		assert r_2.json().get("email") == self.laundry.email

	async def test_read_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Получить данные пользователя может либо сам пользователь, либо сисадмин;
		- users auth auto test
		"""
		permissions_error_r = await ac.get(
			f"/api/v1/users/{self.laundry.id}",
			headers=self.installer.headers
		)
		assert permissions_error_r.status_code == 403

		await auth.url_auth_test(
			f"/api/v1/users/{self.sysadmin.id}",
			"get", self.sysadmin, ac, session
		)

	async def test_update_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление данных пользователя.
		Если изменился email - нужно заново подтверждать.
		Изменить роль и заблокировать юзера может только сисадмин.
		Изменить email и пароль может только сам пользователь.
		"""
		put_from_sysadmin_data = dict(user={
			"password": "testtesttest",
			"role": RoleEnum.MANAGER.value,
			"email": "testitplease@gmail.com",
			"disabled": True
		})
		if isinstance(self.laundry.id, int):  # чтобы линтер не ругался
			user_before_put = await session.execute(
				select(User).where(User.id == self.laundry.id)
			)
			current_user_password_hash = sa_object_to_dict(user_before_put.scalar()).get("hashed_password")

		response = await ac.put(
			f"/api/v1/users/{self.laundry.id}",
			headers=self.sysadmin.headers,
			json=put_from_sysadmin_data
		)
		assert response.status_code == 200
		response_schema = users.User(**response.json())  # если что, вызовет ValidationError
		user_after_put = await session.execute(
			select(User).where(User.id == self.laundry.id)
		)
		updated_data = sa_object_to_dict(user_after_put.scalar())
		updated_user_password_hash = updated_data.get("hashed_password")
		assert updated_user_password_hash == current_user_password_hash
		assert updated_data["email"] == self.laundry.email
		assert updated_data["disabled"] is put_from_sysadmin_data["user"].get("disabled")
		assert updated_data["role"].value == put_from_sysadmin_data["user"].get("role")
		assert response_schema.email == self.laundry.email
		assert response_schema.disabled is put_from_sysadmin_data["user"].get("disabled")
		assert response_schema.role.value == put_from_sysadmin_data["user"].get("role")

		# _________________________________________________________________________________

		put_from_user_data = put_from_sysadmin_data

		if isinstance(self.installer.id, int):
			user_before_put = await session.execute(
				select(User).where(User.id == self.installer.id)
			)
		current_user_password_hash = sa_object_to_dict(user_before_put.scalar()).get("hashed_password")
		response = await ac.put(
			f"/api/v1/users/{self.installer.id}",
			headers=self.installer.headers,
			json=put_from_user_data
		)
		assert response.status_code == 200
		user_after_put = await session.execute(
			select(User).where(User.id == self.installer.id)
		)
		updated_data = sa_object_to_dict(user_after_put.scalar())
		assert updated_data["email"] == put_from_user_data["user"].get("email")
		assert updated_data["role"].value != put_from_user_data["user"].get('role')
		assert updated_data["disabled"] is not put_from_user_data["user"].get("disabled")
		assert updated_data["email_confirmed"] is False
		assert updated_data["hashed_password"] != current_user_password_hash

	async def test_update_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Обновить данные может либо сам пользователь, либо сисадмин;
		- ИД юзера должен быть существующим;
		- users auth auto test.
		"""
		non_permissions_r = await ac.put(
			f"/api/v1/users/{self.installer.id}",
			headers=self.laundry.headers,
			json=dict(user={})
		)

		assert non_permissions_r.status_code == 403

		non_existing_id_r = await ac.put(
			f"/api/v1/users/12345",
			headers=self.sysadmin.headers,
			json=dict(user={})
		)
		assert non_existing_id_r.status_code == 404

		await auth.url_auth_test(
			f"/api/v1/users/{self.installer.id}", "put",
			self.installer, ac, session, json=dict(user={})
		)

	async def test_delete_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Удаление пользователя.
		Удалить пользователя могут: сам пользователь / сисадмин.
		"""
		response_sysadmin = await ac.delete(
			f"/api/v1/users/{self.laundry.id}",
			headers=self.sysadmin.headers
		)
		assert response_sysadmin.status_code == 200

		response_user = await ac.delete(
			f"/api/v1/users/{self.installer.id}",
			headers=self.installer.headers
		)
		assert response_user.status_code == 200

		users_in_db = await session.execute(
			select(User)
		)

		users_list = sa_objects_dicts_list(users_in_db.scalars().all())

		assert not any(
			(user.id in [u["id"] for u in users_list])
			for user in [self.installer, self.laundry]
		), str(users_list)

	async def test_delete_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Удалить пользователя могут: сам пользователь / сисадмин;
		- users auth auto test
		"""
		non_permissions_r = await ac.delete(
			f"/api/v1/users/{self.installer.id}",
			headers=self.laundry.headers
		)

		assert non_permissions_r.status_code == 403

		await auth.url_auth_test(
			f"/api/v1/users/{self.installer.id}", "delete",
			self.installer, ac, session
		)
