from typing import Annotated

from fastapi import APIRouter, Depends, Path, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stations import StationControl, StationSettings, StationProgram
from ..models.washing import WashingAgent, WashingMachine
from ..schemas import schemas_stations as stations, schemas_users as users, schemas_washing as washing
from ..dependencies import get_async_session
from ..dependencies.roles import get_sysadmin_user, get_installer_user
from ..dependencies.stations import get_station_by_id, get_station_program_by_number
from ..dependencies.users import get_current_active_user
from ..static.enums import StationParamsEnum, QueryFromEnum
from ..crud import crud_stations, crud_washing
from ..exceptions import GettingDataError, UpdatingError
from ..static.enums import RoleEnum
from ..exceptions import PermissionsError, CreatingError, DeletingError


router = APIRouter(
	prefix="/manage",
	tags=["stations_management"]
)


@router.get("/station/{station_id}/{dataset}", response_model=stations.StationPartialForUser)
async def read_station_partial_by_user(
	current_user: Annotated[users.User, Depends(get_current_active_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	dataset: Annotated[StationParamsEnum, Path(title="Набор параметров станции")]
):
	"""
	Получение выборочных данных по станции пользователем.

	Основные параметры доступны только для SYSADMIN-пользователей.
	Остальные - для INSTALLER и выше.
	"""
	match dataset:
		case StationParamsEnum.GENERAL:
			if current_user.role != RoleEnum.SYSADMIN:
				raise PermissionsError()
			return stations.StationPartialForUser(partial_data=station)
		case _:
			if current_user.role not in (RoleEnum.SYSADMIN, RoleEnum.MANAGER, RoleEnum.INSTALLER):
				raise PermissionsError()
			try:
				return await crud_stations.read_station(station, dataset, db, query_from=QueryFromEnum.USER)
			except GettingDataError as e:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/station/{station_id}", response_model=stations.Station)
async def read_station_all_by_user(
	current_user: Annotated[users.User, Depends(get_sysadmin_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Получение всех данных по станции пользователем.

	Доступно только для SYSADMIN-пользователей.
	"""
	try:
		return await crud_stations.read_station_all(station, db, query_from=QueryFromEnum.USER)
	except GettingDataError as e:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/station/{station_id}/" + StationParamsEnum.GENERAL.value,
			response_description="Возвращаются основные параметры станции "
								 "с изменениями (пример не показан, ибо сложности с типизацией во фреймворке)")
async def update_station_general(
	current_user: Annotated[users.User, Depends(get_sysadmin_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	updating_params: Annotated[stations.StationGeneralParamsUpdate, Body(embed=True,
																	  title="Измененные основные параметры станции")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Обновление основных параметров станции.
	Если wifi изменился, он возвращается с ответом, если нет - прежний не показывается.
	Если станция стала неактивная - меняются и зависимые параметры настроек и контроля
	 (неактивная станция не может быть включенной (ТЭН тоже выключаю), не может иметь статус, ...).

	Если стала активной, то зависимые параметры не меняются - как я понимаю, после активации нужно
	 еще вручную включить станцию, ТЭН, и т.д.

	Доступно только для SYSADMIN-пользователей.
	"""
	if any(
		val is not None for val in (updating_params.dict().values())
	):
		result = await crud_stations.update_station_general(station, updating_params, db, action_by=current_user)
		if station.is_active is True and updating_params.is_active is False:
			await StationControl.update_relation_data(station, stations.StationControlUpdate(), db)
			# StationControlUpdate() - там по умолчанию все нулевое
			await StationSettings.update_relation_data(
				station, stations.StationSettingsUpdate(station_power=False, teh_power=False), db
			)
	else:
		result = station
	return result


@router.put("/station/{station_id}/" + StationParamsEnum.CONTROL.value,
			response_model=stations.StationControl)
async def update_station_control(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	updating_params: Annotated[stations.StationControlUpdate, Body(embed=True,
																	  title="Измененные параметры состояния станции")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Обновление текущего состояния станции.
	Чтобы изменить статус на "ожидание", кроме него ничего не нужно передавать (иначе вернется ошибка).
	После смены статуса на "ожидание" остальные параметры становятся нулевыми.

	Если статус "работа" - должно быть указано что-то одно из: шаг программы, стиральные средства. Стиральная машина
	 при работе указана всегда. При обновлении параметров БЕЗ изменения номера машины, машину указывать НЕ НУЖНО.
	Если при статусе "работа" происходят какие-либо изменения, можно его тоже не передавать - останется
	 "работа" (статус становится нулевым автоматически, когда машина выключается в настройках (station_power)).

	Стиральное средство можно передать с кастомными параметрами - лишь бы номер его был среди номеров средств станции.
	А вот программу и машину нужно передавать со всеми существующими в БД параметрами, иначе будет ошибка.

	Если передать статус не нулевой, но при этом в настройках стация выключена - вернется ошибка.
	Если переданная стиральная машина неактивна - вернется ошибка.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	try:
		return await crud_stations.update_station_control(
			station, updating_params, db, action_by=current_user
		)
	except UpdatingError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/station/{station_id}/" + StationParamsEnum.SETTINGS.value,
			response_model=stations.StationSettings)
async def update_station_settings(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	updating_params: Annotated[stations.StationSettingsUpdate, Body(embed=True,
																   title="Измененные настройки станции")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Изменение настроек станции.

	Если передать station_power 'False', в текущем состоянии станции все автоматически обнуляется.
	Если передать station_power 'True' при неактивной станции, вернется ошибка.
	Если station_power был 'False' и стал 'True' - статус автоматически становится "ожидание".

	Доступно только для INSTALLER-пользователей и выше.
	"""
	if updating_params.station_power is False:
		await StationControl.update_relation_data(station, stations.StationControlUpdate(), db)
		# StationControlUpdate() - все нулевое
	try:
		return await crud_stations.update_station_settings(station, updating_params, db, action_by=current_user)
	except UpdatingError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/station/{station_id}/" + StationParamsEnum.PROGRAMS.value,
			 response_model=list[stations.StationProgram], response_description="Возвращает СОЗДАННЫЕ программы")
async def create_station_program(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	programs: Annotated[list[stations.StationProgramCreate], Body(embed=True, title="Программа станции")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Создание программ станции.

	Как и при первоначальном создании станции, для программы можно определить уже существующие средства станции,
	 указав их номера, или передать кастомные программы.

	Создать программу с уже существующим номером шага (этапа) нельзя.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	station_current_programs: list[stations.StationProgram] = await StationProgram.get_relation_data(station, db)
	if any(
		(program.program_step in map(lambda pg: pg.program_step, station_current_programs) for program in programs)
	):
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Got an existing program step")
	station_full_data = await crud_stations.read_station_all(station, db)
	station_with_created_programs = await StationProgram.create_station_programs(
		station_full_data, programs, db
	)
	return list({*station_with_created_programs} - {*station_full_data.station_programs})


@router.put("/station/{station_id}/" + StationParamsEnum.PROGRAMS.value + "/{program_step_number}",
			response_model=stations.StationProgram)
async def update_station_program(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station_and_program: Annotated[tuple[stations.StationGeneralParams, stations.StationProgram],
	Depends(get_station_program_by_number)],
	updating_params: Annotated[stations.StationProgramUpdate, Body(embed=True, title="Обновленные параметры программы")],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Обновление программы станции.
	Как и в других методах, можно передать как кастомные стиральные средства, так и просто номера существующих
	 у станции средств.
	Средства нужно передавать ЯВНЫМ списком (напр., если передать пустой список, то список средств программы
	 станет пустым) - нельзя обновить произвольно выбранные средства программы.
	Если обновляется, программа, по которой станция в данный момент работает - в текущем состоянии программа
	 тоже обновится.

	Номер шага программы в новых параметрах можно не передавать (и так указывается в пути). Но можно передать и
	 даже изменить на новый - в этом случае выполнится проверка на занятость номера.
	Можно не передавать номер программы, а только номер шага - программа определится автоматически.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	station, current_program = station_and_program
	try:
		return await crud_stations.update_station_program(station, current_program, updating_params, db,
														  action_by=current_user)
	except UpdatingError as err:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete("/station/{station_id}/" + StationParamsEnum.PROGRAMS.value + "/{program_step_number}")
async def update_station_program(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station_and_program: Annotated[tuple[stations.StationGeneralParams, stations.StationProgram],
	Depends(get_station_program_by_number)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Удаление этапа программы станции.
	Нельзя удалить программу, если в данный момент станция работает по ней.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	station, program = station_and_program

	station_control = await StationControl.get_relation_data(station, db)
	if station_control.program_step.dict() == program.dict():
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can't delete program step "
																		  "using in station working now")

	return await crud_stations.delete_station_program(
		station, program, db, current_user
	)


@router.delete("/station/{station_id}")
async def delete_station(
	current_user: Annotated[users.User, Depends(get_sysadmin_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	db: Annotated[AsyncSession, Depends(get_async_session)]
):
	"""
	Удаление станции.

	Доступно только для SYSADMIN-пользователей.
	"""
	await crud_stations.delete_station(station, db, action_by=current_user)
	return {"deleted": station.id}


@router.post("/station/{station_id}/{dataset}", response_description="Созданный объект",
			 tags=["washing_services_management"])
async def create_station_washing_services(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	dataset: Annotated[StationParamsEnum, Path(title="Набор данных",
											   description="Стиральные машины или стиральные средства")],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	creating_params: Annotated[washing.WashingAgentCreateMixedInfo | washing.WashingMachineCreateMixedInfo,
								Body(embed=True, title="Параметры объекта")]
):
	"""
	Добавление нового стирального средства / стиральной машины.
	Нельзя создать объект с уже существующим номером и с номером больше, чем определенное
	максимально количество объектов у станции.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	params_dict = creating_params.dict()
	match dataset:
		case StationParamsEnum.WASHING_MACHINES.value:
			schema = washing.WashingMachineCreateMixedInfo
			object_number = params_dict.pop("machine_number")
		case StationParamsEnum.WASHING_AGENTS.value:
			schema = washing.WashingAgentCreateMixedInfo
			object_number = params_dict.pop("agent_number")
		case _:
			raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

	if not isinstance(creating_params, schema):
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

	try:
		created_obj = await WashingMachine.create_object(
			db=db, station_id=station.id, object_number=object_number, **params_dict
		)
	except CreatingError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
	return created_obj


@router.put("/station/{station_id}/{dataset}/{object_number}", response_description="Измененный объект",
			tags=["washing_services_management"])
async def update_station_washing_services(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	dataset: Annotated[StationParamsEnum, Path(title="Набор данных",
											   description="Стиральные машины или стиральные средства")],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	updating_params: Annotated[washing.WashingMachineUpdate | washing.WashingAgentUpdate,
								Body(embed=True, title="Обновленные параметры объекта")],
	object_number: Annotated[int, Path(title="Номер обновляемого объекта")]
):
	"""
	Обновление стирального средства/стиральной машины станции.
	Нельзя обновить номер объекта на уже существующий.
	Нельзя сделать неактивной стиральную машину, которая в данный момент в работе.
	Если обновить стиральную машину, которая сейчас в работе (в текущем состоянии станции), или
	 стиральное средство, которое в данный момент используется программой станции, то все автоматически обновится.

	Передавать новые параметры нужно ЯВНО все. Вместо неуказанных установятся дефолтные.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	match dataset:
		case StationParamsEnum.WASHING_MACHINES:
			schema = washing.WashingMachineUpdate
			cls = WashingMachine
		case StationParamsEnum.WASHING_AGENTS:
			schema = washing.WashingAgentUpdate
			cls = WashingAgent
		case _:
			raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

	obj: washing.WashingAgent | washing.WashingMachine = await cls.get_obj_by_number(db, object_number, station.id)

	if not isinstance(updating_params, schema):
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

	try:
		return await crud_washing.update_washing_object(
			schema, obj, updating_params, station, db, action_by=current_user
		)
	except UpdatingError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/station/{station_id}/{dataset}/{object_number}", tags=["washing_services_management"])
async def delete_station_washing_services(
	current_user: Annotated[users.User, Depends(get_installer_user)],
	station: Annotated[stations.StationGeneralParams, Depends(get_station_by_id)],
	dataset: Annotated[StationParamsEnum, Path(title="Набор данных",
											   description="Стиральные машины или стиральные средства")],
	db: Annotated[AsyncSession, Depends(get_async_session)],
	object_number: Annotated[int, Path(title="Номер удаляемого объекта")]
):
	"""
	Удаление стиральной машины / стирального средства.
	Есть объект в данный момент используется станцией, удалить его нельзя.

	Доступно только для INSTALLER-пользователей и выше.
	"""
	match dataset:
		case StationParamsEnum.WASHING_MACHINES:
			cls = WashingMachine
		case StationParamsEnum.WASHING_AGENTS:
			cls = WashingAgent
		case _:
			raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

	obj: washing.WashingAgent | washing.WashingMachine = await cls.get_obj_by_number(db, object_number, station.id)

	try:
		await crud_washing.delete_washing_object(obj, station, db, current_user)
	except DeletingError as e:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

	return {"deleted": {
		f"{cls.__class__.__name__}_number": object_number,
		"station_id": station.id
	}}
