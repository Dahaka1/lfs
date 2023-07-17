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
from ..exceptions import ProgramsDefiningError, GettingDataError, CreatingError

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
	"""
	Создание станции.
	
	Настройки станции можно не определять - установятся дефолтные.
	
	Wifi-данные видны только для станции.
	
	Программы станции создаются опционально.
	
	Средства станции и стиральные машины - тоже опционально. Если не передавать их, будет созданы 
	 их дефолтные объекты в количестве, установленном по умолчанию. Количество тоже можно изменить.
	Можно передать ИЛИ количество объектов по умолчанию для автоматического создания, ИЛИ явный список объектов
	 с определенными параметрами.
	Количество средств и машин у станции должно быть не меньше минимального определенного в бизнес-параметрах проекта.

	При создании программ для программы можно передать уже созданные средства (просто передавая список номеров средств) 
	 или переопределить их параметры.
	Номер программы можно не указывать - по номеру этапа (шага) программы он определится автоматически.
	
	Статус станции по умолчанию - "AWAITING", если станция включена (station_power=true).
	Если станция отключена, то статус может быть только None.
	Если станция активна, ТЭН по умолчанию всегда включен.
	
	Работать без программ с определенными машиной и средствами станция может.
	 
	Доступно только для SYSADMIN-пользователей.
	"""
	try:
		station = await crud_stations.create_station(
			db=db, station=station, settings=settings, washing_agents=washing_agents,
			washing_machines=washing_machines
		)
	except CreatingError as e:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

	if not station.is_active and settings:
		if any((settings.station_power is True, settings.teh_power is True)):
			await crud_stations.delete_station(station, db)  # сделал так, ибо rollback почему-то не работает... в шоке
			raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inactive station hasn't to be "
																				"powered on (includes its TEH)")
	if programs:
		try:
			station = await StationProgram.create_station_programs(station, programs, db)
		except ProgramsDefiningError as e:  # ошибки при создании программ
			# TODO решить с rollback'ом
			await crud_stations.delete_station(station, db)  # сделал так, ибо rollback почему-то не работает... в шоке
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

	log_text = f"Station with UUID {station.id} was successfully created by " \
			   f"user {current_user.email} ({current_user.first_name} {current_user.last_name})"

	await ChangesLog.log(
		db=db, user=current_user, station=station, content=log_text
	)
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
