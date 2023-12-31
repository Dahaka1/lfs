from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Enum, Column, Integer, String, Boolean, ForeignKey, \
	UUID, JSON, func, insert, select, PrimaryKeyConstraint, update, TIMESTAMP, Row
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import error_wrappers

import config
import services
from .washing import WashingAgent, WashingMachine, WashingMixin
from ..database import Base
from ..exceptions import GettingDataError, UpdatingError, CreatingError
from ..schemas import schemas_stations, schemas_washing, schemas_users
from ..schemas.schemas_washing import WashingMachineCreate, WashingAgentCreate, \
	WashingAgentCreateMixedInfo, WashingMachineCreateMixedInfo
from ..static.enums import StationStatusEnum, RegionEnum, RoleEnum
from ..static.typing import StationParamsSet
from ..utils.general import sa_object_to_dict, sa_objects_dicts_list
from ..utils.google_sheets import get_sheet_data


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
	FIELDS = ["is_active", "is_protected", "hashed_wifi_data", "region", "serial", "comment",
			  "created_at", "name"]

	__tablename__ = "station"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	serial = Column(String, unique=True)
	name = Column(String)
	is_active = Column(Boolean, default=services.DEFAULT_STATION_IS_ACTIVE)
	is_protected = Column(Boolean)
	hashed_wifi_data = Column(String)
	created_at = Column(TIMESTAMP(timezone=True))
	updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
	region = Column(Enum(RegionEnum))
	comment = Column(String)

	@staticmethod
	async def relations(db: AsyncSession, station: schemas_stations.StationGeneralParams) -> \
		list[StationSettings, StationControl]:
		"""
		Объединил сбор данных по станции.
		"""
		relations = (await db.execute(
			select(StationSettings, StationControl).join_from(
				StationSettings, StationControl, StationSettings.station_id == StationControl.station_id
			).where(StationSettings.station_id == station.id)
		)).all()
		objs = []
		for entry in relations:
			entry: Row
			for j in entry:
				objs.append(j)

		if len(objs) != 2:
			raise GettingDataError()

		return objs

	@staticmethod
	async def get_station_by_id(db: AsyncSession,
								station_id: uuid.UUID | str) -> schemas_stations.StationGeneralParamsInDB | None:
		"""
		Возвращает объект станции с определенным ИД (или серийным номером).
		Если его нет - None.
		"""
		try:
			uuid.UUID(str(station_id))
			query = select(Station).where(Station.id == station_id)
		except ValueError:
			query = select(Station).where(Station.serial == station_id)
		result = await db.execute(query)
		station = result.scalar()
		if station:
			return schemas_stations.StationGeneralParamsInDB(
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
		washing_machines_amount: int | None,
		washing_agents_amount: int | None,
		washing_agents: list[WashingAgentCreateMixedInfo] | None,
		washing_machines: list[WashingMachineCreateMixedInfo] | None
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
			model: WashingMixin = models[obj.__class__.__name__]
			numeric_field = model.NUMERIC_FIELDS[model.__name__]
			obj_number = obj_data.pop(numeric_field)
			created_object = await model.create_object(db=db, station_id=station_id,
													   object_number=obj_number, **obj_data,
													   defaults=True)
			return created_object

		if washing_machines is None:
			for machine_number in range(washing_machines_amount):
				created_machine = await WashingMachine.create_object(db=db, station_id=station_id,
																	 object_number=machine_number + 1,
																	 defaults=True)
				inserted_washing_machines.append(created_machine)
		else:
			for machine in washing_machines:
				created_machine = await create_object(machine)
				inserted_washing_machines.append(created_machine)

		if washing_agents is None:
			for agent_number in range(washing_agents_amount):
				created_agent = await WashingAgent.create_object(db=db, station_id=station_id,
																 object_number=agent_number + 1,
																 defaults=True)
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
		Optional[schemas_stations.StationGeneralParamsInDB]:
		"""
		Авторизация станции (проверка UUID).
		"""
		station = await Station.get_station_by_id(db=db, station_id=station_id)
		return station

	@classmethod
	async def update(cls, db: AsyncSession, station_id: uuid.UUID,
					 updated_params: schemas_stations.StationGeneralParamsUpdate | dict) -> None:
		try:
			data = updated_params.dict(exclude_unset=True)
		except AttributeError:
			data = updated_params
		query = update(cls).where(
			cls.id == station_id
		).values(**data)

		await db.execute(query)
		await db.commit()

	@staticmethod
	def check_user_permissions(user: schemas_users.User,
									 station: schemas_stations.StationGeneralParams) -> None:
		if user.role < RoleEnum.MANAGER and user.region != station.region:
			raise PermissionError


class StationMixin:
	station_id: uuid.UUID

	@classmethod
	async def get_relation_data(cls, station: schemas_stations.StationGeneralParams | uuid.UUID,
								db: AsyncSession) -> StationParamsSet:
		"""
		Поиск записей по станции в побочных таблицах.
		"""
		station_id = station.id if isinstance(station, schemas_stations.StationGeneralParams) else station
		query = select(cls).where(cls.station_id == station_id)
		result = await db.execute(query)

		match cls.__name__:
			case "StationProgram":
				data = result.scalars().all()
				station_programs = sa_objects_dicts_list(data)
				schema = schemas_stations.StationProgram
				return [
					schema(**item) for item in station_programs
				]

			case "StationControl" | "StationSettings":
				schema = getattr(
					schemas_stations,
					cls.__name__
				)
				data = result.scalar()
				if data is None:
					raise GettingDataError(f"Getting {cls.__name__} for station {station.id} error.\n"
										   f"DB data not found")
				return schema(
					**sa_object_to_dict(data)
				)

	@classmethod
	async def update_relation_data(cls,
		station: schemas_stations.StationGeneralParams,
		updated_params: schemas_stations.StationSettingsUpdate | \
								   schemas_stations.StationProgramUpdate,
		db: AsyncSession, **kwargs
	) -> schemas_stations.StationSettings | schemas_stations.StationProgram:
		"""
		Обновление данных по станции в побочных таблицах.
		"""
		match cls.__name__:
			case "StationSettings":
				if updated_params.station_power is True:
					if not station.is_active:
						raise UpdatingError("Station currently is inactive, but got an station_power 'True'")
			case "StationProgram":
				station_washing_agents: list[WashingAgent] = kwargs.get("washing_agents")
				if not station_washing_agents:
					raise ValueError("Expected for station washing agents list")

				for washing_agent in updated_params.washing_agents:
					idx = updated_params.washing_agents.index(washing_agent)
					if isinstance(washing_agent, int):  # если был передан номер средства, а не объект
						washing_agent = next(ag for ag in station_washing_agents if ag.agent_number == washing_agent)
						updated_params.washing_agents[idx] = washing_agent

				current_program_number: int = kwargs.get("current_program_number")
				if not current_program_number:
					raise ValueError("Expected for current program number")

		updated_params_dict = dict(**updated_params.dict(), updated_at=datetime.datetime.now())
		# updated_at почему-то автоматически не обновляется =(

		match cls.__name__:
			case "StationProgram":
				query = update(cls).where(
					(cls.station_id == station.id) &
					(cls.program_step == current_program_number)
					).values(**updated_params_dict)
			case "StationSettings":
				query = update(cls).where(
					cls.station_id == station.id
				).values(**updated_params_dict)

		await db.execute(query)
		await db.commit()

		schema = getattr(schemas_stations, cls.__name__)

		return schema(**updated_params_dict)


class StationSettings(Base, StationMixin):
	"""
	Настройки станции.

	Station_power- вкл/выкл.
	Teh_power - вкл/выкл ТЭНа.
	Updated_at - дата и время последнего обновления.
	"""
	FIELDS = ["station_power", "teh_power"]

	__tablename__ = "station_settings"

	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), unique=True,
						primary_key=True)
	station_power = Column(Boolean, default=services.DEFAULT_STATION_POWER)
	teh_power = Column(Boolean, default=services.DEFAULT_STATION_TEH_POWER)
	updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

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


class StationProgram(Base, StationMixin):
	"""
	Программы (дозировки) станции.

	Program_step - номер метки (этапа/"шага") программы станции (11-15, 21-25, ...).
	Program_number - номер программы станции (определяется по первой цифре шага программы, и наоборот).
	Washing_agents - объекты стиральных средств.
	Updated_at - дата и время последнего обновления.
	"""
	__tablename__ = "station_program"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "program_step"),
	)

	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"))
	name = Column(String, nullable=False)
	program_step = Column(Integer, nullable=False)
	program_number = Column(Integer, nullable=False)
	washing_agents = Column(JSON)
	updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

	@staticmethod
	async def create_station_programs(station: schemas_stations.Station,
											  programs: list[schemas_stations.StationProgramCreate],
											  db: AsyncSession) -> schemas_stations.Station:
		"""
		Создание программ станции (при создании самой станции).
		"""
		not_found_agent_err_text = "Washing agent №{agent_number} not found in station washing agents"

		for program in programs:
			for washing_agent in program.washing_agents:
				if isinstance(washing_agent, int):
					washing_agent_number = washing_agent
					try:
						washing_agent = next(ag for ag in station.station_washing_agents
											 if ag.agent_number == washing_agent_number)
						idx = program.washing_agents.index(washing_agent_number)
						program.washing_agents[idx] = washing_agent  # линтер ругается, но я заменил ведь инты на объекты
					except StopIteration:
						raise CreatingError(not_found_agent_err_text.format(agent_number=washing_agent_number))
				elif isinstance(washing_agent, schemas_washing.WashingAgentWithoutRollback):
					washing_agent_number = washing_agent.agent_number
					if washing_agent_number not in [ag.agent_number for ag in station.station_washing_agents]:
						raise CreatingError(not_found_agent_err_text.format(agent_number=washing_agent_number))

			program.washing_agents = sorted([item.dict() for item in program.washing_agents],
											key=lambda agent: agent["agent_number"])

			await db.execute(
				insert(StationProgram), {**program.dict(), "station_id": station.id}
			)

			station.station_programs.append(program)

		await db.flush()
		return station

	@staticmethod
	async def get_default_programs(station_washing_agents: list[schemas_washing.WashingAgentCreate]) \
		-> list[schemas_stations.StationProgramCreate]:
		"""
		Получение списка дефолтных программ из онлайн-таблицы.
		:raises: app.exceptions.GettingDataError
		"""
		error_postfix = ". Please, fix the problem or pass the defined station programs list"
		try:
			default_programs_r = await get_sheet_data(config.GoogleSheetTableQuery.station_default_programs)
		except ConnectionError as err:
			raise ConnectionError(str(err) + error_postfix)
		programs = []
		err_text = "Programs reading from google sheets error:"
		for item in default_programs_r:
			try:
				program_name, program_number, program_step_number, washing_agent_numbers = item
			except ValueError:
				raise GettingDataError(f"{err_text} invalid length of item" + error_postfix)
			try:
				schema = schemas_stations.StationProgramInGoogleSheet(program_name=program_name, program_number=program_number,
															 program_step_number=program_step_number,
															 washing_agent_numbers=washing_agent_numbers)
			except error_wrappers.ValidationError as err:
				raise GettingDataError(str(err) + error_postfix)
			agent_numbers = [ag.agent_number for ag in station_washing_agents]
			for num in schema.washing_agent_numbers:
				if num not in agent_numbers:
					raise GettingDataError(f"{err_text} washing agent №{num} not found in station washing agents" +
										   error_postfix)
			program = schemas_stations.StationProgramCreate(name=schema.program_name, program_number=schema.program_number,
													  program_step=schema.program_step_number,
													  washing_agents=schema.washing_agent_numbers)
			programs.append(program)

		return programs


class StationControl(Base, StationMixin):
	"""
	Контроль и управление станцией.
	Может быть установлена программа ИЛИ средство + доза.

	Status - статус станции.
	Если статус "ожидание", то все параметры должны быть NONE.
	Program_step - объект этапа программы.
	Washing_machine - объект стиральной машины.
	Washing_agents - стиральные средства станции.
	Washing_machines_queue - ни на что не влияющий параметр. Получается от станции.
	Updated_at - дата и время последнего обновления.
	"""
	__tablename__ = "station_control"

	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", onupdate="CASCADE",
										 ondelete="CASCADE"), unique=True, primary_key=True)
	status = Column(Enum(StationStatusEnum), default=services.DEFAULT_STATION_STATUS)
	program_step = Column(JSON)
	washing_machine = Column(JSON)
	washing_agents = Column(JSON, default=[])
	washing_machines_queue = Column(JSON, default=[])
	updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

	@staticmethod
	async def create(db: AsyncSession, station_id: uuid.UUID, **kwargs) -> schemas_stations.StationControl:
		"""
		Создание в БД записи о статусе станции.
		БЕЗ коммита (нужно сделать его вне функции).

		Возвращает pydantic-схему созданного дефолтного объекта.
		"""
		query = insert(StationControl).values(
			station_id=station_id,
			**kwargs
		)

		await db.execute(query)

		return schemas_stations.StationControl(
			status=kwargs["status"] if "status" in kwargs else services.DEFAULT_STATION_STATUS,
		)

	@classmethod
	async def update_relation_data(cls,
		station: schemas_stations.StationGeneralParams,
		updated_params: schemas_stations.StationControlUpdate,
		db: AsyncSession, **kwargs
	) -> schemas_stations.StationControl:
		"""
		Переопределяю метод, ибо непонятная ошибка
		"""
		if any(
			(any(updated_params.washing_agents), updated_params.program_step,
			 updated_params.washing_machine, updated_params.status)
		):
			station_settings = await StationSettings.get_relation_data(station, db)
			if station_settings.station_power is False:
				raise UpdatingError("Station power currently is False, but got non-nullable control params")

		ctrl: schemas_stations.StationControl = await cls.get_relation_data(station, db)

		if not updated_params.updated_at:
			updated_params.updated_at = datetime.datetime.now()

		for k, v in updated_params.dict().items():
			if getattr(ctrl, k) != v:
				match k:
					case "program_step" | "washing_machine":
						setattr(ctrl, k, jsonable_encoder(v))
					case "washing_agents":
						setattr(ctrl, k, [jsonable_encoder(ag) for ag in v])
					case _:
						setattr(ctrl, k, v)

		await db.execute(
			update(StationControl).where(StationControl.station_id == station.id).
			values(**ctrl.dict())
		)
		await db.commit()

		return ctrl
