from typing import TypeAlias

from ..schemas import schemas_stations


StationParamsSet: TypeAlias = schemas_stations.StationGeneralParams | schemas_stations.StationSettings | \
	schemas_stations.StationControl | list[schemas_stations.StationProgram] | schemas_stations.Station
