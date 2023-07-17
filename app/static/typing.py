from typing import TypeAlias

from ..schemas import schemas_stations as stations


StationParamsSet: TypeAlias = stations.StationGeneralParams | stations.StationSettings | \
	stations.StationControl | list[stations.StationProgram] | stations.Station | \
	stations.StationProgram

