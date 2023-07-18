import datetime
import uuid
from typing import Any, Literal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, update

from app.models.auth import RegistrationCode
from .users import change_user_data, UserData
from app.static.enums import StationStatusEnum, RoleEnum
from .stations import StationData, change_station_params


async def delete_user_code(user: Any, session: AsyncSession) -> None:
	"""
	Удаляет код подтверждения email пользователя.
	"""
	if isinstance(user.id, int):  # чтоб не ругался линтер
		await session.execute(
			delete(RegistrationCode).where(RegistrationCode.user_id == user.id)
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
				expires_at=datetime.datetime.now() - datetime.timedelta(hours=10)
			)
		)
		await session.commit()


async def url_auth_test(url: str, method: Literal["get", "post", "put", "delete"], user: Any,
						ac: AsyncClient, session: AsyncSession, json: dict[str, Any] = None) -> None:
	"""
	Проверяет УРЛ на ответ:
	- Невалидному токену пользователя;
	- Заблокированному пользователю;
	- Неподтвержденному пользователю (или подтвержденному, где это запрещено).
	"""
	await change_user_data(user, session, email_confirmed=False)
	requests = {
		"get": ac.get, "post": ac.post, "put": ac.put, "delete": ac.delete
	}

	func = requests.get(method)

	await change_user_data(user, session, disabled=True)
	match method:
		case "get":
			disabled_user_r = await func(url=url, headers=user.headers)
		case _:
			disabled_user_r = await func(url=url, headers=user.headers, json=json or {})

	assert disabled_user_r.status_code == 403, f"{disabled_user_r} status code != 403"

	await change_user_data(user, session, disabled=False)
	if url == "/api/v1/auth/confirm_email":
		await change_user_data(user, session, email_confirmed=True)
		match method:
			case "get":
				email_already_confirmed_r = await func(url=url, headers=user.headers)
			case _:
				email_already_confirmed_r = await func(url=url, headers=user.headers,
													   json=json or {})

		assert email_already_confirmed_r.status_code == 403, f"{email_already_confirmed_r} status code != 403"

		await change_user_data(user, session, email_confirmed=False)
	else:
		match method:
			case "get":
				email_not_confirmed_r = await func(url=url, headers=user.headers)
			case _:
				email_not_confirmed_r = await func(url=url, headers=user.headers,
												   json=json or {})

		assert email_not_confirmed_r.status_code == 403, f"{email_not_confirmed_r} status code != 403"

	user.headers["Authorization"] += "qwerty"
	match method:
		case "get":
			bad_token_r = await func(url=url, headers=user.headers)
		case _:
			bad_token_r = await func(url=url, headers=user.headers, json=json or {})

	assert bad_token_r.status_code == 401, f"{bad_token_r} status code != 401"

	await change_user_data(user, session, email_confirmed=True)
	user.headers["Authorization"] = user.headers["Authorization"].replace("qwerty", str())


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

	current_station_uuid = station.id

	station.headers["X-Station-Uuid"] = str(uuid.uuid4())

	match method:
		case "get":
			incorrect_uuid_r = await func(url, headers=station.headers)
		case _:
			incorrect_uuid_r = await func(url, headers=station.headers, json=json or {})

	assert incorrect_uuid_r.status_code == 401, f"{incorrect_uuid_r} status code != 401"

	station.headers["X-Station-Uuid"] = current_station_uuid

	await change_station_params(station, session, is_active=False)

	match method:
		case "get":
			inactive_station_r = await func(url, headers=station.headers)
		case _:
			inactive_station_r = await func(url, headers=station.headers, json=json or {})

	assert inactive_station_r.status_code == 403, f"{inactive_station_r} status code != 403"

	await change_station_params(station, session, is_active=True, status=StationStatusEnum.MAINTENANCE)

	match method:
		case "get":
			station_in_maintenance_r = await func(url, headers=station.headers)
		case _:
			station_in_maintenance_r = await func(url, headers=station.headers, json=json or {})

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
	if user.role != RoleEnum.SYSADMIN:
		raise ValueError
	requests = {
		"get": ac.get, "post": ac.post, "put": ac.put, "delete": ac.delete
	}
	correct_url = url
	url = correct_url.format(station_id=uuid.uuid4())

	func = requests.get(method)

	match method:
		case "get":
			incorrect_station_uuid_r = await func(url, headers=user.headers)
		case _:
			incorrect_station_uuid_r = await func(url, headers=user.headers, json=json or {})

	assert incorrect_station_uuid_r.status_code == 404, f"{incorrect_station_uuid_r} status code != 404"

	await change_station_params(
		station, session, status=StationStatusEnum.MAINTENANCE
	)

	url = correct_url.format(station_id=station.id)

	match method:
		case "get":
			station_in_maintenance_r = await func(url, headers=user.headers)
		case _:
			station_in_maintenance_r = await func(url, headers=user.headers, json=json or {})

	assert station_in_maintenance_r.status_code == 403
