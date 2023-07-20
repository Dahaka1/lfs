import copy
import random

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from fastapi.encoders import jsonable_encoder

from app.static.enums import StationParamsEnum, RoleEnum, RegionEnum, StationStatusEnum
from tests.additional import auth, stations as stations_funcs, logs as logs_funcs
from app.schemas import schemas_stations as stations, schemas_washing as washing
from app.models import stations as stations_models
from app.utils.general import decrypt_data


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestManagement:
	"""
	Тестирование менеджмента станций.
	"""
	async def test_read_station_partial_by_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Тест по данным станции есть в test_stations (методы для станции и для юзеров работают аналогично);
		- Разрешенные роли пользователей.
		"""
		url = f"/api/v1/manage/station/{self.station.id}/"
		roles_responses = [
			(await ac.get(url + StationParamsEnum.GENERAL.value, headers=self.sysadmin.headers)),
			(await ac.get(url + StationParamsEnum.SETTINGS.value, headers=self.manager.headers)),
			(await ac.get(url + StationParamsEnum.CONTROL.value, headers=self.installer.headers))
		]

		assert all(
			(r.status_code == 200 for r in roles_responses)
		), [r for r in roles_responses]

		for r in roles_responses:
			stations.StationPartialForUser(**r.json())  # Validation error

	async def test_read_station_partial_by_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Запрещенные роли пользователей;
		- users auth auto test;
		- station get by id auto test;
		- 404 есть в test_stations
		"""
		url = f"/api/v1/manage/station/{self.station.id}"
		responses = []
		for user in (self.installer, self.manager, self.laundry):
			forbidden_r = await ac.get(url + StationParamsEnum.GENERAL.value, headers=user.headers)
			responses.append(forbidden_r)
		for dataset in (StationParamsEnum.GENERAL, StationParamsEnum.CONTROL, StationParamsEnum.SETTINGS,
						StationParamsEnum.WASHING_MACHINES, StationParamsEnum.WASHING_AGENTS):
			url_ = url + dataset.value
			laundry_forbidden_r = await ac.get(url_, headers=self.laundry.headers)
			responses.append(laundry_forbidden_r)

		assert all(
			(r.status_code == 403 for r in responses)
		)

		await auth.url_auth_test(
			url + StationParamsEnum.GENERAL.value, "get", self.sysadmin, ac, session
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + StationParamsEnum.GENERAL.value, "get", self.sysadmin, self.station,
			session, ac
		)

	async def test_read_station_all_by_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение всех данных станции пользователем.
		"""
		response = await ac.get(
			f"/api/v1/manage/station/{self.station.id}", headers=self.sysadmin.headers
		)
		assert response.status_code == 200

		stations.Station(**response.json())  # Validation error

	async def test_read_station_all_by_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- 404 есть в test_stations;
		- users auth auto test;
		- roles auto test,
		- station get by id auto test.
		"""
		url = "/api/v1/manage/station/"

		await auth.url_auth_test(
			url + self.station.id, "get", self.sysadmin, ac, session
		)
		await auth.url_auth_roles_test(
			url + self.station.id, "get", RoleEnum.SYSADMIN, self.sysadmin, session, ac
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}", "get", self.sysadmin, self.station,
			session, ac
		)

	async def test_update_station_general(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление основных параметров станции.
		- Если станция становится неактивной, то выключаются ее питание и ТЭНА, а также обнуляется все в
		 текущем состоянии станции;
		- Если wifi обновился, он вернется вместе с результатом, если не обновился - его не будет видно;
		- При успешном обновлении создается лог об изменениях.
		"""
		updated_data = dict(is_protected=False, address="Москва",
							region="Центральный", wifi_name="test",
							wifi_password="test")

		response = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=dict(updating_params=updated_data)
		)
		assert response.status_code == 200
		result = response.json()
		stations.StationGeneralParamsForStation(**result)  # Validation error
		station = await stations_funcs.get_station_by_id(self.station.id, session)
		station.id = str(station.id)
		del result["updated_at"]
		del result["created_at"]  # костылики
		station.region = station.region.value

		assert station.region == RegionEnum.CENTRAL.value
		assert station.is_protected is False
		assert station.location == {"latitude": 55.7504461, "longitude": 37.6174943}
		assert result["wifi_name"] == "test" and result["wifi_password"] == "test"

		station_general = await stations_funcs.get_station_relation(self.station.id, stations_models.Station, session)
		wifi_data = decrypt_data(station_general["hashed_wifi_data"])
		assert wifi_data["login"] == "test" and wifi_data["password"] == "test"

		for k, v in station.__dict__.items():
			if k in result:
				assert result[k] == v

		assert (await logs_funcs.get_user_last_changes_log(self.sysadmin, session)) is not None

		# _____________________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)

		response = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=dict(updating_params={"is_active": False})
		)

		assert response.status_code == 200
		stations.StationGeneralParams(**response.json())  # Validation error
		assert "wifi_name" not in response.json() and "wifi_password" not in response.json()

		station = await stations_funcs.get_station_by_id(self.station.id, session)

		assert station.is_active is False
		assert station.station_settings.station_power is False and station.station_settings.teh_power is False
		control = station.station_control
		assert all(
			(val is None for val in (control.status, control.washing_machine,
									 control.program_step))
		) and control.washing_agents == []
		assert control.updated_at is not None

	async def test_update_station_general_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Невалидные данные;
		- users auth auto test;
		- get station by id auto test;
		- roles auto test
		"""
		updating_data = dict(updating_params={
			"address": "qwerty_qwerty",
			"region": "Москва"
		})

		invalid_data_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=updating_data
		)
		assert invalid_data_r.status_code == 422

		await auth.url_auth_test(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			"put", self.sysadmin, ac, session, json=updating_data
		)
		await auth.url_auth_roles_test(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value, "put",
			RoleEnum.SYSADMIN, self.sysadmin, session, ac, json=updating_data
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + StationParamsEnum.GENERAL.value,
			"put", self.sysadmin, self.station, session, ac, json=updating_data
		)

	async def test_update_station_control(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление текущего состояния станции.
		- Чтобы изменить статус на "ожидание", кроме него ничего не нужно передавать (иначе вернется ошибка).
		 После смены статуса на "ожидание" остальные параметры становятся нулевыми;
		- При обновлении параметров БЕЗ изменения номера машины, машину указывать НЕ НУЖНО;
		- Если при статусе "работа" происходят какие-либо изменения, можно его тоже не передавать - останется
	 	 "работа";
	 	- Если статус "работа" - должно быть указано что-то одно из: шаг программы, стиральные средства;
	 	- Стиральная машина при работе указана всегда;
	 	- Стиральное средство можно передать с кастомными параметрами - лишь бы номер его был среди номеров средств станции.
		- А вот программу и машину нужно передавать со всеми существующими в БД параметрами, иначе будет ошибка.
		"""
		await stations_funcs.generate_station_control(self.station, session)
		status_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.AWAITING.value})
		)
		assert status_r.status_code == 200

		station = await stations_funcs.get_station_by_id(self.station.id, session)
		ctrl = station.station_control
		assert ctrl.status == StationStatusEnum.AWAITING

		ctrl.status = ctrl.status.value
		ctrl.updated_at = ctrl.updated_at.isoformat()  # чтобы сравнить с ответом серва

		assert status_r.json() == ctrl

		assert all(
			(val is None for val in (ctrl.program_step, ctrl.washing_machine))
		) and ctrl.washing_agents == []
		assert ctrl.updated_at is not None

		# _____________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)

		ctrl = await stations_funcs.get_station_relation(self.station.id, stations_models.StationControl, session)
		programs = await stations_funcs.get_station_relation(self.station.id, stations_models.StationProgram, session,
															 many=True)
		current_washing_machine = ctrl["washing_machine"]
		random_program = jsonable_encoder(stations.StationProgram(**random.choice(programs)))

		response = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"program_step": random_program})
		)
		assert response.status_code == 200

		updated_ctrl = await stations_funcs.get_station_relation(self.station.id, stations_models.StationControl, session)
		assert updated_ctrl["washing_machine"]["machine_number"] == current_washing_machine["machine_number"]
		assert updated_ctrl["status"] == StationStatusEnum.WORKING
		assert response.json()["washing_machine"]["machine_number"] == current_washing_machine["machine_number"]
		assert updated_ctrl["program_step"] == random_program
		assert response.json()["program_step"] == random_program

		# ____________________________________________________________________________

		agent = washing.WashingAgentWithoutRollback(**random.choice(station.station_washing_agents).dict())
		agent.volume = 40

		await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": [agent.dict()]})
		)

		updated_ctrl = await stations_funcs.get_station_relation(self.station.id, stations_models.StationControl, session)

		assert updated_ctrl["program_step"] is None
		assert updated_ctrl["washing_machine"] == current_washing_machine
		assert updated_ctrl["washing_agents"] == [agent.dict()]

		assert (await logs_funcs.get_user_last_changes_log(self.installer, session)) is not None

	async def test_update_station_control_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Чтобы изменить статус на "ожидание", кроме него ничего не нужно передавать (иначе вернется ошибка);
		- Программу и машину нужно передавать со всеми существующими (не кастомными) в БД параметрами, иначе будет ошибка;
		- Если передать статус не нулевой, но при этом в настройках стация выключена - вернется ошибка;
		- Если переданная стиральная машина неактивна - вернется ошибка;
		- users auth auto test;
		- roles auto test;
		- get station by id auto test
		"""
		await stations_funcs.generate_station_control(self.station, session)
		program_step = random.choice(self.station.station_programs)
		status_invalid_data_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.AWAITING.value,
									   "program_step": program_step})
		)
		assert status_invalid_data_r.status_code == 422

		# ________________________________________________________________________

		machine = washing.WashingMachine(**copy.deepcopy(self.station.station_washing_machines[1]))
		machine.volume = 7
		program = stations.StationProgram(**copy.deepcopy(self.station.station_programs[1]))
		washing_agent = washing.WashingAgent(**self.station.station_washing_agents[1])
		program.washing_agents = [{"agent_number": washing_agent.agent_number,"volume": 17}]

		invalid_machine_data_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"washing_machine": machine.dict()})
		)
		invalid_program_data_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"program_step": program.dict()})
		)

		assert invalid_machine_data_r.status_code == 409
		assert invalid_program_data_r.status_code == 409

		# ________________________________________________________________________

		await stations_funcs.change_station_params(self.station, session, station_power=False)

		machine = random.choice(self.station.station_washing_machines)
		program = random.choice(self.station.station_programs)

		powered_off_station_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.WORKING.value,
									   "washing_machine": machine, "program_step": program})
		)
		assert powered_off_station_r.status_code == 409

		await stations_funcs.change_station_params(self.station, session, station_power=True)

		# ________________________________________________________________________

		machine = washing.WashingMachine(**machine)
		await stations_funcs.change_washing_machine_params(
			machine.machine_number, self.station, session, is_active=False
		)
		machine.is_active = False

		inactive_machine_r = await ac.put(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.WORKING.value,
									   "washing_machine": machine.dict(), "program_step": program})
		)
		assert inactive_machine_r.status_code == 409

		await stations_funcs.change_washing_machine_params(
			machine.machine_number, self.station, session, is_active=True
		)
		machine.is_active = True

		# ________________________________________________________________________

		testing_data = dict(updating_params={"status": StationStatusEnum.WORKING.value,
						 "washing_machine": machine.dict(), "program_step": program})

		await auth.url_auth_test(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			"put", self.sysadmin, ac, session, json=testing_data
		)
		await auth.url_auth_roles_test(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			"put", RoleEnum.INSTALLER, self.installer, session, ac, json=testing_data
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + StationParamsEnum.CONTROL.value,
			"put", self.sysadmin, self.station, session, ac, json=testing_data
		)

	async def test_create_station_program(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание программ станции.
		- Как и при первоначальном создании станции, для программы можно определить уже существующие средства станции,
		 указав их номера, или передать кастомные программы;
		- Номер программы можно не указывать - по номеру этапа (шага) программы он определится автоматически.
		"""
		washing_agents = [ag["agent_number"] for ag in self.station.station_washing_agents]
		programs = [
			{"program_step": num, "washing_agents": washing_agents} for num in range(31, 36)
		]
		response = await ac.post(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			headers=self.installer.headers,
			json=dict(programs=programs)
		)

		assert response.status_code == 201

		programs_in_db = await stations_funcs.get_station_relation(
			self.station.id, stations_models.StationProgram, session, many=True
		)

		for pg in response.json():
			assert pg in programs_in_db

		for pg in response.json():
			defined_program = next(p for p in programs if p["program_step"] == pg["program_step"])
			washing_agents_numbers = [ag["agent_number"] for ag in pg["washing_agents"]]
			for washing_agent_number in defined_program["washing_agents"]:
				assert washing_agent_number in washing_agents_numbers

		# _______________________________________________________________________________________

		programs = [
			{"program_step": num, "washing_agents": [{"agent_number": 2, "volume": 16},
													 {"agent_number": 3, "volume": 18}],
			 "program_number": 4} for num in range(41, 46)
		]

		response = await ac.post(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			headers=self.installer.headers,
			json=dict(programs=programs)
		)

		assert response.status_code == 201

		programs_in_db = await stations_funcs.get_station_relation(
			self.station.id, stations_models.StationProgram, session, many=True
		)

		for pg in response.json():

			assert pg in programs_in_db

		for pg in programs_in_db:
			if pg["program_step"] in range(41, 46):
				assert pg["washing_agents"] == [{"agent_number": 2, "volume": 16},
													 {"agent_number": 3, "volume": 18}]

	async def test_create_station_program_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Создать программу с уже существующим номером шага (этапа) нельзя;
		- Номер переданного средства должен существовать (у станции);
		- users auth auto test;
		- roles auto test;
		- station get by id auto test+
		"""
		testing_data = dict(programs=[{"program_step": 51, "washing_agents": [1, 2]}])
		for _ in range(2):
			existing_program_r = await ac.post(
				f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
				headers=self.installer.headers,
				json=testing_data
			)
		assert existing_program_r.status_code == 409

		# _____________________________________________________________________________________

		await stations_funcs.delete_washing_services(
			object_number=1, station=self.station, session=session, object_type="agent"
		)

		non_existing_agent_response = await ac.post(
				f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
				headers=self.installer.headers,
				json=dict(programs=[{"program_step": 52, "washing_agents": [1, 2]}])
			)
		assert non_existing_agent_response.status_code == 404

		# ____________________________________________________________________________________

		await auth.url_auth_test(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			"post", self.sysadmin, ac, session, json=testing_data
		)
		await auth.url_auth_roles_test(
			f"/api/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			"post", RoleEnum.INSTALLER, self.installer, session, ac, json=testing_data
		)
		await auth.url_get_station_by_id_test(
			"/api/v1/manage/station/{station_id}/" + StationParamsEnum.PROGRAMS.value,
			"post", self.sysadmin, self.station, session, ac, json=testing_data
		)

