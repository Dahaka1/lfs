import uuid
from typing import Annotated

from fastapi import Header, Depends, HTTPException, status, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import get_async_session
from ..exceptions import PermissionsError, GettingDataError
from ..models.stations import Station, StationProgram, StationControl
from ..schemas import schemas_stations
from ..schemas.schemas_stations import StationGeneralParams, StationGeneralParamsForStation
from ..static.enums import StationStatusEnum
from ..utils.general import decrypt_data
from ..utils.general import sa_object_to_dict


async def get_current_station(
	x_station_uuid: Annotated[uuid.UUID, Header()],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	x_station_maintenance_end: Annotated[str | None, Header(title="Хедер для прекращения статуса обслуживания")] = None,
	x_station_error_end: Annotated[str | None, Header(title="Хедер для прекращения статуса ошибки")] = None
) -> StationGeneralParamsForStation:
	"""
	Простая авторизация станции.
	Получает header 'X-Station-Uuid' - ИД станции.
	Проверяет, есть ли такая в базе.
	Проверяет, активна ли станция и не стоит ли статус сейчас "Обслуживание".
	Расшифровывает wifi данные (возвращаемая схема используется ТОЛЬКО станцией).

	Если станция в режиме "MAINTENANCE", то все запросы от нее блокируются.
	"""
	station = await Station.authenticate_station(db=db, station_id=x_station_uuid)
	if not station:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect station UUID")
	if not station.is_active:
		raise PermissionsError("Inactive station")
	try:
		station_control = await StationControl.get_relation_data(station, db)
	except GettingDataError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
	if station_control.status == StationStatusEnum.MAINTENANCE:
		if not x_station_maintenance_end:
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
								detail=f"Station status: {station_control.status.name}")
	elif station_control.status == StationStatusEnum.ERROR:
		if not x_station_error_end:
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
								detail=f"Station status: {station_control.status.name}")

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
	Проверяет, не обслуживается ли сейчас станция.
	"""
	station = await Station.get_station_by_id(db=db, station_id=station_id)
	if not station:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
	try:
		station_control = await StationControl.get_relation_data(station, db)
	except GettingDataError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
	if station_control.status in (StationStatusEnum.MAINTENANCE, StationStatusEnum.ERROR):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
							detail=f"Station status: {station_control.status.name}")
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
