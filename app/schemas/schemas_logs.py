import datetime
from typing import Optional

from pydantic import BaseModel, Field, root_validator, UUID4

import services
from ..static.enums import LogCaseEnum, ErrorTypeEnum, LogFromEnum, LogActionEnum


class LogCreate(BaseModel):
	"""
	Создание лога.
	ИД станции опционально, ибо можно определить автоматически при авторизации станции
	 в Path Operation и т.д.
	"""
	station_id: Optional[UUID4] = Field(title="ИД станции")
	code: float | int = Field(title="Код лога/ошибки")
	event: str | None = Field(title="Определение (описание) события (раздела лога)")
	content: str = Field(title="Содержание лога/ошибки")

	@root_validator()
	def get_log_event(cls, values):
		event = values.get("event")
		if not event:
			code = values.get("code")
			if code:
				try:
					values["event"] = str(LogCaseEnum(code))
				except KeyError:
					raise ValueError("Got an non-existing log/error code")
		return values


class ErrorCreate(LogCreate):
	"""
	Создание ошибки.
	"""
	scope: ErrorTypeEnum | None = Field(title="Видимость ошибки (публичная/служебная)")

	@root_validator()
	def get_error_scope(cls, values):
		scope = values.get("scope")
		if not scope:
			values["scope"] = services.DEFAULT_ERROR_SCOPE
		return values


class Log(LogCreate):
	"""
	Вывод лога.
	"""
	id: int
	station_id: UUID4 = Field(title="ИД станции")
	sended_from: LogFromEnum = Field(title="От станции/сервера")
	timestamp: datetime.datetime = Field(title="Время создания лога")
	event: str = Field(title="Определение (описание) события (раздела лога)")
	action: Optional[LogActionEnum] = Field(title="Совершенное действие после добавления лога")

	class Config:
		orm_mode = True


class Error(Log):
	"""
	Вывод ошибки.
	"""
	scope: ErrorTypeEnum = Field(title="Видимость ошибки (публичная/служебная)")
