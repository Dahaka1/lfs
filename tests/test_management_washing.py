import copy
import random

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

import services
from app.static.enums import RoleEnum, WashingServicesEnum
from tests.additional import auth, stations as stations_funcs, logs as logs_funcs, users as users_funcs
from app.schemas import schemas_washing as washing


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestManagementWashing:
	"""
	Тестирование управления стиральными объектами
	"""
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: stations_funcs.StationData

	async def test_create_station_washing_services(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание стирального объекта (можно создать, указав только номер объекта).
		"""
		washing_agent_number = random.randint(1, services.MAX_STATION_WASHING_AGENTS_AMOUNT)

		await stations_funcs.delete_washing_services(washing_agent_number, self.station, session, "agent")
		washing_agent_r = await ac.post(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value,
			headers=self.installer.headers,
			json=dict(creating_params={"agent_number": washing_agent_number})
		)
		assert washing_agent_r.status_code == 201

		await self.station.refresh(session)

		agent_in_db = next(ag for ag in self.station.station_washing_agents if ag.agent_number == washing_agent_number)

		assert washing.WashingAgent(**washing_agent_r.json()).dict() == agent_in_db.dict()

		assert agent_in_db.volume == services.DEFAULT_WASHING_AGENTS_VOLUME
		assert agent_in_db.rollback == services.DEFAULT_WASHING_AGENTS_ROLLBACK

		# ___________________________________________________________________________________________

		washing_machine_number = random.randint(1, services.MAX_STATION_WASHING_MACHINES_AMOUNT)

		await stations_funcs.delete_washing_services(washing_machine_number, self.station, session, "machine")

		machine_params = {"machine_number": washing_machine_number, "is_active": False, "volume": 30,
						  "track_length": 12.5}

		washing_machine_r = await ac.post(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value,
			headers=self.installer.headers,
			json=dict(creating_params=machine_params)
		)

		assert washing_machine_r.status_code == 201

		await self.station.refresh(session)

		machine_in_db = next(
			m for m in self.station.station_washing_machines if m.machine_number == washing_machine_number)

		assert machine_in_db.dict() == washing.WashingMachine(**washing_machine_r.json()).dict()

		for k, v in machine_params.items():
			assert getattr(machine_in_db, k) == v


	async def test_create_station_washing_services_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Нельзя создать объект с уже существующим номером;
		- users auth auto test;
		- get station by id auto test;
		- roles auto test
		"""
		rand_washing_agent = random.choice(self.station.station_washing_agents)
		testing_json = dict(creating_params={"agent_number": rand_washing_agent.agent_number})

		existing_object_r = await ac.post(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value,
			headers=self.installer.headers,
			json=testing_json
		)
		assert existing_object_r.status_code == 409

		# ___________________________________________________________________________________________

		await auth.url_auth_test(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value,
			"post", self.installer, ac, session, json=testing_json
		)
		await auth.url_auth_roles_test(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value,
			"post", RoleEnum.INSTALLER, self.installer, session, ac, json=testing_json
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + WashingServicesEnum.WASHING_AGENTS.value,
			"post", self.sysadmin, self.station, session, ac, json=testing_json
		)


	async def test_update_station_washing_services(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление стирального средства.
		"""
		rand_washing_agent = random.choice(self.station.station_washing_agents)

		response = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" +
			WashingServicesEnum.WASHING_AGENTS.value + f"/{rand_washing_agent.agent_number}",
			headers=self.installer.headers,
			json=dict(updating_params={"rollback": False, "volume": 14})
		)

		assert response.status_code == 200

		await self.station.refresh(session)

		agent_in_db = next(ag for ag in self.station.station_washing_agents if ag.agent_number ==
						   rand_washing_agent.agent_number)

		assert washing.WashingAgent(**response.json()).dict() == agent_in_db.dict()
		assert agent_in_db.volume == 14
		assert agent_in_db.rollback is False

		await logs_funcs.check_user_log_exists(self.installer, session)

		# ___________________________________________________________________________________________

		rand_washing_machine = random.choice(self.station.station_washing_machines)
		testing_data = dict(updating_params={"volume": 11, "track_length": 15.5})

		response = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/{WashingServicesEnum.WASHING_MACHINES.value}/"
			f"{rand_washing_machine.machine_number}",
			headers=self.installer.headers,
			json=testing_data
		)

		assert response.status_code == 200

		await self.station.refresh(session)

		machine_in_db = next(m for m in self.station.station_washing_machines if m.machine_number ==
							 rand_washing_machine.machine_number)

		assert machine_in_db.track_length == 15.5
		assert machine_in_db.volume == 11
		assert machine_in_db.dict() == washing.WashingMachine(**response.json()).dict()

		# ___________________________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)
		await self.station.refresh(session)
		machine = copy.deepcopy(self.station.station_control.washing_machine)

		using_machine_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/{WashingServicesEnum.WASHING_MACHINES.value}/"
			f"{machine.machine_number}",
			headers=self.installer.headers,
			json=testing_data
		)

		assert using_machine_r.status_code == 200
		await self.station.refresh(session)

		updated_machine = self.station.station_control.washing_machine

		assert updated_machine.machine_number == machine.machine_number
		assert updated_machine.volume == testing_data["updating_params"]["volume"]
		assert updated_machine.track_length == testing_data["updating_params"]["track_length"]

		# ___________________________________________________________________________________________

		await stations_funcs.delete_washing_services(updated_machine.machine_number, self.station,
													 session, "machine")

		await self.station.refresh(session)

		rand_washing_machine = random.choice(self.station.station_washing_machines)

		change_obj_number_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{rand_washing_machine.machine_number}",
			headers=self.installer.headers,
			json=dict(updating_params={"machine_number": updated_machine.machine_number})
		)

		assert change_obj_number_r.status_code == 200

		await self.station.refresh(session)

		next(m for m in self.station.station_washing_machines if m.machine_number == updated_machine.machine_number)


	# StopIteration error

	async def test_update_station_washing_services_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Нельзя обновить номер объекта на уже существующий;
		- Нельзя сделать неактивной стиральную машину, которая в данный момент в работе;
		- Объект должен существовать;
		- users auth auto test;
		- roles auto test;
		- get station by id auto test
		"""
		rand_washing_agent, rand_washing_agent_ = (random.choice(self.station.station_washing_agents) for _ in range(2))

		change_obj_number_to_existing_number_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value +
			f"/{rand_washing_agent_.agent_number}",
			headers=self.installer.headers,
			json=dict(updating_params={"agent_number": rand_washing_agent.agent_number})
		)

		assert change_obj_number_to_existing_number_r.status_code == 409

		# ___________________________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)
		await self.station.refresh(session)
		machine_number = self.station.station_control.washing_machine.machine_number

		using_machine_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{machine_number}",
			headers=self.installer.headers,
			json=dict(updating_params={"is_active": False})
		)

		assert using_machine_r.status_code == 409

		# ___________________________________________________________________________________________

		testing_json = dict(updating_params={"volume": 40})

		non_existing_obj_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value + "/50",
			headers=self.installer.headers,
			json=testing_json
		)
		assert non_existing_obj_r.status_code == 404

		# ___________________________________________________________________________________________

		await auth.url_auth_test(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{machine_number}",
			"put", self.sysadmin, ac, session, json=testing_json
		)

		await auth.url_auth_roles_test(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{machine_number}", "put",
			RoleEnum.INSTALLER, self.installer, session, ac, json=testing_json
		)

		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{machine_number}", "put", self.sysadmin, self.station, session, ac, json=testing_json
		)


	async def test_delete_station_washing_services(self, ac: AsyncClient, session: AsyncSession):
		"""
		Удаление стирального объекта
		"""
		rand_machine = random.choice(self.station.station_washing_machines)

		response = await ac.delete(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{rand_machine.machine_number}",
			headers=self.installer.headers
		)

		assert response.status_code == 200

		await self.station.refresh(session)

		assert rand_machine.machine_number not in [m.machine_number for m in self.station.station_washing_machines]

	async def test_delete_station_washing_services_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Если объект в данный момент используется станцией, удалить его нельзя;
		- users auth auto test;
		- roles auto test;
		- get station by id auto test
		"""
		await stations_funcs.generate_station_control(self.station, session)
		await self.station.refresh(session)

		machine_number = self.station.station_control.washing_machine.machine_number

		using_machine_r = await ac.delete(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_MACHINES.value +
			f"/{machine_number}",
			headers=self.installer.headers
		)
		assert using_machine_r.status_code == 409

		# ___________________________________________________________________________________________

		using_washing_agent_number = random.choice(self.station.station_control.program_step.washing_agents).agent_number

		using_agent_r = await ac.delete(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value +
			f"/{using_washing_agent_number}",
			headers=self.installer.headers
		)

		assert using_agent_r.status_code == 409

		# ___________________________________________________________________________________________

		agent_number = random.choice(self.station.station_control.program_step.washing_agents).agent_number
		if not agent_number:
			raise ValueError("Expected for object")

		using_agent_r = await ac.delete(
			f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value +
			f"/{agent_number}",
			headers=self.installer.headers
		)

		assert using_agent_r.status_code == 409

		# ___________________________________________________________________________________________

		testing_url = f"/api/v1/manage/station/{self.station.id}/" + WashingServicesEnum.WASHING_AGENTS.value + \
					  f"/{agent_number}"

		await auth.url_auth_test(
			testing_url, "delete", self.installer, ac, session
		)
		await auth.url_auth_roles_test(
			testing_url, "delete", RoleEnum.INSTALLER, self.installer, session, ac
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + WashingServicesEnum.WASHING_AGENTS.value +
			f"/{agent_number}", "delete", self.sysadmin,
			self.station, session, ac
		)
