from typing import Any

from fastapi import HTTPException, status
from loguru import logger

from .schemas.schemas_stations import StationGeneralParams
from .models.logs import ErrorsLog
from .static import error_codes


class CredentialsException(HTTPException):
	"""
	authorizing by Bearer token error
	"""
	def __init__(
		self,
		detail: str = "Could not validate credentials",
		headers=None,
		status_code: int = status.HTTP_401_UNAUTHORIZED
	):
		super().__init__(detail=detail, status_code=status_code, headers=headers)
		if headers is None:
			self.headers = {"WWW-Authenticate": "Bearer"}


class PermissionsError(HTTPException):
	"""
	permissions error
	"""
	def __init__(
		self,
		detail: str = "Permissions error",
		headers=None,
		status_code: int = status.HTTP_403_FORBIDDEN
	):
		super().__init__(detail=detail, status_code=status_code, headers=headers)


class LoggingError(Exception):
	message: str
	code: int
	db: Any  # AsyncSession не могу указать - проблема
	station: StationGeneralParams | int

	def __init__(self, **kwargs):
		if not all(
			(arg in self.__annotations__ for arg in kwargs)
		):
			raise AttributeError(f"Got not all arguments that was expected. "
								 f"Expected for: {self.__annotations__.keys()}")
		for k, v in kwargs.items():
			if k not in self.__annotations__:
				raise AttributeError(f"'{k}' is unexpected argument")
			type_ = self.__annotations__.get(k)
			if type_ != Any and not isinstance(v, type_):
				raise TypeError(f"'{k}' argument type isn't {type_.__name__}")
			setattr(self, k, v)
		super().__init__(self.message)

	async def __aenter__(self):
		"""
		При вызове в менеджера контекста всегда добавляется в лог в БД
		"""
		await ErrorsLog.log(self.db, self.station, self.message, self.code)
		logger.error(self.message)
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		pass


class ProgramsDefiningError(LoggingError):
	"""
	Ошибка при создании программ станции (при создании самой станции).
	"""
	def __init__(self, **kwargs):
		kwargs.setdefault("code", error_codes.BAD_DATA_CODE)
		super().__init__(**kwargs)


class GettingDataError(LoggingError):
	"""
	Ошибка при получении данных по станции (отсутствуют данные).
	"""
	def __init__(self, **kwargs):
		kwargs.setdefault("code", error_codes.EMPTY_DATA_CODE)
		super().__init__(**kwargs)


class UpdatingError(LoggingError):
	"""
	Ошибка при обновлении данных станции.
	"""
	def __init__(self, **kwargs):
		kwargs.setdefault("code", error_codes.BAD_DATA_CODE)
		super().__init__(**kwargs)


