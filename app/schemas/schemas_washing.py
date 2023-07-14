from typing import Optional, Any

from pydantic import BaseModel, Field, UUID4

import services


class WashingMachineBase(BaseModel):
	"""
	Стиральная машина. Основные параметры.
	"""
	machine_number: int = Field(title="Номер стиральной машины", description="Номер относительно станции",
								ge=1, le=7)
	volume: int = Field(title="Вместимость, кг")
	is_active: bool = Field(title="Активна/нет")
	track_length: float = Field(title="Длина трассы, м")


class WashingMachineCreate(WashingMachineBase):
	"""
	Добавление стиральной машины.
	"""
	station_id: UUID4 = Field(title="ИД станции")
	volume: Optional[int] = Field(title="Вместимость, кг", ge=10, le=100,
								  default=services.DEFAULT_WASHING_MACHINES_VOLUME)
	is_active: Optional[bool] = Field(title="Активна/нет", default=services.DEFAULT_STATION_IS_ACTIVE)
	track_length: Optional[float] = Field(title="Длина трассы, м", ge=1,
										  default=services.DEFAULT_WASHING_MACHINES_TRACK_LENGTH)


class WashingMachineCreateMixedInfo(WashingMachineCreate):
	"""
	Создание стиральной машины БЕЗ УКАЗАНИЯ ИД станции.
	Нужно, например, при создании станции.
	"""
	station_id: Any = Field(exclude=True)


class WashingMachine(WashingMachineBase):
	"""
	Основная модель стиральной машины.
	"""
	pass


class WashingMachineUpdate(WashingMachine):
	"""
	Обновление стиральной машины.
	"""
	volume: Optional[int] = Field(title="Вместимость, кг", ge=10, le=100)
	is_active: Optional[bool] = Field(title="Активна/нет")


class WashingMachineInDB(WashingMachine):
	"""
	Стиральная машина в БД (с ИД станции).
	"""
	station_id: UUID4 = Field(title="ИД станции")


class WashingAgentBase(BaseModel):
	"""
	Стиральное средство. Основные параметры.
	"""
	agent_number: int = Field(title="Номер стирального средства", description="Номер относительно станции",
							  ge=1, le=8)
	concentration_rate: int = Field(title="Концентрация средства", ge=0, le=50)
	rollback: bool = Field(title="\"Откат\" средства")


class WashingAgentCreate(WashingAgentBase):
	"""
	Добавление стирального средства.
	"""
	station_id: UUID4 = Field(title="ИД станции")
	concentration_rate: Optional[int] = Field(title="Концентрация средства", ge=1, le=50,
											  default=services.DEFAULT_WASHING_AGENTS_CONCENTRATION_RATE)
	rollback: Optional[bool] = Field(title="\"Откат\" средства", default=services.DEFAULT_WASHING_AGENTS_ROLLBACK)


class WashingAgentCreateMixedInfo(WashingAgentCreate):
	"""
	Создание стирального средства БЕЗ УКАЗАНИЯ ИД станции.
	Нужно, например, при создании станции.
	"""
	station_id: Any = Field(exclude=True)


class WashingAgent(WashingAgentBase):
	"""
	Основная модель стирального средства.
	"""
	pass


class WashingAgentWithoutRollback(WashingAgentBase):
	"""
	Здесь исключается rollback-field.
	Например, вроде как, в программах станции его указывать не нужно.
	"""
	rollback: Any = Field(exclude=True)


class WashingAgentUpdate(WashingAgent):
	"""
	Обновление стирального средства.
	"""
	concentration_rate: Optional[int] = Field(title="Концентрация средства", ge=0, le=50)
	rollback: Optional[bool] = Field(title="\"Откат\" средства")


class WashingAgentInDB(WashingAgent):
	"""
	Стиральное средство в БД (с ИД станции).
	"""
	station_id: UUID4 = Field(title="ИД станции")
