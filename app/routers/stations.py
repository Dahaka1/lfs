from typing import Annotated

from fastapi import APIRouter, Depends, Body, status, HTTPException, Path
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.logs import ChangesLog
from ..schemas import schemas_stations, schemas_washing
from ..schemas.schemas_users import User
from ..models.stations import StationProgram
from ..dependencies.roles import get_sysadmin_user
from ..dependencies import get_async_session
from ..dependencies.stations import get_current_station
from ..crud import crud_stations
from ..static.enums import StationParamsEnum, QueryFromEnum
from ..exceptions import GettingDataError, CreatingError

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


@router.post("/", response_model=schemas_stations.Station, status_code=status.HTTP_201_CREATED,
			 tags=["station_creating"])
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

	log_text = f"Station with UUID {created_station.id} was successfully created by " \
			   f"user {current_user.email} ({current_user.first_name} {current_user.last_name})"

	await ChangesLog.log(
		db=db, user=current_user, station=created_station, content=log_text
	)
	await db.commit()
	return created_station


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
		case StationParamsEnum.SETTINGS:
			return schemas_stations.StationPartial(partial_data=current_station.settings)
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
