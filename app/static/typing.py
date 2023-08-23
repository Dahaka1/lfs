from typing import TypeAlias, Callable, Awaitable, Any

from sqlalchemy import Select, Insert, Delete, Update

from ..schemas import schemas_stations as stations
from ..exceptions import GettingDataError, DeletingError, ValidationError, CreatingError, UpdatingError

StationParamsSet: TypeAlias = stations.StationGeneralParams | stations.StationGeneralParamsForStation | \
	stations.StationSettings | stations.StationControl | list[stations.StationProgram] | stations.Station | \
	stations.StationProgram


PathOperation: TypeAlias = Callable[[Any], Awaitable[Any]]

SAQueryInstance: TypeAlias = Select, Insert, Update, Delete

AppException: TypeAlias = GettingDataError | DeletingError | ValidationError | CreatingError | UpdatingError
