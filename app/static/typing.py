from typing import TypeAlias, Callable, Awaitable, Any

from ..schemas import schemas_stations as stations

StationParamsSet: TypeAlias = stations.StationGeneralParams | stations.StationGeneralParamsForStation | \
	stations.StationSettings | stations.StationControl | list[stations.StationProgram] | stations.Station | \
	stations.StationProgram


PathOperation: TypeAlias = Callable[[Any], Awaitable[Any]]
