from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from ...exceptions import ValidationError
from ...models.washing import WashingAgent, WashingMachine
from ...schemas import schemas_washing as washing
from ...schemas.schemas_stations import StationGeneralParams
from ...static.enums import WashingServicesEnum


class WashingServicesManagerBase:
	"""
	Управление стиральными средствами/машинами.
	Работать только через менеджер контекста (если не передан список объектов).
	В args передается enum объектов, которые нужны.
	"""
	_attrs = {WashingServicesEnum.WASHING_AGENTS: "_agents", WashingServicesEnum.WASHING_MACHINES: "_machines"}

	def __init__(self, station: StationGeneralParams, db: AsyncSession, *args, **kwargs):
		self._station_general = station
		self._db = db
		self._agents: list[washing.WashingAgent] = kwargs.get("washing_agents") or []
		self._machines: list[washing.WashingMachine] = kwargs.get("washing_machines") or []
		self._datasets = args

	async def __aenter__(self):
		for dataset in self._datasets:
			if dataset not in list(WashingServicesEnum):
				raise ValueError("Undefined washing service")
			attr = self._attrs[dataset]
			if not getattr(self, attr):
				match dataset:
					case WashingServicesEnum.WASHING_AGENTS:
						data = await WashingAgent.get_station_objects(self._station_general.id, self._db)
					case WashingServicesEnum.WASHING_MACHINES:
						data = await WashingMachine.get_station_objects(self._station_general.id, self._db)
				setattr(self, attr, data)
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		pass


class WashingServicesManager(WashingServicesManagerBase):
	"""
	Необходимые функции.
	В каждой функции стоит проверять наличие нужных данных - временное решение.
	"""
	async def _washing_machine_change_power(self, washing_machine_number: int, action: Literal["on", "off"]) -> None:
		if not self._machines:
			raise ValueError("Undefined washing machines")
		try:
			machine = next(m for m in self._machines if m.machine_number == washing_machine_number)
			machine = washing.WashingMachineUpdate(**machine.dict())
		except StopIteration:
			raise ValidationError(f"Station {self._station_general.id} washing machine number {washing_machine_number}"
								  f" not found")
		match action:
			case "on":
				machine.is_active = True
			case "off":
				machine.is_active = False
		await WashingMachine.update_object(self._station_general.id, self._db, machine, washing_machine_number)

	async def _washing_agent_change_volume(self, washing_agent_number: int, volume: int) -> None:
		if not self._agents:
			raise ValueError("Undefined washing agents")
		try:
			agent = next(a for a in self._agents if a.agent_number == washing_agent_number)
			agent = washing.WashingAgentUpdate(**agent.dict())
		except StopIteration:
			raise ValidationError(f"Station {self._station_general.id} washing agent number {washing_agent_number}"
								  f" not found")
		agent.volume = volume
		await WashingAgent.update_object(self._station_general.id, self._db, agent, washing_agent_number)

	async def washing_agent_change_volume(self, washing_agent_number: int, volume: int) -> None:
		await self._washing_agent_change_volume(washing_agent_number, volume)

	async def washing_machine_turn_off(self, washing_machine_number: int):
		await self._washing_machine_change_power(washing_machine_number, "off")

	async def washing_machine_turn_on(self, washing_machine_number: int):
		await self._washing_machine_change_power(washing_machine_number, "on")