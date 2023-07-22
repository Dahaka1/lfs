import datetime
import random
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

import services
from app.static.enums import RoleEnum, RegionEnum, StationStatusEnum
from app.schemas import schemas_stations, schemas_washing
from .users import create_authorized_user, UserData
from app.models.stations import StationControl, Station, StationSettings, StationProgram
from app.models.washing import WashingAgent, WashingMachine
from app.models import logs
from app.utils.general import sa_object_to_dict, sa_objects_dicts_list
from app.database import Base


@dataclass
class StationData:
	"""
	Класс станции с парамерами для тестов.
	"""
	id: uuid.UUID
	is_active: bool
	is_protected: bool
	location: dict
	region: RegionEnum
	station_programs: list[schemas_stations.StationProgram]
	station_washing_machines: list[schemas_washing.WashingMachine]
	station_washing_agents: list[schemas_washing.WashingAgent]
	station_control: schemas_stations.StationControl
	station_settings: schemas_stations.StationSettings
	created_at: datetime.datetime
	updated_at: Optional[datetime.datetime]
	headers: dict[str, str]

	# пришлось сделать дикты вторым вариантом атрибутов, иначе везде ошибка линтера =(
	# а pydantic модели почему-то вообще не работают внутри этого класса

	async def refresh(self, session: AsyncSession):
		"""
		Обновить все данные станции
		"""
		updated_data = await get_station_by_id(self.id, session)
		for k in updated_data.dict():
			if k in self.__dict__:
				setattr(self, k, getattr(updated_data, k))


async def generate_station(
	ac: AsyncClient,
	sync_session: Session = None,
	user: Any = None,
	**kwargs
) -> StationData:
	"""
	Генерирует станцию.
	Работает через запрос к АПИ (иначе оч долго заполнять вручную таблицы).
	Поэтому поаккуратней с этим =)
	"""
	if kwargs:
		kwargs = kwargs["station"]

	if not user:
		if not sync_session:
			raise Exception
		user, user_schema = await create_authorized_user(ac, sync_session, RoleEnum.SYSADMIN, confirm_email=True)
	station_data = dict(station={
		"is_active": kwargs.get("is_active") or True,
		"is_protected": kwargs.get("is_protected") or False,
		"wifi_name": "qwerty",
		"wifi_password": "qwerty",
		"address": "Санкт-Петербург",
		"region": "Северо-западный"
	})

	for k, v in kwargs.items():
		if v is not None:
			station_data["station"][k] = v

	if not kwargs.get("programs"):
		station_data["station"]["programs"] = generate_station_programs()

	response = await ac.post(
		"/api/v1/stations/",
		headers=user.headers,
		json=station_data
	)

	if response.status_code == 201:
		station = schemas_stations.Station(**response.json())
		headers = {"X-Station-Uuid": str(station.id)}
		attrs = {attr: getattr(station, attr) for attr in station.dict()}
		return StationData(
			**attrs, headers=headers
		)
	else:
		raise AssertionError(str(response))


async def change_station_params(station: StationData, session: AsyncSession, **kwargs) -> None:
	"""
	Изменение параметров станции.
	"""
	for k, v in kwargs.items():
		match k:
			case "is_active":
				query = update(Station).where(Station.id == station.id).values(is_active=v)
			case "status" | "washing_machine" | "washing_agents":
				query = update(StationControl).where(StationControl.station_id == station.id).values(
					**{k: v}
				)
			case "station_power" | "teh_power":
				query = update(StationSettings).where(StationSettings.station_id == station.id).values(
					**{k: v}
				)
			case _:  # надо тут определять аргументы явно
				raise AttributeError
		await session.execute(query)
	await session.commit()


async def create_random_station_logs(station: StationData,
										user: UserData,
									 session: AsyncSession,
									 amount: int = 3) -> None:
	"""
	Создать рандомные логи для тестов.
	"""
	rand_washing_machine = random.choice(station.station_washing_machines)
	rand_washing_agent = random.choice(station.station_washing_agents)
	rand_program = random.choice(station.station_programs)

	error = logs.ErrorsLog(station_id=station.id, code=0, content="qwerty")
	washing_agents_using = logs.WashingAgentsUsingLog(station_id=station.id,
													  washing_machine=rand_washing_machine.dict(),
													  washing_agent=rand_washing_agent.dict())
	change = logs.ChangesLog(station_id=station.id, user_id=user.id, content="qwerty")
	program_using = logs.StationProgramsLog(station_id=station.id, program_step=rand_program.dict())
	maintenance = logs.StationMaintenanceLog(station_id=station.id, user_id=user.id,
											 started_at=datetime.datetime.now() - datetime.timedelta(days=1),
											 ended_at=datetime.datetime.now())

	for log in (error, washing_agents_using, change, program_using, maintenance):
		for _ in range(amount):
			session.add(log)
			await session.commit()


def generate_station_programs() -> list[dict[str, Any]]:
	"""
	Сгенерировать программы для станции.
	"""
	programs = []
	program_step = 11
	for _ in range(4):
		washing_agents = [random.randint(1, services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT)]
		program = schemas_stations.StationProgramCreate(
			program_step=program_step, washing_agents=washing_agents
		)
		programs.append(program)
		program_step += 1
	return [pg.dict() for pg in programs]


async def get_station_relation(station_id: uuid.UUID, cls: Base, session: AsyncSession, many: bool = False) -> \
	Optional[dict[str, Any] | list[dict[str, Any]]]:
	if not many:
		try:
			searched_id = cls.station_id
		except AttributeError:
			searched_id = cls.id
		result = (await session.execute(
			select(cls).where(searched_id == station_id)
		)).scalar()
		if result:
			return sa_object_to_dict(result)
		return

	result = (await session.execute(
			select(cls).where(cls.station_id == station_id)
		)).scalars().all()

	if any(result):
		return sa_objects_dicts_list(result)


async def get_station_by_id(station_id: uuid.UUID, session: AsyncSession) -> Optional[schemas_stations.Station]:
	"""
	Собрать данные по станции в БД.
	"""
	station_general = await get_station_relation(station_id, Station, session)
	if station_general:
		station_washing_machines = await get_station_relation(station_id, WashingMachine, session, many=True)
		station_washing_agents = await get_station_relation(station_id, WashingAgent, session, many=True)
		station_settings = await get_station_relation(station_id, StationSettings, session)
		station_control = await get_station_relation(station_id, StationControl, session)
		station_programs = await get_station_relation(station_id, StationProgram, session, many=True)

		return schemas_stations.Station(
			**station_general,
			station_programs=station_programs,
			station_washing_agents=station_washing_agents,
			station_washing_machines=station_washing_machines,
			station_settings=station_settings,
			station_control=station_control
		)


async def generate_station_control(station: StationData, session: AsyncSession) -> None:
	"""
	Установить случайное текущее состояние станции (рабочее).
	"""
	if not station.is_active or station.station_settings.station_power is False \
		or station.station_settings.teh_power is False:
		raise ValueError

	program = random.choice(station.station_programs)
	machine = random.choice(station.station_washing_machines)
	query = update(StationControl).where(StationControl.station_id == station.id).values(
			program_step=program.dict(), washing_machine=machine.dict(), status=StationStatusEnum.WORKING
		)
	await session.execute(query)
	await session.commit()


async def change_washing_machine_params(machine_number: int, station: StationData, session: AsyncSession,
										**kwargs) -> None:
	"""
	Обновить данные стиральной машины.
	"""
	await session.execute(
		update(WashingMachine).where(
			(WashingMachine.station_id == station.id) &
			(WashingMachine.machine_number == machine_number)
		).values(**kwargs)
	)
	await session.commit()


async def delete_washing_services(object_number: int, station: StationData, session: AsyncSession,
									object_type: Literal["agent", "machine"]) -> None:
	"""
	Удаление стирального объекта
	"""
	classes = {
		"agent": WashingAgent,
		"machine": WashingMachine
	}
	cls = classes[object_type]
	numeric_field = cls.NUMERIC_FIELDS.get(cls.__name__)

	await session.execute(
		delete(cls).where(
			(cls.station_id == station.id) &
			(getattr(cls, numeric_field) == object_number)
		)
	)
	await session.commit()
