from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

from ...exceptions import ValidationError, UpdatingError
from ...models.stations import StationSettings, StationControl, StationProgram, Station
from ...models.washing import WashingAgent, WashingMachine
from ...schemas import schemas_stations, schemas_washing
from ...static.enums import StationParamsEnum, StationStatusEnum
from ...static.typing import StationParamsSet


class StationManagerBase:
	"""
	Понятно, что надо бы вообще тут все переписать =)
	Но так как это сейчас долго и неуместно, пока просто добавлю
	 некоторый функционал в этот класс.
	В args передаются наборы данных, которые нужно обновить. И, естественно, они не должны быть определены в kwargs
	 при этом.

	Если получать никаких данных в ходе инициализации объекта не нужно - можно без менеджера контекста.
	"""
	_relations = {StationParamsEnum.CONTROL: "_control", StationParamsEnum.SETTINGS: "_settings",
				 StationParamsEnum.PROGRAMS: "_programs", StationParamsEnum.WASHING_AGENTS: "_agents",
				 StationParamsEnum.WASHING_MACHINES: "_machines"}

	def __init__(self, station: schemas_stations.StationGeneralParams, db: AsyncSession, *args, **kwargs):
		self._general = station
		self._db: AsyncSession = db
		self._control: schemas_stations.StationControl | None = kwargs.get("control")
		self._settings: schemas_stations.StationSettings | None = kwargs.get("settings")
		self._programs: list[schemas_stations.StationProgram] | None = kwargs.get("programs")
		self._machines: list[schemas_washing.WashingMachine] | None = kwargs.get("machines")
		self._agents: list[schemas_washing.WashingAgent] | None = kwargs.get("agents")
		self._datasets = args

	async def __aenter__(self):
		for dataset in self._datasets:
			if dataset not in list(StationParamsEnum):
				raise ValueError("Unexpected station dataset")
			attr = self._relations[dataset]
			if not getattr(self, attr):
				data = await CRUDStation.read_station(self._general, dataset, self._db)
				setattr(self, attr, data)
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		await self.__check()

	async def __check(self) -> None:
		if not self._settings:
			self._settings = await CRUDStation.read_station(self._general, StationParamsEnum.SETTINGS, self._db)
		if not self._control:
			self._control = await CRUDStation.read_station(self._general, StationParamsEnum.CONTROL, self._db)
		if self._control.status:
			if self._settings.station_power is False:
				update_settings_schema = schemas_stations.StationSettingsUpdate(**self._settings.dict())
				update_settings_schema.station_power = True
				await StationSettings.update_relation_data(self._general, update_settings_schema, self._db)


class StationManager(StationManagerBase):
	"""
	В функции при создании нужно рейзить ошибку, если нет нужного набора данных!
	Пока решил это временно только так.
	"""
	_programs: list[schemas_stations.StationProgram]
	_machines: list[schemas_washing.WashingMachine]
	_agents: list[schemas_washing.WashingAgent]
	_settings: schemas_stations.StationSettings
	_control: schemas_stations.StationControl
	_db: AsyncSession
	_general: schemas_stations.StationGeneralParams

	async def raise_error(self) -> None:
		update_control_schema = schemas_stations.StationControlUpdate(
			status=StationStatusEnum.ERROR  # остальное нулевое
		)
		await StationControl.update_relation_data(self._general, update_control_schema, self._db)

	async def pass_error(self) -> None:
		"""
		Снятие статуса "Ошибка"
		"""
		if not self._control:
			raise AttributeError("Control wasn't defined")
		if self._control.status != StationStatusEnum.ERROR:
			raise UpdatingError(f"Can't stop ERROR mode. Station {self._general.id} status isn't ERROR")
		update_control_schema = schemas_stations.StationControlUpdate(
			status=StationStatusEnum.AWAITING
		)
		await StationControl.update_relation_data(self._general, update_control_schema, self._db)

	async def _change_station_power(self, do_power: Literal["on", "off"]) -> None:
		if not self._settings:
			raise AttributeError("Settings wasn't defined")
		update_settings_schema = schemas_stations.StationSettingsUpdate(**self._settings.dict())
		update_control_schema = schemas_stations.StationControlUpdate()
		update_settings_schema.station_power = False
		match do_power:
			case "on":
				update_control_schema.status = StationStatusEnum.AWAITING
				update_settings_schema.station_power = True
			case "off":
				update_settings_schema.station_power = False
		await StationSettings.update_relation_data(self._general, update_settings_schema, self._db)
		await StationControl.update_relation_data(self._general, update_control_schema, self._db)

	async def _activate(self):
		await self._change_station_power("on")
		self._settings.station_power = True  # костылик. ORM в принципе не реализована. но надо бы =)
		await self._change_teh_power("on")
		update_general_schema = schemas_stations.StationGeneralParamsUpdate(
			is_protected=True, is_active=True
		)
		await Station.update(self._db, self._general.id, update_general_schema)

	async def _change_teh_power(self, do_power: Literal["on", "off"]) -> None:
		if not self._settings:
			raise AttributeError("Settings wasn't defined")
		update_settings_schema = schemas_stations.StationSettingsUpdate(**self._settings.dict())
		update_settings_schema.teh_power = False
		match do_power:
			case "on":
				update_settings_schema.teh_power = True
		await StationSettings.update_relation_data(self._general, update_settings_schema, self._db)

	async def _start_manual_working(self, washing_machine_number: int, washing_agent_number: int, volume: int) -> None:
		if any((not dataset for dataset in (self._machines, self._agents, self._control))):
			raise AttributeError("Some dataset wasn't defined")
		update_control_schema = schemas_stations.StationControlUpdate(**self._control.dict())
		update_control_schema.status = StationStatusEnum.WORKING
		update_control_schema.program_step = None
		try:
			machine = next(m for m in self._machines if m.machine_number == washing_machine_number)
			agent = next(a for a in self._agents if a.agent_number == washing_agent_number)
			agent = schemas_washing.WashingAgentWithoutRollback(**agent.dict())
		except StopIteration:
			raise ValidationError(f"Got an non-existing station washing agent or machine. Station ID {self._general.id}")
		if not machine.is_active:
			raise UpdatingError(f"Can't initiate manual working for station {self._general.id}. "
								f"Machine №{machine.machine_number} isn't active")
		update_control_schema.washing_machine = machine
		agent.volume = volume
		if agent.agent_number not in (ag.agent_number for ag in update_control_schema.washing_agents):
			update_control_schema.washing_agents.append(agent)
		else:
			for ag in update_control_schema.washing_agents:
				if ag.agent_number == washing_agent_number:
					ag.volume = volume
		await StationControl.update_relation_data(self._general, update_control_schema, self._db)

	async def _update_working_process(self, washing_machine_number: int, program_step_number: int,
									  program_number: int, washing_machines_queue: list[int]) -> None:
		if any((not dataset for dataset in (self._programs, self._control, self._machines))):
			raise AttributeError("Some dataset wasn't defined")
		if any(
			(m_number not in (m.machine_number for m in self._machines)
			 for m_number in washing_machines_queue)
		):
			raise ValidationError(f"Got an non-existing machine number for machines queue. Station ID {self._general.id}")
		try:
			program = next(p for p in self._programs if p.program_number == program_number and
						   p.program_step == program_step_number)
			machine = next(m for m in self._machines if m.machine_number == washing_machine_number)
		except StopIteration:
			raise ValidationError(f"Got an non-existing program step or washing machine number. Station ID {self._general.id}")
		ctrl = self._control
		ctrl.washing_agents = []
		ctrl.washing_machine = machine
		ctrl.program_step = program
		ctrl.status = StationStatusEnum.WORKING
		ctrl.washing_machines_queue = washing_machines_queue
		if machine.machine_number in ctrl.washing_machines_queue:
			del ctrl.washing_machines_queue[machine.machine_number]
		ctrl = schemas_stations.StationControlUpdate(**ctrl.dict())
		await StationControl.update_relation_data(self._general, ctrl, self._db)

	async def _start_maintenance(self) -> None:
		if not self._control:
			raise AttributeError("Control wasn't defined")
		ctrl = self._control
		ctrl.program_step = None
		ctrl.washing_agents = []
		ctrl.washing_machine = None
		ctrl.status = StationStatusEnum.MAINTENANCE
		ctrl = schemas_stations.StationControlUpdate(**ctrl.dict())
		await StationControl.update_relation_data(self._general, ctrl, self._db)

	async def _end_maintenance(self) -> None:
		if not self._control:
			raise AttributeError("Control wasn't defined")
		ctrl = self._control
		if ctrl.status != StationStatusEnum.MAINTENANCE:
			raise ValidationError("Station isn't in maintenance now")
		ctrl.status = StationStatusEnum.AWAITING
		ctrl = schemas_stations.StationControlUpdate(**ctrl.dict())
		await StationControl.update_relation_data(self._general, ctrl, self._db)

	async def turn_off(self) -> None:
		await self._change_station_power("off")

	async def turn_on(self) -> None:
		await self._change_station_power("on")

	async def turn_teh_on(self) -> None:
		await self._change_teh_power("on")

	async def turn_teh_off(self) -> None:
		await self._change_teh_power("off")

	async def start_manual_working(self, **kwargs) -> None:
		await self._start_manual_working(**kwargs)

	async def update_working_process(self, **kwargs) -> None:
		await self._update_working_process(**kwargs)

	async def start_maintenance(self) -> None:
		await self._start_maintenance()

	async def end_maintenance(self) -> None:
		await self._end_maintenance()

	async def activate(self) -> None:
		await self._activate()


class CRUDStation(StationManagerBase):
	"""
	Здесь дублирование кода, чтобы избежать проблем с импортом из crud.
	В будущем нужно рефакторить - перенести CRUD-функции сюда.
	"""
	_programs: list[schemas_stations.StationProgram]
	_machines: list[schemas_washing.WashingMachine]
	_agents: list[schemas_washing.WashingAgent]
	_settings: schemas_stations.StationSettings
	_control: schemas_stations.StationControl
	_db: AsyncSession
	_general: schemas_stations.StationGeneralParams

	@staticmethod
	async def read_station(station: schemas_stations.StationGeneralParams,
						   params_set: StationParamsEnum,db: AsyncSession) -> StationParamsSet:
		"""
		Возвращает объект с запрошенными данными.
		"""
		match params_set:
			case StationParamsEnum.SETTINGS:
				data: schemas_stations.StationSettings = await StationSettings.get_relation_data(station, db)
			case StationParamsEnum.CONTROL:
				data: schemas_stations.StationControl = await StationControl.get_relation_data(station, db)
			case StationParamsEnum.PROGRAMS:
				data: list[schemas_stations.StationProgram] = await StationProgram.get_relation_data(station, db)
			case StationParamsEnum.WASHING_MACHINES:
				data: list[schemas_washing.WashingMachine] = await WashingMachine.get_station_objects(station.id, db)
			case StationParamsEnum.WASHING_AGENTS:
				data: list[schemas_washing.WashingAgent] = await WashingAgent.get_station_objects(station.id, db)

		return data
