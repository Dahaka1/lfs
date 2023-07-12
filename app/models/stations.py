import uuid
from typing import Optional

from sqlalchemy import Enum, Column, Integer, String, Boolean, ForeignKey, \
	UUID, JSON, DateTime, func, insert, select, PrimaryKeyConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from ..database import Base

import services
from ..schemas.schemas_washing import WashingMachineCreate, WashingAgentCreate, \
	WashingAgentCreateMixedInfo, WashingMachineCreateMixedInfo, WashingAgentWithoutRollback
from ..static.enums import StationStatusEnum
from ..schemas import schemas_stations, schemas_washing
from .washing import WashingAgent, WashingMachine, WashingSource
from ..utils.general import sa_object_to_dict, sa_objects_dicts_list
from ..exceptions import ProgramsDefiningError, GettingDataError
from ..static.typing import StationParamsSet


class Station(Base):
	"""
	Модель станции.

	ID - генерируемый UUID для каждой станции.
	Location - локация станции (JSON с геоданными (latitude, longitude)).
	Is_active - активна или нет.
	Is_protected - включена "охрана" или нет.
	Hashed_auth_code - JWT-токен для активации станции.
	Hashed_wifi_data - JWT-токен с данными WiFi для станции (бессрочный, получается при активации).
	Created_at - дата и время создания.
	Updated_at - дата и время последнего обновления.
	"""
	FIELDS = ["location", "is_active", "is_protected", "hashed_wifi_data"]

	__tablename__ = "station"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	location = Column(JSON, nullable=False, default={})
	is_active = Column(Boolean, default=services.DEFAULT_STATION_IS_ACTIVE)
	is_protected = Column(Boolean)
	hashed_wifi_data = Column(String)
	created_at = Column(DateTime, server_default=func.now())
	updated_at = Column(DateTime, onupdate=func.now())

	@staticmethod
	async def get_station_by_id(db: AsyncSession, station_id: uuid.UUID) -> schemas_stations.StationGeneralParams | None:
		"""
		Возвращает объект станции с определенным ИД.
		Если его нет - None.
		"""
		query = select(Station).where(Station.id == station_id)
		result = await db.execute(query)
		station = result.scalar()
		if station:
			return schemas_stations.StationGeneralParams(
				**sa_object_to_dict(station)
			)

	@classmethod
	async def create(cls, db: AsyncSession, **kwargs) -> uuid.UUID:
		"""
		Создание станции в БД.
		БЕЗ коммита (нужно сделать его вне функции).

		Возвращает ИД созданной станции.
		"""
		if any(
			(key not in cls.FIELDS for key in kwargs)
		):
			raise AttributeError(f"Expected fields for station creating are {cls.FIELDS}")

		query = insert(Station).values(**kwargs)

		inserting = await db.execute(query)

		station_id = inserting.inserted_primary_key[0]

		return station_id

	@staticmethod
	async def create_default_washing_services(
		db: AsyncSession, station_id: uuid.UUID,
		washing_machines_amount: int,
		washing_agents_amount: int,
		washing_agents: list[WashingAgentCreateMixedInfo],
		washing_machines: list[WashingMachineCreateMixedInfo]
	) -> \
		dict[str, list[WashingMachineCreate | WashingAgentCreate]]:
		"""
		При создании станции БЕЗ указания количества машин и средств
		- автоматическое добавление дефолтного количества
		 стиральных машин и средств С ДЕФОЛТНЫМИ параметрами.

		При указании количества - создание объектов в нужном количестве.

		При явном определении объектов - создание их.
		"""
		inserted_washing_machines = []
		inserted_washing_agents = []

		async def create_object(
			obj: WashingMachineCreateMixedInfo | WashingAgentCreateMixedInfo
		) -> WashingMachineCreate | WashingAgentCreate:
			obj_data = obj.dict()
			models = {
				"WashingMachineCreateMixedInfo": WashingMachine,
				"WashingAgentCreateMixedInfo": WashingAgent
			}
			model: WashingSource = models[obj.__class__.__name__]
			numeric_field = model.NUMERIC_FIELDS[model.__class__.__name__]
			obj_number = obj_data.pop(numeric_field)
			created_object = await model.create_object(db=db, station_id=station_id,
													   object_number=obj_number, **obj_data)
			return created_object

		if washing_machines is None:
			for machine_number in range(washing_machines_amount):
				created_machine = await WashingMachine.create_object(db=db, station_id=station_id,
														   object_number=machine_number + 1)
				inserted_washing_machines.append(created_machine)
		else:
			for machine in washing_machines:
				created_machine = await create_object(machine)
				inserted_washing_machines.append(created_machine)

		if washing_agents is None:
			for agent_number in range(washing_agents_amount):
				created_agent = await WashingAgent.create_object(db=db, station_id=station_id,
														 object_number=agent_number + 1)
				inserted_washing_agents.append(created_agent)
		else:
			for agent in washing_agents:
				created_agent = await create_object(agent)
				inserted_washing_agents.append(created_agent)

		return {
			"station_washing_machines": inserted_washing_machines,
			"station_washing_agents": inserted_washing_agents
		}

	@staticmethod
	async def authenticate_station(db: AsyncSession, station_id: uuid.UUID) -> \
		Optional[schemas_stations.StationGeneralParams]:
		"""
		Авторизация станции (проверка UUID).
		"""
		station = await Station.get_station_by_id(db=db, station_id=station_id)
		if not station:
			return
		return station


class StationRelation:
	station_id: uuid.UUID

	@classmethod
	async def get_relation_data(cls, station: schemas_stations.StationGeneralParams,
								   db: AsyncSession) -> StationParamsSet:
		"""
		Поиск записей по станции в побочных таблицах.
		"""
		query = select(cls).where(cls.station_id == station.id)  # не знаю, чего ругается =(
		schema = getattr(schemas_stations, cls.__name__)
		result = await db.execute(query)

		if result is None:
			err_text = f"Getting {cls.__name__} for station {station.id} error.\nDB data not found"
			async with GettingDataError(station=station, db=db, message=err_text) as err:
				raise err

		match cls.__name__:
			case "StationProgram":
				station_programs = sa_objects_dicts_list(result.scalars().all())
				return schemas_stations.StationPrograms(
					station_id=station.id, station_programs=station_programs
				)

			case "StationControl" | "StationSettings":
				return schema(
					**sa_object_to_dict(result.scalar())
				)


class StationSettings(Base, StationRelation):
	"""
	Настройки станции.

	Station_power- вкл/выкл.
	Teh_power - вкл/выкл ТЭНа.
	Updated_at - дата и время последнего обновления.
	"""
	FIELDS = ["station_power", "teh_power"]

	__tablename__ = "station_settings"

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True,
						index=True)
	station_power = Column(Boolean, default=services.DEFAULT_STATION_POWER)
	teh_power = Column(Boolean, default=services.DEFAULT_STATION_TEH_POWER)
	updated_at = Column(DateTime, onupdate=func.now())

	@classmethod
	async def create(cls, db: AsyncSession, station_id: uuid.UUID, **kwargs) -> schemas_stations.StationSettingsCreate:
		"""
		Создание настроек станции в БД.
		БЕЗ коммита (нужно сделать его вне функции).

		Возвращает pydantic-схему созданного дефолтного объекта.
		"""
		if any(
			(key not in cls.FIELDS for key in kwargs)
		):
			raise AttributeError(f"Expected fields for station settings creating are {cls.FIELDS}")

		query = insert(StationSettings).values(station_id=station_id, **kwargs)

		await db.execute(query)

		return schemas_stations.StationSettingsCreate(**kwargs)


class StationProgram(Base, StationRelation):
	"""
	Программы (дозировки) станции.

	ID нужен для создания нескольких записей по одной и той же станции (несколько стиральных средств).
	Program_step - номер метки (этапа/"шага") программы станции (11-15, 21-25, ...).
	Program_number - номер программы станции (определяется по первой цифре шага программы, и наоборот).
	Washing_agents - объекты стиральных средств.
	Updated_at - дата и время последнего обновления.
	"""
	__tablename__ = "station_program"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "program_step"),
	)

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	program_step = Column(Integer, nullable=False)
	program_number = Column(Integer, nullable=False)
	washing_agents = Column(JSON)
	updated_at = Column(DateTime, onupdate=func.now())

	@staticmethod
	async def create_default_station_programs(station: schemas_stations.Station,
									  programs: list[schemas_stations.StationProgramCreate],
									  db: AsyncSession) -> schemas_stations.Station:
		"""
		Создание программ станции (при создании самой станции).
		"""
		for program in programs:
			program: schemas_stations.StationProgramCreate
			washing_agents_to_insert = []

			for washing_agent in program.washing_agents:
				washing_agent: schemas_washing.WashingAgent | int
				washing_agent_number = washing_agent if isinstance(washing_agent, int) else washing_agent.agent_number
				agents_amount = len(station.station_washing_agents)
				if washing_agent_number > agents_amount:
					err_text = f"Station has {agents_amount} washing agents, but got agent №{washing_agent_number}"
					async with ProgramsDefiningError(db=db, message=err_text, station=station) as err:
						raise err

				if isinstance(washing_agent, int):  # случай, если был передан список номеров средств
					washing_agent = next(agent for agent in station.station_washing_agents
										 if agent.agent_number == washing_agent)
					for agent_ in program.washing_agents:
						agent_: int
						program.washing_agents: list[int]  # не знаю, почему ругается на тип - в pydantic-схеме
						# обозначил, что возможен и список интов, и список средств
						if agent_ == washing_agent_number:
							idx = program.washing_agents.index(agent_)
							program.washing_agents[idx] = washing_agent

				if washing_agent.agent_number not in [agent.agent_number for agent in washing_agents_to_insert]:
					washing_agent = WashingAgentWithoutRollback(**washing_agent.dict())
					washing_agents_to_insert.append(washing_agent)
				else:
					err_text = f"Duplicate agent with number {washing_agent.agent_number} found"
					async with ProgramsDefiningError(message=err_text, db=db, station=station) as err:
						raise err

			program_data = {
				"station_id": station.id,
				"program_step": program.program_step,
				"program_number": program.program_number,
				"washing_agents": sorted(
						[item.dict() for item in washing_agents_to_insert], key=lambda agent: agent["agent_number"]
					)
				}
			if any(program_data):
				await db.execute(
					insert(StationProgram), program_data
				)
				station.station_programs.append(
					schemas_stations.StationProgramMixedInfo(
						**program.dict()
					)
				)
		await db.commit()
		return station


class StationControl(Base, StationRelation):
	"""
	Контроль и управление станцией.
	Может быть установлена программа ИЛИ средство + доза.

	Status - статус станции.
	Если статус "ожидание", то все параметры должны быть NONE.
	Program_step - объект этапа программы.
	Washing_machine - объект стиральной машины.
	Washing_agents - стиральные средства станции.
	Updated_at - дата и время последнего обновления.
	"""
	__tablename__ = "station_control"

	station_id = Column(UUID, ForeignKey("station.id", onupdate="CASCADE",
											ondelete="CASCADE"), primary_key=True, index=True)
	status = Column(Enum(StationStatusEnum), default=StationStatusEnum.AWAITING)
	program_step = Column(JSON)
	washing_machine = Column(JSON)
	washing_agents = Column(JSON)
	updated_at = Column(DateTime, onupdate=func.now())

	@staticmethod
	async def create(db: AsyncSession, station_id: uuid.UUID) -> schemas_stations.StationControl:
		"""
		Создание в БД записи о статусе станции.
		БЕЗ коммита (нужно сделать его вне функции).

		Возвращает pydantic-схему созданного дефолтного объекта.
		"""
		query = insert(StationControl).values(
			station_id=station_id
		)

		await db.execute(query)

		return schemas_stations.StationControl(status=StationStatusEnum.AWAITING)
