import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from httpx import AsyncClient

import services
from app.static.enums import RegionEnum, StationStatusEnum, RoleEnum
from app.schemas.schemas_stations import Station
from app.schemas import schemas_washing as washing
from app.models import stations
from tests.additional.stations import get_station_by_id
from tests.additional import auth
from app.utils.general import sa_object_to_dict
from tests.fills import stations as station_fills


@pytest.mark.usefixtures("generate_users")
class TestStationCreate:
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
			json=station_data
		)
		station_response = Station(**response.json())  # Validation error может подняться, если что-то не так
		station_in_db = await get_station_by_id(station_response.id, session)

		assert station_in_db.dict() == station_in_db.dict()
		assert len(station_in_db.station_washing_agents) == services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT
		assert len(station_in_db.station_washing_machines) == services.DEFAULT_STATION_WASHING_MACHINES_AMOUNT
		assert not any(station_in_db.station_programs)
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
			json=params
		)

		station_response = Station(**response.json())
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
				try:
					defined_washing_agent = next(ag for ag in defined_program["washing_agents"]
												 if ag["agent_number"] == washing_agent.agent_number)
				except StopIteration:
					defined_washing_agent = washing.WashingAgentCreateMixedInfo(
						**next(ag for ag in params["washing_agents"] if isinstance(ag, int) and
							   ag == washing_agent.agent_number))
				assert washing_agent.agent_number == defined_washing_agent["agent_number"]
				assert washing_agent.volume == defined_washing_agent["volume"]

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

	async def test_create_station_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- roles auto test;
		- users auth auto test.
		"""
		await auth.url_auth_roles_test(
			"/api/v1/stations/", "post",
			RoleEnum.SYSADMIN, self.sysadmin,
			session, ac, json=station_fills.test_create_station_with_advanced_params
		)
		await auth.url_auth_test(
			"/api/v1/stations", "post", self.sysadmin, ac, session,
			json=station_fills.test_create_station_with_advanced_params
		)
