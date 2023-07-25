import copy

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from httpx import AsyncClient

import services
from app.static.enums import RegionEnum, StationStatusEnum, RoleEnum, StationParamsEnum
from app.schemas import schemas_stations
from app.schemas import schemas_washing as washing
from app.models import stations
from tests.additional.stations import get_station_by_id, generate_station, StationData
from tests.additional import auth, users as users_funcs
from tests.fills import stations as station_fills


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestStations:
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: StationData

	"""
	Тестирование создания станции.
	"""

	async def test_create_station_with_default_params(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание станции без указания опциональных параметров.
		"""
		station_data = dict(station={
			"wifi_name": "qwerty",
			"wifi_password": "qwerty",
			"address": "Санкт-Петербург",
			"region": RegionEnum.NORTHWEST.value
		})
		response = await ac.post(
			"/api/v1/stations/",
			headers=self.sysadmin.headers,
			cookies=self.sysadmin.cookies,
			json=station_data
		)
		station_response = schemas_stations.Station(
			**response.json())  # Validation error может подняться, если что-то не так
		station_in_db = await get_station_by_id(station_response.id, session)

		assert station_in_db.dict() == station_in_db.dict()
		assert len(station_in_db.station_washing_agents) == services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT
		assert len(station_in_db.station_washing_machines) == services.DEFAULT_STATION_WASHING_MACHINES_AMOUNT
		assert not station_in_db.station_programs
		assert station_in_db.location["latitude"] == 59.938732 and station_in_db.location["longitude"] == 30.316229
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

	async def test_create_station_with_advanced_params(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание станции с ручным вводом параметров.
		"""
		params = station_fills.test_create_station_with_advanced_params

		response = await ac.post(
			"/api/v1/stations/",
			headers=self.sysadmin.headers,
			cookies=self.sysadmin.cookies,
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
			"/api/v1/stations/",
			headers=self.sysadmin.headers,
			cookies=self.sysadmin.cookies,
			json=params
		)

		assert non_existing_washing_agent_r.status_code == 422

		params["station"]["programs"].remove(params["station"]["programs"][-1])

		# ________________________________________________________

		params["station"]["settings"]["station_power"] = True
		params["station"]["is_active"] = False

		invalid_params_r = await ac.post(
			"/api/v1/stations/",
			headers=self.sysadmin.headers,
			cookies=self.sysadmin.cookies,
			json=params
		)

		assert invalid_params_r.status_code == 422

		# ________________________________________________________

		await auth.url_auth_roles_test(
			"/api/v1/stations/", "post",
			RoleEnum.SYSADMIN, self.sysadmin,
			session, ac, json=station_fills.test_create_station_with_advanced_params
		)
		await auth.url_auth_test(
			"/api/v1/stations/", "post", self.sysadmin, ac, session,
			json=station_fills.test_create_station_with_advanced_params
		)

	async def test_read_all_stations(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение списка всех станций.
		"""
		stations_list = []
		for _ in range(5):
			station = await generate_station(ac, user=self.sysadmin)
			stations_list.append(station)

		response = await ac.get(
			"/api/v1/stations/",
			headers=self.sysadmin.headers,
			cookies=self.sysadmin.cookies
		)

		assert response.status_code == 200
		for station in response.json():
			assert not any(
				("wifi" in key for key in station)
			)
			station = schemas_stations.StationGeneralParams(**station)  # если что, будет Validation error
			station.id = str(station.id)
			station.region = station.region.value
			try:
				defined_station = next(st for st in stations_list if st.id == station.id)
			except StopIteration:  # там станции лежат уже с других тестов просто
				continue
			for k, v in station.dict().items():
				if k in defined_station.__dict__:
					assert getattr(defined_station, k) == v

	async def test_read_all_stations_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- users auth auto test;
		- roles auto test
		"""
		await auth.url_auth_roles_test(
			"/api/v1/stations/", "get",
			RoleEnum.SYSADMIN, self.sysadmin, session, ac
		)
		await auth.url_auth_test(
			"/api/v1/stations/", "get", self.sysadmin, ac, session
		)

	async def test_read_stations_params(self, ac: AsyncClient, session: AsyncSession):
		"""
		Частичное чтение данных станции станцией.
		"""
		params = station_fills.test_create_station_with_advanced_params

		general_params_r = await ac.get(
			"/api/v1/stations/me/" + StationParamsEnum.GENERAL.value,
			headers=self.station.headers
		)
		assert general_params_r.status_code == 200
		result = schemas_stations.StationGeneralParamsForStation(**general_params_r.json())
		for k, v in self.station.__dict__.items():
			if k in result.dict():
				assert getattr(result, k) == v

		# _____________________________________________________

		settings_r = await ac.get(
			"/api/v1/stations/me/" + StationParamsEnum.SETTINGS.value,
			headers=self.station.headers
		)

		assert settings_r.status_code == 200
		settings_result = schemas_stations.StationSettings(**settings_r.json())
		assert settings_result.station_power == params["station"]["settings"]["station_power"]
		assert settings_result.teh_power == params["station"]["settings"]["teh_power"]

		# _____________________________________________________

		control_r = await ac.get(
			"/api/v1/stations/me/" + StationParamsEnum.CONTROL.value,
			headers=self.station.headers
		)
		assert control_r.status_code == 200
		result = schemas_stations.StationControl(**control_r.json())

		assert settings_result.station_power is True and result.status == StationStatusEnum.AWAITING or \
			   settings_result.station_power is False and result.status is None

		# _____________________________________________________

		washing_agents_r = await ac.get(
			"/api/v1/stations/me/" + StationParamsEnum.WASHING_AGENTS.value,
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
			"/api/v1/stations/me/" + StationParamsEnum.PROGRAMS.value,
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
			"/api/v1/stations/me/" + StationParamsEnum.WASHING_MACHINES.value,
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
			"/api/v1/stations/me/" + StationParamsEnum.CONTROL.value,
			headers=self.station.headers
		)

		assert non_existing_data_r.status_code == 404

		station = await generate_station(ac, user=self.sysadmin)

		await auth.url_auth_stations_test(
			"/api/v1/stations/me/" + StationParamsEnum.GENERAL.value,
			"get", station, session, ac
		)

	async def test_read_stations_me(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение всех данных по станции станцией.
		"""
		response = await ac.get(
			"/api/v1/stations/me",
			headers=self.station.headers
		)
		assert response.status_code == 200
		schemas_stations.StationForStation(**response.json())  # Validation error

	async def test_read_station_me_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Отсутствие данных по станции;
		- stations auth auto test
		"""
		await session.execute(
			delete(stations.StationSettings).where(stations.StationSettings.station_id == self.station.id)
		)
		await session.commit()

		non_existing_data_r = await ac.get(
			"/api/v1/stations/me",
			headers=self.station.headers
		)
		assert non_existing_data_r.status_code == 404

		await auth.url_auth_stations_test(
			"/api/v1/stations/me", "get", self.station, session, ac
		)
