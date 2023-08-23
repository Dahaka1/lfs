from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies.roles import get_sysadmin_user
from ..dependencies.users import get_user_by_query_id
from ..dependencies import get_async_session
from ..dependencies.stations import get_station_by_id
from ..schemas.schemas_relations import LaundryStations
from ..static import openapi
from ..schemas.schemas_users import User
from ..schemas.schemas_stations import StationGeneralParams
from ..crud.managers.relations import CRUDLaundryStation
from ..exceptions import CreatingError, DeletingError, GettingDataError


router = APIRouter(
	prefix="/rel",
	tags=["relations"]
)


@router.post("/laundry_stations/{station_id}", response_model=LaundryStations,
			 responses=openapi.add_laundry_station_post, status_code=status.HTTP_201_CREATED)
async def add_laundry_station(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	station: Annotated[StationGeneralParams, Depends(get_station_by_id)],
	user: Annotated[User, Depends(get_user_by_query_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Добавление нового отношения станции к собственнику (прачечной).
	Уже существовать оно не должно =)

	Добавить может только SYSADMIN-пользователь. И только для LAUNDRY-пользователя.
	"""
	async with CRUDLaundryStation(user, db, station) as laundry_stations:
		try:
			return await laundry_stations.create()
		except CreatingError as err:
			raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))


@router.get("/laundry_stations", response_model=LaundryStations,
			responses=openapi.get_laundry_stations_get)
async def get_laundry_stations(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	user: Annotated[User, Depends(get_user_by_query_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение всех станций, относящихся к пользователю.

	Доступно только для SYSADMIN-пользователей.
	"""
	async with CRUDLaundryStation(user, db) as laundry_stations:
		try:
			return await laundry_stations.get_all()
		except GettingDataError as err:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete("/laundry_stations/{station_id}", response_model=dict[str, Any],
			   responses=openapi.delete_laundry_station_delete)
async def delete_laundry_station(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	station: Annotated[StationGeneralParams, Depends(get_station_by_id)],
	user: Annotated[User, Depends(get_user_by_query_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Удаление отношения станции к пользователю.

	Для удаления оно должно существовать =)
	"""
	async with CRUDLaundryStation(user, db, station) as laundry_stations:
		try:
			return await laundry_stations.delete()
		except DeletingError as err:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
