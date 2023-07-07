from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint, Boolean, UUID

from ..database import Base

import services


class WashingMachine(Base):
	"""
	Стиральная машина.
	
	Number - порядковый номер машины, подключенной к станции.
	Volume - вместимость машины (кг).
	Is_active - активна или нет.
	"""
	__tablename__ = "washing_machine"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "machine_number", name="station_id_machine_number_pkey"),
	)

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	machine_number = Column(Integer, index=True)
	volume = Column(Integer, default=services.DEFAULT_WASHING_MACHINES_VOLUME)
	is_active = Column(Boolean, default=services.DEFAULT_STATION_IS_ACTIVE)


class WashingAgent(Base):
	"""
	Стиральное средство.

	Number - номер стирального средства, подаваемого станцией.
	Concentration_rate - Коэффициент концентрации средства.
	Rollback - "откат" средства.
	"""
	__tablename__ = "washing_agent"
	__table_args__ = (
		PrimaryKeyConstraint("station_id", "agent_number", name="station_id_agent_number_pkey"),
	)

	station_id = Column(UUID, ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"), index=True)
	agent_number = Column(Integer, index=True)
	concentration_rate = Column(Integer, default=services.DEFAULT_WASHING_AGENTS_CONCENTRATION_RATE)
	rollback = Column(Boolean, default=services.DEFAULT_WASHING_AGENTS_ROLLBACK)
	