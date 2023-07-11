import uuid
from typing import Optional

from sqlalchemy import Enum, Column, Integer, String, Boolean, ForeignKey, \
	ForeignKeyConstraint, UUID, JSON, DateTime, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Base

import services
from ..schemas.schemas_washing import WashingMachineCreate, WashingAgentCreate, \
	WashingAgentCreateMixedInfo, WashingMachineCreateMixedInfo
from ..static.enums import StationStatusEnum
from ..schemas import schemas_stations, schemas_washing
from .washing import WashingAgent, WashingMachine, WashingSource
from ..utils import sa_object_to_dict
from ..exceptions import ProgramsDefiningError


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
	async def create_washing_services(
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


class StationSettings(Base):
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


class StationProgram(Base):
	"""
	Программы (дозировки) станции.

	ID нужен для создания нескольких записей по одной и той же станции (несколько стиральных средств).
	Program_step - номер метки (этапа/"шага") программы станции (11-15, 21-25, ...).
	Program_number - номер программы станции (определяется по первой цифре шага программы, и наоборот).
	Washing_agent_id - ИД стирального средства.
	Dosage - доза (мл/кг).
	Rollback - дублирую здесь колонку, ибо пока не понимаю, где она нужна.
	Updated_at - дата и время последнего обновления.
	"""
	__tablename__ = "station_program"
	__table_args__ = (
		ForeignKeyConstraint(["station_id", "washing_agent_number"],
							 ["washing_agent.station_id", "washing_agent.agent_number"]),
	)

	id = Column(Integer, primary_key=True)
	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	program_step = Column(Integer, nullable=False)
	program_number = Column(Integer, nullable=False)
	washing_agent_number = Column(Integer)
	dosage = Column(Integer, default=services.DEFAULT_STATION_DOSAGE)
	updated_at = Column(DateTime, onupdate=func.now())

	@staticmethod
	async def create_station_programs(station: schemas_stations.Station,
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
					raise ProgramsDefiningError(f"Station has {agents_amount} washing agents, but got "
									 f"agent №{washing_agent_number}")

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

				agent_data = {"washing_agent_number": washing_agent.agent_number,
							  "dosage": washing_agent.concentration_rate}
				if washing_agent.agent_number not in \
					[agent_["washing_agent_number"] for agent_ in washing_agents_to_insert]:
					washing_agents_to_insert.append(agent_data)
				else:
					raise ProgramsDefiningError(f"Duplicate agent with number {washing_agent.agent_number} found")

			program_data = [{"station_id": station.id,
							"program_step": program.program_step,
							"program_number": program.program_number,
							**agent} for agent in washing_agents_to_insert]
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


class StationControl(Base):
	"""
	Контроль и управление станцией.
	Может быть установлена программа ИЛИ средство + доза.

	Status - статус станции.
	Если статус "ожидание", то все параметры должны быть NONE.
	Program_step - номер этапа программы (включает в себя информацию о номере программы).
	Washing_machine_number - номер стиральной машины.
	Washing_agent_numbers_and_dosages - стиральные средства станции и дозировки ({1: 50, 2: 40, 3: 10, ...}).
	Updated_at - дата и время последнего обновления.
	"""
	__tablename__ = "station_control"
	__table_args__ = (
		ForeignKeyConstraint(["station_id", "washing_machine_number"],
							 ["washing_machine.station_id", "washing_machine.machine_number"]),
	)

	station_id = Column(UUID, ForeignKey("station.id", onupdate="CASCADE",
											ondelete="CASCADE"), primary_key=True, index=True)
	status = Column(Enum(StationStatusEnum), default=StationStatusEnum.AWAITING)
	program_step = Column(Integer, ForeignKey("station_program.id", onupdate="CASCADE",
											ondelete="CASCADE"))
	washing_machine_number = Column(Integer)
	washing_agent_numbers_and_dosages = Column(JSON, default={})
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
