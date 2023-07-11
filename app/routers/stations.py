from typing import Annotated

from fastapi import APIRouter, Depends, Body, status, HTTPException
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import schemas_stations, schemas_washing
from ..schemas.schemas_users import User
from ..models.stations import StationProgram
from ..dependencies.roles import get_sysadmin_user
from ..dependencies import get_async_session
from ..dependencies.stations import get_current_station
from ..crud import crud_stations
from ..static.enums import StationStatusEnum
from ..exceptions import ProgramsDefiningError


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
	settings: Annotated[schemas_stations.StationSettingsCreate | None, Body(embed=True, title="Настройки станции")] = None,
	programs: Annotated[list[schemas_stations.StationProgramCreateMixedInfo], Body(embed=True, title="Программы станции")] = None,
	washing_agents: Annotated[list[schemas_washing.WashingAgentCreateMixedInfo],
		Body(embed=True, title="Стиральные средства станции")] = None,
	washing_machines: Annotated[list[schemas_washing.WashingMachineCreateMixedInfo],
		Body(embed=True, title="Стиральные средства станции")] = None
):
	f"""
	Создание станции.
	
	Настройки станции можно не определять - установятся дефолтные.
	
	Программы станции создаются опционально.
	
	Средства станции и стиральные машины - тоже опционально. Если не передавать их, будет созданы 
	 их дефолтные объекты в количестве, установленном по умолчанию. Количество тоже можно изменить.
	
	При создании программ для программы можно передать уже созданные средства (просто передавая список номеров средств) 
	 или переопределить их параметры.
	
	Статус станции по умолчанию - "{StationStatusEnum.AWAITING.value}". Работать без программ 
	 с определенными машиной и средствами она может сразу.
	 
	Доступно только для SYSADMIN-пользователей.
	"""
	station = await crud_stations.create_station(
		db=db, station=station, settings=settings, created_by=current_user, washing_agents=washing_agents,
		washing_machines=washing_machines
	)

	if not station.is_active:
		if any((settings.station_power, settings.teh_power)):
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive station hasn't to be "
																				"powered on (includes its TEH)")
	if programs:
		try:
			result = await StationProgram.create_station_programs(station, programs, db)
			return result
		except ProgramsDefiningError as e:  # ошибки при создании программ
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

	return station


@router.get("/me", response_model=schemas_stations.StationGeneralParams)
async def read_stations_me(
	current_station: Annotated[schemas_stations.StationGeneralParams, Depends(get_current_station)]
):
	"""
	Получения основных параметров станции самой станцией.
	Если станция неактивна, возвращается ошибка 403.
	"""
	return current_station


# @router.put("/{station_id}", response_model=schemas_stations.StationGeneralParams)
