import uuid

from sqlalchemy import Enum, Column, Integer, String, Boolean, ForeignKey, \
	ForeignKeyConstraint, UUID

from ..database import Base

import services
from ..static.enums import StationStatusEnum


class Station(Base):
	"""
	Модель станции.

	ID - генерируемый UUID для каждой станции.
	Is_active - активна или нет.
	Is_protected - включена "охрана" или нет.
	Hashed_auth_code - JWT-токен для активации станции.
	Hashed_wifi_data - JWT-токен с данными WiFi для станции (бессрочный, получается при активации).
	"""
	__tablename__ = "station"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	is_active = Column(Boolean, default=services.DEFAULT_STATION_IS_ACTIVE)
	is_protected = Column(Boolean)
	hashed_wifi_data = Column(String)


class StationSettings(Base):
	"""
	Настройки станции.

	Station_power- вкл/выкл.
	Teh_power - вкл/выкл ТЭНа.
	"""
	__tablename__ = "station_settings"

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True,
						index=True)
	station_power = Column(Boolean, default=services.DEFAULT_STATION_POWER)
	teh_power = Column(Boolean, default=services.DEFAULT_STATION_TEH_POWER)


class StationProgram(Base):
	"""
	Программы (дозировки) станции.

	Program_step - номер метки (этапа/"шага") программы станции (11-15, 21-25, ...).
	Program_number - номер программы станции (определяется по первой цифре шага программы, и наоборот).
	Washing_agent_id - ИД стирального средства.
	Dosage - доза (мл/кг).
	"""
	__tablename__ = "station_program"
	__table_args__ = (
		ForeignKeyConstraint(["station_id", "washing_agent_number"],
							 ["washing_agent.station_id", "washing_agent.agent_number"]),
	)

	id = Column(Integer, primary_key=True)
	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	program_step = Column(Integer, nullable=False)
	program_number = Column(Integer, nullable=False)
	washing_agent_number = Column(Integer)
	dosage = Column(Integer, default=services.DEFAULT_STATION_DOSAGE)


class StationControl(Base):
	"""
	Контроль и управление станцией.
	Может быть установлена программа ИЛИ средство + доза.

	Status - статус станции.
	Program_step - номер этапа программы (включает в себя информацию о номере программы).
	Washing_machine_number - номер стиральной машины.
	Washing_agent_number - номер стирального средства.
	Dosage - доза подаваемого средства.

	В данном варианте единовременно может быть только одна запись по станции на стиральную машину
	 (подача одного средства в стиральную машину, стиральных машин может быть несколько).
	Возможно, нужно будет добавить ID-колонку, чтобы можно было добавлять подачу нескольких средств по
	 каждой стиральной машине.
	"""
	__tablename__ = "station_control"
	__table_args__ = (
		ForeignKeyConstraint(["station_id", "washing_machine_number"],
							 ["washing_machine.station_id", "washing_machine.machine_number"]),
		ForeignKeyConstraint(["station_id", "washing_agent_number"],
							 ["washing_agent.station_id", "washing_agent.agent_number"])
	)

	station_id = Column(UUID, ForeignKey("station.id", onupdate="CASCADE",
											ondelete="CASCADE"), primary_key=True, index=True)
	status = Column(Enum(StationStatusEnum))
	program_step = Column(Integer, ForeignKey("station_program.id", onupdate="CASCADE",
											ondelete="CASCADE"))
	washing_machine_number = Column(Integer, nullable=False)
	washing_agent_number = Column(Integer)
	dosage = Column(Integer)
