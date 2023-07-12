import uuid

from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint, Boolean, UUID, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Base
from ..schemas import schemas_washing
from ..utils.general import sa_object_to_dict, sa_objects_dicts_list

import services


class WashingSource:
	NUMERIC_FIELDS = {
		"WashingMachine": "machine_number",
		"WashingAgent": "agent_number"
	}
	station_id: uuid.UUID

	@classmethod
	async def create_object(
		cls, db: AsyncSession, station_id: uuid.UUID, object_number: int, **kwargs
	) -> schemas_washing.WashingMachineCreate | schemas_washing.WashingAgentCreate:
		"""
		Метод для создания нового объекта с ДЕФОЛТНЫМИ параметрами в БД для аналогичных классов
		 (стиральная машина и стиральное средство). Возвращает pydantic-схему добавленного объекта.

		Создает запись в БД БЕЗ КОММИТА, его нужно сделать вне метода.
		"""

		if any(
			(key not in cls.FIELDS for key in kwargs)
		):
			raise AttributeError(f"Expected fields for washing machine creating are {cls.FIELDS}")

		numeric_field = cls.NUMERIC_FIELDS.get(cls.__name__)
		kwargs.setdefault(numeric_field, object_number)
		kwargs.setdefault("station_id", station_id)

		query = insert(cls).values(**kwargs)
		model = getattr(schemas_washing, cls.__name__ + "Create")

		await db.execute(query)

		return model(**kwargs)

	@classmethod
	async def get_obj_by_number(
		cls, db: AsyncSession, object_number: int, station_id: uuid.UUID
	) -> schemas_washing.WashingMachine | schemas_washing.WashingAgent:
		"""
		Поиск объекта по номеру станции и номеру объекта.
		"""
		query = select(cls).where(
			(getattr(cls, cls.NUMERIC_FIELDS[cls.__name__]) == object_number) &
			(cls.station_id == station_id)
		)

		result = await db.execute(query)
		model = getattr(schemas_washing, cls.__name__)

		return model(
			**sa_object_to_dict(result.scalar())
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
		schema = getattr(schemas_washing, cls.__name__ + "Base")

		return [
			schema(**obj) for obj in
			sa_objects_dicts_list(
				result.scalars().all()
			)
		]


class WashingMachine(Base, WashingSource):
	"""
	Стиральная машина.
	
	Number - порядковый номер машины, подключенной к станции.
	Volume - вместимость машины (кг).
	Is_active - активна или нет.
	"""
	FIELDS = ["volume", "is_active"]

	__tablename__ = "washing_machine"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "machine_number", name="station_id_machine_number_pkey"),
	)

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	machine_number = Column(Integer, index=True)
	volume = Column(Integer, default=services.DEFAULT_WASHING_MACHINES_VOLUME)
	is_active = Column(Boolean, default=services.DEFAULT_STATION_IS_ACTIVE)


class WashingAgent(Base, WashingSource):
	"""
	Стиральное средство.

	Number - номер стирального средства, подаваемого станцией.
	Concentration_rate - Коэффициент концентрации средства.
	Rollback - "откат" средства.
	"""
	FIELDS = ["concentration_rate", "rollback"]

	__tablename__ = "washing_agent"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "agent_number", name="station_id_agent_number_pkey"),
	)

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	agent_number = Column(Integer, index=True)
	concentration_rate = Column(Integer, default=services.DEFAULT_WASHING_AGENTS_CONCENTRATION_RATE)
	rollback = Column(Boolean, default=services.DEFAULT_WASHING_AGENTS_ROLLBACK)
