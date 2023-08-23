from sqlalchemy import PrimaryKeyConstraint, Column, Integer, ForeignKey, UUID

from ..database import Base


class LaundryStation(Base):
	"""
	Many-many таблица. Определяет, какие станции относятся к Laundry-пользователю (собственнику).
	Станция не может принадлежать сразу нескольким собственникам.
	"""
	__tablename__ = "users_stations"
	__table_args__ = (
		PrimaryKeyConstraint("user_id", "station_id"),
	)

	user_id = Column(Integer, ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"))
	station_id = Column(UUID(as_uuid=True), ForeignKey("station.id", ondelete="CASCADE", onupdate="CASCADE"),
						unique=True)

