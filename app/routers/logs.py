import datetime
import uuid
from typing import Annotated

import pydantic
from fastapi import APIRouter, Depends, Body, Path, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud import crud_logs
from ..dependencies import get_async_session
from ..dependencies.roles import get_installer_user
from ..dependencies.stations import get_current_station
from ..dependencies.users import get_current_active_user
from ..exceptions import PermissionsError
from ..models.logs import StationMaintenanceLog
from ..models.stations import Station, StationControl
from ..schemas import schemas_logs as logs, schemas_stations as stations, schemas_users as users
from ..static import openapi
from ..static.enums import RoleEnum as roles, LogTypeEnum, StationStatusEnum, CreateLogByStationEnum
from ..utils.logs import parse_log_class

router = APIRouter(
	prefix="/logs",
	tags=["logs"]
)


@router.post("/{log_type}", status_code=status.HTTP_201_CREATED, responses=openapi.add_station_log_post_responses)
async def add_station_log(
	station: Annotated[stations.StationGeneralParams, Depends(get_current_station)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	log_type: Annotated[CreateLogByStationEnum, Path(title="Тип логов")],
	log: Annotated[logs.LogCreate, Body(title="Содержание лога")]
):
	"""
	Логирование действий станции.
	Логировать по этому маршруту изменения данных станции нельзя - они логируются только автоматически.
	Логировать по этому маршруту обслуживание станции тоже нельзя - см. "Station maintenance log".

	Доступно только для станции.
	"""

	log_types = {
		CreateLogByStationEnum.ERRORS: logs.ErrorLogCreate,
		CreateLogByStationEnum.PROGRAMS_USING: logs.StationProgramsLogCreate,
		CreateLogByStationEnum.WASHING_AGENTS_USING: logs.WashingAgentUsingLogCreate
	}

	schema = log_types[log_type]

	try:
		log = schema(**log.content.dict())
	except pydantic.error_wrappers.ValidationError:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

	log_cls = parse_log_class(log_type)

	return await crud_logs.create_log(
		log_cls(**log.dict(), station_id=station.id), db
	)


@router.get("/{log_type}/{station_id}", responses=openapi.get_station_logs_get)
async def get_station_logs(
	current_user: Annotated[users.User, Depends(get_current_active_user)],
	station_id: Annotated[uuid.UUID, Path(title="ИД станции")],
	log_type: Annotated[LogTypeEnum, Path(title="Тип логов")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение журнала по действиям станции выбранного типа.
	Логи сортированы по убыванию даты создания.
	Если будет нужно, могу добавить настройку параметров сортировки/фильтрации.

	Доступ к журналам:
	- Ошибки: INSTALLER и выше;
	- Подача средств: INSTALLER и выше;
	- Изменения: MANAGER и выше;
	- Выполнение программ: LAUNDRY и выше;
	- Обслуживание: MANAGER и выше.
	"""
	station = await Station.authenticate_station(db=db, station_id=station_id)  # здесь дополнительно ищу станцию,
	# ибо ее логи должно быть можно просматривать в режиме обслуживания
	if not station:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")

	logs_getting_roles = {
		LogTypeEnum.ERRORS: (roles.INSTALLER, roles.MANAGER, roles.SYSADMIN),
		LogTypeEnum.WASHING_AGENTS_USING: (roles.INSTALLER, roles.MANAGER, roles.SYSADMIN),
		LogTypeEnum.CHANGES: (roles.MANAGER, roles.SYSADMIN),
		LogTypeEnum.PROGRAMS_USING: (roles.INSTALLER, roles.MANAGER, roles.SYSADMIN, roles.LAUNDRY),
		LogTypeEnum.MAINTENANCE: (roles.SYSADMIN, roles.MANAGER)
	}

	if current_user.role not in logs_getting_roles[log_type]:
		raise PermissionsError()

	log_cls = parse_log_class(log_type)

	return await crud_logs.get_station_logs(station, log_cls, db)


@router.post("/" + LogTypeEnum.MAINTENANCE.value + "/{station_id}", tags=["maintenance_logs"],
			 responses=openapi.station_maintenance_log_post, response_model=logs.StationMaintenanceLog)
async def station_maintenance_log(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station_id: Annotated[uuid.UUID, Path(title="ИД станции")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Начать обслуживание станции

	Начать обслуживание можно только при статусе "Ожидание" (машина включена и не работает в данный момент).

	Когда обслуживание начинается, статус станции сменяется на "MAINTENANCE".
	Во время действия этого статуса никакие действия станции/со станцией невозможны.
	Чтобы вернуть прежний статус, нужно завершить обслуживание.

	Доступно для INSTALLER-пользователей и выше.
	"""
	station = await Station.get_station_by_id(db=db, station_id=station_id)
	if not station:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
	# здесь ИД станции проверяю отдельно, ибо в dependencies ограничиваю взаимодействие со станцией, у которой статус
	# "обслуживание"
	station_control = await StationControl.get_relation_data(station, db)
	if station_control.status != StationStatusEnum.AWAITING:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Station status must be awaiting")

	existing_started_log = await crud_logs.get_last_maintenance_log(station_id, current_user.id, db)

	if not existing_started_log:
		log = StationMaintenanceLog(
			station_id=station.id,
			user_id=current_user.id
		)
		created_log = await crud_logs.create_log(log, db)

		await db.execute(
			update(StationControl).where(StationControl.station_id == station_id).values(
				**stations.StationControlUpdate(status=StationStatusEnum.MAINTENANCE).dict()  # остальное там нулевое
			)
		)
		await db.commit()

		logger.info(f"User {current_user.email} started the maintenance of station {station_id}")

		return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(created_log))
	else:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not ended station maintenance exists")


@router.put("/" + LogTypeEnum.MAINTENANCE.value + "/{station_id}", tags=["maintenance_logs"],
			responses=openapi.station_maintenance_log_put, response_model=logs.StationMaintenanceLog)
async def station_maintenance_log(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station_id: Annotated[uuid.UUID, Path(title="ИД станции")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Окончание обслуживания станции.
	Чтобы закончить обслуживание, оно должно существовать =)

	Доступно для INSTALLER-пользователей и выше.
	"""
	existing_started_log = await crud_logs.get_last_maintenance_log(station_id, current_user.id, db)

	station = await Station.get_station_by_id(db=db, station_id=station_id)
	if not station:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")

	if existing_started_log:
		end_time = datetime.datetime.now()
		await db.execute(
			update(StationMaintenanceLog).where(
				StationMaintenanceLog.id == existing_started_log.id
			).values(ended_at=end_time)
		)
		await db.execute(
			update(StationControl).where(StationControl.station_id == station_id).values(
				status=StationStatusEnum.AWAITING
			)  # возвращение статуса
		)
		await db.commit()

		logger.info(f"User {current_user.email} ended the maintenance of station {station_id}")

		existing_started_log.ended_at = end_time
		return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder(existing_started_log))
	else:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Station maintenance not found")

