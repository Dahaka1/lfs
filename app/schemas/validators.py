import datetime
from typing import Any

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

import config


def validate_program_step(program_step: int | None) -> None:
	"""
	Этап программы станции заканчивается на 1-5.
	"""
	if program_step and int(str(program_step)[-1]) not in range(1, 6):
		raise ValueError("Program step number must ends with 1 or 5.")


def validate_program_number(program_step: int, program_number: int) -> None:
	"""
	Номер программы - это первые цифры (количество десятков) числа, обозначающего шаг программы.
	"""
	if program_step // 10 != program_number:
		raise ValueError("Program number must be 'program_step' // 10")


def validate_address(address: str) -> None:
	"""
	Проверка адреса на валидность.
	"""
	geolocator = Nominatim(user_agent=config.GEO_APP, timeout=10)
	geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
	location = geocode(address)
	if location is None:
		raise ValueError(f"Incorrect station address '{address}'")


def update_updated_at_field(values: dict[str, Any]) -> dict[str, Any] | None:
	"""
	SA не обновляет updated_at... Поэтому вручную буду =)
	"""
	try:
		updated_at = values["updated_at"]
		if not updated_at:
			values["updated_at"] = datetime.datetime.now()
		return values
	except KeyError:
		pass

