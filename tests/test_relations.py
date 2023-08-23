import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from httpx import AsyncClient

from tests.additional.auth import url_auth_test, url_auth_roles_test, url_get_station_by_id_test
from tests.additional import users as users_funcs, stations as stations_funcs
from app.schemas import schemas_relations as schema
from app.static.enums import RoleEnum


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestLaundryStations:
	"""
	Тестирование изменения отношений пользователь - станция.
	"""
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: stations_funcs.StationData

	async def generate_relations(self, laundry: users_funcs.UserData, ac: AsyncClient, amount: int = 5)\
		-> list[uuid.UUID]:
		added_station_ids = []
		for _ in range(amount):
			station = await stations_funcs.generate_station(ac, user=self.sysadmin)
			url = f"/v1/rel/laundry_stations/{station.serial}?user_id={laundry.id}"
			await ac.post(
				url,
				headers=self.sysadmin.headers
			)
			added_station_ids.append(station.id)
		return added_station_ids
	
	async def get_relations(self, laundry: users_funcs.UserData, ac: AsyncClient) -> schema.LaundryStations:
		url = f"/v1/rel/laundry_stations?user_id={laundry.id}"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		return schema.LaundryStations(**r.json())

	async def test_add_laundry_station(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.serial}?user_id={self.laundry.id}"
		r = await ac.post(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 201
		r = schema.LaundryStations(**r.json())
		assert self.station.id in (s.id for s in r.stations)
		assert r.user.id == self.laundry.id

	async def test_add_laundry_stations(self, session: AsyncSession, ac: AsyncClient,
										sync_session: Session):
		added_station_ids = []
		for _ in range(3):
			station = await stations_funcs.generate_station(ac, user=self.sysadmin)
			url = f"/v1/rel/laundry_stations/{station.serial}?user_id={self.laundry.id}"
			r = await ac.post(
				url,
				headers=self.sysadmin.headers
			)
			added_station_ids.append(station.id)
		assert r.status_code == 201
		r = schema.LaundryStations(**r.json())
		assert len(r.stations) == 3
		assert all(
			(station_id in (s.id for s in r.stations) for station_id in added_station_ids)
		)
		assert r.user.id == self.laundry.id

	async def test_add_laundry_station_with_existing_relation(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.laundry.id}"
		for _ in range(2):
			r = await ac.post(
				url,
				headers = self.sysadmin.headers
			)
		assert r.status_code == 409

	async def test_add_laundry_station_with_related_station(self, session: AsyncSession, ac: AsyncClient,
															sync_session: Session):
		user, user_schema = await users_funcs.create_authorized_user(ac, sync_session, RoleEnum.LAUNDRY)
		station_id = (await self.generate_relations(user, ac, amount=1))[0]
		url = f"/v1/rel/laundry_stations/{station_id}?user_id={self.laundry.id}"
		r = await ac.post(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 409s

	async def test_add_laundry_station_with_invalid_user_role(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.installer.id}"
		r = await ac.post(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 409

	async def test_add_laundry_station_auto_tests(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.laundry.id}"
		await url_auth_test(url, "post", self.sysadmin, ac, session)
		# ____
		station_url = "/v1/rel/laundry_stations/{station_id}?user_id=" + f"{self.laundry.id}"
		await url_get_station_by_id_test(station_url, "post", self.sysadmin, self.station,
										 session, ac)
		# ____
		await url_auth_roles_test(url, "post", RoleEnum.SYSADMIN, self.sysadmin,
								  session, ac)

	async def test_add_laundry_station_non_existing_user(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.laundry.id}123"
		r = await ac.post(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 404

	async def test_get_laundry_stations(self, session: AsyncSession, ac: AsyncClient):
		await self.generate_relations(self.laundry, ac)
		url = f"/v1/rel/laundry_stations?user_id={self.laundry.id}"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		schema.LaundryStations(**r.json())  # Validation error

	async def test_get_laundry_stations_empty_list(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations?user_id={self.laundry.id}"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		r = schema.LaundryStations(**r.json())
		assert not any(r.stations)
		assert r.user.id == self.laundry.id

	async def test_get_laundry_stations_with_invalid_user_role(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations?user_id={self.installer.id}"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 400
	
	async def test_get_laundry_stations_auto_test(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations?user_id={self.laundry.id}"
		await url_auth_test(url, "get", self.sysadmin, ac, session)
		await url_auth_roles_test(url, "get", RoleEnum.SYSADMIN, self.sysadmin, session, ac)
		
	async def test_delete_laundry_station(self, session: AsyncSession, ac: AsyncClient):
		station_id = (await self.generate_relations(self.laundry, ac, amount=1))[0]
		url = f"/v1/rel/laundry_stations/{station_id}?user_id={self.laundry.id}"
		r = await ac.delete(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		assert r.json() == {
			"deleted": {"user_id": self.laundry.id, "station_id": str(station_id)}
		}
		relations = await self.get_relations(self.laundry, ac)
		assert not any(relations.stations)
	
	async def test_delete_laundry_station_non_existing_relation(self, session: AsyncSession, ac: AsyncClient):		
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.laundry.id}"
		r = await ac.delete(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 400

	async def test_delete_laundry_station_with_invalid_user_role(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.installer.id}"
		r = await ac.delete(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 400
				
	async def test_delete_laundry_station_auto_tests(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/{self.station.id}?user_id={self.installer.id}"
		await url_auth_test(url, "delete", self.sysadmin, ac, session)
		await url_auth_roles_test(url, "delete", RoleEnum.SYSADMIN, self.sysadmin, session, ac)
		station_url = "/v1/rel/laundry_stations/{station_id}?user_id=" + f"{self.installer.id}"
		await url_get_station_by_id_test(station_url, "delete", self.sysadmin, self.station,
										 session, ac)
