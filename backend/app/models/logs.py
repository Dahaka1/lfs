from loguru import logger
from sqlalchemy import JSON, Column, String, Integer, ForeignKey, UUID, insert, func, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Base
from ..schemas.schemas_stations import StationGeneralParams
from ..schemas.schemas_users import User


class ErrorsLog(Base):
	"""
	Логирование ошибок в БД.

	Code - код ошибки.
	Content - содержание (описание) ошибки.
	"""
	__tablename__ = "errors_log"

	id = Column(Integer, primary_key=True)
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
	code = Column(Integer)
	content = Column(String)


class WashingAgentsUsingLog(Base):
	"""
	Журнал подачи стиральных средств.

	Washing_machine - стиральная машина.
	Washing_agent - стиральное средство.
	Dosage - количество средства.
	"""
	__tablename__ = "washing_agents_using_log"

	id = Column(Integer, primary_key=True)
	timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	washing_machine = Column(JSON)
	washing_agent = Column(JSON)


class ChangesLog(Base):
	"""
	Журнал изменений (изменений от пользователей).

	Station_id - ИД станции, относительно которой произошли изменения.
	User_id - ИД пользователя, совершившего изменения.
	Content - содержание (описание) изменения.
	"""
	__tablename__ = "changes_log"

	id = Column(Integer, primary_key=True)
	timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"))
	content = Column(String, nullable=False)

	@staticmethod
	async def log(db: AsyncSession, user: User, station: StationGeneralParams, content: str) -> None:
		"""
		Добавление записи в лог.
		"""
		query = insert(ChangesLog).values(
			station_id=station.id, user_id=user.id, content=content
		)

		await db.execute(query)
		await db.commit()

		logger.info(content)


class StationProgramsLog(Base):
	"""
	Журнал выполнения станциями программ.

	Station_id - ИД станции.
	Program_step - этап программы.
	"""
	__tablename__ = "station_programs_log"

	id = Column(Integer, primary_key=True)
	timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	program_step = Column(JSON)


class StationMaintenanceLog(Base):
	"""
	Журнал обслуживания станции

	Station_id - ИД станции.
	User_id - ИД пользователя, производившего обслуживание.
	"""
	__tablename__ = "station_maintenance_log"

	id = Column(Integer, primary_key=True)
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"))
	started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
	ended_at = Column(TIMESTAMP(timezone=True))

