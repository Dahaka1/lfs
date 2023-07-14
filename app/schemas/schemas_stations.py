import datetime
from typing import Optional, Any, Union

from pydantic import BaseModel, Field, UUID4, validator, root_validator

import services
from ..static.enums import StationStatusEnum, RegionEnum
from . import validators
from .schemas_washing import WashingAgent, WashingMachine, WashingMachineUpdate, WashingAgentUpdate, \
	WashingAgentCreateMixedInfo, WashingAgentWithoutRollback


class StationCreate(BaseModel):
	"""
	Создание станции.
	"""
	is_active: Optional[bool] = Field(title="Активна/неактивна", default=services.DEFAULT_STATION_IS_ACTIVE)
	is_protected: Optional[bool] = Field(title='"Под охраной"/нет', default=services.DEFAULT_STATION_IS_PROTECTED)
	wifi_name: str = Field(min_length=1, title="Имя точки доступа WiFi")
	wifi_password: str = Field(min_length=1, title="Пароль для точки доступа WiFi")
	washing_machines_amount: Optional[int] = Field(title="Количество стиральных машин у станции", ge=0, le=7,
												   default=services.DEFAULT_STATION_WASHING_MACHINES_AMOUNT)
	washing_agents_amount: Optional[int] = Field(title="Количество стиральных средств у станции", ge=0, le=8,
												 default=services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT)
	address: str = Field(max_length=200, title="Физический адрес местоположения станции",
						 example="Санкт-Петербург, ул. Дыбенко, 26")
	region: RegionEnum = Field(title="Регион станции")

	@validator("address")
	def validate_address(cls, address):
		validators.validate_address(address)
		return address


class StationServicesUpdate(BaseModel):
	"""
	Обновление станции (стиральных машин и стиральных средств).
	"""
	station_id: UUID4 = Field(title="Уникальный номер станции")
	washing_machines: Optional[list[WashingMachineUpdate]] = Field(title="Список стиральных машин с новыми параметрами")
	washing_agents: Optional[list[WashingAgentUpdate]] = Field(title="Список стиральных средств с новыми параметрами")


class StationGeneralParams(BaseModel):
	"""
	Основные параметры станции (таблица station).
	"""
	id: UUID4 = Field(title="Уникальный номер станции")
	created_at: datetime.datetime = Field(title="Дата/время создания станции")
	updated_at: Optional[datetime.datetime] = Field(title="Дата/время последнего обновления (основных параметров станции)")
	is_active: bool = Field(title="Активна/неактивна")
	is_protected: bool = Field(title='"Под охраной"/нет')
	location: dict = Field(title="Координаты местоположения станции")
	region: RegionEnum = Field(title="Регион станции")

	@validator("location")
	def validate_location(cls, location):
		"""
		Location - словарь с данными о геолокации.
		"""
		lng, lat = location.get("longitude"), location.get("latitude")
		if lng is None or lat is None:
			raise ValueError(f"Invalid station location data")
		return location


class StationGeneralParamsInDB(StationGeneralParams):
	"""
	Основные параметры станции с данными wifi.
	"""
	hashed_wifi_data: str = Field(title="Хэшированные данные Wi-Fi")


class StationGeneralParamsForStation(StationGeneralParams):
	"""
	Схема станции с расшифрованными данными wifi (только для использования самой станцией).

	... и мб другие параметры, которые нужны для показа только станции.
	"""
	wifi_name: str = Field(min_length=1, title="Имя точки доступа WiFi")
	wifi_password: str = Field(min_length=1, title="Пароль для точки доступа WiFi")


class StationGeneralParamsUpdate(BaseModel):
	"""
	Обновление станции (ее параметров).
	"""
	is_protected: Optional[bool] = Field(title='"Под охраной"/нет')
	is_active: Optional[bool] = Field(title="Активна/неактивна")
	wifi_name: Optional[str] = Field(min_length=1, title="Имя точки доступа WiFi")
	wifi_password: Optional[str] = Field(min_length=1, title="Пароль для точки доступа WiFi")
	address: Optional[str] = Field(max_length=200, title="Физический адрес местоположения станции",
						 example="Санкт-Петербург, ул. Дыбенко, 26")
	region: Optional[RegionEnum] = Field(title="Регион станции")

	@root_validator()
	def validate_wifi_data(cls, values):
		"""
		Проверка заполнения wifi-данных.
		"""
		wifi_name, wifi_password = values.get("wifi_name"), values.get("wifi_password")
		if any((wifi_name, wifi_password)):
			if not all((wifi_name, wifi_password)):
				raise ValueError(f"If wifi data updating, both of fields wifi name and password are expecting")
		return values

	@validator("address")
	def validate_address(cls, address):
		validators.validate_address(address)
		return address


class StationSettings(BaseModel):
	"""
	Настройки станции (таблица station_settings).
	"""
	station_power: bool = Field(title="Включена/выключена")
	teh_power: bool = Field(title="ТЭН включен/выключен")
	updated_at: Optional[datetime.datetime] = Field(title="Дата и время последнего обновления (настроек станции)")


class StationSettingsCreate(BaseModel):
	"""
	Создание записи о настройках станции в БД.
	"""
	station_power: Optional[bool] = Field(title="Включена/выключена", default=services.DEFAULT_STATION_POWER)
	teh_power: Optional[bool] = Field(title="ТЭН включен/выключен", default=services.DEFAULT_STATION_TEH_POWER)


class StationSettingsUpdate(StationSettingsCreate):
	"""
	Изменение настроек станции.
	"""
	station_power: Optional[bool] = Field(title="Включена/выключена")
	teh_power: Optional[bool] = Field(title="ТЭН включен/выключен")


class StationProgram(BaseModel):
	"""
	Программы станции (таблица station_program).
	"""
	program_step: int = Field(ge=11, title="Шаг (этап) программы станции", example="11-15, 21-25, 31-35, ...")
	program_number: int = Field(ge=1, title="Номер программы станции", example="1, 2, 3, ...")
	washing_agents: list[WashingAgentWithoutRollback] = Field(
		title="Стиральные средства станции и дозировки"
	)
	updated_at: Optional[datetime.datetime] = Field(title="Дата и время последнего обновления (программы станции)")

	@validator("program_step")
	def validate_program_step(cls, program_step):
		"""
		Этап программы заканчивается на 1-5.
		"""
		validators.validate_program_step(program_step)
		return program_step

	@root_validator()
	def validate_program_number(cls, values):
		"""
		Номер программы - это первые цифры (количество десятков) числа, обозначающего шаг программы.
		"""
		program_step, program_number = values.get("program_step"), values.get("program_number")
		validators.validate_program_number(program_step, program_number)
		return values


class StationProgramCreate(StationProgram):
	"""
	Создание программы станции.
	Washing_agents: list[WashingAgentCreateMixedInfo] | list[int]
	"""
	updated_at: Any = Field(exclude=True)
	washing_agents: list[WashingAgentCreateMixedInfo] | list[int] = Field(
		title="Стиральные средства станции и дозировки"
	)


class StationProgramUpdate(StationProgramCreate):
	"""
	Обновление программы станции
	"""
	washing_agents: Optional[list[WashingAgentCreateMixedInfo] | list[int]] = Field(
		title="Стиральные средства станции и дозировки"
	)


class StationControl(BaseModel):
	"""
	Эта модель - для вывода ОТДЕЛЬНО от общей инфы станции (указан station_id).
	То есть, когда станция опрашивает сервер на предмет текущего состояния.

	Когда станция выключена (power off), статус NONE.

	Текущее состояние и контроль над станцией (таблица station_control).
	Должна быть указана ЛИБО программа, ЛИБО номер средства и доза.
	Номер стиральной машины указан всегда (если статус "подача").
	Доп. инфо см. в models.
	"""
	status: Optional[StationStatusEnum] = Field(title="Статус станции")
	program_step: Optional[StationProgram] = Field(title="Этап программы станции")
	washing_machine: Optional[WashingMachine] = Field(
		title="Стиральная машина станции"
	)
	washing_agents: Optional[list[WashingAgentWithoutRollback]] = Field(
		title="Стиральные средства станции, используемые в данный момент",
		default_factory=list
	)
	updated_at: Optional[datetime.datetime] = Field(title="Дата и время последнего обновления (состояния станции)")

	@validator("program_step")
	def validate_program_step(cls, program_step):
		"""
		Этап программы заканчивается на 1-5.
		"""
		validators.validate_program_step(program_step)
		return program_step

	@root_validator()
	def validate_station_control(cls, values):
		"""
		Когда станция в ожидании - параметры работы не могут быть определены.
		Когда станция в работе - не могут быть определены сразу все параметры.
		"""
		status, program_step, washing_machine, washing_agents = values.get("status"), \
			values.get("program_step"), values.get("washing_machine"), \
			values.get("washing_agents")
		match status:
			case StationStatusEnum.AWAITING.value:
				if any(
					(program_step, washing_machine, any(washing_agents))
				):
					raise ValueError("While station status is AWAITING, all params must be null")
			case StationStatusEnum.WORKING.value:
				if not any(
					(program_step, any(washing_agents))
				):
					raise ValueError("While station status is WORKING, program_step OR washing_machine_number "
									 "and washing_agent_numbers_and_dosages must be not null")
				elif all(
					(program_step, any(washing_agents))
				):
					raise ValueError("While station status is WORKING, "
									 "only one of params (program_step OR washing_machine_number "
									 "and washing_agent_numbers_and_dosages) must be not null")

		return values


class StationControlUpdate(StationControl):
	"""
	Обновление станции (текущего состояния).
	"""
	updated_at: Any = Field(exclude=True)


class Station(StationGeneralParams):
	"""
	В этой модели собираются данные из ВСЕХ таблиц по станции с нужным ИД.

	По умолчанию (при создании) у станции нет программ, поэтому параметр опциональный.
	"""
	id: UUID4 = Field(title="Уникальный номер станции")
	station_programs: Optional[list[StationProgram]] = Field(title="Программы станции",
																						default_factory=list)
	station_washing_machines: list[WashingMachine] = Field(title="Стиральные машины станции")
	station_washing_agents: list[WashingAgent] = Field(title="Стиральные средства станции")
	station_control: StationControl
	station_settings: StationSettings


class StationForStation(Station, StationGeneralParamsForStation):
	pass


class StationPartial(BaseModel):
	"""
	   Схема для ответа по запросу определенных данных станцией (а не всех).
	   """
	partial_data: Union[
		StationGeneralParamsForStation,
		list[StationProgram],
		StationSettings,
		StationControl,
		list[WashingMachine],
		list[WashingAgent]
	] = Field(title="Запрашиваемый набор параметров станции")


class StationPartialForUser(BaseModel):
	"""
	Схема для ответа по запросу определенных данных станцией пользователем.
	"""
	partial_data: Union[
		StationGeneralParams,
		list[StationProgram],
		StationSettings,
		StationControl,
		list[WashingMachine],
		list[WashingAgent]
	] = Field(title="Запрашиваемый набор параметров станции")

