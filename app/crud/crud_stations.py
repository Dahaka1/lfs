import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Bundle
from sqlalchemy import select, delete

from ..models.stations import Station, StationSettings, StationControl, StationProgram
from ..models.logs import ChangesLog
from ..models.washing import WashingAgent, WashingMachine
from ..schemas import schemas_stations, schemas_users, schemas_washing
from ..utils.general import sa_objects_dicts_list, encrypt_data
import config
from geopy.location import Location
from geopy.geocoders import Nominatim
from geopy.adapters import AioHTTPAdapter
from ..static.enums import StationParamsEnum


async def read_all_stations(db: AsyncSession) -> list[schemas_stations.StationGeneralParams]:
	"""
	Возвращает pydantic-модели станций (основные параметры).
	"""
	query = select(Station).order_by(Station.updated_at.desc())
	result = await db.execute(query)
	stations = sa_objects_dicts_list(result.scalars().all())

	result = []
	for station in stations:
		station_obj = schemas_stations.StationGeneralParams(**station)
		result.append(station_obj)

	return result


async def create_station(db: AsyncSession,
						 station: schemas_stations.StationCreate,
						 settings: schemas_stations.StationSettingsCreate | None,
						 washing_agents: list[schemas_washing.WashingAgentCreateMixedInfo] | None,
						 washing_machines: list[schemas_washing.WashingMachineCreateMixedInfo] | None,
						 created_by: schemas_users.User) -> schemas_stations.Station:
	"""
	Создает станцию в БД с определенными или дефолтными параметрами.
	"""
	wifi_data = {"login": station.wifi_name, "password": station.wifi_password}
	hashed_wifi_data = encrypt_data(wifi_data)
	async with Nominatim(user_agent=config.GEO_APP, adapter_factory=AioHTTPAdapter) as geolocator:
		location: Location = await geolocator.geocode(station.address)

	station_id = await Station.create(
		db=db,
		location={"latitude": location.latitude, "longitude": location.longitude},
		is_active=station.is_active,
		is_protected=station.is_protected,
		hashed_wifi_data=hashed_wifi_data
	)
	station_settings = await StationSettings.create(
		db=db,
		station_id=station_id,
		station_power=settings.station_power,
		teh_power=settings.teh_power
	) if settings else await StationSettings.create(db=db, station_id=station_id)

	station_control = await StationControl.create(db=db, station_id=station_id)

	station_washing_services = await Station.create_default_washing_services(
		db=db, station_id=station_id,
		washing_agents_amount=station.washing_agents_amount,
		washing_machines_amount=station.washing_machines_amount,
		washing_agents=washing_agents,
		washing_machines=washing_machines
	)

	inserted_station = await Station.get_station_by_id(db=db, station_id=station_id)

	created_station_obj = schemas_stations.Station(
		**inserted_station.dict(),
		**station_washing_services,
		station_control=station_control,
		station_settings=station_settings
	)

	log_text = f"Station with UUID {created_station_obj.id} was successfully created by " \
			   f"user {created_by.email} ({created_by.first_name} {created_by.last_name})"

	await ChangesLog.log(
		db=db, user=created_by, station=created_station_obj, content=log_text
	)
	await db.commit()
	return created_station_obj


async def read_station(
	station: schemas_stations.StationGeneralParams,
	params_set: StationParamsEnum,
	db: AsyncSession
) -> schemas_stations.StationPartial:
	"""
	Возвращает объект с запрошенными данными.
	"""
	match params_set:
		case StationParamsEnum.SETTINGS:
			data = await StationSettings.get_relation_data(station, db)
		case StationParamsEnum.CONTROL:
			data = await StationControl.get_relation_data(station, db)
		case StationParamsEnum.PROGRAMS:
			data = await StationProgram.get_relation_data(station, db)
		case StationParamsEnum.WASHING_MACHINES:
			data = await WashingMachine.get_station_objects(station.id, db)
		case StationParamsEnum.WASHING_AGENTS:
			data = await WashingAgent.get_station_objects(station.id, db)

	return schemas_stations.StationPartial(data=data)


async def read_station_all(
	station: schemas_stations.StationGeneralParams,
	db: AsyncSession
) -> schemas_stations.Station:
	"""
	Возвращает все данные по станции.

	Надо обязательно сократить количество запросов... (отмечено в TODO).
	"""
	settings = await StationSettings.get_relation_data(station, db)
	control = await StationControl.get_relation_data(station, db)
	programs = await StationProgram.get_relation_data(station, db)
	washing_machines = await WashingMachine.get_station_objects(station.id, db)
	washing_agents = await WashingAgent.get_station_objects(station.id, db)

	return schemas_stations.Station(
		**station.dict(), station_programs=programs, station_washing_machines=washing_machines,
		station_washing_agents=washing_agents, station_control=control, station_settings=settings
	)


async def delete_station(
	station: schemas_stations.StationGeneralParams | uuid.UUID,
	db: AsyncSession
) -> None:
	"""
	Удаление станции.
	"""
	station_id = station.id if isinstance(station, schemas_stations.StationGeneralParams) else station

	query = delete(Station).where(Station.id == station_id)
	await db.execute(query)
	await db.commit()
