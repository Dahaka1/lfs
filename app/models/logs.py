from sqlalchemy import Column, Integer, Float, String, UUID, ForeignKey, Enum, TIMESTAMP, func

from ..database import Base
from ..static.enums import LogFromEnum, ErrorTypeEnum, LogActionEnum


class Log(Base):
	"""
	Логирование событий станцией/сервером.
	"""
	__tablename__ = "logs"

	id = Column(Integer, primary_key=True)
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"))
	code = Column(Float, nullable=False)
	event = Column(String, nullable=False)
	content = Column(String, nullable=False)
	sended_from = Column(Enum(LogFromEnum), nullable=False)
	timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
	action = Column(Enum(LogActionEnum), nullable=True)


class Error(Base):
	"""
	Логирование ошибок станцией/сервером.
	"""
	__tablename__ = "errors"

	id = Column(Integer, primary_key=True)
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"))
	code = Column(Float, nullable=False)
	event = Column(String, nullable=False)
	content = Column(String, nullable=False)
	sended_from = Column(Enum(LogFromEnum), nullable=False)
	timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
	action = Column(Enum(LogActionEnum), nullable=True)
	scope = Column(Enum(ErrorTypeEnum), nullable=False)

