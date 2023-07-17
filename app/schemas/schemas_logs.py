import datetime
import uuid
from typing import Any

from pydantic import BaseModel, Field

from .schemas_washing import WashingAgentWithoutRollback, WashingMachine
from .schemas_stations import StationProgram


class ErrorLogBase(BaseModel):
	"""
	Схема для ошибки в логах (основные параметры).
	"""
	station_id: uuid.UUID = Field(title="ИД станции, к которой относится ошибка")
	code: int = Field(title="Код ошибки")
	content: str = Field(title="Содержание (описание) ошибки")


class ErrorLogCreate(ErrorLogBase):
	"""
	Создание ошибки.
	"""
	station_id: Any = Field(exclude=True)


class ErrorLog(ErrorLogBase):
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
	washing_agent: WashingAgentWithoutRollback = Field(title="Стиральное средство")


class WashingAgentUsingLogCreate(WashingAgentUsingLogBase):
	"""
	Создание лога.
	"""
	station_id: Any = Field(exclude=True)


class WashingAgentUsingLog(WashingAgentUsingLogBase):
	"""
	Лог.
	"""
	id: int = Field(title="ИД лога")
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
	station_id: Any = Field(exclude=True)


class StationProgramsLog(StationProgramsLogBase):
	"""
	Лог.
	"""
	id: int = Field(title="ИД лога")
	timestamp: datetime.datetime = Field("Дата и время создания лога")


class ChangesLog(BaseModel):
	"""
	Схема для логов изменений.
	"""
	id: int = Field(title="ИД лога")
	timestamp: datetime.datetime = Field("Дата и время создания лога")
	station_id: uuid.UUID = Field(title="ИД станции, которая использовала средство")
	user_id: int = Field(title="ИД юзера, совершившего изменение")
	content: str = Field(title="Содержание (описание) изменения")


class LogCreate(BaseModel):
	"""
	Схема для создания лога.
	"""
	content: StationProgramsLogCreate | ErrorLogCreate | WashingAgentUsingLogCreate
