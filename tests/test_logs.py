import random
import uuid

from httpx import AsyncClient
import pytest

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.schemas import schemas_logs
from app.models.stations import StationControl
from app.models.logs import StationMaintenanceLog
from tests.additional import auth, users as users_funcs
from tests.additional.stations import create_random_station_logs, change_station_params, StationData
from app.static.enums import CreateLogByStationEnum, LogTypeEnum, StationStatusEnum
from app.utils.general import sa_object_to_dict


@pytest.mark.usefixtures("generate_users", "generate_default_station")
class TestLog:
	installer: users_funcs.UserData
	manager: users_funcs.UserData
	sysadmin: users_funcs.UserData
	laundry: users_funcs.UserData
	station: StationData
	"""
	Тестирование логирования.
	"""
	async def test_add_station_log(self, ac: AsyncClient, session: AsyncSession):
		"""
		Создание лога станцией.
		"""
		log = dict(content={"station_id": self.station.id, "code": 0, "content": "Qwerty"})
		response = await ac.post(
			"/api/v1/logs/" + CreateLogByStationEnum.ERRORS.value,
			headers=self.station.headers,
			json=log
		)
		assert response.status_code == 201
		error = response.json()
		assert error.get("station_id") == self.station.id and error.get("code") == 0 and error.get("content") == "Qwerty"

	async def test_add_station_log_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Некорректное содержание лога (тип лога указан один, а содержание - другого типа);
		- auto auth test.
		"""
		log = dict(content={"station_id": self.station.id, "code": 0, "content": "Qwerty"})
		incorrect_log_r = await ac.post(
			"/api/v1/logs/" + CreateLogByStationEnum.PROGRAMS_USING.value,
			headers=self.station.headers,
			json=log
		)
		assert incorrect_log_r.status_code == 422

		await auth.url_auth_stations_test(
			"api/v1/logs/" + CreateLogByStationEnum.ERRORS.value,
			"post", self.station, session, ac, log
		)

	async def test_get_station_logs(self, ac: AsyncClient, session: AsyncSession):
		"""
		Получение разных логов станции разными пользователями.
		"""
		await create_random_station_logs(self.station, self.installer, session)

		responses = []
		for log_type in (LogTypeEnum.ERRORS, LogTypeEnum.MAINTENANCE, LogTypeEnum.CHANGES,
						 LogTypeEnum.WASHING_AGENTS_USING, LogTypeEnum.PROGRAMS_USING):
			sysadmin_response = await ac.get(
				"/api/v1/logs/" + log_type.value + f"/{self.station.id}",
				headers=self.sysadmin.headers
			)
			manager_response = await ac.get(
				"/api/v1/logs/" + log_type.value + f"/{self.station.id}",
				headers=self.manager.headers
			)
			responses.extend((sysadmin_response, manager_response))

		for log_type in (LogTypeEnum.ERRORS, LogTypeEnum.WASHING_AGENTS_USING,
						 LogTypeEnum.PROGRAMS_USING):
			installer_response = await ac.get(
				"/api/v1/logs/" + log_type.value + f"/{self.station.id}",
				headers=self.installer.headers
			)
			responses.append(installer_response)

		laundry_response = await ac.get(
			"/api/v1/logs/" + LogTypeEnum.PROGRAMS_USING.value + f"/{self.station.id}",
			headers=self.laundry.headers
		)
		responses.append(laundry_response)

		assert all(
			(r.status_code == 200 and len(r.json()) for r in responses)
		)

	async def test_get_station_logs_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Пользователь не может получить логи, запрещенные к просмотру для его роли;
		- Станция должна существовать;
		- auto auth test.
		"""
		await create_random_station_logs(self.station, self.installer, session)

		for log_type in (LogTypeEnum.ERRORS, LogTypeEnum.CHANGES,
						 LogTypeEnum.MAINTENANCE, LogTypeEnum.WASHING_AGENTS_USING):
			forbidden_laundry_r = await ac.get(
				"/api/v1/logs/" + log_type.value + f"/{self.station.id}",
				headers=self.laundry.headers
			)
			assert forbidden_laundry_r.status_code == 403

		for log_type in (LogTypeEnum.CHANGES, LogTypeEnum.MAINTENANCE):
			forbidden_installer_r = await ac.get(
				"/api/v1/logs/" + log_type.value + f"/{self.station.id}",
				headers=self.installer.headers
			)
			assert forbidden_installer_r.status_code == 403

		non_existing_station_r = await ac.get(
			"/api/v1/logs/" + LogTypeEnum.ERRORS.value + f"/{uuid.uuid4()}",
			headers=self.sysadmin.headers
		)
		assert non_existing_station_r.status_code == 404

		await auth.url_auth_test(
			"/api/v1/logs/" + LogTypeEnum.CHANGES.value + f"/{self.station.id}",
			"get", self.sysadmin, ac, session
		)

	async def test_station_maintenance_log(self, ac: AsyncClient, session: AsyncSession):
		"""
		Обслуживание станции.
		Добавление лога о начале обслуживания + установка статуса "обслуживание".
		Дополнение лога (внесение времени окончания обслуживания) + снятие статуса "обслуживание".
		"""
		response = await ac.post(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f"/{self.station.id}",
			headers=self.installer.headers
		)
		station_control = await StationControl.get_relation_data(self.station.id, session)

		if isinstance(self.station.id, str):  # чтобы не ругался линтер
			inserted_log = await session.execute(
				select(StationMaintenanceLog).where(StationMaintenanceLog.station_id == self.station.id)
			)
		inserted_log_schema = schemas_logs.StationMaintenanceLog(
			**sa_object_to_dict(
				inserted_log.scalar()
			)
		)
		assert response.status_code == 201
		assert station_control.status == StationStatusEnum.MAINTENANCE
		assert inserted_log
		assert schemas_logs.StationMaintenanceLog(
			**response.json()
		) == inserted_log_schema

		end_maintenance_response = await ac.put(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f"/{self.station.id}",
			headers=self.installer.headers
		)

		assert end_maintenance_response.status_code == 200
		ending_result = schemas_logs.StationMaintenanceLog(
			**end_maintenance_response.json()
		)
		assert ending_result.started_at == inserted_log_schema.started_at
		assert ending_result.ended_at

	async def test_station_maintenance_log_post_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Не должно быть уже начатого обслуживания.;
		- Станция должна существовать (здесь автотест не сработает, статус-код 409, а не 404);
		- Должен быть статус "ожидание" для начала обслуживания (не должна работать);
		- user auth auto test.
		"""
		for _ in range(2):
			existing_maintenance_r = await ac.post(
				"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{self.station.id}',
				headers=self.installer.headers
			)
		assert existing_maintenance_r.status_code == 409
		if isinstance(self.station.id, uuid.UUID):  # чтоб не ругался линтер
			await session.execute(
				delete(StationMaintenanceLog).where(StationMaintenanceLog.station_id == self.station.id)
			)
		await session.commit()
		rand_washing_machine = random.choice(self.station.station_washing_machines)
		rand_washing_agent = random.choice(self.station.station_washing_agents)
		await change_station_params(self.station, session, status=StationStatusEnum.WORKING,
									washing_machine=rand_washing_machine, washing_agents=[rand_washing_agent])

		working_station_r = await ac.post(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{self.station.id}',
			headers=self.installer.headers
		)

		assert working_station_r.status_code == 409

		non_existing_station_r = await ac.post(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{uuid.uuid4()}',
			headers=self.installer.headers
		)

		assert non_existing_station_r.status_code == 404

		await auth.url_auth_test(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{self.station.id}',
			"post", self.installer, ac, session
		)

	async def test_station_maintenance_log_put_errors(self, ac: AsyncClient, session: AsyncSession):
		"""
		- Завершить можно лог, если начатый существует;
		- user auth auto test;
		- Станция должна существовать.
		"""
		non_existing_maintenance_r = await ac.put(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{self.station.id}',
			headers=self.installer.headers
		)
		assert non_existing_maintenance_r.status_code == 409

		non_existing_station = await ac.put(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{uuid.uuid4()}',
			headers=self.installer.headers
		)

		assert non_existing_station.status_code == 404

		await auth.url_auth_test(
			"/api/v1/logs/" + LogTypeEnum.MAINTENANCE.value + f'/{self.station.id}',
			"put", self.installer, ac, session
		)
