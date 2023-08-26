import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.users import User
from app.schemas import schemas_users as users
from app.static.enums import RoleEnum, RegionEnum, UserSortingEnum
from app.utils.general import verify_data_hash
from tests.additional import auth, users as users_funcs, strings, other


@pytest.mark.usefixtures("generate_users")
class TestUsers:
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	region_manager: users_funcs.UserData
	"""
	Тестирование функционала пользователей.
	"""
	async def test_read_users(self, ac: AsyncClient):
		"""
		Получение списка всех пользователей.
		"""
		response = await ac.get(
			"/v1/users/",
			headers=self.sysadmin.headers
		)

		assert response.status_code == 200
		users_list = response.json()
		assert len(users_list) > 0
		map(lambda u: users.User(**u), users_list)  # здесь поднимется ValidationError, если что-то не так

		# ___

		response_general_manager = await ac.get(
			"/v1/users/",
			headers=self.manager.headers
		)
		assert len(response_general_manager.json()) == len(users_list)

		# ___

		assert not any(
			(u for u in users_list if u["id"] == self.sysadmin.id)
		)

	async def test_read_users_by_region_manager(self, session: AsyncSession, ac: AsyncClient,
												sync_session: Session):
		users_ = await users_funcs.get_all_users(session)
		for user in users_:
			await users_funcs.change_user_data(user["id"], session, region=RegionEnum.NORTHWEST)

		users_funcs.create_user(sync_session, region=RegionEnum.SOUTH)
		await users_funcs.change_user_data(self.region_manager, session,
										   region=RegionEnum.SOUTH)
		self.region_manager.region = RegionEnum.SOUTH
		r = await ac.get(
			"/v1/users/",
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [users.User(**u) for u in r.json()]
		assert all(
			(u.region == self.region_manager.region for u in r)
		)
		assert len(r) == 1

	async def test_read_users_with_ordering(self, session: AsyncSession, ac: AsyncClient):
		users_ = await users_funcs.get_all_users(session)
		for u in users_:
			u_id = u["id"]
			await users_funcs.change_user_data(u_id, session,
											   last_action_at=other.generate_datetime())
			# иначе ошибка при сравнении None для сортировки
		for param in list(UserSortingEnum):
			for desc in (True, False):
				r = await ac.get("/v1/users/" + f"?order_by={param.value}&desc={desc}",
								 headers=self.manager.headers)
				users_ = [users.User(**u) for u in r.json()]
				sorting_params = {"key": None, "reverse": desc}
				match param:
					case UserSortingEnum.NAME:
						sorting_params["key"] = lambda u: u.last_name
					case UserSortingEnum.REGION:
						sorting_params["key"] = lambda u: u.region.value
					case UserSortingEnum.LAST_ACTION:
						sorting_params["key"] = lambda u: u.last_action_at
					case UserSortingEnum.ROLE:
						sorting_params["key"] = lambda u: u.role.value
				assert users_ == sorted(users_, **sorting_params)

	async def test_read_users_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- user roles auto test;
		- users auth auto test.
		"""
		await auth.url_auth_roles_test(
			"/v1/users/",
			"get", RoleEnum.REGION_MANAGER, self.region_manager, session, ac
		)

		await auth.url_auth_test(
			"/v1/users/",
			"get", self.sysadmin, ac, session
		)

	async def test_create_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание пользователя.
		"""
		user_data = dict(user={
			"first_name": "Test",
			"last_name": "Test",
			"email": "awdafggdgsefdwed@gmail.com",
			"password": "qwerty123"
		})

		response = await ac.post(
			"/v1/users/",
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

	async def test_create_user_by_sysadmin(self, session: AsyncSession, ac: AsyncClient):
		user_data = dict(user={
			"first_name": "Test",
			"last_name": "Test",
			"region": RegionEnum.NORTHWEST.value,
			"email": "asdasdasdceeegt@gmail.com",
			"password": "qwerty123",
			"role": RoleEnum.REGION_MANAGER.value
		})
		r = await ac.post(
			"/v1/users/user",
			headers=self.sysadmin.headers,
			json=user_data
		)
		assert r.status_code == 201
		r = users.User(**r.json())
		assert r.role.value == user_data["user"]["role"]
		user_in_db = await users_funcs.get_user_by_id(r.id, session)
		assert user_in_db.role.value == user_data["user"]["role"]

	async def test_create_user_by_sysadmin_autotests(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/users/user"
		json = dict(user={
			"first_name": "Test",
			"last_name": "Test",
			"region": RegionEnum.NORTHWEST.value,
			"email": "asdasdasdceeegt@gmail.com",
			"password": "qwerty123",
			"role": RoleEnum.REGION_MANAGER.value
		})

		await auth.url_auth_test(url, "post", self.sysadmin, ac, session, json=json)
		await auth.url_auth_roles_test(url, "post", RoleEnum.SYSADMIN, self.sysadmin,
									   session, ac, json=json)

	async def test_create_user_with_region(self, session: AsyncSession, ac: AsyncClient):
		"""
		если регион не нужен для роли - установится как None
		"""
		url = "/v1/users/user"
		for role in (RoleEnum.MANAGER, RoleEnum.SYSADMIN, RoleEnum.LAUNDRY):
			json = dict(user={
				"first_name": "Test",
				"last_name": "Test",
				"region": RegionEnum.NORTHWEST.value,
				"email": f"{strings.generate_string()}@gmail.com",
				"password": "qwerty123",
				"role": role.value
			})
			r = await ac.post(
				url,
				headers=self.sysadmin.headers,
				json=json
			)
			user = users.User(**r.json())
			assert user.region is None
		for role in (RoleEnum.INSTALLER, RoleEnum.REGION_MANAGER):
			json = dict(user={
				"first_name": "Test",
				"last_name": "Test",
				"region": RegionEnum.NORTHWEST.value,
				"email": f"{strings.generate_string()}@gmail.com",
				"password": "qwerty123",
				"role": role.value
			})
			r = await ac.post(
				url,
				headers=self.sysadmin.headers,
				json=json
			)
			user = users.User(**r.json())
			assert user.region == RegionEnum.NORTHWEST

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
				"/v1/users/",
				json=user_data
			)
		assert existing_email_r.status_code == 409

	async def test_read_users_me(self, ac: AsyncClient):
		"""
		Получение пользователем своих данных
		"""
		response = await ac.get(
			"/v1/auth/user",
			headers=self.laundry.headers
		)

		assert response.status_code == 200

		assert response.json().get("email") == self.laundry.email

	async def test_read_users_me_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- users auth auto test
		"""
		await auth.url_auth_test(
			"/v1/auth/user", "get",
			self.sysadmin, ac, session
		)

	async def test_read_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение данных пользователя
		"""
		r_1 = await ac.get(
			f"/v1/users/{self.laundry.id}",
			headers=self.laundry.headers
		)

		assert r_1.status_code == 200
		assert r_1.json().get("email") == self.laundry.email

		r_2 = await ac.get(
			f"/v1/users/{self.laundry.id}",
			headers=self.sysadmin.headers
		)

		assert r_2.status_code == 200
		assert r_2.json().get("email") == self.laundry.email

		# ___

		await users_funcs.change_user_data(self.region_manager, session,
										   region=self.laundry.region)
		region_manager_r = await ac.get(
			f"/v1/users/{self.laundry.id}",
			headers=self.region_manager.headers
		)
		assert region_manager_r.status_code == 200

		# ___

		manager_r = await ac.get(
			f"/v1/users/{self.laundry.id}",
			headers=self.manager.headers
		)
		assert manager_r.status_code == 200

	async def test_read_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Получить данные пользователя может либо сам пользователь, либо сисадмин;
		- users auth auto test
		"""
		permissions_error_r = await ac.get(
			f"/v1/users/{self.laundry.id}",
			headers=self.installer.headers
		)
		assert permissions_error_r.status_code == 403

		await auth.url_auth_test(
			f"/v1/users/{self.sysadmin.id}",
			"get", self.sysadmin, ac, session
		)

		# ___

		await users_funcs.change_user_data(self.laundry, session,
										   region=RegionEnum.SOUTH)
		if self.region_manager.region == RegionEnum.SOUTH:
			raise ValueError
		r = await ac.get(
			f"/v1/users/{self.laundry.id}",
			headers=self.region_manager.headers
		)
		assert r.status_code == 403

	async def test_update_user_laundry_password_by_self(self, ac: AsyncClient, session: AsyncSession):
		password = "qwertyqwerty"
		params = dict(user_update={"password": password})
		r = await ac.put(
			f"/v1/users/{self.laundry.id}",
			headers=self.laundry.headers,
			json=params
		)
		assert r.status_code == 200
		r = users.User(**r.json())
		assert r.email == self.laundry.email

		user_in_db = await users_funcs.get_user_by_id(self.laundry.id, session, in_db=True)
		assert verify_data_hash(password, user_in_db.hashed_password)

	async def test_update_user_laundry_by_self_not_permitted_fields(self, session: AsyncSession, ac: AsyncClient):
		params = dict(user_update={"email": "qwerty@gmail.com"})
		r = await ac.put(
			f"/v1/users/{self.laundry.id}",
			headers=self.laundry.headers,
			json=params
		)
		assert r.status_code == 403

	async def test_update_another_user_password_by_manager_and_sysadmin(self, session: AsyncSession,
																		ac: AsyncClient):
		params = dict(user_update={"password": "qwertyqweqwe"})
		await users_funcs.change_user_data(self.region_manager, session,
										   region=self.laundry.region)
		for user in (self.sysadmin, self.manager, self.region_manager):
			r = await ac.put(
				f"/v1/users/{self.laundry.id}",
				headers=user.headers,
				json=params
			)
			assert r.status_code == 403

	async def test_update_another_user_by_sysadmin_or_manager(self, session: AsyncSession, ac: AsyncClient):
		email = "qwerty@gmail.com"
		region = RegionEnum.SOUTH
		role = RoleEnum.INSTALLER

		params = dict(user_update={"email": email,
								   "region": region.value,
								   "role": role.value})

		r = await ac.put(
			f"/v1/users/{self.laundry.id}",
			headers=self.sysadmin.headers,
			json=params
		)
		assert r.status_code == 200
		updated_user = users.User(**r.json())
		assert updated_user.email == email
		assert updated_user.region == region
		assert updated_user.role == role

		updated_user_in_db = await users_funcs.get_user_by_id(updated_user.id,
															  session)
		assert updated_user_in_db.email == email
		assert updated_user_in_db.region == region
		assert updated_user_in_db.role == role

		# ___

		await users_funcs.change_user_data(self.installer, session,
										   region=self.region_manager.region,
										   role=RoleEnum.LAUNDRY,
										   email="asdsadasfg@gmail.com")
		params["user_update"]["email"] = "qwersfwef@gmail.com"
		r = await ac.put(
			f"/v1/users/{self.installer.id}",
			headers=self.region_manager.headers,
			json=params
		)
		assert r.status_code == 200
		upd_user = users.User(**r.json())
		assert upd_user.region == region
		assert upd_user.email == params["user_update"]["email"]
		assert upd_user.role == role

	async def test_update_user_manager_and_sysadmin_data_by_self(self, session: AsyncSession, ac: AsyncClient):
		"""
		password included
		"""
		password = "qwetyqwertywe"
		region = RegionEnum.SOUTH
		last_name = "admin"
		params = dict(user_update={"password": password,
								   "region": region.value,
								   "last_name": last_name})
		for user in (self.sysadmin, self.region_manager, self.manager):
			r = await ac.put(
				f"/v1/users/{user.id}",
				headers=user.headers,
				json=params
			)
			assert r.status_code == 200
			updated_user = users.User(**r.json())
			assert updated_user.region == region
			assert updated_user.last_name == last_name
			updated_user_in_db = await users_funcs.get_user_by_id(user.id,
																  session, in_db=True)
			assert verify_data_hash(password, updated_user_in_db.hashed_password)

	async def test_update_user_by_not_permitted_user(self, session: AsyncSession, ac: AsyncClient):
		params = dict(user_update={"region": RegionEnum.NORTHWEST.value})
		r = await ac.put(
			f"/v1/users/{self.laundry.id}",
			headers=self.installer.headers,
			json=params
		)
		assert r.status_code == 403

		# ___

		r_ = await ac.put(
			f"/v1/users/{self.manager.id}",
			headers=self.region_manager.headers,
			json=params
		)
		assert r_.status_code == 403

		# ___

		await users_funcs.change_user_data(self.installer, session,
										   region=RegionEnum.SOUTH)
		if self.region_manager.region == RegionEnum.SOUTH:
			raise ValueError
		r__ = await ac.put(
			f"/v1/users/{self.installer.id}",
			headers=self.region_manager.headers,
			json=params
		)
		assert r__.status_code == 403

	async def test_update_user_self_role_by_self(self, session: AsyncSession, ac: AsyncClient):
		for user in (self.manager, self.sysadmin, self.region_manager):
			r = await ac.put(
				f"/v1/users/{user.id}",
				headers=user.headers,
				json=dict(user_update={"role": RoleEnum.INSTALLER.value})
			)
			assert r.status_code == 403

	async def test_delete_user(self, ac: AsyncClient, session: AsyncSession):
		r = await ac.delete(
			f"/v1/users/{self.manager.id}",
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		user_exists = await users_funcs.get_user_by_id(self.manager.id, session)
		assert not user_exists

	async def test_delete_user_by_self(self, session: AsyncSession, ac: AsyncClient):
		r = await ac.delete(
			f"/v1/users/{self.manager.id}",
			headers=self.manager.headers
		)
		assert r.status_code == 403

	async def test_delete_user_by_not_permitted_user(self, session: AsyncSession, ac: AsyncClient):
		r = await ac.delete(
			f"/v1/users/{self.installer.id}",
			headers=self.laundry.headers
		)
		assert r.status_code == 403

		r_ = await ac.delete(
			f"/v1/users/{self.sysadmin.id}",
			headers=self.manager.headers
		)
		assert r_.status_code == 403


