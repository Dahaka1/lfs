from typing import Optional

from pydantic import BaseModel, Field, UUID4, validator

import services
from ..static.enums import StationStatusEnum
from . import validators


class StationBase(BaseModel):
	"""
	Модель станции (базовые параметры).
	"""
	is_protected: bool = Field(title='"Под охраной"/нет')


class StationRelation(BaseModel):
	"""
	Модель для наследования station_id побочными моделями (таблицами).

	Опциональный УУИД для того, чтобы в главной модели Station
	 не было лишних ссылок на ИД в собранных побочных моделях.
	"""
	station_id: Optional[UUID4] = Field(title="Уникальный номер станции")


class StationCreate(StationBase):
	"""
	Создание станции.
	"""
	is_active: Optional[bool] = Field(title="Активна/неактивна")
	wifi_name: str = Field(min_length=1, title="Имя точки доступа WiFi")
	wifi_password: str = Field(min_length=1, title="Пароль для точки доступа WiFi")
	washing_machines_amount: Optional[int] = Field(title="Количество стиральных машин у станции",
												   default=services.DEFAULT_STATION_WASHING_MACHINES_AMOUNT)
	washing_agents_amount: Optional[int] = Field(title="Количество стиральных средств у станции",
												 default=services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT)


class StationGeneralParams(StationBase):
	"""
	Основные параметры станции (таблица station).
	"""
	id: UUID4 = Field(title="Уникальный номер станции")
	is_active: bool = Field(title="Активна/неактивна")
	hashed_wifi_data: str = Field(title="Хэшированные данные Wi-Fi (JWT)")


class StationSettings(StationRelation):
	"""
	Настройки станции (таблица station_settings).
	"""
	station_power: bool = Field(title="Включена/выключена")
	teh_power: bool = Field(title="ТЭН включен/выключен")


class StationProgram(StationRelation):
	"""
	Программы станции (таблица station_program).
	"""
	program_step: int = Field(ge=11, title="Шаг (этап) программы станции", example="11-15, 21-25, 31-35, ...")
	program_number: int = Field(ge=1, title="Номер программы станции", example="1, 2, 3, ...")
	washing_agent_numbers_and_dosages: dict[int, int] = Field(
		title="Стиральные средства станции и дозировки", example="{1: 50, 2: 40, 3: 10, ...}"
	)

	@validator("program_step")
	def validate(cls, program_step):
		"""
		Этап программы заканчивается на 1-5.
		"""
		return validators.validate_program_step(program_step)


class StationControl(StationRelation):
	"""
	Текущее состояние и контроль над станцией (таблица station_control).
	Должна быть указана ЛИБО программа, ЛИБО номер средства и доза.
	Номер стиральной машины указан всегда.
	Доп. инфо см. в models.
	"""
	status: StationStatusEnum = Field(title="Статус станции")
	program_step: Optional[int] = Field(ge=11, title="Шаг (этап) программы станции", example="11-15, 21-25, 31-35, ...")
	washing_machine_number: int = Field(title="Номер стиральной машины станции")
	washing_agent_numbers_and_dosages: Optional[dict[int, int]] = Field(
		title="Стиральные средства станции и дозировки", example="{1: 50, 2: 40, 3: 10, ...}"
	)

	@validator("program_step")
	def validate(cls, program_step):
		"""
		Этап программы заканчивается на 1-5.
		"""
		return validators.validate_program_step(program_step)

	@validator("status", "program_step", "washing_machine_number", "washing_agent_numbers_and_dosages")
	def validate(cls, status, program_step, washing_machine_number, washing_agent_numbers_and_dosages):
		"""
		Когда станция в ожидании - параметры работы не могут быть определены.
		Когда станция в работе - не могут быть определены сразу все параметры.
		"""
		match status:
			case StationStatusEnum.AWAITING.value:
				if any(
					(program_step, washing_machine_number, washing_agent_numbers_and_dosages)
				):
					raise ValueError("While station status is AWAITING, all params must be null")
			case StationStatusEnum.WORKING.value:
				if not any(
					(program_step, washing_machine_number, washing_agent_numbers_and_dosages)
				):
					raise ValueError("While station status is WORKING, program_step OR washing_machine_number "
									 "and washing_agent_numbers_and_dosages must be not null")
				elif all(
					(program_step, washing_machine_number, washing_agent_numbers_and_dosages)
				):
					raise ValueError("While station status is WORKING, "
									 "only one of params (program_step OR washing_machine_number "
									 "and washing_agent_numbers_and_dosages) must be not null")
		return status, program_step, washing_machine_number, washing_agent_numbers_and_dosages


class Station(StationGeneralParams, StationSettings, StationControl):
	"""
	В этой модели собираются данные из ВСЕХ таблиц по станции с нужным ИД.
	"""
	id: UUID4 = Field(title="Уникальный номер станции")
	station_programs: list[StationProgram] = Field(title="Программы станции")

