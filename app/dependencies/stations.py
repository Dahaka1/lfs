import uuid
from typing import Annotated

from fastapi import Header, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession

from . import get_async_session
from ..models.stations import Station
from ..schemas.schemas_stations import StationGeneralParams
from ..exceptions import PermissionsError


async def get_current_station(
	x_station_uuid: Annotated[uuid.UUID, Header()],
	db: Annotated[AsyncSession, Depends(get_async_session)]
) -> StationGeneralParams:
	"""
	Простая авторизация станции.
	Получает header 'X-Station-Uuid' - ИД станции.
	Проверяет, есть ли такая в базе.
	Проверяет, активна ли станция.
	"""
	station = await Station.authenticate_station(db=db, station_id=x_station_uuid)
	if not station:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect station UUID")
	if not station.is_active:
		raise PermissionsError("Inactive station")
	return station


async def get_station_id(
	station_id: Annotated[uuid.UUID, Path(ge=1)],
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
