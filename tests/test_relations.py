import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.schemas import schemas_relations as schema
from app.schemas.schemas_stations import StationGeneralParams
from app.static.enums import RoleEnum, RegionEnum, LaundryStationSorting
from tests.additional import users as users_funcs, stations as stations_funcs
from tests.additional.auth import url_auth_test, url_auth_roles_test, url_get_station_by_id_test


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
	region_manager: users_funcs.UserData

	async def generate_relations(self, laundry: users_funcs.UserData, ac: AsyncClient, amount: int = 5,
								 generate_users: bool = False, sync_session: Session = None) \
		-> list[uuid.UUID]:
		added_station_ids = []
		for _ in range(amount):
			if generate_users:
				if not sync_session:
					raise ValueError
				laundry, _ = await users_funcs.create_authorized_user(
					ac, sync_session, RoleEnum.LAUNDRY
				)
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
				headers=self.sysadmin.headers
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
		assert r.status_code == 409

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

	async def test_get_all_laundry_stations(self, session: AsyncSession, ac: AsyncClient,
											sync_session: Session):
		relations = []
		for _ in range(3):
			user, user_schema = await users_funcs.create_authorized_user(ac, sync_session,
																		 RoleEnum.LAUNDRY)
			station_id = await self.generate_relations(user, ac, amount=1)
			station = await stations_funcs.get_station_by_id(station_id[0], session)
			relations.append(schema.LaundryStationRelation(user=user_schema, station=station))
		url = "/v1/rel/laundry_stations/all"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStationRelation(**rel) for rel in r.json()]
		for rel in relations:
			assert rel.station.id in [rel_.station.id for rel_ in r]
			assert rel.user.id in [rel_.user.id for rel_ in r]

	async def test_get_all_laundry_stations_by_region_manager(self, session: AsyncSession, ac: AsyncClient,
															  sync_session: Session):
		await users_funcs.change_user_data(self.laundry, session, region=RegionEnum.CENTRAL)
		await self.generate_relations(self.laundry, ac, amount=2)
		user_2, _ = await users_funcs.create_authorized_user(ac, sync_session, RoleEnum.LAUNDRY)
		await users_funcs.change_user_data(user_2.id, session, region=RegionEnum.SIBERIA)
		await self.generate_relations(user_2, ac, amount=1)
		user_3, _ = await users_funcs.create_authorized_user(ac, sync_session, RoleEnum.LAUNDRY)
		await users_funcs.change_user_data(user_3.id, session, region=RegionEnum.NORTHWEST)
		await self.generate_relations(user_3, ac, amount=1)

		await users_funcs.change_user_data(self.region_manager, session, region=RegionEnum.CENTRAL)
		self.region_manager.region = RegionEnum.CENTRAL

		url = "/v1/rel/laundry_stations/all"
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStationRelation(**r_) for r_ in r.json()]

		assert all(
			(rel.user.region == self.region_manager.region for rel in r)
		)
		assert len(r) == 2

	async def test_get_all_laundry_stations_order_by_name(self, sync_session: Session,
														  session: AsyncSession, ac: AsyncClient):
		await self.generate_relations(self.laundry, ac, amount=4,
									  generate_users=True, sync_session=sync_session)

		url = "/v1/rel/laundry_stations/all" + f"?order_by={LaundryStationSorting.NAME.value}"
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStations(**r) for r in r.json()]
		assert any(r)
		assert [r_.user.last_name for r_ in r] == sorted([r_.user.last_name for r_ in r])

		# ___

		url = url + "&desc=yes"
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStations(**r) for r in r.json()]
		assert any(r)
		assert [r_.user.last_name for r_ in r] == sorted([r_.user.last_name for r_ in r], reverse=True)

	async def test_get_all_laundry_stations_order_by_station_serial(self, session: AsyncSession,
																	ac: AsyncClient,
																	sync_session: Session):
		await self.generate_relations(self.laundry, ac, amount=4,
									  generate_users=True, sync_session=sync_session)
		url = ("/v1/rel/laundry_stations/all" +
			   f"?order_by={LaundryStationSorting.STATION_SERIAL.value}")
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStationRelation(**rel) for rel in r.json()]
		assert any(r)
		assert [r_.station.serial for r_ in r] == sorted([r_.station.serial for r_ in r], key=
														 lambda serial: int(serial.lstrip("0")))
		# ___
		url = url + "&desc=true"
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		r = [schema.LaundryStationRelation(**rel) for rel in r.json()]
		assert any(r)
		assert [r_.station.serial for r_ in r] == sorted([r_.station.serial for r_ in r], key=
														 lambda serial: int(serial.lstrip("0")),
														 reverse=True)

	async def test_get_all_laundry_stations_order_by_user_region(self, session: AsyncSession, ac: AsyncClient,
																 sync_session: Session):
		await self.generate_relations(self.laundry, ac, amount=4,
									  generate_users=True, sync_session=sync_session)
		url = ("/v1/rel/laundry_stations/all" +
			   f"?order_by={LaundryStationSorting.REGION.value}")
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStationRelation(**rel) for rel in r.json()]
		assert any(r)
		assert [r_.user.region for r_ in r] == sorted([r_.user.region for r_ in r],
													  key=lambda reg: reg.value)
		# ___
		url = url + "&desc=1"
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [schema.LaundryStationRelation(**rel) for rel in r.json()]
		assert any(r)
		assert [r_.user.region for r_ in r] == sorted([r_.user.region for r_ in r],
													  key=lambda reg: reg.value, reverse=True)

	async def test_get_all_laundry_stations_auto_tests(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/rel/laundry_stations/all"
		await url_auth_test(url, "get", self.sysadmin, ac, session)
		await url_auth_roles_test(url, "get", RoleEnum.REGION_MANAGER,
								  self.region_manager, session, ac)

	async def test_get_all_not_related_stations(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/rel/laundry_stations/not_related"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		r = [StationGeneralParams(**s) for s in r.json()]
		assert self.station.id in [s.id for s in r]

	async def test_get_all_not_related_stations_by_region(self, session: AsyncSession, ac: AsyncClient):
		await stations_funcs.change_station_params(self.station, session,
												   region=RegionEnum.SIBERIA)
		url = f"/v1/rel/laundry_stations/not_related?region={RegionEnum.SIBERIA.value}"

		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		r = [StationGeneralParams(**s) for s in r.json()]
		assert self.station.id in [s.id for s in r]

	async def test_get_all_not_related_stations_by_region_manager(self, session: AsyncSession,
																  ac: AsyncClient):
		await stations_funcs.change_station_params(self.station, session,
												   region=self.region_manager.region)
		url = f"/v1/rel/laundry_stations/not_related"
		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 200
		r = [StationGeneralParams(**s) for s in r.json()]
		assert self.station.id in [s.id for s in r]

	async def test_get_all_not_related_stations_by_region_manager_by_another_region(self,
																					session: AsyncSession,
																					ac: AsyncClient):
		url = f"/v1/rel/laundry_stations/not_related?region={RegionEnum.SIBERIA.value}"

		r = await ac.get(
			url,
			headers=self.region_manager.headers
		)
		assert r.status_code == 403

	async def test_get_all_not_related_stations_auto_tests(self, session: AsyncSession,
														   ac: AsyncClient):
		url = "/v1/rel/laundry_stations/not_related"

		await url_auth_test(url, "get", self.sysadmin, ac, session)
		await url_auth_roles_test(url, "get", RoleEnum.REGION_MANAGER,
								  self.region_manager, session, ac)