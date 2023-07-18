import datetime
import random
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

import services
from app.static.enums import RoleEnum, RegionEnum
from app.schemas import schemas_stations, schemas_washing
from .users import create_authorized_user, UserData
from app.models.stations import StationControl, Station
from app.models import logs


@dataclass
class StationData:
	"""
	Класс станции с парамерами для тестов.
	"""
	id: uuid.UUID
	is_active: bool
	is_protected: bool
	location: dict
	region: RegionEnum
	station_programs: list[schemas_stations.StationProgram]
	station_washing_machines: list[schemas_washing.WashingMachine]
	station_washing_agents: list[schemas_washing.WashingAgent]
	station_control: schemas_stations.StationControl
	station_settings: schemas_stations.StationSettings
	headers: dict[str, str]


async def generate_station(
	ac: AsyncClient,
	sync_session: Session,
	**kwargs
) -> StationData:
	"""
	Генерирует станцию.
	Работает через запрос к АПИ (иначе оч долго заполнять вручную таблицы).
	Поэтому поаккуратней с этим =)
	"""
	user, user_schema = await create_authorized_user(ac, sync_session, RoleEnum.SYSADMIN, confirm_email=True)
	station_data = dict(station={
		"is_active": kwargs.get("is_active") or True,
		"is_protected": kwargs.get("is_protected") or False,
		"wifi_name": "qwerty",
		"wifi_password": "qwerty",
		"address": "Санкт-Петербург",
		"region": "Северо-западный"
	})

	additional = {
		"settings": kwargs.get("settings"),
		"programs": kwargs.get("programs"),
		"washing_agents": kwargs.get("washing_agents"),
		"washing_machines": kwargs.get("washing_machines")
	}

	for k, v in additional.items():
		if v is not None:
			station_data.setdefault(k, v)

	if not additional["programs"]:
		station_data["programs"] = generate_station_programs()

	response = await ac.post(
		"/api/v1/stations/",
		headers=user.headers,
		json=station_data
	)

	if response.status_code == 201:
		station = response.json()
		station.pop("updated_at")
		station.pop("created_at")
		station["headers"] = {"X-Station-Uuid": str(station["id"])}
		return StationData(**station)
	else:
		raise AssertionError(str(response))


async def change_station_params(station: StationData, session: AsyncSession, **kwargs) -> None:
	"""
	Изменение параметров станции.
	"""
	for k, v in kwargs.items():
		match k:
			case "is_active":
				query = update(Station).where(Station.id == station.id).values(is_active=v)
			case "status" | "washing_machine" | "washing_agents":
				query = update(StationControl).where(StationControl.station_id == station.id).values(
					**{k: v}
				)
			case _:  # надо тут определять аргументы явно
				raise AttributeError
		await session.execute(query)
	await session.commit()


async def create_random_station_logs(station: StationData,
										user: UserData,
									 session: AsyncSession,
									 amount: int = 3) -> None:
	"""
	Создать рандомные логи для тестов.
	"""
	rand_washing_machine = random.choice(station.station_washing_machines)
	rand_washing_agent = random.choice(station.station_washing_agents)
	rand_program = random.choice(station.station_programs)

	error = logs.ErrorsLog(station_id=station.id, code=0, content="qwerty")
	washing_agents_using = logs.WashingAgentsUsingLog(station_id=station.id,
													  washing_machine=rand_washing_machine,
													  washing_agent=rand_washing_agent)
	change = logs.ChangesLog(station_id=station.id, user_id=user.id, content="qwerty")
	program_using = logs.StationProgramsLog(station_id=station.id, program_step=rand_program)
	maintenance = logs.StationMaintenanceLog(station_id=station.id, user_id=user.id,
											 started_at=datetime.datetime.now() - datetime.timedelta(days=1),
											 ended_at=datetime.datetime.now())

	for log in (error, washing_agents_using, change, program_using, maintenance):
		for _ in range(amount):
			session.add(log)
			await session.commit()


def generate_station_programs() -> list[dict[str, Any]]:
	"""
	Сгенерировать программы для станции.
	"""
	programs = []
	program_step = 11
	for _ in range(4):
		washing_agents = [random.randint(1, services.DEFAULT_STATION_WASHING_AGENTS_AMOUNT)]
		program = schemas_stations.StationProgramCreate(
			program_step=program_step, washing_agents=washing_agents
		)
		programs.append(program)
		program_step += 1
	return [pg.dict() for pg in programs]
