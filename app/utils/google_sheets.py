from httpx import AsyncClient
from httpx import TimeoutException
from loguru import logger

from ..exceptions import GettingDataError


async def get_sheet_data(url: str) -> list[list[str]] | None:
	"""
	Получение google-sheets данных из таблицы.
	"""
	err_text = "Google sheets getting data error:"
	async with AsyncClient() as client:
		try:
			r = await client.get(url, timeout=10)
		except TimeoutException as err:
			logger.error(str(err))
			raise ConnectionError(f"{err_text} {err}")
	if r.status_code == 200:
		return r.json()["values"]
	raise ConnectionError(f"{err_text} {r.status_code=}, {r.json=}")
