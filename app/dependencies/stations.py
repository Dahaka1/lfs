import uuid
from typing import Annotated

from fastapi import Header, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from . import get_async_session
from ..models.stations import Station, StationProgram
from ..schemas.schemas_stations import StationGeneralParams, StationGeneralParamsForStation
from ..schemas import schemas_stations
from ..exceptions import PermissionsError
from ..utils.general import decrypt_data
from ..utils.general import sa_object_to_dict


async def get_current_station(
	x_station_uuid: Annotated[uuid.UUID, Header()],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> StationGeneralParamsForStation:
	"""
	Простая авторизация станции.
	Получает header 'X-Station-Uuid' - ИД станции.
	Проверяет, есть ли такая в базе.
	Проверяет, активна ли станция.
	Расшифровывает wifi данные (возвращаемая схема используется ТОЛЬКО станцией).
	"""
	station = await Station.authenticate_station(db=db, station_id=x_station_uuid)
	if not station:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect station UUID")
	if not station.is_active:
		raise PermissionsError("Inactive station")

	wifi_data = decrypt_data(station.hashed_wifi_data)

	return StationGeneralParamsForStation(
		**station.dict(),
		wifi_name=wifi_data.get("login"),
		wifi_password=wifi_data.get("password")
	)


async def get_station_by_id(
	station_id: Annotated[uuid.UUID, Path()],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> StationGeneralParams:
	"""
	Функция проверяет, существует ли станция с переданным ИД в URL'е (пути запроса).
	Возвращает объект станции (базовые параметры).
	"""
	station = await Station.get_station_by_id(db=db, station_id=station_id)
	if not station:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
	return station


async def get_station_program_by_number(
	station: Annotated[StationGeneralParams, Depends(get_station_by_id)],
	program_step_number: Annotated[int, Path()],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> tuple[schemas_stations.StationGeneralParams, schemas_stations.StationProgram]:
	"""
	Функция проверяет, существует ли программа с переданным номером у станции, ИД которой
	 был получен.

	Возвращает станцию и программу, если они существуют.
	"""
	query = select(StationProgram).where(
		(StationProgram.station_id == station.id) &
		(StationProgram.program_step == program_step_number)
	)
	result = await db.execute(query)
	program = result.scalar()

	if program:
		program = schemas_stations.StationProgram(**sa_object_to_dict(program))
		return station, program

	raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program step not found")
