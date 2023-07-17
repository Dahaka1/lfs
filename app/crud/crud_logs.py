from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.logs import ErrorsLog, WashingAgentsUsingLog, StationProgramsLog
from ..models import logs

from ..utils.general import sa_object_to_dict, sa_objects_dicts_list
from ..schemas.schemas_stations import StationGeneralParams


async def create_log(
	log_obj: ErrorsLog | WashingAgentsUsingLog | StationProgramsLog,
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
	query = select(log_class).where(
		log_class.station_id == station.id
	).order_by(log_class.timestamp.desc())

	result = await db.execute(query)

	return sa_objects_dicts_list(result.scalars().all())
