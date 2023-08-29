import copy
import datetime
import random
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Optional, Self

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from sqlalchemy import update, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import services
from app.crud.managers.relations import CRUDLaundryStation
from app.database import Base
from app.models.stations import StationControl, Station, StationSettings, StationProgram
from app.models.washing import WashingAgent, WashingMachine
from app.schemas import schemas_stations, schemas_washing
from app.static.enums import RoleEnum, RegionEnum, StationStatusEnum, LogActionEnum, LogTypeEnum
from app.utils.general import sa_object_to_dict, sa_objects_dicts_list
from .logs import Log
from .strings import generate_string
from .users import create_authorized_user


@dataclass
class StationData:
	"""
	Класс станции с парамерами для тестов.
	"""
	id: uuid.UUID
	name: str
	serial: str
	is_active: bool
	is_protected: bool
	# location: dict
	region: RegionEnum
	station_programs: list[schemas_stations.StationProgram]
	station_washing_machines: list[schemas_washing.WashingMachine]
	station_washing_agents: list[schemas_washing.WashingAgent]
	station_control: schemas_stations.StationControl
	station_settings: schemas_stations.StationSettings
	created_at: Optional[datetime.datetime]
	updated_at: Optional[datetime.datetime]
	headers: dict[str, str]
	comment: Optional[str]
	general_schema: schemas_stations.StationGeneralParams

	# пришлось сделать дикты вторым вариантом атрибутов, иначе везде ошибка линтера =(
	# а pydantic модели почему-то вообще не работают внутри этого класса

	async def refresh(self, session: AsyncSession) -> None:
		"""
		Обновить все данные станции
		"""
		updated_data = await get_station_by_id(self.id, session)
		for k in updated_data.dict():
			if k in self.__dict__:
				setattr(self, k, getattr(updated_data, k))

	async def reset(self, session: AsyncSession) -> None:
		"""
		Для положительного теста логов.
		"""
		for machine in self.station_washing_machines:
			if not machine.is_active:
				await change_washing_machine_params(machine.machine_number, self,
													session, is_active=True)
		if not self.station_settings.station_power:
			await change_station_params(self, session, station_power=True)

		if self.station_control.status in (StationStatusEnum.ERROR, StationStatusEnum.MAINTENANCE, None):
			await change_station_params(self, session, status=StationStatusEnum.AWAITING)

	async def prepare_for_log(self, log: Any, session: AsyncSession) -> None:
		action = log.action
		match action:
			case LogActionEnum.ERROR_STATION_CONTROL_STATUS_START:
				await self.turn_on(session)
				await generate_station_control(self, session)
			case LogActionEnum.STATION_TURN_OFF:
				await self.turn_on(session)
				await generate_station_control(self, session)
			case LogActionEnum.STATION_TURN_ON:
				await self.turn_off(session)
			case LogActionEnum.WASHING_MACHINE_TURN_ON:
				await self.turn_on(session)
				await change_washing_machine_params(log.data["washing_machine_number"], self, session, is_active=True)
			case LogActionEnum.WASHING_MACHINE_TURN_OFF:
				await self.turn_on(session)
				await change_washing_machine_params(log.data["washing_machine_number"], self, session, is_active=False)
			case LogActionEnum.WASHING_AGENTS_CHANGE_VOLUME:
				pass
			case LogActionEnum.STATION_SETTINGS_CHANGE:
				teh_power = log.data["teh_power"]
				if teh_power is True:
					await change_station_params(self, session, teh_power=False)
				elif teh_power is False:
					await change_station_params(self, session, teh_power=True)
			case LogActionEnum.STATION_START_MANUAL_WORKING:
				await self.turn_on(session)
				await generate_station_control(self, session)
			case LogActionEnum.STATION_WORKING_PROCESS:
				await self.turn_on(session)
				await generate_station_control(self, session)
			case LogActionEnum.STATION_MAINTENANCE_START:
				await self.turn_on(session)
				await generate_station_control(self, session)
			case LogActionEnum.STATION_MAINTENANCE_END:
				await self.turn_on(session)
				await change_station_params(self, session, status=StationStatusEnum.MAINTENANCE)
			case LogActionEnum.ERROR_STATION_CONTROL_STATUS_END:
				await self.turn_on(session)
				await change_station_params(self, session, status=StationStatusEnum.ERROR)
			case LogActionEnum.STATION_ACTIVATE:
				await self.turn_off(session)
				await change_station_params(self, session, teh_power=False, is_protected=False)

	async def turn_on(self, session: AsyncSession) -> None:
		await change_station_params(self, session, station_power=True, status=StationStatusEnum.AWAITING,
									program_step=None, washing_agents=[], washing_machine=None)
		await self.refresh(session)

	async def turn_off(self, session: AsyncSession) -> None:
		await change_station_params(self, session, station_power=False, status=None,
									program_step=None, washing_agents=[], washing_machine=None)
		await self.refresh(session)

	async def generate_owner(self, session: AsyncSession, ac: AsyncClient,
							 sync_session: Session) -> None:
		_, user = await create_authorized_user(ac, sync_session, RoleEnum.LAUNDRY)
		relation = CRUDLaundryStation(user, session, self.general_schema)
		await relation.create()

	@classmethod
	async def generate_stations_list(cls, ac: AsyncClient,
									 sync_session: Session,
									 sysadmin: Any,
									 session: AsyncSession,
									 amount: int = None,
									 create_rand_data_for_stations_list=True) -> list[Self]:
		"""
		:params sysadmin: tests.additional.users.UserData
		"""
		stations_ = []
		if not amount:
			amount = random.randint(1, 5)
		for _ in range(amount):
			station = await generate_station(ac, sync_session, sysadmin)
			if create_rand_data_for_stations_list:
				await station.generate_data_for_read_stations_list(session, ac, sync_session)
			stations_.append(station)
		return stations_

	async def generate_data_for_read_stations_list(
		self, session: AsyncSession, ac: AsyncClient, sync_session: Session,
		ctrl=False, owner=False, logs=False
	) -> None:
		def rand() -> int:
			return random.randint(0, 1)

		if not ctrl:
			ctrl = rand()
		if not owner:
			owner = rand()
		if not logs:
			logs = rand()
		if ctrl:
			await generate_station_control(self, session)
		if owner:
			await self.generate_owner(session, ac, sync_session)
		if logs:
			await Log.generate(self, LogTypeEnum.LOG,
							   [3.1], session, ac, amount=1)
			await change_station_params(self, session,
										status=StationStatusEnum.MAINTENANCE)
			await Log.generate(self, LogTypeEnum.LOG,
							   [9.17], session, ac, amount=1)
		await self.refresh(session)


def rand_serial() -> str:
	return "".join(
		(str(num) for num in (random.randrange(10) for _ in range(5)))
	)


async def generate_station(
	ac: AsyncClient,
	sync_session: Session = None,
	user: Any = None,
	use_default_programs=False,
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
		user, user_schema = await create_authorized_user(ac, sync_session, RoleEnum.SYSADMIN)
	station_data = dict(station={
		"name": generate_string(),
		"serial": rand_serial(),
		"is_active": kwargs.get("is_active") or True,
		"is_protected": kwargs.get("is_protected") or False,
		"wifi_name": "qwerty",
		"wifi_password": "qwerty",
		# "address": "Санкт-Петербург",
		"region": "Северо-западный"
	})

	for k, v in kwargs.items():
		if v is not None:
			station_data["station"][k] = v

	if not kwargs.get("programs") and not use_default_programs:
		station_data["station"]["programs"] = generate_station_programs()

	response = await ac.post(
		"/v1/stations/",
		headers=user.headers,
		json=station_data
	)

	if response.status_code == 201:
		station = schemas_stations.Station(**response.json())
		station_general_schema = schemas_stations.StationGeneralParams(
			**station.dict()
		)
		headers = {"X-Station-Uuid": str(station.id)}
		attrs = {attr: getattr(station, attr) for attr in station.dict()}
		return StationData(
			**attrs, headers=headers, general_schema=station_general_schema
		)
	else:
		raise AssertionError(str(response))


async def change_station_params(station: StationData | schemas_stations.Station, session: AsyncSession, **kwargs) -> None:
	"""
	Изменение параметров станции.
	"""
	for k, v in kwargs.items():
		match k:
			case "is_active" | "is_protected" | "region":
				query = update(Station).where(Station.id == station.id).values(**{k: v})
			case "status" | "washing_machine" | "washing_agents" | "program_step":
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


def generate_station_programs(amount: int = 4,
							  as_schema=False) -> list[schemas_stations.StationProgramCreate] | list[dict[str, Any]]:
	"""
	Сгенерировать программы для станции.
	"""
	programs = []
	program_step = 11
	names = ["Махра белая", "Махра цветная"]
	for _ in range(amount):
		washing_agents = [random.randint(1, services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT)]
		program = schemas_stations.StationProgramCreate(
			name=random.choice(names), program_step=program_step, washing_agents=washing_agents
		)
		programs.append(program)
		program_step += 1
		if program_step % 10 == 6:
			program_step += 5
	if as_schema:
		return programs
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
			station_control=station_control,
			general_schema=station_general
		)


async def generate_station_control(station: StationData, session: AsyncSession) -> None:
	"""
	Установить случайное текущее состояние станции (рабочее).
	"""
	if not station.is_active or station.station_settings.station_power is False:
		raise ValueError

	program = random.choice(station.station_programs)
	machines = copy.deepcopy(station.station_washing_machines)
	machine = random.choice(machines)
	del machines[machines.index(machine)]
	ctrl = (await session.execute(select(StationControl).where(StationControl.station_id == station.id))).scalar()
	ctrl.program_step = jsonable_encoder(program.dict())
	ctrl.washing_machine = jsonable_encoder(machine.dict())
	ctrl.status = StationStatusEnum.WORKING
	ctrl.washing_machines_queue = [m.machine_number for m in machines][-3:]
	random.shuffle(ctrl.washing_machines_queue)
	await session.merge(ctrl)
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


async def get_all_stations(session: AsyncSession) -> list[schemas_stations.StationGeneralParams]:
	query = select(Station)
	r = await session.execute(query)
	res = [schemas_stations.StationGeneralParams(**s.__dict__) for s in r.scalars().all()]
	return res


async def delete_all_stations(session: AsyncSession) -> None:
	query = delete(Station)
	await session.execute(query)
	await session.commit()
