import datetime
import uuid

from pydantic import BaseModel, Field

from .schemas_washing import WashingAgent, WashingMachine
from .schemas_stations import StationProgram


class ErrorBase(BaseModel):
	"""
	Схема для ошибки в логах (основные параметры).
	"""
	station_id: uuid.UUID = Field(title="ИД станции, к которой относится ошибка")
	code: int = Field(title="Код ошибки")
	content: str = Field(title="Содержание (описание) ошибки")


class ErrorCreate(ErrorBase):
	"""
	Создание ошибки.
	"""
	pass


class Error(ErrorBase):
	"""
	Ошибка.
	"""
	id: int = Field(title="ИД ошибки")
	timestamp: datetime.datetime = Field("Дата и время создания ошибки")


class WashingAgentUsingLogBase(BaseModel):
	"""
	Логирование использования стиральных средств.
	"""
	station_id: uuid.UUID = Field(title="ИД станции, которая использовала средство")
	washing_machine: WashingMachine = Field(title="Стиральная машина, в которую подавалось средство")
	washing_agent: WashingAgent = Field(title="Стиральное средство")


class WashingAgentUsingLogCreate(WashingAgentUsingLogBase):
	"""
	Создание лога.
	"""
	pass


class WashingAgentUsingLog(WashingAgentUsingLogBase):
	"""
	Лог.
	"""
	id: int = Field("ИД лога")
	timestamp: datetime.datetime = Field("Дата и время создания лога")


class StationProgramsLogBase(BaseModel):
	"""
	Логирование использования программ станцией.
	"""
	station_id: uuid.UUID = Field(title="ИД станции, которая использовала средство")
	program_step: StationProgram = Field(title="Программа станции")


class StationProgramsLogCreate(StationProgramsLogBase):
	"""
	Создание лога.
	"""
	pass


class StationProgramsLog(StationProgramsLogBase):
	"""
	Лог.
	"""
	id: int = Field("ИД лога")
	timestamp: datetime.datetime = Field("Дата и время создания лога")

