from typing import Annotated

from fastapi import APIRouter, Depends, Body, status, HTTPException, Path
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud import crud_stations, crud_logs as log
from ..dependencies import get_async_session
from ..dependencies.roles import get_sysadmin_user
from ..dependencies.stations import get_current_station
from ..exceptions import GettingDataError, CreatingError
from ..schemas import schemas_stations
from ..schemas.schemas_users import User
from ..static import openapi
from ..static.enums import StationParamsEnum, QueryFromEnum

router = APIRouter(
	prefix="/stations",
	tags=["stations"],
)


@router.get("/", responses=openapi.read_all_stations_get, response_model=list[schemas_stations.StationGeneralParams])
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


@router.post("/", response_model=schemas_stations.Station, status_code=status.HTTP_201_CREATED,
			 tags=["station_creating"], responses=openapi.create_station_post)
async def create_station(
	current_user: Annotated[User, Depends(get_sysadmin_user)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	station: Annotated[schemas_stations.StationCreate, Body(embed=True, title="Параметры станции и зависимостей")],
):
	"""
	Создание станции.
	
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
			washing_machines=station.washing_machines, programs=station.programs
		)
	except CreatingError as e:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

	log_text = f"Станция с UUID {created_station.id} была успешно создана пользователем" \
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
