import uuid
from typing import Any, Sequence

from sqlalchemy import select, insert, delete, Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ...schemas.schemas_stations import StationGeneralParams
from ...schemas import schemas_relations as schema
from ...schemas.schemas_users import User
from ...models.relations import LaundryStation
from ...static.typing import SAQueryInstance
from ...exceptions import CreatingError, DeletingError, GettingDataError
from ...static.enums import RoleEnum
from ...models.stations import Station
from ...utils.general import sa_objects_dicts_list


class LaundryStationManagerBase:
	"""
	Определение отношений между собственником и станцией.
	"""
	def __init__(self, user: User, db: AsyncSession, station: StationGeneralParams = None):
		self.station: StationGeneralParams | None = station
		self.user = user
		self._is_relation: bool = False
		self._db = db
		self._model = LaundryStation

	async def __aenter__(self):
		if self.station:
			query = self._query(select)
			is_relation = await self._db.execute(query)
			if is_relation.scalar():
				self._is_relation = True
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		pass

	def __str__(self):
		return f"Relation <user ID {self.user.id} & station ID '{self.station.id}'>"

	def _query(self, foo) -> SAQueryInstance:
		return foo(self._model).where(
			(self._model.station_id == self.station.id) &
			(self._model.user_id == self.user.id)
		)

	async def _all(self) -> dict[str, Sequence[Row | RowMapping | Any] | User]:
		query = select(self._model).where(self._model.user_id == self.user.id)
		result = await self._db.execute(query)
		station_ids = sa_objects_dicts_list(result.scalars().all())
		stations = []
		for instance in station_ids:
			station_id = instance["station_id"]
			station = await Station.get_station_by_id(self._db, station_id)
			stations.append(station)
		return {"user": self.user, "stations": stations}


class CRUDLaundryStation(LaundryStationManagerBase):
	station: StationGeneralParams
	user: User
	_is_relation: bool
	_db: AsyncSession
	_model: DeclarativeMeta

	def _check(self, err: Any) -> None:
		if self.user.role != RoleEnum.LAUNDRY:
			raise err(f"User ID{self.user.id} role isn't {RoleEnum.LAUNDRY.value}")

	def __check_station(self) -> None:
		if not self.station:
			raise ValueError("Undefined station")

	async def create(self):
		"""
		:rtype: schema.LaundryStations
		"""
		self.__check_station()
		self._check(CreatingError)
		if self._is_relation:
			raise CreatingError(f"{self} already exists")
		query = insert(self._model).values(user_id=self.user.id, station_id=self.station.id)
		try:
			await self._db.execute(query)
		except IntegrityError:
			raise CreatingError(f"Station ID {self.station.id} already related")
		await self._db.commit()
		logger.info(f"{self} was successfully created")
		return await self._all()

	async def get_all(self):
		"""
		:rtype: schema.LaundryStations
		"""
		self._check(GettingDataError)
		return await self._all()

	async def delete(self) -> dict[str, dict[str, int | uuid.UUID]]:
		self.__check_station()
		self._check(DeletingError)
		if not self._is_relation:
			raise DeletingError(f"{self} doesn't exists")
		await self._db.execute(self._query(delete))
		await self._db.commit()
		logger.info(f"{self} was successfully deleted")
		return {"deleted": {"user_id": self.user.id, "station_id": self.station.id}}
