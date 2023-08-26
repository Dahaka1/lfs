import random
from math import floor

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import schemas_logs as schema
from app.static.enums import LogTypeEnum, ErrorTypeEnum, RoleEnum
from tests.additional import stations as stations_funcs, auth as auth_funcs, users as users_funcs
from tests.additional.logs import Log

log_codes = [
		1, 1.1, 1.2,
		2, 2.1, 2.2, 2.3,
		3, 3.1, 3.2, 3.3,
		4, 4.1, 4.2, 4.3, 4.4,
		5, 5.1,
		6, 6.1, 6.2, 6.3, 6.4, 6.5,
		9, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 9.13, 9.14, 9.15
	]


@pytest.mark.usefixtures("generate_default_station")
class TestLogsCreate:
	"""
	Создание логов станцией.
	Обновление данных станции в соответствии с логами.
	"""
	station: stations_funcs.StationData
	
	async def test_create_log(self, session: AsyncSession, ac: AsyncClient):
		for code in log_codes:
			log = Log(code, "content", LogTypeEnum.LOG, station=self.station)
			r = await ac.post(
				"/v1/logs/log",
				headers=self.station.headers,
				json=log.json()
			)
			assert r.status_code == 201
			created_log = schema.Log(**r.json())
			assert created_log.code == code
			assert created_log.event == log.event
			assert created_log.content == log.content
			assert created_log.station_id == self.station.id
			assert created_log.action == log.action
			log_in_db = await Log.find_in_db(created_log, session)
			assert log_in_db

			await self.station.refresh(session)
			await self.station.reset(session)
			await self.station.refresh(session)

	async def test_station_maintenance_start(self, session: AsyncSession, ac: AsyncClient):
		log = Log(9.16, "test", LogTypeEnum.LOG, station=self.station)
		await self.station.prepare_for_log(log, session)
		r = await ac.post(
			"/v1/logs/log",
			headers=self.station.headers,
			json=log.json()
		)
		assert r.status_code == 201
		await self.station.refresh(session)
		log.check_action(self.station)

	async def test_station_maintenance_end(self, session: AsyncSession, ac: AsyncClient):
		log = Log(9.17, "test", LogTypeEnum.LOG, station=self.station)
		await self.station.prepare_for_log(log, session)
		headers = self.station.headers
		headers["X-Station-Maintenance-End"] = "true"
		r = await ac.post(
			"/v1/logs/log",
			headers=headers,
			json=log.json()
		)
		assert r.status_code == 201
		await self.station.refresh(session)
		log.check_action(self.station)

	async def test_station_error_start(self, session: AsyncSession, ac: AsyncClient):
		error = Log(3.3, "text", LogTypeEnum.ERROR, scope=ErrorTypeEnum.PUBLIC, station=self.station)
		await self.station.prepare_for_log(error, session)
		r = await ac.post(
			"/v1/logs/error",
			headers=self.station.headers,
			json=error.json()
		)
		assert r.status_code == 201
		await self.station.refresh(session)
		error.check_action(self.station)

	async def test_station_error_end(self, session: AsyncSession, ac: AsyncClient):
		log = Log(9.18, "text", LogTypeEnum.LOG, station=self.station)
		await self.station.prepare_for_log(log, session)
		headers = self.station.headers
		headers["X-Station-Error-End"] = "true"
		r = await ac.post(
			"/v1/logs/log",
			headers=headers,
			json=log.json()
		)
		assert r.status_code == 201
		await self.station.refresh(session)
		log.check_action(self.station)

	async def test_create_error(self, session: AsyncSession, ac: AsyncClient):
		for code in log_codes:
			error = Log(code, "test", LogTypeEnum.ERROR, scope=ErrorTypeEnum.PUBLIC, station=self.station)
			r = await ac.post(
				"/v1/logs/error",
				headers=self.station.headers,
				json=error.json()
			)
			assert r.status_code == 201
			created_error = schema.Error(**r.json())
			assert created_error.scope == ErrorTypeEnum.PUBLIC
			error_in_db = await Log.find_in_db(created_error, session)
			assert error_in_db

			await self.station.refresh(session)
			if error.action:
				error.check_action(self.station)

			await self.station.reset(session)
			await self.station.refresh(session)

	async def test_log_actions(self, session: AsyncSession, ac: AsyncClient):
		async def check_all_logs_actions() -> None:
			for code in log_codes:
				log = Log(code, "test", LogTypeEnum.LOG, station=self.station)
				if log.action:
					await self.station.prepare_for_log(log, session)
					r = await ac.post(
						"/v1/logs/log",
						headers=self.station.headers,
						json=log.json()
					)
					assert r.status_code == 201
					await self.station.refresh(session)
					log.check_action(self.station)
					await self.station.reset(session)
					await self.station.refresh(session)
		await check_all_logs_actions()

		await stations_funcs.change_station_params(self.station, session, station_power=False)
		# даже если станция выключена, при логе о работе состояние должно измениться на "включена"
		await self.station.refresh(session)
		await check_all_logs_actions()

	async def test_station_create_log_auth(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/logs/log"
		log = next(l for l in [Log(log, "test", LogTypeEnum.LOG) for log in log_codes]
						if l.action is None)
		await auth_funcs.url_auth_stations_test(
			url, "post", self.station, session, ac, json=log.json()
		)

	async def test_station_create_error_log_auth(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/logs/error"
		error = next(e for e in [Log(er, "test", LogTypeEnum.ERROR, station=self.station,
									 scope=ErrorTypeEnum.PUBLIC) for er in log_codes]
				   if e.action is None)
		await auth_funcs.url_auth_stations_test(
			url, "post", self.station, session, ac, json=error.json()
		)

	async def test_station_create_log_end_error_with_non_error_status(self, session: AsyncSession, ac: AsyncClient):
		log = Log(9.18, "test", LogTypeEnum.LOG)
		await stations_funcs.generate_station_control(self.station, session)
		r = await ac.post(
			"/v1/logs/log",
			headers=self.station.headers,
			json=log.json()
		)
		assert r.status_code == 409

	async def test_station_manual_working_with_non_active_washing_machine(self, session: AsyncSession, ac: AsyncClient):
		log = Log(9.12, "test", LogTypeEnum.LOG, station=self.station)
		machine_number = log.data["washing_machine_number"]
		await stations_funcs.change_washing_machine_params(machine_number, self.station, session, is_active=False)
		r = await ac.post(
			"/v1/logs/log",
			headers=self.station.headers,
			json=log.json()
		)
		assert r.status_code == 409

	async def test_station_create_log_invalid_additional_data(self, session: AsyncSession, ac: AsyncClient):
		log = next(l for l in [Log(log, "test", LogTypeEnum.LOG, station=self.station)
							   for log in log_codes] if l.action)
		for field in log.data:
			k, v = field, log.data[field]
			del log.data[field]
			log.data[k + "qwerty"] = v
			break

		await self.station.prepare_for_log(log, session)

		r = await ac.post(
			"/v1/logs/log",
			headers=self.station.headers,
			json=log.json()
		)
		assert r.status_code == 422
		

@pytest.mark.usefixtures("generate_default_station", "generate_users")
class TestLogsGet:
	"""
	Получение логов станции пользователем.
	"""
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: stations_funcs.StationData

	async def test_get_station_logs(self, session: AsyncSession, ac: AsyncClient):
		await Log.generate(self.station, LogTypeEnum.LOG, log_codes, session, ac,
								amount=20)
		r = await ac.get(
			f"/v1/logs/log/station/{self.station.id}",
			headers=self.laundry.headers
		)
		assert r.status_code == 200
		logs = r.json()
		assert len(logs) == 21  # один лог - это создание станции =)

	async def test_get_station_logs_by_code(self, session: AsyncSession, ac: AsyncClient):
		logs = await Log.generate(self.station, LogTypeEnum.LOG, log_codes, session, ac,
						   amount=100)
		rand_codes = (l.code for l in random.choices(logs, k=10))
		for code in rand_codes:
			r = await ac.get(
				f"/v1/logs/log/station/{self.station.id}" + f"?code={code}",
				headers=self.laundry.headers
			)
			assert r.status_code == 200
			logs = (schema.Log(**l) for l in r.json())
			assert all(
				(log.code == code for log in logs)
			)

	async def test_get_station_logs_by_limit(self, session: AsyncSession, ac: AsyncClient):
		rand_amount = random.randint(2, 50)
		logs = await Log.generate(self.station, LogTypeEnum.LOG, log_codes, session, ac, amount=rand_amount)
		limit = floor(len(logs)/2)
		r = await ac.get(
			f"/v1/logs/log/station/{self.station.id}" + f"?limit={limit}",
			headers=self.laundry.headers
		)
		assert r.status_code == 200
		assert len(r.json()) == limit

	async def test_get_station_logs_get_station_by_id_errors(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/logs/log/station/{station_id}"
		await auth_funcs.url_get_station_by_id_test(url, "get", self.sysadmin,
													self.station, session, ac)

	async def test_get_station_logs_auth_errors(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/logs/log/station/{self.station.id}"
		await auth_funcs.url_auth_test(url, "get", self.laundry, ac, session)

	async def test_get_station_errors(self, session: AsyncSession, ac: AsyncClient):
		errors = await Log.generate(self.station, LogTypeEnum.ERROR, log_codes, session, ac, scope=ErrorTypeEnum.PUBLIC)
		r = await ac.get(
			f"/v1/logs/error/station/{self.station.id}",
			headers=self.manager.headers
		)
		assert r.status_code == 200
		created_errors = [schema.Error(**log) for log in r.json()]
		assert len(created_errors) == len(errors)
		assert all((e.scope == ErrorTypeEnum.PUBLIC for e in created_errors))

	async def test_get_station_errors_by_code_and_limit(self, session: AsyncSession, ac: AsyncClient):
		errors = await Log.generate(self.station, LogTypeEnum.ERROR, log_codes, session, ac, scope=ErrorTypeEnum.PUBLIC)
		rand_code = random.choice(errors).code
		limit = int(len(errors) / 2)
		r = await ac.get(
			f"/v1/logs/error/station/{self.station.id}" + f"?code={rand_code}&limit={limit}",
			headers=self.manager.headers
		)
		assert r.status_code == 200
		response_errors = [schema.Error(**err) for err in r.json()]
		assert all(
			(e.code == rand_code for e in response_errors)
		)
		assert len(response_errors) == len([er for er in errors if er.code == rand_code][:limit])

	async def test_get_station_errors_service(self, session: AsyncSession, ac: AsyncClient):
		errors = await Log.generate(self.station, LogTypeEnum.ERROR, log_codes,
									session, ac, scope=ErrorTypeEnum.SERVICE)
		r = await ac.get(
			f"/v1/logs/error/station/{self.station.id}" + f"?scope={ErrorTypeEnum.SERVICE.value}",
			headers=self.sysadmin.headers
		)
		assert r.status_code == 200
		assert len(r.json()) == len(errors)
		created_errors = [schema.Error(**e) for e in r.json()]
		assert all((err.scope == ErrorTypeEnum.SERVICE for err in created_errors))

	async def test_get_station_errors_service_without_permission(self, session: AsyncSession, ac: AsyncClient):
		r = await ac.get(
			f"/v1/logs/error/station/{self.station.id}" + f"?scope={ErrorTypeEnum.SERVICE}",
			headers=self.installer.headers
		)
		assert r.status_code == 403

	async def test_get_station_errors_roles_errors(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/logs/error/station/{self.station.id}"
		await auth_funcs.url_auth_roles_test(url, "get", RoleEnum.MANAGER, self.manager, session, ac)

	async def test_get_station_errors_auth_errors(self, session: AsyncSession, ac: AsyncClient):
		url = f"/v1/logs/error/station/{self.station.id}"
		await auth_funcs.url_auth_test(url, "get", self.manager, ac, session)

	async def test_get_station_errors_get_station_by_id_errors(self, session: AsyncSession, ac: AsyncClient):
		url = "/v1/logs/error/station/{station_id}"
		await auth_funcs.url_get_station_by_id_test(url, "get", self.sysadmin, self.station, session, ac)
