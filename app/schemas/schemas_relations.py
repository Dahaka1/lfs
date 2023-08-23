from pydantic import BaseModel, Field, UUID4

from .schemas_users import User
from .schemas_stations import StationGeneralParams


class LaundryStations(BaseModel):
	user: User
	stations: list[StationGeneralParams] = Field(default_factory=list)

	class Config:
		orm_mode = True
