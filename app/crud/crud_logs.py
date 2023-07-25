import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import logs
from ..models.logs import ErrorsLog, WashingAgentsUsingLog, StationProgramsLog, StationMaintenanceLog
from ..schemas import schemas_logs
from ..schemas.schemas_stations import StationGeneralParams
from ..utils.general import sa_object_to_dict, sa_objects_dicts_list


async def create_log(
	log_obj: ErrorsLog | WashingAgentsUsingLog | StationProgramsLog | StationMaintenanceLog,
	db: AsyncSession
):
	"""
	Создание лога.
	"""
	db.add(log_obj)

	await db.commit()
	await db.refresh(log_obj)
	return sa_object_to_dict(log_obj)


async def get_station_logs(
	station: StationGeneralParams,
	log_class: logs,
	db: AsyncSession
):
	"""
	Получение логов станции.
	"""
	match log_class:
		case logs.StationMaintenanceLog:
			query = select(log_class).where(
				log_class.station_id == station.id
			).order_by(log_class.started_at.desc())
		case _:
			query = select(log_class).where(
				log_class.station_id == station.id
			).order_by(log_class.timestamp.desc())

	result = await db.execute(query)

	return sa_objects_dicts_list(result.scalars().all())


async def get_last_maintenance_log(
	station_id: uuid.UUID,
	user_id: int,
	db: AsyncSession
) -> Optional[schemas_logs.StationMaintenanceLog]:
	"""
	Поиск последнего НЕЗАВЕРШЕННОГО лога обслуживания станции юзером.
	"""
	query = select(StationMaintenanceLog).where(
		(StationMaintenanceLog.station_id == station_id) &
		(StationMaintenanceLog.user_id == user_id)
	).order_by(StationMaintenanceLog.started_at.desc()).limit(1)

	result = await db.execute(query)

	log = result.scalar()

	if log:
		log_dict = sa_object_to_dict(log)
		if log_dict["ended_at"] is None:
			return schemas_logs.StationMaintenanceLog(
				**log_dict
			)
