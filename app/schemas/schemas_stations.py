import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, UUID4, validator, root_validator

import services
from . import validators
from .schemas_washing import WashingAgent, WashingMachine, WashingMachineUpdate, WashingAgentUpdate, \
	WashingAgentWithoutRollback, WashingAgentCreateMixedInfo, WashingMachineCreateMixedInfo
from ..static.enums import StationStatusEnum, RegionEnum


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
	id: UUID4 = Field(title="Уникальный ID станции")
	serial: str = Field(title="Серийный номер станции")
	created_at: Optional[datetime.datetime] = Field(title="Дата/время создания станции",
													description="Может быть пустым, если станция еще не выпущена")
	updated_at: Optional[datetime.datetime] = Field(title="Дата/время последнего обновления (основных параметров станции)")
	is_active: bool = Field(title="Активна/неактивна")
	is_protected: bool = Field(title='"Под охраной"/нет')
	location: dict = Field(title="Координаты местоположения станции")
	region: RegionEnum = Field(title="Регион станции")
	comment: Optional[str] = Field(title="Комментарий (заметка) о станции")

	@validator("location")
	def validate_location(cls, location):
		"""
		Location - словарь с данными о геолокации.
		"""
		lng, lat = location.get("longitude"), location.get("latitude")
		if lng is None or lat is None:
			raise ValueError(f"Invalid station location data")
		return location

	class Config:
		orm_mode = True


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

	class Config:
		orm_mode = True


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
		if program_number:  # он опциональный
			validators.validate_program_number(program_step, program_number)
		return values


class StationProgramCreate(StationProgram):
	"""
	Создание программы станции.
	"""
	program_number: Optional[int] = Field(ge=1, title="Номер программы станции", example="1, 2, 3, ...")
	updated_at: Any = Field(exclude=True)
	washing_agents: list[WashingAgentWithoutRollback | int] = Field(
		title="Стиральные средства станции и дозировки"
	)

	@validator("washing_agents")
	def validate_washing_agents(cls, washing_agents):
		"""
		Нельзя дублировать стиральные средства.
		"""
		washing_agents_numbers = [
			ag.agent_number if isinstance(ag, WashingAgent) else ag for ag in washing_agents
		]
		if any(
			(washing_agents_numbers.count(ag_number) > 1 for ag_number in washing_agents_numbers)
		):
			raise ValueError("Got an washing agents numbers duplicate")
		return washing_agents

	@root_validator()
	def auto_fill_program_number(cls, values):
		"""
		Номер программы - это первые цифры (количество десятков) числа, обозначающего шаг программы.

		Нельзя указать номер программы без номера этапа (шага).
		Если указан шаг программы - номер программы определится автоматически.
		"""
		program_step, program_number = values.get("program_step"), values.get("program_number")
		if program_step and program_number:
			validators.validate_program_number(program_step, program_number)
		elif program_number and not program_step:
			raise ValueError("Got an program number, but program step wasn't defined")
		elif program_step and not program_number:
			values["program_number"] = program_step // 10
		return values


class StationProgramUpdate(StationProgramCreate):
	"""
	Обновление программы станции.
	"""
	program_step: Optional[int] = Field(ge=11, title="Новый шаг (этап) программы станции",
										example="11-15, 21-25, 31-35, ...")
	washing_agents: Optional[list[WashingAgentWithoutRollback | int]] = Field(
		title="Стиральные средства станции и дозировки",
		default_factory=list
	)


class StationControl(BaseModel):
	"""
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
	washing_machines_queue: Optional[list[int]] = Field(
		title="Очередь стиральных машин для работы",
		description="Номера стиральных машин станции в текущем порядке очереди",
		example="[1, 3, 5, 7, 6]",
		default_factory=list
	)
	updated_at: Optional[datetime.datetime] = Field(title="Дата и время последнего обновления (состояния станции)")

	@validator("program_step")
	def validate_program_step(cls, program_step):
		"""
		Этап программы заканчивается на 1-5.
		"""
		if program_step:
			validators.validate_program_step(program_step.program_step)
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
			case StationStatusEnum.AWAITING | StationStatusEnum.ERROR:
				if any(
					(program_step, washing_machine, any(washing_agents))
				):
					raise ValueError("While station status is AWAITING/ERROR, all params must be null")
			case StationStatusEnum.WORKING:
				if not washing_machine:
					raise ValueError(f"While station status is WORKING, washing machine can't be null")
				if not program_step and not any(washing_agents):
					raise ValueError("While station status is WORKING, program step or washing agents "
									 "must be defined")
				elif program_step and any(washing_agents):
					raise ValueError("While station status is WORKING, "
									 "only one of params (program step, washing agents) could be chosen")

		return values

	class Config:
		orm_mode = True


class StationControlUpdate(StationControl):
	"""
	Обновление станции (текущего состояния).
	"""
	@root_validator()
	def update_updated_at_field(cls, values):
		return validators.update_updated_at_field(values)


class Station(StationGeneralParams):
	"""
	В этой модели собираются данные из ВСЕХ таблиц по станции с нужным ИД.

	По умолчанию (при создании) у станции нет программ, поэтому параметр опциональный.
	"""
	station_programs: Optional[list[StationProgram]] = Field(title="Программы станции",
																						default_factory=list)
	station_washing_machines: list[WashingMachine] = Field(title="Стиральные машины станции")
	station_washing_agents: list[WashingAgent] = Field(title="Стиральные средства станции")
	station_control: StationControl
	station_settings: StationSettings


class StationForStation(Station, StationGeneralParamsForStation):
	pass


class StationCreate(BaseModel):
	"""
	Создание станции.
	"""
	serial: str = Field(title="Серийный номер станции", min_length=3, max_length=10)
	is_active: Optional[bool] = Field(title="Активна/неактивна", default=services.DEFAULT_STATION_IS_ACTIVE)
	is_protected: Optional[bool] = Field(title='"Под охраной"/нет', default=services.DEFAULT_STATION_IS_PROTECTED)
	wifi_name: str = Field(min_length=1, title="Имя точки доступа WiFi")
	wifi_password: str = Field(min_length=1, title="Пароль для точки доступа WiFi")
	comment: Optional[str] = Field(title="Комментарий (заметка) о станции", max_length=200)
	washing_machines_amount: Optional[int] = Field(title="Количество стиральных машин у станции",
												   ge=services.MIN_STATION_WASHING_MACHINES_AMOUNT,
												   le=services.MAX_STATION_WASHING_MACHINES_AMOUNT,
												   default=services.DEFAULT_STATION_WASHING_MACHINES_AMOUNT)
	washing_agents_amount: Optional[int] = Field(title="Количество стиральных средств у станции",
												 ge=services.MIN_STATION_WASHING_AGENTS_AMOUNT,
												 le=services.MAX_STATION_WASHING_AGENTS_AMOUNT,
												 default=services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT)
	address: str = Field(max_length=200, title="Физический адрес местоположения станции",
						 example="Санкт-Петербург, ул. Дыбенко, 26")
	region: RegionEnum = Field(title="Регион станции")

	settings: Optional[StationSettingsCreate] = Field(title="Настройки станции", default=None)
	programs: Optional[list[StationProgramCreate]] = Field(title="Программы станции", default=None)
	washing_agents: Optional[list[WashingAgentCreateMixedInfo]] = Field(title="Стиральные средства станции",
																		default=None)
	washing_machines: Optional[list[WashingMachineCreateMixedInfo]] = Field(title="Стиральные машины станции",
																			default=None)

	@validator("address")
	def validate_address(cls, address):
		validators.validate_address(address)
		return address

	@validator("serial")
	def validate_serial(cls, serial):
		serial: str
		if any(
			(not ch.isdigit() for ch in serial)
		):
			raise ValueError("Expected for only digits at station serial number")
		return serial

	@root_validator()
	def validate_params(cls, values):
		washing_agents, washing_machines = values.get("washing_agents"), values.get("washing_machines")

		services_objects_amount = {
			"washing_agents": range(services.MIN_STATION_WASHING_AGENTS_AMOUNT,
									services.MAX_STATION_WASHING_AGENTS_AMOUNT + 1),
			"washing_machines": range(services.MIN_STATION_WASHING_MACHINES_AMOUNT,
									  services.MAX_STATION_WASHING_MACHINES_AMOUNT + 1)
		}
		if washing_agents:
			objects_amount_range = services_objects_amount["washing_agents"]
			if len(washing_agents) not in objects_amount_range:
				raise ValueError(f"Ensure that washing agents amount in {objects_amount_range}")
			for agent in washing_agents:
				if [ag.agent_number for ag in washing_agents].count(agent.agent_number) > 1:
					raise ValueError("Got an duplicated washing agent numbers")

		if washing_machines:
			objects_amount_range = services_objects_amount["washing_machines"]
			if len(washing_machines) not in objects_amount_range:
				raise ValueError(f"Ensure that washing machines amount in {objects_amount_range}")
			for machine in washing_machines:
				if [m.machine_number for m in washing_machines].count(machine.machine_number) > 1:
					raise ValueError("Got an duplicated washing machines numbers")

		# __________________________________________________________________________________

		is_active, settings = values.get("is_active"), values.get("settings")
		if is_active is False and settings:
			if settings.station_power is True or settings.teh_power is True:
				raise ValueError("Inactive station hasn't to be powered on (or its TEH)")

		# __________________________________________________________________________________

		programs = values.get("programs")
		if programs:
			for program in programs:
				if [pg.program_step for pg in programs].count(program.program_step) > 1:
					raise ValueError("Got an program step number duplicate")

		return values

