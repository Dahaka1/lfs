from typing import Optional, Any

from pydantic import BaseModel, Field, UUID4

import services


class WashingMachineBase(BaseModel):
	"""
	Стиральная машина. Основные параметры.
	"""
	machine_number: int = Field(title="Номер стиральной машины", description="Номер относительно станции",
								ge=1, le=services.MAX_STATION_WASHING_MACHINES_AMOUNT)
	volume: int = Field(title="Вместимость, кг")
	is_active: bool = Field(title="Активна/нет")
	track_length: float = Field(title="Длина трассы, м")


class WashingMachineCreate(WashingMachineBase):
	"""
	Добавление стиральной машины.
	"""
	station_id: UUID4 = Field(title="ИД станции")
	volume: Optional[int] = Field(title="Вместимость, кг", ge=services.MIN_WASHING_MACHINE_VOLUME,
								  le=services.MAX_WASHING_MACHINE_VOLUME,
								  default=services.DEFAULT_WASHING_MACHINES_VOLUME)
	is_active: Optional[bool] = Field(title="Активна/нет", default=services.DEFAULT_STATION_IS_ACTIVE)
	track_length: Optional[float] = Field(title="Длина трассы, м", ge=services.MIN_WASHING_MACHINE_TRACK_LENGTH,
										  le=services.MAX_WASHING_MACHINE_TRACK_LENGTH,
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


class WashingMachineUpdate(WashingMachineCreateMixedInfo):
	"""
	Обновление стиральной машины.
	"""
	pass


class WashingAgentBase(BaseModel):
	"""
	Стиральное средство. Основные параметры.
	"""
	agent_number: int = Field(title="Номер стирального средства", description="Номер относительно станции",
							  ge=1, le=services.MAX_STATION_WASHING_AGENTS_AMOUNT)
	concentration_rate: int = Field(title="Концентрация средства")
	rollback: bool = Field(title="\"Откат\" средства")


class WashingAgentCreate(WashingAgentBase):
	"""
	Добавление стирального средства.
	"""
	station_id: UUID4 = Field(title="ИД станции")
	concentration_rate: Optional[int] = Field(title="Концентрация средства", ge=1,
											  le=services.MAX_WASHING_AGENTS_CONCENTRATION_RATE,
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


class WashingAgentUpdate(WashingAgentCreateMixedInfo):
	"""
	Обновление стирального средства.
	"""
	pass
