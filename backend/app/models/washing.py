import uuid
from typing import Optional

from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint, Boolean, UUID, insert, select, Float, \
	update, delete
from sqlalchemy.ext.asyncio import AsyncSession

import services
from ..database import Base
from ..exceptions import GettingDataError, CreatingError
from ..schemas import schemas_washing
from ..utils.general import sa_object_to_dict, sa_objects_dicts_list


class WashingMixin:
	NUMERIC_FIELDS = {
		"WashingMachine": "machine_number",
		"WashingAgent": "agent_number"
	}
	FIELDS: list[str]

	station_id: uuid.UUID

	@classmethod
	async def create_object(
		cls, db: AsyncSession, station_id: uuid.UUID, object_number: int,
		defaults: bool = False, **kwargs
	) -> schemas_washing.WashingMachineCreate | schemas_washing.WashingAgentCreate:
		"""
		Метод для создания нового объекта в БД для аналогичных классов
		 (стиральная машина и стиральное средство). Возвращает pydantic-схему добавленного объекта.

		Создает запись в БД БЕЗ КОММИТА, его нужно сделать вне метода.

		Если defaults = True, то не делается проверка на существование объекта (используется при создании
		 станции).
		"""

		if any(
			(key not in cls.FIELDS for key in kwargs)
		):
			raise AttributeError(f"Expected fields for {cls.__name__} creating are {cls.FIELDS}")

		if not defaults:
			current_objects = await cls.get_station_objects(station_id, db)
			if object_number in map(lambda obj: getattr(obj, cls.NUMERIC_FIELDS[cls.__name__]), current_objects):
				raise CreatingError("Got an existing object number")

		numeric_field = cls.NUMERIC_FIELDS.get(cls.__name__)
		kwargs.setdefault(numeric_field, object_number)
		kwargs.setdefault("station_id", station_id)

		query = insert(cls).values(**kwargs)
		model = getattr(schemas_washing, cls.__name__ + "Create")

		await db.execute(query)
		await db.commit()
		return model(**kwargs)

	@classmethod
	async def get_obj_by_number(
		cls, db: AsyncSession, object_number: int, station_id: uuid.UUID
	) -> Optional[schemas_washing.WashingMachine | schemas_washing.WashingAgent]:
		"""
		Поиск объекта по номеру станции и номеру объекта.
		"""
		query = select(cls).where(
			(getattr(cls, cls.NUMERIC_FIELDS[cls.__name__]) == object_number) &
			(cls.station_id == station_id)
		)

		result = await db.execute(query)
		model = getattr(schemas_washing, cls.__name__)

		data = result.scalar()
		if data:
			return model(
				**sa_object_to_dict(data)
			)

	@classmethod
	async def get_station_objects(
		cls, station_id: uuid.UUID, db: AsyncSession
	) -> list[schemas_washing.WashingMachine] | list[schemas_washing.WashingAgent]:
		"""
		Ищет все объекты, относящиеся к станции.
		"""
		query = select(cls).where(
			cls.station_id == station_id  # хз, почему ошибка
		)
		result = await db.execute(query)
		data = result.scalars().all()
		if not any(data):
			raise GettingDataError(f"Getting {cls.__name__} for station {station_id} error.\nDB data not found")

		schema = getattr(schemas_washing, cls.__name__ + "Base")

		return [
			schema(**obj) for obj in
			sa_objects_dicts_list(
				data
			)
		]

	@classmethod
	async def update_object(
		cls, station_id: uuid.UUID, db: AsyncSession,
		updated_object: schemas_washing.WashingMachineUpdate | schemas_washing.WashingAgentUpdate,
		obj_number: int
	) -> schemas_washing.WashingMachine | schemas_washing.WashingAgent:
		"""
		Обновление объекта.
		"""
		numeric_field = cls.NUMERIC_FIELDS[cls.__name__]
		query = update(cls).where(
			(cls.station_id == station_id) &
			(getattr(cls, numeric_field) == obj_number)
		).values(
			**updated_object.dict()
		)

		await db.execute(query)
		await db.commit()

		schema = getattr(schemas_washing, cls.__name__)

		return schema(
			**updated_object.__dict__
		)

	@classmethod
	async def delete_object(
		cls, station_id: uuid.UUID, db: AsyncSession, object_number: int
	) -> None:
		"""
		Удаление объекта.
		"""
		query = delete(cls).where(
			(cls.station_id == station_id) &
			(getattr(cls, cls.NUMERIC_FIELDS[cls.__name__]) == object_number)
		)

		await db.execute(query)
		await db.commit()


class WashingMachine(Base, WashingMixin):
	"""
	Стиральная машина.
	
	Number - порядковый номер машины, подключенной к станции.
	Volume - вместимость машины (кг).
	Is_active - активна или нет.
	Track_length - длина трассы (м).
	"""
	FIELDS = ["volume", "is_active", "track_length"]

	__tablename__ = "washing_machine"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "machine_number", name="station_id_machine_number_pkey"),
	)

	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	machine_number = Column(Integer, index=True)
	volume = Column(Integer, default=services.DEFAULT_WASHING_MACHINES_VOLUME)
	is_active = Column(Boolean, default=services.DEFAULT_STATION_IS_ACTIVE)
	track_length = Column(Float, default=services.DEFAULT_WASHING_MACHINES_TRACK_LENGTH)


class WashingAgent(Base, WashingMixin):
	"""
	Стиральное средство.

	Number - номер стирального средства, подаваемого станцией.
	Volume - объем средства.
	Rollback - "откат" средства.
	"""
	FIELDS = ["volume", "rollback"]

	__tablename__ = "washing_agent"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "agent_number", name="station_id_agent_number_pkey"),
	)

	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	agent_number = Column(Integer, index=True)
	volume = Column(Integer, default=services.DEFAULT_WASHING_AGENTS_VOLUME)
	rollback = Column(Boolean, default=services.DEFAULT_WASHING_AGENTS_ROLLBACK)
