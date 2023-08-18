from fastapi import HTTPException, status
from loguru import logger

from config import CUSTOM_EXCEPTIONS_OUTPUT_PARAMS


class CredentialsException(HTTPException):
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
	def __init__(
		self,
		detail: str = "Permissions error",
		headers=None,
		status_code: int = status.HTTP_403_FORBIDDEN
	):
		super().__init__(detail=detail, status_code=status_code, headers=headers)


class GettingDataError(Exception):
	"""
	Ошибка при получении данных по станции (отсутствуют данные).
	"""
	def __init__(self, message="Station data not found"):
		super().__init__(message)
		logger.error(message)


class UpdatingError(Exception):
	"""
	Ошибка при обновлении данных станции.
	"""
	def __init__(self, message="Station updating error"):
		super().__init__(message)
		logger.error(message)


class CreatingError(Exception):
	"""
	Ошибка при создании данных станции.
	"""
	def __init__(self, message="Station data creating error"):
		super().__init__(message)
		logger.error(message)


class DeletingError(Exception):
	"""
	Ошибка при удалении данных станции.
	"""
	def __init__(self, message="Station data deleting error"):
		super().__init__(message)
		logger.error(message)


class ValidationError(Exception):
	"""
	Ошибка при получении кастомных данных от клиента.
	"""
	def __init__(self, message="Incoming data validation error"):
		super().__init__(message)
		logger.error(message)
