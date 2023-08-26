import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Body, status, HTTPException, Path, Query
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..crud import crud_stations, crud_logs as log
from ..models.stations import Station
from ..dependencies import get_async_session, get_sync_session
from ..dependencies.roles import get_sysadmin_user, get_installer_user
from ..dependencies.stations import get_current_station
from ..exceptions import GettingDataError, CreatingError
from ..schemas import schemas_stations
from ..schemas.schemas_users import User
from ..static import openapi
from ..static.enums import StationParamsEnum, QueryFromEnum, StationsSortingEnum
from .config import CACHE_EXPIRING_DEFAULT

router = APIRouter(
	prefix="/stations",
	tags=["stations"]
)


@router.get("/", responses=openapi.read_all_stations_get,
			response_model=list[schemas_stations.StationInList])
@cache(expire=CACHE_EXPIRING_DEFAULT)
async def read_all_stations(
	current_user: Annotated[User, Depends(get_installer_user)],
	db: Annotated[Session, Depends(get_sync_session)],
	async_db: Annotated[AsyncSession, Depends(get_async_session)],
	order_by: Annotated[StationsSortingEnum, Query(title="Сортировка по столбцам")] = StationsSortingEnum.NAME,
	desc: Annotated[bool, Query(title="В обратном порядке или нет")] = False
):
	"""
	Получение списка всех станций (без подробных данных по каждой).
	Доступно только для SYSADMIN-пользователей.

	Основные параметры станций будут меняться редко, поэтому здесь делаю кэширование
	 ответа на час. Можно сократить время, если потребуется.
	"""
	return await crud_stations.read_all_stations(db, async_db, current_user,
												 order_by, desc)


@router.post("/", response_model=schemas_stations.Station, status_code=status.HTTP_201_CREATED,
			 tags=["station_creating"], responses=openapi.create_station_post)
async def create_station(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	station: Annotated[schemas_stations.StationCreate, Body(embed=True, title="Параметры станции и зависимостей")],
	released: Annotated[bool, Query(title="Выпущена станция или нет",
										description="Если нет, установится пустая дата создания станции")] = True
):
	"""
	Создание станции.

	Создать станцию можно без ее выпуска (?released=false). В таком случае
	 все запросы к станции и от нее будут блокироваться. "Выпустить" можно
	 методом patch (з.ы. доку).
	
	Настройки станции можно не определять - установятся дефолтные.
	
	Wifi-данные видны только для станции.
	
	Программы станции создаются опционально.
	
	Средства станции и стиральные машины - тоже опционально. Если не передавать их, будет созданы 
	 их дефолтные объекты в количестве, установленном по умолчанию. Количество тоже можно изменить.
	Можно передать ИЛИ количество объектов по умолчанию для автоматического создания, ИЛИ явный список объектов
	 с определенными параметрами (если указано и то, и другое - явные объекты будут использованы в приоритете).
	Количество средств и машин у станции должно быть не меньше (и не больше)
	 минимального определенного в бизнес-параметрах проекта.

	При создании программ для программы можно передать уже созданные средства (просто передавая список номеров средств) 
	 или переопределить их параметры (можно сочетать в списке средств программы и номера, и словари с параметрами).
	Номер программы можно не указывать - по номеру этапа (шага) программы он определится автоматически.
	
	Статус станции по умолчанию - "AWAITING", если станция включена (station_power=true).
	Если станция отключена, то статус может быть только None.
	Если станция активна, ТЭН по умолчанию всегда включен.
	
	Работать без программ с определенными машиной и средствами станция может.
	 
	Доступно только для SYSADMIN-пользователей.
	"""
	try:
		created_station = await crud_stations.create_station(
			db=db, station=station, settings=station.settings, washing_agents=station.washing_agents,
			washing_machines=station.washing_machines, programs=station.programs,
			released=released
		)
	except CreatingError as e:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

	log_text = f"Станция успешно создана пользователем" \
			   f" {current_user.email} ({current_user.first_name} {current_user.last_name})"

	await log.CRUDLog.server(6.4, log_text, created_station, db)

	await db.commit()
	return created_station


@router.get("/me/{dataset}", responses=openapi.read_stations_params_get)
async def read_stations_params(
	current_station: Annotated[schemas_stations.StationGeneralParamsForStation, Depends(get_current_station)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	dataset: Annotated[StationParamsEnum, Path(title="Набор параметров станции")]
):
	"""
	Получение параметров станции самой станцией.
	Если станция неактивна, возвращается ошибка 403.
	"""
	match dataset:
		case StationParamsEnum.GENERAL:
			return current_station
		case _:
			try:
				return await crud_stations.read_station(current_station, dataset, db)
			except GettingDataError as e:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/me", response_model=schemas_stations.StationForStation, responses=openapi.read_stations_me_get)
async def read_stations_me(
	current_station: Annotated[schemas_stations.StationGeneralParamsForStation, Depends(get_current_station)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение ВСЕХ параметров станции станцией.
	"""
	try:
		return await crud_stations.read_station_all(current_station, db, query_from=QueryFromEnum.STATION)
	except GettingDataError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/release/{station_id}", responses=openapi.release_station_patch,
			  response_model=schemas_stations.StationGeneralParams)
async def release_station(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	station_id: Annotated[uuid.UUID, Path(title="ИД станции")]
):
	"""
	"Выпуск" станции (установка даты создания).
	Станция должна быть не выпущена =)

	Доступно только для SYSADMIN.
	"""
	station = await Station.get_station_by_id(db, station_id)
	if not station:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
	if station.created_at:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station already released")
	release_datetime = datetime.datetime.now()
	await Station.update(db, station.id, {"created_at": release_datetime})
	station.created_at = release_datetime
	info_text = f"Станция успешно выпущена пользователем {current_user.email}"
	await log.CRUDLog.server(9, info_text, station, db)
	return station
