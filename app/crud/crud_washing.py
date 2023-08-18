"""
Здесь малая часть действий со стиральными объектами.
Остальное - в методах моделей (washing).
Для удобства, мб, можно потом сюда переписать все.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import UpdatingError, DeletingError
from ..models.stations import StationControl
from ..models.washing import WashingAgent, WashingMachine
from ..schemas import schemas_washing as washing, schemas_users
from ..schemas.schemas_stations import StationGeneralParams, StationControlUpdate
from ..crud import crud_logs as log


async def update_washing_object(
	schema: washing,
	current_object: washing.WashingAgent | washing.WashingMachine,
	updated_object: washing.WashingMachineUpdate | washing.WashingAgentUpdate,
	station: StationGeneralParams,
	db: AsyncSession,
	action_by: schemas_users.User
) -> washing.WashingMachine | washing.WashingAgent:
	"""
	Обновление стирального объекта.
	"""
	station_control = await StationControl.get_relation_data(station, db)

	async def check_updating_washing_machine() -> bool:
		"""
		Возвращает True, если стиральная машина сейчас занята и нужно обновить ее в текущем
		 состоянии станции тоже.
		"""
		if station_control.washing_machine and station_control.washing_machine.dict() == current_object.dict():
			machine_using = True
		else:
			machine_using = False

		if machine_using and current_object.is_active and updated_object.is_active is False:
			raise UpdatingError("Can't mark washing machine as non-active if now using by station")
		return machine_using

	match schema:
		case washing.WashingAgentUpdate:
			numeric_field = "agent_number"
			model = WashingAgent

		case washing.WashingMachineUpdate:
			numeric_field = "machine_number"
			model = WashingMachine
			object_uses = await check_updating_washing_machine()

	for k, v in updated_object.dict().items():
		if v is None:
			setattr(updated_object, k, getattr(current_object, k))

	updated_object_number = getattr(updated_object, numeric_field)

	if updated_object_number and updated_object_number != getattr(current_object, numeric_field):
		existing_object = await model.get_obj_by_number(
			db, updated_object_number, station.id
		)
		if existing_object:
			raise UpdatingError("Can't change object number to existing object number")

	updated_object = await model.update_object(
		station.id, db, updated_object, getattr(current_object, numeric_field)
	)

	if schema == washing.WashingMachineUpdate and object_uses:
		station_control.washing_machine = updated_object.dict()

		await StationControl.update_relation_data(
			station, StationControlUpdate(**station_control.dict()), db
		)

	updated_fields = [key for key, val in updated_object.dict().items() if
					  getattr(current_object, key) != val]

	if any(updated_fields):
		info_text = f"Объект {model.__name__} №{getattr(current_object, numeric_field)} " \
					f"для станции {station.id} " \
					f"был успешно изменен пользователем {action_by.email}. " \
					f"Обновленные данные: {', '.join(updated_fields)}"
		await log.CRUDLog.server(6.2, info_text, station, db)

	return updated_object


async def delete_washing_object(
	current_object: washing.WashingAgent | washing.WashingMachine,
	station: StationGeneralParams,
	db: AsyncSession,
	action_by: schemas_users.User
) -> None:
	"""
	Удаление стирального объекта
	"""
	station_control = await StationControl.get_relation_data(station, db)

	async def check_machine_using() -> None:
		"""
		Проверяет, используется ли сейчас стиральная машина.
		"""
		if station_control.washing_machine:
			if station_control.washing_machine.machine_number == current_object.machine_number:
				raise DeletingError("Can't delete using washing machine")

	async def check_agent_using() -> None:
		"""
		Проверяет, используется ли сейчас стиральное средство.
		"""
		if station_control.program_step:
			if current_object.agent_number in map(
				lambda ag: ag.agent_number, station_control.program_step.washing_agents
			):
				raise DeletingError("Can't delete using washing agent")

	if isinstance(current_object, washing.WashingAgent):
		await check_agent_using()
		model = WashingAgent
		numeric_field = "agent_number"

	elif isinstance(current_object, washing.WashingMachine):
		await check_machine_using()
		model = WashingMachine
		numeric_field = "machine_number"

	await model.delete_object(station.id, db, getattr(current_object, numeric_field))

	info_text = f"{model.__class__.__name__} №{getattr(current_object, numeric_field)} " \
				f"for station {station.id} was successfully deleted by user {action_by.email}"

	# await ChangesLog.log(db, action_by, station, info_text)
