from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import services
from ..schemas import schemas_logs as schema, schemas_stations
from ..models import logs
from ..models.logs import Log, Error
from ..static.enums import LogFromEnum, LogActionEnum, LogTypeEnum, StationParamsEnum, WashingServicesEnum, ErrorTypeEnum
from .managers.station import StationManager
from .managers.washing import WashingServicesManager
from ..utils.general import sa_object_to_dict
from ..exceptions import ValidationError


class CRUDLog:
	def __init__(self, log: schema.ErrorCreate | schema.LogCreate, log_type: LogTypeEnum, **kwargs):
		if not log.station_id:
			raise ValueError("Need for station ID")
		self._instance = log
		self._code = log.code
		self._data = kwargs
		match log_type:
			case LogTypeEnum.LOG:
				self._model = "Log"
				self._schema = schema.Log
			case LogTypeEnum.ERROR:
				self._model = "Error"
				self._schema = schema.Error
			case _:
				raise ValueError("Undefined log type")
		self._check_additional_data()

	async def add(self, station: schemas_stations.StationGeneralParams, db: AsyncSession,
				  log_from: LogFromEnum = LogFromEnum.STATION) -> schema.Log | schema.Error:
		"""
		Добавление лога.
		По дефолту лог от станции, ибо от сервера логи намного реже будут нужны (мб поменять наоборот).
		"""
		data = dict(**self._instance.dict(), sended_from=log_from)
		if self._model == "Error":
			action = services.ERROR_ACTIONS[self._instance.scope].get(self._code)
		elif self._model == "Log":
			action = services.LOG_ACTIONS.get(self._code)
		if action:
			data.setdefault("action", action)
		model = getattr(logs, self._model)
		instance = model(**data)
		db.add(instance)

		if action:
			await self.__initiate_action(action, db, station, self._data)

		await db.commit()
		await db.refresh(instance)

		return self._schema(
			**sa_object_to_dict(instance)
		)

	@staticmethod
	async def get_station_logs(station: schemas_stations.StationGeneralParams, db: AsyncSession, limit: int,
							   *args, schemas: bool = False):
		"""
		:params args: нужные коды логов
		"""
		code_type = int | float | None
		if any((not isinstance(code, code_type) for code in args)):
			raise ValueError("Invalid log code type")
		codes = [float(c) for c in args if c]
		if not codes:
			query = select(Log).where(Log.station_id == station.id).order_by(Log.timestamp.desc()).limit(limit)
		else:
			query = select(Log).where(
				(Log.station_id == station.id) & (Log.code.in_(codes))
			).order_by(Log.timestamp.desc()).limit(limit)
		result = (await db.execute(query)).scalars().all()
		if schemas:
			result = [schema.Log(**l.__dict__) for l in result]
		return result

	@staticmethod
	async def get_station_errors(station: schemas_stations.StationGeneralParams, db: AsyncSession, limit: int,
								 errors_type: ErrorTypeEnum, code: int | float | None):
		match errors_type:
			case errors_type.PUBLIC | errors_type.SERVICE:
				if not code:
					query = select(Error).where(
						(Error.station_id == station.id)
						& (Error.scope == errors_type)
					).order_by(Error.timestamp.desc()).limit(limit)
				else:
					query = select(Error).where(
						(Error.station_id == station.id)
						& (Error.scope == errors_type) &
						(Error.code == code)
					).order_by(Error.timestamp.desc()).limit(limit)
			case errors_type.ALL:
				if not code:
					query = select(Error).where(
						Error.station_id == station.id
					).order_by(Error.timestamp.desc()).limit(limit)
				else:
					query = select(Error).where(
						(Error.station_id == station.id) &
						(Error.code == code)
					).order_by(Error.timestamp.desc()).limit(limit)
		result = (await db.execute(query)).scalars().all()

		return result

	@classmethod
	async def server(cls, code: int | float, content: str,
					 station: schemas_stations.StationGeneralParams, db: AsyncSession) -> None:
		"""
		Добавление лога от сервера.
		"""
		log = schema.LogCreate(station_id=station.id, code=code, content=content)
		await cls(log, LogTypeEnum.LOG).add(station, db, LogFromEnum.SERVER)

	def _check_additional_data(self) -> None:
		if self._model == "Log":
			expecting_data_dict = services.LOG_EXPECTING_DATA
		elif self._model == "Error":
			expecting_data_dict = services.ERROR_EXPECTING_DATA[self._instance.scope]
		if self._code in expecting_data_dict:
			fields = expecting_data_dict[self._code]
			for field, type_ in fields.items():
				if field not in self._data:
					raise ValidationError(f"Expected for {field} at body field \"data\"")
				value = self._data[field]
				if type(value) != type_:
					raise ValidationError(f"Field \"{field}\" must be type *{type_}*")
			for field in self._data:
				if field not in fields:
					raise ValidationError(f"Got an unexpected field \"{field}\"")

	@staticmethod
	async def __initiate_action(action: LogActionEnum, db: AsyncSession,
							  station: schemas_stations.StationGeneralParams, data: dict[str, Any]) -> None:
		"""
		Осуществить действие, требуемое при получении лога.
		:param data: Необходимые данные, полученные из строки лога.
		"""
		match action:
			case LogActionEnum.ERROR_STATION_CONTROL_STATUS_START:
				await StationManager(station, db).raise_error()

			case LogActionEnum.ERROR_STATION_CONTROL_STATUS_END:
				async with StationManager(station, db, StationParamsEnum.CONTROL) as sm:
					await sm.pass_error()

			case LogActionEnum.STATION_TURN_OFF:
				async with StationManager(station, db, StationParamsEnum.SETTINGS) as sm:
					await sm.turn_off()
			case LogActionEnum.STATION_TURN_ON:
				async with StationManager(station, db, StationParamsEnum.SETTINGS) as sm:
					await sm.turn_on()

			case LogActionEnum.WASHING_MACHINE_TURN_OFF:
				async with WashingServicesManager(station, db, WashingServicesEnum.WASHING_MACHINES) as wsm:
					await wsm.washing_machine_turn_off(**data)
			case LogActionEnum.WASHING_MACHINE_TURN_ON:
				async with WashingServicesManager(station, db, WashingServicesEnum.WASHING_MACHINES) as wsm:
					await wsm.washing_machine_turn_on(**data)

			case LogActionEnum.WASHING_AGENTS_CHANGE_VOLUME:
				async with WashingServicesManager(station, db, WashingServicesEnum.WASHING_AGENTS) as wsm:
					await wsm.washing_agent_change_volume(**data)

			case LogActionEnum.STATION_SETTINGS_CHANGE:
				teh_power = data["teh_power"]
				async with StationManager(station, db, StationParamsEnum.SETTINGS) as sm:
					if teh_power is True:
						await sm.turn_teh_on()
					if teh_power is False:
						await sm.turn_teh_off()

			case LogActionEnum.STATION_START_MANUAL_WORKING:
				async with StationManager(station, db, StationParamsEnum.CONTROL,
										  StationParamsEnum.WASHING_MACHINES, StationParamsEnum.WASHING_AGENTS) as sm:
					await sm.start_manual_working(**data)

			case LogActionEnum.STATION_WORKING_PROCESS:
				async with StationManager(station, db, StationParamsEnum.CONTROL, StationParamsEnum.PROGRAMS,
										  StationParamsEnum.WASHING_MACHINES) as sm:
					await sm.update_working_process(**data)

			case LogActionEnum.STATION_MAINTENANCE_START:
				async with StationManager(station, db, StationParamsEnum.CONTROL) as sm:
					await sm.start_maintenance()

			case LogActionEnum.STATION_MAINTENANCE_END:
				async with StationManager(station, db, StationParamsEnum.CONTROL) as sm:
					await sm.end_maintenance()

			case LogActionEnum.STATION_ACTIVATE:
				async with StationManager(station, db, StationParamsEnum.SETTINGS) as sm:
					await sm.activate()

			case _:
				raise ValueError("Invalid log action")
