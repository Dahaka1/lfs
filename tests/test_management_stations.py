import copy
import datetime
import random

import pytest
import pytz
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import stations as stations_models
from app.schemas import schemas_stations as stations, schemas_washing as washing
from app.static.enums import StationParamsEnum, RoleEnum, RegionEnum, StationStatusEnum
from app.utils.general import decrypt_data
from tests.additional import auth, stations as stations_funcs, logs as logs_funcs, users as users_funcs, strings


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestManagement:
	"""
	Тестирование менеджмента станций
	"""
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: stations_funcs.StationData

	async def test_read_station_partial_by_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Тест по данным станции есть в test_stations (методы для станции и для юзеров работают аналогично);
		- Разрешенные роли пользователей.
		"""
		url = f"/v1/manage/station/{self.station.id}/"
		roles_responses = [
			(await ac.get(url + StationParamsEnum.GENERAL.value, headers=self.sysadmin.headers)),
			(await ac.get(url + StationParamsEnum.SETTINGS.value, headers=self.manager.headers)),
			(await ac.get(url + StationParamsEnum.CONTROL.value, headers=self.installer.headers))
		]

		assert all(
			(r.status_code == 200 for r in roles_responses)
		), [r for r in roles_responses]

		stations.StationGeneralParams(**roles_responses[0].json())
		stations.StationSettings(**roles_responses[1].json())
		stations.StationControl(**roles_responses[2].json())

		gen_r = roles_responses[0].json()
		assert all(
			(key not in gen_r for key in ("wifi_name", "wifi_password", "hashed_wifi_data"))
		)

	async def test_read_station_partial_by_user_by_serial_number(self, ac: AsyncClient, session: AsyncSession):
		url = f"/v1/manage/station/{self.station.serial}/general"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		stations.StationGeneralParams(**r.json())  # Validation error

	async def test_read_station_partial_by_user_by_invalid_serial_number(self, ac: AsyncClient, session: AsyncSession):
		url = f"/v1/manage/station/{self.station.serial}+qwe/general"
		r = await ac.get(
			url,
			headers=self.sysadmin.headers
		)
		assert r.status_code == 404

	async def test_read_station_partial_by_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Запрещенные роли пользователей;
		- users auth auto test;
		- station get by id auto test;
		- 404 есть в test_stations
		"""
		url = f"/v1/manage/station/{self.station.id}"
		responses = []
		datasets = (StationParamsEnum.GENERAL, StationParamsEnum.CONTROL, StationParamsEnum.SETTINGS,
						StationParamsEnum.WASHING_MACHINES, StationParamsEnum.WASHING_AGENTS)
		for dataset in datasets:
			url_ = url + dataset.value
			laundry_forbidden_r = await ac.get(url_, headers=self.laundry.headers)
			responses.append(laundry_forbidden_r)

		assert all(
			(r.status_code == 403 for r in responses)
		)

		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.GENERAL.value, "get", self.sysadmin,
			self.station,
			session, ac
		)
		# ___
		for dataset in datasets:
			url_ = url + f"/{dataset.value}"
			await auth.station_access_for_user_roles_test(
				url_, "get", self.sysadmin, self.station, ac, session
			)

	async def test_read_station_all_by_user(self, ac: AsyncClient, session: AsyncSession):
		"""
		Чтение всех данных станции пользователем.
		"""
		response = await ac.get(
			f"/v1/manage/station/{self.station.id}", headers=self.sysadmin.headers
		)
		assert response.status_code == 200
		result = response.json()
		assert "wifi_name" not in result
		assert "wifi_password" not in result
		assert "hashed_wifi_data" not in result
		stations.Station(**result)  # Validation error

	async def test_read_station_all_by_user_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- 404 есть в test_stations;
		- users auth auto test;
		- roles auto test,
		- station get by id auto test.
		"""
		url = "/v1/manage/station/"

		await auth.url_auth_test(
			url + str(self.station.id), "get", self.sysadmin, ac, session
		)
		await auth.station_access_for_user_roles_test(
			url + str(self.station.id), "get", self.sysadmin, self.station, ac, session
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}", "get", self.sysadmin, self.station,
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
		random_region = random.choice(list(RegionEnum))
		params = dict(
			is_protected=False,
			region=random_region.value, wifi_name=strings.generate_string(),
			wifi_password=strings.generate_string()
		)
		# location = await read_location(params.get("address"))

		response = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=dict(updating_params=params)
		)

		assert response.status_code == 200
		result = stations.StationGeneralParamsForStation(**response.json())
		await self.station.refresh(session)

		assert self.station.region == result.region == random_region
		assert self.station.is_protected is result.is_protected is params.get("is_protected")
		# assert self.station.location == result.location == {"latitude": location.latitude,
		# 													"longitude": location.longitude}
		assert result.wifi_name == params.get("wifi_name") and result.wifi_password == params.get("wifi_password")

		station_general = await stations_funcs.get_station_relation(self.station.id, stations_models.Station, session)
		wifi_data = decrypt_data(station_general["hashed_wifi_data"])
		assert wifi_data["login"] == params.get("wifi_name") and wifi_data["password"] == params.get("wifi_password")
		assert self.station.updated_at is not None

		await logs_funcs.check_station_log_exists(station_general["id"], session)

		# _____________________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)

		response = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=dict(updating_params={"is_active": False})
		)

		assert response.status_code == 200
		stations.StationGeneralParams(**response.json())  # Validation error
		assert "wifi_name" not in response.json() and "wifi_password" not in response.json()

		await self.station.refresh(session)

		assert self.station.is_active is False
		assert self.station.station_settings.station_power is False and self.station.station_settings.teh_power is False
		control = self.station.station_control
		assert all(
			(val is None for val in (control.status, control.washing_machine,
									 control.program_step))
		) and control.washing_agents == []
		assert control.updated_at is not None

		# _____________________________________________________________________________________

		"""обновление комментария по станции"""
		rand_comment = strings.generate_string()
		r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=dict(updating_params={"comment": rand_comment})
		)

		assert r.status_code == 200
		r = stations.StationGeneralParams(**r.json())
		assert r.comment == rand_comment
		await self.station.refresh(session)
		assert self.station.comment == rand_comment

	async def test_update_station_general_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Невалидные данные;
		- users auth auto test;
		- get station by id auto test;
		- roles auto test
		"""
		updating_data = dict(updating_params={
			"region": "Москва"
		})

		invalid_data_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			headers=self.sysadmin.headers,
			json=updating_data
		)
		assert invalid_data_r.status_code == 422

		await auth.url_auth_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value,
			"put", self.sysadmin, ac, session, json=updating_data
		)
		await auth.station_access_for_user_roles_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.GENERAL.value, "put",
			self.sysadmin, self.station, ac, session, json=dict(updating_params={"region": RegionEnum.NORTHWEST.value})
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.GENERAL.value,
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
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.AWAITING.value})
		)
		assert status_r.status_code == 200
		await self.station.refresh(session)

		ctrl = self.station.station_control
		assert ctrl.status == StationStatusEnum.AWAITING
		ctrl_response = stations.StationControl(**status_r.json())
		updated_at_timestamp = ctrl_response.updated_at.timestamp()
		ctrl_response.updated_at = datetime.datetime.fromtimestamp(updated_at_timestamp, tz=pytz.UTC)
		assert ctrl_response.dict() == ctrl.dict()

		assert all(
			(val is None for val in (ctrl.program_step, ctrl.washing_machine))
		) and ctrl.washing_agents == []
		assert ctrl.updated_at is not None

		# _____________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)

		await self.station.refresh(session)
		ctrl = copy.deepcopy(self.station.station_control)
		current_washing_machine = ctrl.washing_machine
		random_program = random.choice(self.station.station_programs)

		response = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"program_step": random_program.dict()})
		)
		assert response.status_code == 200

		await self.station.refresh(session)

		updated_ctrl = self.station.station_control
		assert updated_ctrl.washing_machine.machine_number == current_washing_machine.machine_number
		assert updated_ctrl.status == StationStatusEnum.WORKING
		response_control = stations.StationControl(**response.json())
		assert response_control.washing_machine.machine_number == current_washing_machine.machine_number
		assert updated_ctrl.program_step.dict() == random_program
		assert response_control.program_step.dict() == random_program

		# ____________________________________________________________________________

		agent = washing.WashingAgentWithoutRollback(**random.choice(self.station.station_washing_agents).dict())
		agent.volume = 40

		await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": [agent.dict()]})
		)
		await self.station.refresh(session)
		updated_ctrl = self.station.station_control
		assert updated_ctrl.program_step is None
		assert updated_ctrl.washing_machine == current_washing_machine
		assert updated_ctrl.washing_agents == [agent.dict()]

		# assert (await logs_funcs.get_user_last_changes_log(self.installer, session)) is not None

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
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.AWAITING.value,
									   "program_step": program_step.dict()})
		)
		assert status_invalid_data_r.status_code == 422

		# ________________________________________________________________________

		machine = copy.deepcopy(random.choice(self.station.station_washing_machines))
		machine.volume -= 1
		program = copy.deepcopy(random.choice(self.station.station_programs))
		washing_agent_number = random.choice(self.station.station_washing_agents).agent_number
		program.washing_agents = [{"agent_number": washing_agent_number, "volume": 17}]

		invalid_machine_data_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"washing_machine": machine.dict()})
		)
		invalid_program_data_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
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
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.WORKING.value,
									   "washing_machine": machine.dict(), "program_step": program.dict()})
		)
		assert powered_off_station_r.status_code == 409

		await stations_funcs.change_station_params(self.station, session, station_power=True)

		# ________________________________________________________________________

		await stations_funcs.change_washing_machine_params(
			machine.machine_number, self.station, session, is_active=False
		)
		machine.is_active = False

		inactive_machine_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			headers=self.installer.headers,
			json=dict(updating_params={"status": StationStatusEnum.WORKING.value,
									   "washing_machine": machine.dict(), "program_step": program.dict()})
		)
		assert inactive_machine_r.status_code == 409

		await stations_funcs.change_washing_machine_params(
			machine.machine_number, self.station, session, is_active=True
		)
		machine.is_active = True

		# ________________________________________________________________________

		testing_data = dict(updating_params={"status": StationStatusEnum.WORKING.value,
											 "washing_machine": machine.dict(), "program_step": program.dict()})

		await auth.url_auth_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			"put", self.sysadmin, ac, session, json=testing_data
		)
		await auth.station_access_for_user_roles_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.CONTROL.value,
			"put", self.sysadmin, self.station, ac, session, json=testing_data
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.CONTROL.value,
			"put", self.sysadmin, self.station, session, ac, json=testing_data
		)

	async def test_update_station_settings(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление настроек станции.

		Если передать station_power 'False', в текущем состоянии станции все автоматически обнуляется
		 (ТЭН не выключается при выключении станции).
		Если station_power был 'False' и стал 'True' - статус автоматически становится "ожидание".
		Выключение/включение ТЭН'а ни на что не влияет.
		"""
		await stations_funcs.generate_station_control(self.station, session)
		current_station_teh_power = self.station.station_settings.teh_power

		turn_off_response = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.SETTINGS.value,
			headers=self.installer.headers,
			json={"updating_params": {"station_power": False}}
		)

		assert turn_off_response.status_code == 200

		settings_response = stations.StationSettings(**turn_off_response.json())
		await self.station.refresh(session)
		updated_at_timestamp = settings_response.updated_at.timestamp()
		settings_response.updated_at = datetime.datetime.fromtimestamp(updated_at_timestamp, tz=pytz.UTC)
		assert settings_response.dict() == self.station.station_settings.dict()

		assert self.station.station_settings.station_power is False and self.station.station_settings.teh_power == \
			   current_station_teh_power

		ctrl = self.station.station_control

		assert all(
			(val is None for val in (ctrl.status, ctrl.program_step, ctrl.washing_machine))
		) and ctrl.washing_agents == []
		assert ctrl.updated_at is not None

		# assert (await logs_funcs.get_user_last_changes_log(self.installer, session)) is not None

		# ____________________________________________________________________________________

		turn_on_response = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.SETTINGS.value,
			headers=self.installer.headers,
			json={"updating_params": {"station_power": True}}
		)
		assert turn_on_response.status_code == 200

		ctrl = stations.StationControl(**(await stations_funcs.get_station_relation(self.station.id,
																					stations_models.StationControl,
																					session)))
		assert ctrl.status == StationStatusEnum.AWAITING
		assert all(
			(val is None for val in (ctrl.program_step, ctrl.washing_machine))
		) and ctrl.washing_agents == []

	async def test_update_station_settings_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Если передать station_power 'True' при неактивной станции, вернется ошибка;
		- users auth auto test;
		- roles auto test;
		- get station by id auto test
		"""
		await stations_funcs.change_station_params(self.station, session, is_active=False, station_power=False)
		test_json = dict(updating_params={"station_power": True})

		non_active_station_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.SETTINGS.value,
			headers=self.installer.headers,
			json=test_json
		)
		assert non_active_station_r.status_code == 409

		await stations_funcs.change_station_params(self.station, session, is_active=True)
		# __________________________________________________________________________________

		await auth.url_auth_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.SETTINGS.value,
			"put", self.installer, ac, session, json=test_json
		)
		await auth.station_access_for_user_roles_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.SETTINGS.value,
			"put", self.sysadmin, self.station, ac, session, json=test_json
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.SETTINGS.value,
			"put", self.sysadmin, self.station, session, ac, json=test_json
		)

	async def test_create_station_program(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание программ станции.
		- Как и при первоначальном создании станции, для программы можно определить уже существующие средства станции,
		 указав их номера, или передать кастомные программы;
		- Номер программы можно не указывать - по номеру этапа (шага) программы он определится автоматически.
		"""
		washing_agents = [ag.agent_number for ag in self.station.station_washing_agents]
		programs = [
			{"program_step": num, "washing_agents": washing_agents, "name": "Махра"} for num in range(31, 36)
		]
		response = await ac.post(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			headers=self.installer.headers,
			json=dict(programs=programs)
		)

		assert response.status_code == 201

		await self.station.refresh(session)

		for pg in response.json():
			assert pg in [p.dict() for p in self.station.station_programs]

			defined_program = next(p for p in programs if p["program_step"] == pg["program_step"])
			washing_agents_numbers = [ag["agent_number"] for ag in pg["washing_agents"]]
			for washing_agent_number in defined_program["washing_agents"]:
				assert washing_agent_number in washing_agents_numbers

		# _______________________________________________________________________________________

		programs = [
			{"program_step": num, "washing_agents": [{"agent_number": 2, "volume": 16},
													 {"agent_number": 3, "volume": 18}],
			 "program_number": 4, "name": "Махра"} for num in range(41, 46)
		]

		response = await ac.post(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			headers=self.installer.headers,
			json=dict(programs=programs)
		)

		assert response.status_code == 201

		await self.station.refresh(session)

		for pg in response.json():
			assert pg in [p.dict() for p in self.station.station_programs]

		for pg in self.station.station_programs:
			if pg.program_step in range(41, 46):
				assert pg.dict()["washing_agents"] == [{"agent_number": 2, "volume": 16},
													   {"agent_number": 3, "volume": 18}]

	async def test_create_station_program_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Создать программу с уже существующим номером шага (этапа) нельзя;
		- Номер переданного средства должен существовать (у станции);
		- users auth auto test;
		- roles auto test;
		- station get by id auto test+
		"""
		testing_data = dict(programs=[{"name": "Махра", "program_step": 51, "washing_agents": [1, 2]}])
		for _ in range(2):
			existing_program_r = await ac.post(
				f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
				headers=self.installer.headers,
				json=testing_data
			)
		assert existing_program_r.status_code == 409

		# _____________________________________________________________________________________

		await stations_funcs.delete_washing_services(
			object_number=1, station=self.station, session=session, object_type="agent"
		)

		non_existing_agent_response = await ac.post(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			headers=self.installer.headers,
			json=dict(programs=[{"name": "Махра", "program_step": 52, "washing_agents": [1, 2]}])
		)
		assert non_existing_agent_response.status_code == 404

		# ____________________________________________________________________________________

		await auth.url_auth_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			"post", self.sysadmin, ac, session, json=testing_data
		)
		testing_data["programs"][0]["program_step"] = 61
		testing_data["programs"][0]["washing_agents"] = [2]
		await auth.station_access_for_user_roles_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value,
			"post", self.sysadmin, self.station, ac, session, json=testing_data
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.PROGRAMS.value,
			"post", self.sysadmin, self.station, session, ac, json=testing_data
		)

	async def test_update_station_program(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обновление программы станции.
		- Как и в других методах, можно передать как кастомные стиральные средства, так и просто номера существующих
	 	 у станции средств;
	 	- Средства нужно передавать ЯВНЫМ списком (напр., если передать пустой список, то список средств программы
	 	 станет пустым) - нельзя обновить произвольно выбранные средства программы;
	 	- Если обновляется программа, по которой станция в данный момент работает, то в текущем состоянии программа
	     тоже обновится;
	    - Номер шага программы в новых параметрах можно не передавать (и так указывается в пути). Но можно передать и
		 даже изменить на новый - в этом случае выполнится проверка на занятость номера;
		- Можно не передавать номер программы, а только номер шага - номер программы определится автоматически.
		"""
		rand_program = random.choice(self.station.station_programs)
		rand_washing_agent = random.choice(self.station.station_washing_agents)

		washing_agent_object_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": [rand_washing_agent.dict()]})
		)
		assert washing_agent_object_r.status_code == 200
		response_program = stations.StationProgram(**washing_agent_object_r.json())
		await self.station.refresh(session)
		program_in_db = next(pg for pg in self.station.station_programs if pg.program_step == rand_program.program_step)
		response_program.updated_at = program_in_db.updated_at
		assert response_program.dict() == program_in_db.dict()

		washing_agent = next(ag for ag in self.station.station_washing_agents
														if ag.agent_number == rand_washing_agent.agent_number)

		assert response_program.washing_agents == [washing.WashingAgentWithoutRollback(**washing_agent.dict())]

		await logs_funcs.check_station_log_exists(self.station.id, session)

		# _____________________________________________________________________________________________

		rand_washing_agent = random.choice(self.station.station_washing_agents)
		rand_washing_agent.volume = 32

		washing_agent_object_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": [rand_washing_agent.dict()]})
		)

		assert washing_agent_object_r.status_code == 200
		response_program = stations.StationProgram(**washing_agent_object_r.json())
		assert response_program.updated_at is not None
		assert response_program.washing_agents == [washing.WashingAgentWithoutRollback(**rand_washing_agent.dict())]
		assert response_program.program_step == rand_program.program_step and response_program.program_number == \
			   rand_program.program_number

		# ___________________________________________________________________________________________

		washing_agents_empty_list_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": []})
		)

		assert washing_agents_empty_list_r.status_code == 200
		assert washing_agents_empty_list_r.json()["washing_agents"] == []

		# ___________________________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)

		await self.station.refresh(session)
		ctrl = self.station.station_control

		program_step_number = ctrl.program_step.program_step
		rand_washing_agent = random.choice(self.station.station_washing_agents)
		dict_comparing = rand_washing_agent.dict()
		dict_comparing["rollback"] = None

		response = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{program_step_number}",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": [rand_washing_agent.dict()]})
		)
		assert response.status_code == 200

		await self.station.refresh(session)
		assert self.station.station_control.program_step.washing_agents == \
			   [washing.WashingAgentWithoutRollback(**dict_comparing)]

		# ___________________________________________________________________________________________

		rand_program = random.choice(self.station.station_programs)

		change_program_number_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"program_step": 201,
									   "washing_agents": [ag.dict() for ag in rand_program.washing_agents]})
		)
		assert change_program_number_r.status_code == 200

		await self.station.refresh(session)

		program_in_db = next(pg for pg in self.station.station_programs if pg.program_step == 201)

		assert program_in_db.washing_agents == rand_program.washing_agents
		assert program_in_db.program_number == 20

		# ___________________________________________________________________________________________

		await stations_funcs.generate_station_control(self.station, session)
		await self.station.refresh(session)
		ctrl = self.station.station_control
		program_step = ctrl.program_step
		washing_agents_numbers = self.station.station_washing_agents[0].agent_number, \
			self.station.station_washing_agents[1].agent_number

		change_program_agents_by_numbers_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{program_step.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": list(washing_agents_numbers)})
		)

		assert change_program_agents_by_numbers_r.status_code == 200
		await self.station.refresh(session)

		ctrl = self.station.station_control
		assert all(
			(ag_num in [ag.agent_number for ag in ctrl.program_step.washing_agents]
			 for ag_num in washing_agents_numbers)
		)

	async def test_update_station_program_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Номер шага программы в новых параметрах можно не передавать (и так указывается в пути). Но можно передать, указав
	 	 новый нужный номер - в этом случае выполнится проверка на занятость номера;
	 	 - Программа должна существовать;
	 	 - Стиральное средство должно существовать;
	 	- users auth auto test;
	 	- get station by id auto test;
	 	- roles auto test
		"""
		rand_program, rand_program_ = random.choice(self.station.station_programs), \
			random.choice(self.station.station_programs)

		existing_program_step_number_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program_.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"program_step": rand_program.program_step})
		)

		assert existing_program_step_number_r.status_code == 409

		# ___________________________________________________________________________________________

		rand_washing_agent = random.choice(self.station.station_washing_agents)
		await stations_funcs.delete_washing_services(rand_washing_agent.agent_number, self.station,
													 session, "agent")
		await self.station.refresh(session)
		non_existing_washing_agent_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": [rand_washing_agent.dict()]})
		)
		assert non_existing_washing_agent_r.status_code == 404

		# ___________________________________________________________________________________________

		non_existing_program_step_r = await ac.put(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/2001",
			headers=self.installer.headers,
			json=dict(updating_params={"washing_agents": []})
		)

		assert non_existing_program_step_r.status_code == 404

		# ___________________________________________________________________________________________

		testing_json = dict(updating_params={"washing_agents": []})

		await auth.url_auth_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			"put", self.installer, ac, session, json=testing_json
		)
		await auth.station_access_for_user_roles_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			"put", self.sysadmin, self.station, ac, session, json=testing_json
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			"put", self.sysadmin, self.station, session, ac, json=testing_json
		)

	async def test_delete_program(self, ac: AsyncClient, session: AsyncSession):
		"""
		Удаление этапа программы станции
		"""
		rand_program = random.choice(self.station.station_programs)

		response = await ac.delete(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{rand_program.program_step}",
			headers=self.installer.headers,
			
		)
		assert response.status_code == 200
		await self.station.refresh(session)

		assert rand_program.dict() not in (pg.dict() for pg in self.station.station_programs)

	async def test_delete_program_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Нельзя удалить программу, если в данный момент станция работает по ней;
		- Программа должна существовать;
		- users auth auto test;
		- roles auto test;
		- get station by id auto test
		"""
		await stations_funcs.generate_station_control(self.station, session)
		await self.station.refresh(session)
		program_step = self.station.station_control.program_step

		program_in_control_r = await ac.delete(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{program_step.program_step}",
			headers=self.installer.headers,
			
		)
		assert program_in_control_r.status_code == 409

		# ___________________________________________________________________________________________

		non_existing_program_r = await ac.delete(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/2001",
			headers=self.installer.headers,
			
		)
		assert non_existing_program_r.status_code == 404

		# ___________________________________________________________________________________________

		await auth.url_auth_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{program_step.program_step}",
			"delete", self.installer, ac, session
		)
		await auth.station_access_for_user_roles_test(
			f"/v1/manage/station/{self.station.id}/" + StationParamsEnum.PROGRAMS.value + f"/{program_step.program_step}",
			"delete", self.sysadmin, self.station, ac, session
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}/" + StationParamsEnum.PROGRAMS.value + f"/{program_step.program_step}",
			"delete", self.sysadmin, self.station, session, ac
		)

	async def test_delete_station(self, ac: AsyncClient, session: AsyncSession):
		"""
		Удаление станции
		"""
		response = await ac.delete(
			f"/v1/manage/station/{self.station.id}",
			headers=self.sysadmin.headers
		)
		assert response.status_code == 200

		station_exists = await stations_funcs.get_station_by_id(self.station.id, session)
		assert not station_exists

	async def test_delete_station_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- users auth auto test;
		- get station by id auto test;
		- roles auto test
		"""
		url = f"/v1/manage/station/{self.station.id}"
		await auth.url_auth_test(
			url, "delete", self.sysadmin, ac, session
		)
		await auth.url_auth_roles_test(
			url, "delete", RoleEnum.SYSADMIN, self.sysadmin, session, ac
		)
		await auth.url_get_station_by_id_test(
			"/v1/manage/station/{station_id}", "delete", self.sysadmin, self.station, session, ac
		)
