from typing import Annotated

from fastapi import APIRouter, status, Depends, Body, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

import config
from ..static import openapi
from ..dependencies.stations import get_current_station, get_station_by_id
from ..dependencies import get_async_session
from ..schemas.schemas_stations import StationGeneralParams
from ..schemas.schemas_logs import ErrorCreate, LogCreate, Log, Error
from ..schemas.schemas_users import User
from ..crud.crud_logs import CRUDLog
from ..static.enums import LogTypeEnum, ErrorTypeEnum, RoleEnum
from ..exceptions import ValidationError, UpdatingError, PermissionsError
from ..dependencies.roles import get_laundry_user, get_manager_user

router = APIRouter(
	prefix="/logs",
	tags=["logs"]
)


@router.post("/log", responses=openapi.create_log_post, status_code=status.HTTP_201_CREATED,
			 response_model=Log)
async def create_log(
	station: Annotated[StationGeneralParams, Depends(get_current_station)],
	log: Annotated[LogCreate, Body(title="Параметры лога", embed=True)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	data: Annotated[dict, Body(embed=True, title="Дополнительные данные")] = None
):
	"""
	Создание лога станцией.
	Если после добавления лога необходимо действие (обновление данных станции), оно выполнится автоматически.

	Код лога можно указать только предопределенный в списке логов.
	Можно указать конкретный случай (например, код 3.3), а можно - общий (например, код 3).

	Data - вспомогательные данные, когда нужно совершить действие (номер стиральной машины, ...).

	Для прекращения статуса обслуживания нужно отправить хедер X-Station-Maintenance-End.
	Для прекращения статуса ошибки нужно отправить хедер X-Station-Error-End.
	Иначе запросы от станции не принимаются.
	"""
	if not log.station_id:
		log.station_id = station.id
	if not data:
		data = {}
	try:
		created_log = await CRUDLog(log, log_type=LogTypeEnum.LOG, **data).add(station, db)
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
	except UpdatingError as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
	return created_log


@router.post("/error", responses=openapi.create_error_post, status_code=status.HTTP_201_CREATED,
			 response_model=Error)
async def create_error(
	station: Annotated[StationGeneralParams, Depends(get_current_station)],
	error: Annotated[ErrorCreate, Body(title="Параметры ошибки", embed=True)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	data: Annotated[dict, Body(embed=True, title="Дополнительные данные")] = None
):
	"""
	Создание ошибки станцией.
	Ошибка отличается от лога тем, что для нее можно указать область видимости (Scope).
	Если после добавления ошибки необходимо действие (обновление данных станции), оно выполнится автоматически.

	Код ошибки можно указать только предопределенный в списке ошибок.
	Можно указать конкретный случай (например, код 3.3), а можно - общий (например, код 3).

	P.S. Этот метод сделан (практически продублирован) из-за особенностей FastAPI -
	 объединить обработку сразу нескольких pydantic-схем в одном методе получается только криво.

	Data - вспомогательные данные, когда нужно совершить действие (номер стиральной машины, ...).
	"""
	if not error.station_id:
		error.station_id = station.id
	if not data:
		data = {}
	try:
		created_log = await CRUDLog(error, log_type=LogTypeEnum.ERROR, **data).add(station, db)
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
	except UpdatingError as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

	return created_log


@router.get("/log/station/{station_id}", response_model=list[Log], responses=openapi.get_station_logs_get)
async def get_station_logs(
	current_user: Annotated[User, Depends(get_laundry_user)],
	station: Annotated[StationGeneralParams, Depends(get_station_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	limit: Annotated[int, Query(title="Количество записей", ge=1,
								le=config.MAX_LOGS_GETTING_AMOUNT)] = config.STD_LOGS_GETTING_AMOUNT,
	code: Annotated[int | float, Query(title="Код логов")] = None
):
	"""
	Получение логов станции пользователем.
	По умолчанию возвращаются только 100 записей.

	Доступно для LAUNDRY-пользователей и выше.
	"""
	return await CRUDLog.get_station_logs(station, db, limit, code)


@router.get("/error/station/{station_id}", response_model=list[Error], responses=openapi.get_station_errors_get)
async def get_station_errors(
	current_user: Annotated[User, Depends(get_manager_user)],
	station: Annotated[StationGeneralParams, Depends(get_station_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	scope: Annotated[ErrorTypeEnum, Query(title="Тип ошибок (видимость)")] = ErrorTypeEnum.PUBLIC,
	limit: Annotated[int, Query(title="Количество записей", ge=1,
								le=config.MAX_LOGS_GETTING_AMOUNT)] = config.STD_LOGS_GETTING_AMOUNT,
	code: Annotated[int | float, Query(title="Код ошибок")] = None
):
	"""
	Получение ошибок станции пользователем.
	По умолчанию возвращаются только публичные ошибки.
	Сисадмин может получить все ошибки (или отдельно служебные).

	Доступно для MANAGER-пользователей и выше.
	"""
	if scope != ErrorTypeEnum.PUBLIC and current_user.role != RoleEnum.SYSADMIN:
		raise PermissionsError()
	return await CRUDLog.get_station_errors(station, db, limit, scope, code)
