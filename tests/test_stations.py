import copy
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import services
from app.models import stations
from app.schemas import schemas_stations
from app.schemas import schemas_washing as washing
# from app.utils.general import read_location
from app.static.enums import RegionEnum, StationStatusEnum, RoleEnum, StationParamsEnum, \
	StationsSortingEnum
from tests.additional import auth, users as users_funcs
from tests.additional.stations import get_station_by_id, generate_station, StationData, change_station_params, \
	rand_serial, delete_all_stations
from tests.fills import stations as station_fills


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestStations:
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	region_manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: StationData

	async def test_create_station_with_default_params(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание станции без указания опциональных параметров.
		"""
		station_data = dict(station={
			"name": "Qwerty",
			"wifi_name": "qwerty",
			"wifi_password": "qwerty",
			# "address": "Санкт-Петербург",
			"region": RegionEnum.NORTHWEST.value,
			"serial": rand_serial()
		})
		response = await ac.post(
			"/v1/stations/",
			headers=self.sysadmin.headers,
			json=station_data
		)
		# real_location = await read_location("Санкт-Петербург")
		station_response = schemas_stations.Station(
			**response.json())  # Validation error может подняться, если что-то не так
		station_in_db = await get_station_by_id(station_response.id, session)

		assert station_in_db.dict() == station_in_db.dict()
		assert len(station_in_db.station_washing_agents) == services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT
		assert len(station_in_db.station_washing_machines) == services.DEFAULT_STATION_WASHING_MACHINES_AMOUNT
		assert not station_in_db.station_programs
		# assert station_in_db.location["latitude"] == real_location.latitude and \
		# 	   station_in_db.location["longitude"] == real_location.longitude
		assert station_in_db.is_active == services.DEFAULT_STATION_IS_ACTIVE
		assert station_in_db.is_protected == services.DEFAULT_STATION_IS_PROTECTED
		assert station_in_db.station_control.status == services.DEFAULT_STATION_STATUS
		assert not (station_in_db.is_active and not station_in_db.station_settings.teh_power), \
			"If station is active, teh must be powered on"
		assert not (not station_in_db.is_active and (station_in_db.station_settings.station_power is True or
													 station_in_db.station_control.status is not None
													 or station_in_db.station_settings.teh_power is True)), \
			"If station isn't active, station power and TEH power must be False and station status must be null"
		assert not (
			station_in_db.station_settings.station_power is True and station_in_db.station_control.status is None), \
			"If station is powered on, station status must be not null"
		assert not (station_in_db.station_control.status == StationStatusEnum.WORKING and not all(
			station_in_db.station_control.washing_machine and any(
				(station_in_db.station_control.program_step, station_in_db.station_control.washing_agents)
			)
		)), "If station status is working, washing machine must be defined, and one of params [program_step, washing_agents] " \
			"must be not null"
		assert station_in_db.name == station_data["station"]["name"]

	async def test_create_station_with_advanced_params(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание станции с ручным вводом параметров.
		"""
		params = station_fills.test_create_station_with_advanced_params

		response = await ac.post(
			"/v1/stations/",
			headers=self.sysadmin.headers,
			json=params
		)

		station_response = schemas_stations.Station(**response.json())
		station_in_db = await get_station_by_id(station_response.id, session)
		params = params["station"]
		params["region"] = RegionEnum.NORTHWEST  # или менять на строковый регион в полученных объектах

		assert station_response.dict() == station_in_db.dict()
		assert len(station_in_db.station_washing_agents) == len(params["washing_agents"])
		assert len(station_in_db.station_washing_machines) == len(params["washing_machines"])
		assert len(station_in_db.station_programs) == len(params["programs"])
		for k, v in params.items():
			if k in station_in_db.dict():
				assert station_in_db.dict()[k] == v
		for k, v in params["settings"].items():
			assert getattr(station_in_db.station_settings, k) == v

		for program in station_in_db.station_programs:
			defined_program = next(pg for pg in params["programs"] if pg["program_step"] == program.program_step)
			assert program.program_step == defined_program["program_step"]
			for washing_agent in program.washing_agents:
				for ag in defined_program["washing_agents"]:
					if isinstance(ag, int) and ag == washing_agent.agent_number:
						defined_washing_agent = next(agent for agent in params["washing_agents"] if
													 agent["agent_number"] == ag)
						defined_washing_agent = washing.WashingAgentCreateMixedInfo(**defined_washing_agent)
					elif isinstance(ag, dict) and ag["agent_number"] == washing_agent.agent_number:
						defined_washing_agent = washing.WashingAgentWithoutRollback(**ag)
				assert washing_agent.volume == defined_washing_agent.volume

		default_washing_agents_params = {
			"rollback": services.DEFAULT_WASHING_AGENTS_ROLLBACK,
			"volume": services.DEFAULT_WASHING_AGENTS_VOLUME
		}

		for washing_agent in station_in_db.station_washing_agents:
			defined_washing_agent = next(ag for ag in params["washing_agents"]
										 if ag["agent_number"] == washing_agent.agent_number)
			for param in default_washing_agents_params:
				default_param = default_washing_agents_params.get(param)
				if param in defined_washing_agent:
					assert getattr(washing_agent, param) == defined_washing_agent[param]
				else:
					assert getattr(washing_agent, param) == default_param

		default_washing_machines_params = {
			"track_length": services.DEFAULT_WASHING_MACHINES_TRACK_LENGTH,
			"is_active": services.DEFAULT_WASHING_MACHINES_IS_ACTIVE,
			"volume": services.DEFAULT_WASHING_MACHINES_VOLUME
		}
		for washing_machine in station_in_db.station_washing_machines:
			defined_washing_machine = next(machine for machine in params["washing_machines"]
										   if machine["machine_number"] == washing_machine.machine_number)
			for param in default_washing_machines_params:
				default_param = default_washing_machines_params.get(param)
				if param in defined_washing_machine:
					assert getattr(washing_machine, param) == defined_washing_machine[param]
				else:
					assert getattr(washing_machine, param) == default_param

		params["region"] = "Северо-западный"  # меняю обратно для след тестов

	async def test_create_station_with_comment(self, ac: AsyncClient, session: AsyncSession):
		"""
		Новый параметр, поэтому добавлю отдельный тест
		"""
		station_data = dict(station={
			"name": "qwerty",
			"wifi_name": "qwerty",
			"wifi_password": "qwerty",
			# "address": "Санкт-Петербург",
			"region": RegionEnum.NORTHWEST.value,
			"serial": rand_serial(),
			"comment": "it is test!"
		})
		response = await ac.post(
			"/v1/stations/",
			headers=self.sysadmin.headers,
			json=station_data
		)
		assert response.status_code == 201
		r = schemas_stations.Station(**response.json())
		assert r.comment == station_data["station"]["comment"]

		# ______________

		"""
		пустой коммент
		"""
		del station_data["station"]["comment"]
		station_data["station"]["serial"] = rand_serial()
		response = await ac.post(
			"/v1/stations/",
			headers=self.sysadmin.headers,
			json=station_data
		)
		assert response.status_code == 201
		assert response.json()["comment"] is None

	async def test_create_station_not_released(self, session: AsyncSession, ac: AsyncClient):
		"""
		Если станция не выпущена - установится пустая дата создания
		"""
		station_data = dict(station={
			"name": "qwerty",
			"wifi_name": "qwerty",
			"wifi_password": "qwerty",
			# "address": "Санкт-Петербург",
			"region": RegionEnum.NORTHWEST.value,
			"serial": rand_serial()
		})
		url = "/v1/stations/?released=false"

		r = await ac.post(
			url,
			headers=self.sysadmin.headers,
			json=station_data
		)

		assert r.status_code == 201
		r = schemas_stations.Station(**r.json())
		assert r.created_at is None

	async def test_release_station(self, session: AsyncSession, ac: AsyncClient):
		"""
		Если станция не выпущена, можно ее выпустить.
		"""
		station_data = dict(station={
			"name": "qwerty",
			"wifi_name": "qwerty",
			"wifi_password": "qwerty",
			# "address": "Санкт-Петербург",
			"region": RegionEnum.NORTHWEST.value,
			"serial": rand_serial()
		})
		url = "/v1/stations/?released=false"
		r = await ac.post(
			url,
			headers=self.sysadmin.headers,
			json=station_data
		)

		station = schemas_stations.Station(**r.json())

		release_r = await ac.patch(
			f"/v1/stations/release/{station.id}",
			headers=self.sysadmin.headers
		)
		assert release_r.status_code == 200
		station = schemas_stations.StationGeneralParams(**release_r.json())
		assert station.created_at

	async def test_not_released_station(self, session: AsyncSession, ac: AsyncClient):
		station_data = dict(station={
			"name": "qwerty",
			"wifi_name": "qwerty",
			"wifi_password": "qwerty",
			# "address": "Санкт-Петербург",
			"region": RegionEnum.NORTHWEST.value,
			"serial": rand_serial()
		})
		url = "/v1/stations/?released=false"
		r = await ac.post(
			url,
			headers=self.sysadmin.headers,
			json=station_data
		)
		station = schemas_stations.Station(**r.json())

		request_to_station_r = await ac.get(
			f"/v1/manage/station/{station.id}/{StationParamsEnum.GENERAL}",
			headers=self.sysadmin.headers
		)
		assert request_to_station_r.status_code == 403

		# ____
		station_headers = {"X-Station-Uuid": str(station.id)}

		request_from_station_r = await ac.get(
			"/v1/stations/me",
			headers=station_headers
		)
		assert request_from_station_r.status_code == 403

	async def test_release_station_not_sysadmin_role(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/stations/release/{self.station.id}"
		r = await ac.patch(
			url,
			headers=self.manager.headers
		)
		assert r.status_code == 403

	async def test_release_station_not_existing_station_id(self, session: AsyncSession, ac: AsyncClient):
		rand_uuid = uuid.uuid4()
		url = f"/v1/stations/release/{rand_uuid}"
		r = await ac.patch(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 404

	async def test_release_station_already_released(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/stations/release/{self.station.id}"
		r = await ac.patch(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 400

	async def test_create_station_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Нельзя передать в программу несуществующее стиральное средство;
		- Нельзя передать невалидные параметры станции (норм проверяются в schemas_stations);
		- roles auto test;
		- users auth auto test.
		"""
		params = copy.deepcopy(station_fills.test_create_station_with_advanced_params)
		if not isinstance(params["station"]["region"], str):
			params["station"]["region"] = params["station"][
				"region"].value  # не успевает поменяться обратно на строку (
		# _______________________________________________________________
		params["station"]["programs"].append(
			{
				"program_step": 13,
				"washing_agents": [
					{
						"agent_number": 5  # такого в списке нет
					}
				]
			}
		)

		non_existing_washing_agent_r = await ac.post(
			"/v1/stations/",
			headers=self.sysadmin.headers,
			json=params
		)

		assert non_existing_washing_agent_r.status_code == 422

		params["station"]["programs"].remove(params["station"]["programs"][-1])

		# ________________________________________________________

		params["station"]["settings"]["station_power"] = True
		params["station"]["is_active"] = False

		invalid_params_r = await ac.post(
			"/v1/stations/",
			headers=self.sysadmin.headers,
			json=params
		)

		assert invalid_params_r.status_code == 422

		# ________________________________________________________

		await auth.url_auth_roles_test(
			"/v1/stations/", "post",
			RoleEnum.SYSADMIN, self.sysadmin,
			session, ac, json=station_fills.test_create_station_with_advanced_params
		)
		await auth.url_auth_test(
			"/v1/stations/", "post", self.sysadmin, ac, session,
			json=station_fills.test_create_station_with_advanced_params
		)

	async def test_read_all_stations(self, ac: AsyncClient, session: AsyncSession,
									 sync_session: Session):
		"""
		Чтение списка станций.
		"""
		await delete_all_stations(session)  # не могу проследить, откуда появляется ошибка - где-то
		# из контроля станции удалил стиральную машину при рабочем состоянии
		stations_ = await StationData.generate_stations_list(ac, sync_session, self.sysadmin, session,
												 amount=10)
		# ____
		# sys, manager role
		for user in (self.sysadmin, self.manager):
			r = await ac.get(
				"/v1/stations/",
				headers=user.headers
			)
			assert r.status_code == 200
			r = [schemas_stations.StationInList(**s) for s in r.json()]
			assert len(r) >= len(stations_)

		# ____
		# region manager & installer role
		for user in (self.installer, self.region_manager):
			r = await ac.get(
				"/v1/stations/",
				headers=user.headers
			)
			assert r.status_code == 200
			r = [schemas_stations.StationInList(**s) for s in r.json()]
			assert len(r)
			assert all(
				(st.general.region == user.region for st in r)
			)

	async def test_read_all_stations_(self, session: AsyncSession, ac: AsyncClient,
									  sync_session: Session):
		"""
		проверить, что точно возвращаются параметры
		"""
		await self.station.generate_data_for_read_stations_list(
			session, ac, sync_session, ctrl=True, owner=True, logs=True
		)
		r = await ac.get(
			"/v1/stations/",
			headers=self.sysadmin.headers
		)
		r = [schemas_stations.StationInList(**s) for s in r.json()]
		station = next(s for s in r if str(s.general.id) == str(self.station.id))
		assert station.last_work_at
		assert station.last_maintenance_at
		assert station.owner
		assert station.control.status

	async def test_read_all_stations_with_ordering(self, ac: AsyncClient, session: AsyncSession,
												   sync_session: Session):
		headers = self.sysadmin.headers
		await StationData.generate_stations_list(ac, sync_session, self.sysadmin, session,
												 amount=10)
		sorting_keys = {StationsSortingEnum.OWNER: lambda st_: st_.owner.last_name,
						StationsSortingEnum.STATUS: lambda st_: st_.control.status.value,
						StationsSortingEnum.MAINTENANCE: lambda st_: st_.last_maintenance_at,
						StationsSortingEnum.LAST_WORK: lambda st_: st_.last_work_at,
						StationsSortingEnum.NAME: lambda st_: st_.general.name,
						StationsSortingEnum.REGION: lambda st_: st_.general.region.value}
		for order in list(StationsSortingEnum):
			for desc in (True, False):
				url = f"/v1/stations/?order_by={order.value}"
				sorting_params = {"key": sorting_keys[order]}
				if desc:
					url += "&desc=true"
					sorting_params["reverse"] = True
				r = await ac.get(url, headers=headers)
				assert r.status_code == 200
				r = [schemas_stations.StationInList(**s) for s in r.json()]
				nullable_objs = []
				for s in r:
					nullable_fields = {StationsSortingEnum.OWNER: s.owner,
									  StationsSortingEnum.STATUS: s.control.status,
									  StationsSortingEnum.MAINTENANCE: s.last_maintenance_at,
									  StationsSortingEnum.LAST_WORK: s.last_work_at}
					if order in nullable_fields:
						nullable_field = nullable_fields[order]
						if nullable_field is None:
							nullable_objs.append(s)
				for obj in nullable_objs:
					del r[r.index(obj)]
				assert r == sorted(r, **sorting_params)

	async def test_read_all_stations_by_not_permitted_user(self, ac: AsyncClient, session: AsyncSession):
		r = await ac.get(
			"/v1/stations/",
			headers=self.laundry.headers
		)
		assert r.status_code == 403

	async def test_read_all_stations_not_authenticated(self, ac: AsyncClient,
													   session: AsyncSession):
		await auth.url_auth_test(
			"/v1/stations/", "get", self.sysadmin,
			ac, session
		)

	async def test_read_stations_params(self, ac: AsyncClient, session: AsyncSession):
		"""
		Частичное чтение данных станции станцией.
		"""
		general_params_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.GENERAL.value,
			headers=self.station.headers
		)
		assert general_params_r.status_code == 200
		result = schemas_stations.StationGeneralParamsForStation(**general_params_r.json())
		for k, v in self.station.__dict__.items():
			if k in result.dict():
				assert getattr(result, k) == v

		# _____________________________________________________

		settings_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.SETTINGS.value,
			headers=self.station.headers
		)

		assert settings_r.status_code == 200
		settings_result = schemas_stations.StationSettings(**settings_r.json())

		# _____________________________________________________

		control_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.CONTROL.value,
			headers=self.station.headers
		)
		assert control_r.status_code == 200
		result = schemas_stations.StationControl(**control_r.json())

		assert settings_result.station_power is True and result.status == StationStatusEnum.AWAITING or \
			   settings_result.station_power is False and result.status is None

		# _____________________________________________________

		washing_agents_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.WASHING_AGENTS.value,
			headers=self.station.headers
		)
		assert washing_agents_r.status_code == 200
		washing_agents_result = washing_agents_r.json()

		for washing_agent in washing_agents_result:
			washing_agent = washing.WashingAgent(**washing_agent)  # Validation error
			assert services.MIN_WASHING_AGENTS_VOLUME <= washing_agent.volume <= services.MAX_WASHING_AGENTS_VOLUME
			assert washing_agent.rollback is services.DEFAULT_WASHING_AGENTS_ROLLBACK
		# _____________________________________________________

		programs_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.PROGRAMS.value,
			headers=self.station.headers
		)
		assert programs_r.status_code == 200

		result = programs_r.json()
		for program in result:
			program = schemas_stations.StationProgram(**program)
			assert program.program_number == program.program_step // 10
			for washing_agent in program.washing_agents:
				assert washing_agent.agent_number in [ag["agent_number"] for ag in washing_agents_result]
				assert services.MIN_STATION_WASHING_AGENTS_AMOUNT <= washing_agent.agent_number <= \
					   services.MAX_STATION_WASHING_AGENTS_AMOUNT

		# ____________________________________________________

		washing_machines_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.WASHING_MACHINES.value,
			headers=self.station.headers
		)

		assert washing_machines_r.status_code == 200
		result = washing_machines_r.json()

		for machine in result:
			machine = washing.WashingMachine(**machine)
			assert services.MIN_WASHING_MACHINE_VOLUME <= machine.volume <= services.MAX_WASHING_MACHINE_VOLUME
			assert services.MIN_STATION_WASHING_MACHINES_AMOUNT <= machine.machine_number \
				   <= services.MAX_STATION_WASHING_MACHINES_AMOUNT
			assert services.MIN_WASHING_MACHINE_TRACK_LENGTH <= machine.track_length <= \
				   services.MAX_WASHING_MACHINE_TRACK_LENGTH
			assert machine.is_active == services.DEFAULT_WASHING_MACHINES_IS_ACTIVE

	async def test_read_stations_params_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Отсутствие данных по станции;
		- stations auth auto test
		"""
		await session.execute(
			delete(stations.StationControl).where(stations.StationControl.station_id == self.station.id)
		)
		await session.commit()

		non_existing_data_r = await ac.get(
			"/v1/stations/me/" + StationParamsEnum.CONTROL.value,
			headers=self.station.headers
		)

		assert non_existing_data_r.status_code == 404

		station = await generate_station(ac, user=self.sysadmin)

		await auth.url_auth_stations_test(
			"/v1/stations/me/" + StationParamsEnum.GENERAL.value,
			"get", station, session, ac
		)

	async def test_read_stations_me(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение всех данных по станции станцией.
		"""
		response = await ac.get(
			"/v1/stations/me",
			headers=self.station.headers
		)
		assert response.status_code == 200
		schemas_stations.StationForStation(**response.json())  # Validation error

	async def test_read_station_me_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Отсутствие данных по станции;
		- stations auth auto test
		"""
		await auth.url_auth_stations_test(
			"/v1/stations/me", "get", self.station, session, ac
		)
		await change_station_params(self.station, session, status=StationStatusEnum.AWAITING)

		await session.execute(
			delete(stations.StationSettings).where(stations.StationSettings.station_id == self.station.id)
		)
		await session.commit()

		non_existing_data_r = await ac.get(
			"/v1/stations/me",
			headers=self.station.headers
		)

		assert non_existing_data_r.status_code == 404

