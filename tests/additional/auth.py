import datetime
import uuid
from typing import Any, Literal, Optional

from httpx import AsyncClient
from sqlalchemy import delete, update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import RegistrationCode, RefreshToken
from app.static.enums import StationStatusEnum, RoleEnum
from app.utils.general import sa_object_to_dict
from .stations import StationData, change_station_params
from .users import change_user_data, UserData


async def delete_user_code(user: Any, session: AsyncSession) -> None:
	"""
	Удаляет код подтверждения email пользователя.
	"""
	if isinstance(user.id, int):  # чтоб не ругался линтер
		await session.execute(
			delete(RegistrationCode).where(RegistrationCode.user_id == user.id)
		)
		await session.commit()


async def user_refresh_token_in_db(user_id: int, session: AsyncSession) -> Optional[str]:
	"""
	Поиск в БД рефреш-токена пользователя.
	"""
	token = await session.execute(
		select(RefreshToken).where(RefreshToken.user_id == user_id)
	)
	result = token.scalar()
	if result:
		return sa_object_to_dict(result).get("data")


async def delete_user_refresh_token_in_db(user_id: int, session: AsyncSession) -> None:
	"""
	Удаление в БД рефреш-токена пользователя.
	"""
	await session.execute(
		delete(RefreshToken).where(RefreshToken.user_id == user_id)
	)
	await session.commit()


async def do_code_expired(user: Any, session: AsyncSession) -> None:
	"""
	Делает код истекшим.
	"""
	if isinstance(user.id, int):
		await session.execute(
			update(RegistrationCode).
			where(
				RegistrationCode.user_id == user.id
			).
			values(
				expires_at=(datetime.datetime.now() - datetime.timedelta(hours=10))
			)
		)
		await session.commit()


async def url_auth_test(url: str, method: Literal["get", "post", "put", "delete"], user: Any,
						ac: AsyncClient, session: AsyncSession, json: dict[str, Any] = None) -> None:
	"""
	Проверяет УРЛ на ответ:
	- Заблокированному пользователю;
	- Неподтвержденному пользователю (или подтвержденному, где это запрещено);
	- Невалидному токену пользователя.
	"""
	requests = {
		"get": ac.get, "post": ac.post, "put": ac.put, "delete": ac.delete
	}

	func = requests.get(method)
	request_params = {"url": url, "headers": user.headers, "cookies": user.cookies}
	match method:
		case "post" | "put":
			request_params["json"] = json or {}
	# _________________________________________________________________________________________________

	await change_user_data(user, session, disabled=True)
	disabled_user_r = await func(**request_params)
	assert disabled_user_r.status_code == 403, f"{disabled_user_r} status code != 403"

	await change_user_data(user, session, disabled=False)

	# _________________________________________________________________________________________________

	if url == "/api/v1/auth/confirm_email":
		await change_user_data(user, session, email_confirmed=True)
		email_already_confirmed_r = await func(**request_params)
		assert email_already_confirmed_r.status_code == 403, f"{email_already_confirmed_r} status code != 403"
	else:
		await change_user_data(user, session, email_confirmed=False)
		email_not_confirmed_r = await func(**request_params)
		assert email_not_confirmed_r.status_code == 403, f"{email_not_confirmed_r} status code != 403"

	# _________________________________________________________________________________________________
	user.headers["Authorization"] += "qwerty"

	bad_token_r = await func(**request_params)
	assert bad_token_r.status_code == 401, f"{bad_token_r} status code != 401"

	user.headers["Authorization"] = user.headers["Authorization"].replace("qwerty", str())

	await change_user_data(user, session, email_confirmed=True)


async def url_auth_roles_test(url: str, method: Literal["get", "post", "put", "delete"],
							  role: RoleEnum, user: UserData, session: AsyncSession, ac: AsyncClient,
							  json: dict[str, Any] = None) -> None:
	"""
	Проверяет УРЛ на ответ при аутентификации запрещенных ролей.
	"""
	if user.role != role:
		raise ValueError

	requests = {
		"get": ac.get, "post": ac.post, "put": ac.put, "delete": ac.delete
	}

	func = requests.get(method)
	request_params = {"url": url, "headers": user.headers, "cookies": user.cookies}
	match method:
		case "post" | "put":
			request_params["json"] = json or {}

	responses = []

	roles = {
		role.SYSADMIN: (role.MANAGER, role.LAUNDRY, role.INSTALLER),
		role.MANAGER: (role.INSTALLER, role.LAUNDRY),
		role.INSTALLER: (role.LAUNDRY, )
	}

	roles = roles.get(role)

	for r in roles:
		await change_user_data(user, session, role=r)
		permissions_error_r = await func(**request_params)
		responses.append(permissions_error_r)

	await change_user_data(user, session, role=role)

	assert all(
		(response.status_code == 403 for response in responses)
	), str(responses)


async def url_auth_stations_test(url: str, method: Literal["get", "post", "put", "delete"],
								 station: StationData, session: AsyncSession,
								ac: AsyncClient, json: dict[str, Any] = None) -> None:
	"""
	Проверяет УРЛ на ответ при аутентификации станции:
	- Несуществующий УУИД станции;
	- Неактивная станция;
	- Статус станции "технические работы" (обслуживание).
	"""
	requests = {
		"get": ac.get, "post": ac.post, "put": ac.put, "delete": ac.delete
	}
	func = requests.get(method)
	request_params = {"url": url, "headers": station.headers}
	match method:
		case "post" | "put":
			request_params["json"] = json or {}

	# _________________________________________________________________________________________________

	current_station_uuid = station.id
	station.headers["X-Station-Uuid"] = str(uuid.uuid4())
	incorrect_uuid_r = await func(**request_params)
	assert incorrect_uuid_r.status_code == 401, f"{incorrect_uuid_r} status code != 401"
	station.headers["X-Station-Uuid"] = str(current_station_uuid)

	# _________________________________________________________________________________________________

	await change_station_params(station, session, is_active=False)
	inactive_station_r = await func(**request_params)
	assert inactive_station_r.status_code == 403, f"{inactive_station_r} status code != 403"

	# _________________________________________________________________________________________________

	await change_station_params(station, session, is_active=True, status=StationStatusEnum.MAINTENANCE)

	station_in_maintenance_r = await func(**request_params)

	assert station_in_maintenance_r.status_code == 403, f"{station_in_maintenance_r} status code != 403"


async def url_get_station_by_id_test(url: str, method: Literal["get", "post", "put", "delete"],
									 user: UserData,
									 station: StationData, session: AsyncSession, ac: AsyncClient,
									 json: dict[str, Any] = None) -> None:
	"""
	Поиск станции по ИД (в маршруте).
	- Станция должна существовать;
	- Станция не должна быть в статусе "обслуживание".
	"""
	if user.role != RoleEnum.SYSADMIN:  # на всякий случай от него проверяю, у него максимальные права везде
		raise ValueError
	requests = {
		"get": ac.get, "post": ac.post, "put": ac.put, "delete": ac.delete
	}
	correct_url = url
	url = correct_url.format(station_id=uuid.uuid4())

	func = requests.get(method)
	request_params = {"url": url, "headers": user.headers, "cookies": user.cookies}
	match method:
		case "post" | "put":
			request_params["json"] = json or {}

	# _________________________________________________________________________________________________

	incorrect_station_uuid_r = await func(**request_params)
	assert incorrect_station_uuid_r.status_code == 404, f"{incorrect_station_uuid_r} status code != 404"

	# _________________________________________________________________________________________________

	await change_station_params(
		station, session, status=StationStatusEnum.MAINTENANCE
	)

	url = correct_url.format(station_id=station.id)
	request_params["url"] = url
	station_in_maintenance_r = await func(**request_params)

	assert station_in_maintenance_r.status_code == 403, f"{station_in_maintenance_r} status code != 403"
