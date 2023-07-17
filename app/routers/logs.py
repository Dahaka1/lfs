from typing import Annotated

from fastapi import APIRouter, Depends, Body, Path, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import pydantic

from ..dependencies.stations import get_current_station, get_station_by_id
from ..dependencies import get_async_session
from ..dependencies.users import get_current_active_user
from ..schemas import schemas_logs as logs, schemas_stations as stations, schemas_users as users
from ..static.enums import RoleEnum as roles, LogTypeEnum
from ..crud import crud_logs
from ..exceptions import PermissionsError
from ..utils.logs import parse_log_class


router = APIRouter(
	prefix="/logs",
	tags=["logs"]
)


@router.post("/{log_type}", response_description="Созданный лог")
async def log_error(
	station: Annotated[stations.StationGeneralParams, Depends(get_current_station)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	log_type: Annotated[LogTypeEnum, Path(title="Тип логов")],
	log: Annotated[logs.LogCreate, Body(title="Содержание лога")]
):
	"""
	Логирование действий станции.
	Логировать по этому маршруту изменения данных станции нельзя - они логируются только автоматически.

	Доступно только для станции.
	"""
	if log_type == LogTypeEnum.CHANGES:
		raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

	log_types = {
		LogTypeEnum.ERRORS: logs.ErrorLogCreate,
		LogTypeEnum.PROGRAMS_USING: logs.StationProgramsLogCreate,
		LogTypeEnum.WASHING_AGENTS_USING: logs.WashingAgentUsingLogCreate
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


@router.get("/{log_type}/{station_id}", response_description="Логи выбранного типа")
async def get_station_errors_log(
	current_user: Annotated[users.User, Depends(get_current_active_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
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
	- Выполнение программ: LAUNDRY и выше.
	"""
	logs_getting_roles = {
		LogTypeEnum.ERRORS: (roles.INSTALLER, roles.MANAGER, roles.SYSADMIN),
		LogTypeEnum.WASHING_AGENTS_USING: (roles.INSTALLER, roles.MANAGER, roles.SYSADMIN),
		LogTypeEnum.CHANGES: (roles.MANAGER, roles.SYSADMIN),
		LogTypeEnum.PROGRAMS_USING: (roles.INSTALLER, roles.MANAGER, roles.SYSADMIN, roles.LAUNDRY)
	}

	if current_user.role not in logs_getting_roles[log_type]:
		raise PermissionsError()

	log_cls = parse_log_class(log_type)

	return await crud_logs.get_station_logs(station, log_cls, db)



