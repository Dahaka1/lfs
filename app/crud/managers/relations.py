import uuid
from typing import Any, Sequence

from sqlalchemy import select, insert, delete, Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import exists
from loguru import logger

from ...schemas.schemas_stations import StationGeneralParams
from ...schemas import schemas_relations as schema
from ...schemas.schemas_users import User
from ...models.relations import LaundryStation
from ...static.typing import SAQueryInstance
from ...exceptions import CreatingError, DeletingError, GettingDataError
from ...static.enums import RoleEnum, LaundryStationSorting, RegionEnum
from ...models.stations import Station
from ...utils.general import sa_objects_dicts_list
from ...models import users as user_model


class LaundryStationManagerBase:
	"""
	Определение отношений между собственником и станцией.
	"""
	_model = LaundryStation

	def __init__(self, user: User, db: AsyncSession, station: StationGeneralParams = None):
		self.station: StationGeneralParams | None = station
		self.user = user
		self._is_relation: bool = False
		self._db = db

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
	_model: LaundryStation

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

	@staticmethod
	async def _get_relation_user_and_station(data: list[dict[str, Any]], db: AsyncSession) -> \
		list[schema.LaundryStationRelation]:
		user_ids = (rel["user_id"] for rel in data)
		users = sa_objects_dicts_list((await db.execute(
			select(user_model.User).
			where(user_model.User.id.in_(user_ids))
		)).scalars().all())
		station_ids = (rel["station_id"] for rel in data)
		stations = sa_objects_dicts_list((await db.execute(
			select(Station).where(Station.id.in_(station_ids))
		)).scalars().all())
		result = []
		for rel in data:
			user_id = rel["user_id"]
			user = next(u for u in users if u["id"] == user_id)
			station_id = rel["station_id"]
			station = next(s for s in stations if s["id"] == station_id)
			result.append(schema.LaundryStationRelation(**{"user": user, "station": station}))
		return result

	@classmethod
	async def get_all_relations(cls, db: AsyncSession, user: User,
								order_by: LaundryStationSorting = LaundryStationSorting.NAME,
								desc: bool = False) -> \
		list[schema.LaundryStationRelation]:
		"""
		В методе _all - получение станций по пользователю.
		В этом методе - получение вообще всех отношений по всем пользователям (список зависит от роли).

		ПОКА собственников немного, сделаю сортировку и фильтрацию средствами языка.
		Не разобрался, как избежать кучи запросов с SA.
		"""
		query = select(cls._model)
		if user.role == RoleEnum.REGION_MANAGER:
			query = query.join(user_model.User).where(
				user_model.User.region == user.region
			)
		result = sa_objects_dicts_list((await db.execute(query)).scalars().all())
		objs = await cls._get_relation_user_and_station(result, db)
		ordering = {
			LaundryStationSorting.STATION_SERIAL: {"key": lambda rel: int(rel.station.serial.lstrip("0"))},
			LaundryStationSorting.NAME: {"key": lambda rel: rel.user.last_name},
			LaundryStationSorting.REGION: {"key": lambda rel: rel.user.region.value}
		}
		ordering_params = ordering[order_by]
		if desc:
			ordering_params["reverse"] = True

		return sorted(objs, **ordering_params)

	@classmethod
	async def get_all_not_related_stations(cls, db: AsyncSession, user: User,
										   region: RegionEnum | None):
		"""
		:rtype: schemas_stations.StationGeneralParams
		"""
		stmt = exists().where(cls._model.station_id == Station.id)
		query = select(Station).filter(~stmt)
		if user.role == RoleEnum.REGION_MANAGER:
			query = query.where(Station.region == user.region)
		else:
			if region:
				query = query.where(Station.region == region)
		result = await db.execute(query)
		return result.scalars().all()
