from typing import Annotated

from fastapi import APIRouter, Depends, Body, status, HTTPException, Path
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

import services
from ..schemas import schemas_stations, schemas_washing
from ..schemas.schemas_users import User
from ..models.stations import StationProgram
from ..dependencies.roles import get_sysadmin_user
from ..dependencies import get_async_session
from ..dependencies.stations import get_current_station
from ..crud import crud_stations
from ..static.enums import StationParamsEnum, QueryFromEnum
from ..exceptions import ProgramsDefiningError, GettingDataError

router = APIRouter(
	prefix="/stations",
	tags=["stations"],
)


@router.get("/", response_model=list[schemas_stations.StationGeneralParams])
@cache(expire=3600)
async def read_all_stations(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение списка всех станций (без подробных данных по каждой).
	Доступно только для SYSADMIN-пользователей.

	Основные параметры станций будут меняться редко, поэтому здесь делаю кэширование
	 ответа на час. Можно сократить время, если потребуется.
	"""
	return await crud_stations.read_all_stations(db=db)


@router.post("/", response_model=schemas_stations.Station, status_code=status.HTTP_201_CREATED)
async def create_station(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	station: Annotated[schemas_stations.StationCreate, Body(embed=True, title="Основные параметры станции")],
	settings: Annotated[schemas_stations.StationSettingsCreate | None, Body(embed=True, title="Настройки станции")] = \
		schemas_stations.StationSettingsCreate(),
	programs: Annotated[list[schemas_stations.StationProgramCreate],
	Body(embed=True, title="Программы станции")] = None,
	washing_agents: Annotated[list[schemas_washing.WashingAgentCreateMixedInfo],
	Body(embed=True, title="Стиральные средства станции")] = None,
	washing_machines: Annotated[list[schemas_washing.WashingMachineCreateMixedInfo],
	Body(embed=True, title="Стиральные средства станции")] = None
):
	f"""
	Создание станции.
	
	У станции обязательно должны быть машины и средства. Иначе при поиске и использовании данных станции
	 будет выдаваться ошибка (могу отменить это, если не нужно).
	
	Настройки станции можно не определять - установятся дефолтные.
	
	Wifi-данные видны только для станции.
	
	Программы станции создаются опционально.
	
	Средства станции и стиральные машины - тоже опционально. Если не передавать их, будет созданы 
	 их дефолтные объекты в количестве, установленном по умолчанию. Количество тоже можно изменить.
	
	При создании программ для программы можно передать уже созданные средства (просто передавая список номеров средств) 
	 или переопределить их параметры.
	
	Статус станции по умолчанию - "{services.DEFAULT_STATION_STATUS}", если станция включена (station_power=true).
	Если станция отключена, то статус может быть только None.
	
	Работать без программ с определенными машиной и средствами станция может.
	 
	Доступно только для SYSADMIN-пользователей.
	"""
	station = await crud_stations.create_station(
		db=db, station=station, settings=settings, created_by=current_user, washing_agents=washing_agents,
		washing_machines=washing_machines
	)

	if not station.is_active and settings:
		if any((settings.station_power, settings.teh_power)):
			await crud_stations.delete_station(station, db)  # сделал так, ибо rollback почему-то не работает... в шоке
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive station hasn't to be "
																				"powered on (includes its TEH)")
	if programs:
		try:
			station = await StationProgram.create_default_station_programs(station, programs, db)
			return station
		except ProgramsDefiningError as e:  # ошибки при создании программ
			# TODO решить с rollback'ом
			await crud_stations.delete_station(station, db)  # сделал так, ибо rollback почему-то не работает... в шоке
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
	print(station)
	return station


@router.get("/me/{dataset}", response_model=schemas_stations.StationPartial)
async def read_stations_params(
	current_station: Annotated[schemas_stations.StationGeneralParams, Depends(get_current_station)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	dataset: Annotated[StationParamsEnum, Path(title="Набор параметров станции")]
):
	"""
	Получение параметров станции самой станцией.
	Если станция неактивна, возвращается ошибка 403.
	"""
	match dataset:
		case StationParamsEnum.GENERAL:
			return schemas_stations.StationPartial(partial_data=current_station)
		case _:
			try:
				return await crud_stations.read_station(current_station, dataset, db, query_from=QueryFromEnum.STATION)
			except GettingDataError as e:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/me", response_model=schemas_stations.StationForStation)
async def read_stations_me(
	current_station: Annotated[schemas_stations.StationGeneralParams, Depends(get_current_station)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение ВСЕХ параметров станции станцией.
	"""
	try:
		return await crud_stations.read_station_all(current_station, db, query_from=QueryFromEnum.STATION)
	except GettingDataError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
