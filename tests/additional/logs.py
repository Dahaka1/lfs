import random
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models import logs as model
from app.static.enums import LogTypeEnum, LogCaseEnum, LogActionEnum, ErrorTypeEnum, StationStatusEnum
import services
from tests.additional.stations import StationData
from app.schemas import schemas_logs as schema
from app.utils.general import sa_object_to_dict


class Log:
	def __init__(self, code: float | int, content: str, log_type: LogTypeEnum, **kwargs):
		self.code = code
		self.event = str(LogCaseEnum(code))
		self.type = log_type
		self.content = content
		if self.type == LogTypeEnum.ERROR:
			scope = kwargs.get("scope")
			if not kwargs.get("scope"):
				raise ValueError("Error scope not defined")
			self.scope: ErrorTypeEnum = scope
		self.action = self._define_action()
		self.data_fields_and_types = self._define_expecting_data()
		self.data = None

		station = kwargs.get("station")
		if station:
			self.data = self.generate_additional_data(station)

	def __str__(self):
		return f"Log <code: {self.code}> <event: {self.event}> " \
			   f"<type: {self.type}> <content: {self.content}> <action: {self.action}> <data: {self.data}>"

	def __repr__(self):
		return str(self)

	@classmethod
	async def generate(cls, station: StationData, type_: LogTypeEnum, code_base: list[int | float],
							session: AsyncSession, ac: AsyncClient, amount: int = 10, **kwargs) -> list[schema.Log]:
		"""
		Создание логов должно работать!)
		"""
		codes = random.choices(code_base, k=amount)
		params = dict(content="test", log_type=type_, station=station)
		match type_:
			case LogTypeEnum.LOG:
				url = "/v1/logs/log"
				schema_ = schema.Log
			case LogTypeEnum.ERROR:
				url = "/v1/logs/error"
				schema_ = schema.Error
				scope = kwargs.get("scope")
				if not scope:
					raise ValueError("Error scope isn't defined")
				params["scope"] = scope
		logs = []
		for code in codes:
			params["code"] = code
			log = cls(**params)
			r = await ac.post(url, headers=station.headers, json=log.json())
			await station.turn_on(session)
			await station.reset(session)
			logs.append(r.json())
		return [schema_(**l) for l in logs]

	def _define_action(self) -> LogActionEnum | None:
		match self.type:
			case LogTypeEnum.LOG:
				action = services.LOG_ACTIONS.get(self.code)
			case LogTypeEnum.ERROR:
				action = services.ERROR_ACTIONS[self.scope].get(self.code)
		return action

	def _define_expecting_data(self) -> dict[str, type] | None:
		match self.type:
			case LogTypeEnum.LOG:
				data = services.LOG_EXPECTING_DATA.get(self.code)
			case LogTypeEnum.ERROR:
				data = services.ERROR_EXPECTING_DATA[self.scope].get(self.code)
		return data

	def json(self) -> dict[str, Any]:
		if self.type == LogTypeEnum.LOG:
			key = "log"
		elif self.type == LogTypeEnum.ERROR:
			key = "error"
		j = {key: self.as_dict()}
		if self.data:
			j["data"] = self.data
		return j

	def generate_additional_data(self, station: StationData) -> dict[str, Any]:
		json = {}
		rand_station_program = random.choice(station.station_programs)
		default_vals = {
			"washing_machine_number": random.choice(range(1, len(station.station_washing_machines))),
			"washing_agent_number": random.choice(range(1, len(station.station_washing_agents))),
			"volume": random.choice(range(services.MIN_WASHING_AGENTS_VOLUME, services.MAX_WASHING_AGENTS_VOLUME)),
			"program_number": rand_station_program.program_number,
			"program_step_number": rand_station_program.program_step,
			"teh_power": random.choice((True, False))
		}
		if self.data_fields_and_types:
			for field in self.data_fields_and_types:
				json[field] = default_vals[field]

		return json

	def as_dict(self) -> dict[str, Any]:
		dict_ = {
			"code": self.code,
			"content": self.content
		}
		if self.type == LogTypeEnum.ERROR:
			dict_["scope"] = self.scope.value
		return dict_

	@staticmethod
	async def find_in_db(log: schema.Log | schema.Error, db: AsyncSession) -> schema.Log | schema.Error | None:
		if "scope" in log.dict():
			model_ = model.Error
			schema_ = schema.Error
		else:
			model_ = model.Log
			schema_ = schema.Log
		result = (await db.execute(select(model_).where(model_.id == log.id))).scalar()
		if result:
			return schema_(**sa_object_to_dict(result))

	def check_action(self, station: StationData) -> None:
		ctrl = station.station_control
		setts = station.station_settings
		agents = station.station_washing_agents
		machines = station.station_washing_machines
		match self.action:
			case LogActionEnum.ERROR_STATION_CONTROL_STATUS_START:
				assert ctrl.status == StationStatusEnum.ERROR
				assert ctrl.program_step is None
				assert ctrl.washing_machine is None
				assert ctrl.washing_agents == []
				assert setts.station_power is True
			case LogActionEnum.ERROR_STATION_CONTROL_STATUS_END:
				assert ctrl.status == StationStatusEnum.AWAITING
				assert ctrl.program_step is None
				assert ctrl.washing_machine is None
				assert ctrl.washing_agents == []
				assert setts.station_power is True
			case LogActionEnum.STATION_TURN_OFF:
				assert all((attr is None for attr in (ctrl.status, ctrl.program_step, ctrl.washing_machine)))
				assert ctrl.washing_agents == []
				assert setts.station_power is False
			case LogActionEnum.STATION_TURN_ON:
				assert setts.station_power is True
				assert ctrl.status == StationStatusEnum.AWAITING
				assert all((attr is None for attr in (ctrl.program_step, ctrl.washing_machine)))
				assert ctrl.washing_agents == []
			case LogActionEnum.WASHING_MACHINE_TURN_ON | LogActionEnum.WASHING_MACHINE_TURN_OFF:
				machine = next(m for m in machines if m.machine_number == self.data["washing_machine_number"])
				if self.action == LogActionEnum.WASHING_MACHINE_TURN_ON:
					assert machine.is_active is True
				elif self.action == LogActionEnum.WASHING_MACHINE_TURN_OFF:
					assert machine.is_active is False
			case LogActionEnum.WASHING_AGENTS_CHANGE_VOLUME:
				agent = next(a for a in agents if a.agent_number == self.data["washing_agent_number"])
				assert agent.volume == self.data["volume"]
			case LogActionEnum.STATION_SETTINGS_CHANGE:  # тут меняется только состояние ТЭНа
				teh_power = self.data["teh_power"]
				assert setts.teh_power is teh_power
			case LogActionEnum.STATION_START_MANUAL_WORKING:
				agent = next(a for a in agents if a.agent_number == self.data["washing_agent_number"])
				machine = next(m for m in machines if m.machine_number == self.data["washing_machine_number"])
				assert agent.agent_number in [a.agent_number for a in ctrl.washing_agents]
				assert ctrl.washing_machine.dict() == machine.dict()
				for ag in ctrl.washing_agents:
					if ag.agent_number == agent.agent_number:
						assert ag.volume == self.data["volume"]
				assert ctrl.status == StationStatusEnum.WORKING
				assert setts.station_power is True
			case LogActionEnum.STATION_WORKING_PROCESS:
				assert ctrl.washing_machine.machine_number == self.data["washing_machine_number"]
				assert ctrl.program_step.program_step == self.data["program_step_number"]
				assert ctrl.program_step.program_number == self.data["program_number"]
				assert ctrl.washing_agents == []
				assert ctrl.status == StationStatusEnum.WORKING
			case LogActionEnum.STATION_MAINTENANCE_START:
				assert ctrl.status == StationStatusEnum.MAINTENANCE
				assert setts.station_power is True
				assert all((attr is None for attr in (ctrl.program_step, ctrl.washing_machine)))
				assert ctrl.washing_agents == []
			case LogActionEnum.STATION_MAINTENANCE_END:
				assert ctrl.status == StationStatusEnum.AWAITING
				assert all((attr is None for attr in (ctrl.program_step, ctrl.washing_machine)))
				assert ctrl.washing_agents == []
				assert setts.station_power is True


async def check_station_log_exists(station_id: uuid.UUID, session: AsyncSession) -> None:
	"""
	Проверяет наличие созданного лога у станции
	"""
	log = (await session.execute(select(model.Log).where(model.Log.station_id == station_id))).scalar()
	assert log is not None
	if log:
		assert int(log.__dict__["code"]) == 6
