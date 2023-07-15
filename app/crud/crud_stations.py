import datetime
import uuid

from geopy.location import Location
from geopy.geocoders import Nominatim
from geopy.adapters import AioHTTPAdapter
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

from ..models.stations import Station, StationSettings, StationControl, StationProgram
from ..models.logs import ChangesLog
from ..models.washing import WashingAgent, WashingMachine
from ..schemas import schemas_stations, schemas_users, schemas_washing
from ..utils.general import sa_objects_dicts_list, encrypt_data
import config
from ..static.enums import StationStatusEnum
from ..static.enums import StationParamsEnum, QueryFromEnum
from ..exceptions import UpdatingError


async def read_all_stations(db: AsyncSession) -> list[schemas_stations.StationGeneralParams]:
	"""
	Возвращает pydantic-модели станций (основные параметры).
	"""
	query = select(Station).order_by(Station.updated_at.desc())
	result = await db.execute(query)
	stations = sa_objects_dicts_list(result.scalars().all())

	result = []
	for station in stations:
		station_obj = schemas_stations.StationGeneralParams(**station)
		result.append(station_obj)

	return result


async def create_station(db: AsyncSession,
						 station: schemas_stations.StationCreate,
						 settings: schemas_stations.StationSettingsCreate,
						 washing_agents: list[schemas_washing.WashingAgentCreateMixedInfo],
						 washing_machines: list[schemas_washing.WashingMachineCreateMixedInfo],
						 created_by: schemas_users.User) -> schemas_stations.Station:
	"""
	Создает станцию в БД с определенными или дефолтными параметрами.
	"""
	wifi_data = {"login": station.wifi_name, "password": station.wifi_password}
	hashed_wifi_data = encrypt_data(wifi_data)
	async with Nominatim(user_agent=config.GEO_APP, adapter_factory=AioHTTPAdapter) as geolocator:
		location: Location = await geolocator.geocode(station.address)

	station_id = await Station.create(
		db=db,
		location={"latitude": location.latitude, "longitude": location.longitude},
		is_active=station.is_active,
		is_protected=station.is_protected,
		hashed_wifi_data=hashed_wifi_data,
		region=station.region
	)
	station_settings = await StationSettings.create(
		db=db,
		station_id=station_id,
		station_power=settings.station_power,
		teh_power=settings.teh_power
	) if settings else await StationSettings.create(db=db, station_id=station_id)

	station_control_params = {"station_id": station_id}
	if settings.station_power is False:
		station_control_params["status"] = None

	station_control = await StationControl.create(db=db, **station_control_params)

	station_washing_services = await Station.create_default_washing_services(
		db=db, station_id=station_id,
		washing_agents_amount=station.washing_agents_amount,
		washing_machines_amount=station.washing_machines_amount,
		washing_agents=washing_agents,
		washing_machines=washing_machines
	)

	inserted_station = await Station.get_station_by_id(db=db, station_id=station_id)

	created_station_obj = schemas_stations.Station(
		**inserted_station.dict(),
		**station_washing_services,
		station_control=station_control,
		station_settings=station_settings
	)

	log_text = f"Station with UUID {created_station_obj.id} was successfully created by " \
			   f"user {created_by.email} ({created_by.first_name} {created_by.last_name})"

	await ChangesLog.log(
		db=db, user=created_by, station=created_station_obj, content=log_text
	)
	await db.commit()
	return created_station_obj


async def read_station(
	station: schemas_stations.StationGeneralParams,
	params_set: StationParamsEnum,
	db: AsyncSession,
	query_from: QueryFromEnum
) -> schemas_stations.StationPartial | schemas_stations.StationPartialForUser:
	"""
	Возвращает объект с запрошенными данными.
	"""
	match params_set:
		case StationParamsEnum.SETTINGS:
			data = await StationSettings.get_relation_data(station, db)
		case StationParamsEnum.CONTROL:
			data = await StationControl.get_relation_data(station, db)
		case StationParamsEnum.PROGRAMS:
			data = await StationProgram.get_relation_data(station, db)
		case StationParamsEnum.WASHING_MACHINES:
			data = await WashingMachine.get_station_objects(station.id, db)
		case StationParamsEnum.WASHING_AGENTS:
			data = await WashingAgent.get_station_objects(station.id, db)

	match query_from:
		case QueryFromEnum.STATION:
			return schemas_stations.StationPartial(partial_data=data)
		case QueryFromEnum.USER:
			return schemas_stations.StationPartialForUser(partial_data=data)


async def read_station_all(
	station: schemas_stations.StationGeneralParamsForStation | schemas_stations.StationGeneralParams,
	db: AsyncSession,
	query_from: QueryFromEnum = QueryFromEnum.STATION
) -> schemas_stations.StationForStation | schemas_stations.Station:
	"""
	Возвращает все данные по станции.

	Надо обязательно сократить количество запросов... (отмечено в TODO).
	"""
	settings = await StationSettings.get_relation_data(station, db)
	control = await StationControl.get_relation_data(station, db)
	programs = await StationProgram.get_relation_data(station, db)
	washing_machines = await WashingMachine.get_station_objects(station.id, db)
	washing_agents = await WashingAgent.get_station_objects(station.id, db)

	schema = schemas_stations.StationForStation if query_from == QueryFromEnum.STATION else schemas_stations.Station

	return schema(
		**station.dict(), station_programs=programs, station_washing_machines=washing_machines,
		station_washing_agents=washing_agents, station_control=control, station_settings=settings
	)


async def delete_station(
	station: schemas_stations.StationGeneralParams | uuid.UUID,
	db: AsyncSession,
	action_by: schemas_users.User
) -> None:
	"""
	Удаление станции.
	"""
	station_id = station.id if isinstance(station, schemas_stations.StationGeneralParams) else station

	query = delete(Station).where(Station.id == station_id)
	await db.execute(query)
	await db.commit()

	info_text = f"Station {station.id} was successfully deleted by user {action_by.email}"
	await ChangesLog.log(db, action_by, station, info_text)


async def update_station_general(
	station: schemas_stations.StationGeneralParams,
	updating_params: schemas_stations.StationGeneralParamsUpdate,
	db: AsyncSession,
	action_by: schemas_users.User
) -> schemas_stations.StationGeneralParams | schemas_stations.StationGeneralParamsForStation:
	"""
	Обновление данных станции.
	"""
	updated_params_list = []
	current_data = station.dict()
	for key, val in updating_params.dict().items():
		if key in current_data:
			if val is not None:
				if current_data[key] != val:
					current_data[key] = val
					updated_params_list.append(key)
		else:
			current_data.pop(key, None)  # их обновлять не надо и нельзя (id, created_at, updated_at, ...)

	wifi_updated_data = (updating_params.wifi_name, updating_params.wifi_password)
	if all(wifi_updated_data):
		current_data["hashed_wifi_data"] = encrypt_data({"login": updating_params.wifi_name,
														 "password": updating_params.wifi_password})
		updated_params_list.extend(("wifi_name", "wifi_password"))
	else:
		current_data.pop("hashed_wifi_data")  # костыль - надо решить с типизацией, мб сделать еще одну функцию
		# поиска станции по ИД, чтобы она не возвращала wifi

	if updating_params.address:
		async with Nominatim(user_agent=config.GEO_APP, adapter_factory=AioHTTPAdapter) as geolocator:
			location: Location = await geolocator.geocode(updating_params.address)
		location_dict = {"latitude": location.latitude, "longitude": location.longitude}
		if station.location != location_dict:
			current_data["location"] = {"latitude": location.latitude, "longitude": location.longitude}
			updated_params_list.append("location")

	if any(updated_params_list):
		current_data["updated_at"] = datetime.datetime.now()

		query = update(Station).where(
			Station.id == station.id
		).values(**current_data)  # updated_at почему-то автоматически не обновляется =(

		await db.execute(query)
		await db.commit()

		info_text = f"Station {station.id} GENERAL PARAMS was successfully changed by user {action_by.email}.\n" \
					f"Updated data: {', '.join(list(updated_params_list))}"
		await ChangesLog.log(db=db, user=action_by, station=station, content=info_text)

	schema = schemas_stations.StationGeneralParams(
		id=station.id, created_at=station.created_at, updated_at=station.updated_at or datetime.datetime.now(),
		is_active=updating_params.is_active if not updating_params.is_active is None else station.is_active,
		is_protected=updating_params.is_protected if not updating_params.is_protected is None else station.is_protected,
		location=current_data.get("location") or station.location,
		region=updating_params.region or station.region
	)

	if "hashed_wifi_data" in current_data:
		schema = schemas_stations.StationGeneralParamsForStation(
			**schema.dict(),
			wifi_name=updating_params.wifi_name,
			wifi_password=updating_params.wifi_password
		)

	return schema


async def update_station_control(
	station: schemas_stations.StationGeneralParams,
	updated_params: schemas_stations.StationControlUpdate,
	db: AsyncSession,
	action_by: schemas_users.User
) -> schemas_stations.StationControl:
	"""
	Обновление текущего состояния станции.

	:raises Updating error
	"""
	current_station_control = await StationControl.get_relation_data(station, db)

	if updated_params.status is None and any(
		(updated_params.program_step, any(updated_params.washing_agents))
	):
		updated_params.status = StationStatusEnum.WORKING

	if updated_params.status == StationStatusEnum.WORKING and not updated_params.washing_machine:
		if current_station_control.washing_machine:
			updated_params.washing_machine = current_station_control.washing_machine
			# если изменили программу/средства без указания машины

	if (updated_params.program_step is not None or any(updated_params.washing_agents)) \
		and not updated_params.washing_machine:
		err_text = "Can't define station washing machine, but program step or washing agents was received"
		async with UpdatingError(message=err_text, station=station, db=db) as err:
			raise err

	if any(updated_params.washing_agents):
		station_washing_agents: list[WashingAgent] = await WashingAgent.get_station_objects(station.id, db)
		for agent in updated_params.washing_agents:
			if agent.agent_number not in [ag.agent_number for ag in station_washing_agents]:
				err_text = f"Station has only {len(station_washing_agents)} washing agents, " \
						   f"but got agent №{agent.agent_number}"
				async with UpdatingError(station=station, message=err_text, db=db) as err:
					raise err

	if updated_params.program_step:
		station_programs = await read_station(station, StationParamsEnum.PROGRAMS, db, QueryFromEnum.STATION)
		if updated_params.program_step.dict() not in [program.dict() for program in station_programs]:
			err_text = f"Station program '{updated_params.program_step}' wasn't found in station programs"
			async with UpdatingError(station=station, message=err_text, db=db) as err:
				raise err

	if updated_params.washing_machine:
		station_washing_machines: list[WashingMachine] = await WashingMachine.get_station_objects(station.id, db)
		if updated_params.washing_machine.dict() not in [machine.dict() for machine in station_washing_machines]:
			err_text = f"Washing machine '{updated_params.washing_machine}' wasn't found in station washing machines"
			async with UpdatingError(station=station, message=err_text, db=db) as err:
				raise err
		if not updated_params.washing_machine.is_active:
			err_text = f"Chosen washing machine '{updated_params.washing_machine}' is inactive and can't be used"
			async with UpdatingError(station=station, message=err_text, db=db) as err:
				raise err

	updated_params_list = [key for key, val in updated_params.dict().items()
						   if getattr(current_station_control, key) != val]

	if any(updated_params_list):
		info_text = f"Station {station.id} CONTROL was successfully changed by user {action_by.email}.\n" \
						f"Updated data: {', '.join(list(updated_params_list))}"
		await ChangesLog.log(db=db, user=action_by, station=station, content=info_text)

	return await StationControl.update_relation_data(station, updated_params, db)


async def update_station_settings(
	station: schemas_stations.StationGeneralParams,
	updated_params: schemas_stations.StationSettingsUpdate,
	db: AsyncSession,
	action_by: schemas_users.User
) -> schemas_stations.StationSettings:
	"""
	Обновление настроек станции.

	:raises Updating error
	"""
	current_station_settings = await StationSettings.get_relation_data(station, db)

	if any(
		(arg is not None for arg in updated_params.dict().values())
	):
		if updated_params.station_power is None:
			updated_params.station_power = current_station_settings.station_power
		if updated_params.teh_power is None:
			updated_params.teh_power = current_station_settings.teh_power

		updated_params_list = [key for key, val in updated_params.dict().items()
							   if getattr(current_station_settings, key) != val]

		if any(updated_params_list):
			info_text = f"Station {station.id} SETTINGS was successfully changed by user {action_by.email}.\n" \
						f"Updated data: {', '.join(list(updated_params_list))}"
			await ChangesLog.log(db=db, user=action_by, station=station, content=info_text)

		result = await StationSettings.update_relation_data(station, updated_params, db)

		if updated_params.station_power is True:
			if current_station_settings.station_power is False:
				await db.execute(
					update(StationControl).where(StationControl.station_id == station.id).values(
						**schemas_stations.StationControlUpdate(status=StationStatusEnum.AWAITING).dict()
					)
				)
				await db.commit()
		return result
	else:
		return current_station_settings


async def update_station_program(
	station: schemas_stations.StationGeneralParams,
	current_program: schemas_stations.StationProgram,
	updated_program: schemas_stations.StationProgramUpdate,
	db: AsyncSession,
	action_by: schemas_users.User
) -> schemas_stations.StationProgram:
	"""
	Обновление программы станции.
	"""
	station_washing_agents = await WashingAgent.get_station_objects(station.id, db)
	washing_agents_numbers = [
		ag.agent_number if isinstance(ag, schemas_washing.WashingAgentWithoutRollback)
		else ag for ag in updated_program.washing_agents
	]

	if any(
		(agent_number not in map(lambda ag: ag.agent_number, station_washing_agents)
		 for agent_number in washing_agents_numbers)
	):
		err_text = "Got an non-existing washing agent number"
		async with UpdatingError(message=err_text, station=station, db=db) as err:
			raise err

	if not updated_program.program_step:
		updated_program.program_step = current_program.program_step
		updated_program.program_number = current_program.program_number
	else:
		station_programs = await StationProgram.get_relation_data(station, db)
		try:
			next(pg for pg in station_programs if pg.program_step == updated_program.program_step)
			err_text = "Can't change program step number to existing program step number"
			async with UpdatingError(message=err_text, station=station, db=db) as err:
				raise err
		except StopIteration:
			pass

	updated_program = await StationProgram.update_relation_data(
		station, updated_program, db, washing_agents=station_washing_agents
	)
	updated_fields = [key for key, val in updated_program.dict().items() if getattr(current_program, key) != val]

	if any(updated_fields):  # в целом, там по-любому должны быть поля, но на всякий проверю
		info_text = f"Program step №{current_program.program_step} of station {station.id} " \
					f"was successfully updated by user {action_by.email}. Updated fields: " + \
					', '.join(updated_fields)
		await ChangesLog.log(db, action_by, station, info_text)

	if station.is_active:
		station_control = await StationControl.get_relation_data(station, db)
		if station_control.program_step and station_control.program_step.program_step == current_program.program_step:
			station_control.program_step = updated_program
			updates = schemas_stations.StationControlUpdate(**updated_program.dict())
			await StationControl.update_relation_data(station, updates, db)

	return updated_program


async def delete_station_program(
	station: schemas_stations.StationGeneralParams,
	station_program: schemas_stations.StationProgram,
	db: AsyncSession,
	action_by: schemas_users.User
) -> dict[str, dict[str, int | UUID4]]:
	"""
	Удаление шага программы станции.
	"""
	query = delete(StationProgram).where(
		(StationProgram.station_id == station.id) &
		(StationProgram.program_step == station_program.program_step)
	)
	await db.execute(query)
	await db.commit()

	info_text = f"Program step №{station_program.program_step} of station {station.id} was successfully " \
				f"deleted by user {action_by.email}"

	await ChangesLog.log(db, action_by, station, info_text)

	return {"deleted": {
		"program_step": station_program.program_step,
		"station_id": station.id
	}}
