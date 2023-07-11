import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .additional.users import change_user_role
from app.static.enums import RoleEnum
from app.schemas.schemas_stations import StationCreate


@pytest.mark.usefixtures("generate_confirmed_user_with_token")
class TestStations:
	async def test_create_station_with_default_params(self, async_test_client: AsyncClient, session: AsyncSession):
		"""
		Создание станции.
		"""
		await change_user_role(user_id=self.id, needed_role=RoleEnum.SYSADMIN.value, session=session)

		default_station = StationCreate(
			wifi_name="qwerty", wifi_password="qwerty", address="Санкт-Петербург, ул. Дыбенко, 26"
		)

		response = await async_test_client.post(
			"/api/v1/stations/",
			headers=self.headers,
			json=default_station.dict()
		)

		assert response.status_code == 201

		assert response.json() == {
		}
