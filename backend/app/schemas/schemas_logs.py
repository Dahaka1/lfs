import datetime
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from .schemas_stations import StationProgram
from .schemas_washing import WashingAgentWithoutRollback, WashingMachine


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
	Схема для лога использования стиральных средств станцией.
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
	Схема для лога использования программ станцией.
	"""
	id: int = Field(title="ИД лога")
	timestamp: datetime.datetime = Field("Дата и время создания лога")


class ChangesLog(BaseModel):
	"""
	Схема для логов изменений.
	"""
	id: int = Field(title="ИД лога")
	timestamp: datetime.datetime = Field("Дата и время создания лога")
	station_id: uuid.UUID = Field(title="ИД станции, данные которой были изменены")
	user_id: int = Field(title="ИД юзера, совершившего изменение")
	content: str = Field(title="Содержание (описание) изменения")


class StationMaintenanceLog(BaseModel):
	"""
	Схема для логов обслуживания станции.
	"""
	id: int = Field(title="ИД лога")
	station_id: uuid.UUID = Field(title="ИД станции, которая обслуживалась")
	user_id: int = Field(title="ИД юзера, совершившего обслуживание")
	started_at: datetime.datetime = Field(title="Начало обслуживания")
	ended_at: Optional[datetime.datetime] = Field(title="Конец обслуживания")


class LogCreate(BaseModel):
	"""
	Схема для создания лога.
	"""
	content: StationProgramsLogCreate | ErrorLogCreate | WashingAgentUsingLogCreate
