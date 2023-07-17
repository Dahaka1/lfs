from fastapi import HTTPException, status


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


class ProgramsDefiningError(Exception):
	"""
	Ошибка при создании программ станции (при создании самой станции).
	"""
	def __init__(self, message="Station programs defining error"):
		super().__init__(message)


class GettingDataError(Exception):
	"""
	Ошибка при получении данных по станции (отсутствуют данные).
	"""
	def __init__(self, message="Station data not found"):
		super().__init__(message)


class UpdatingError(Exception):
	"""
	Ошибка при обновлении данных станции.
	"""
	def __init__(self, message="Station updating error"):
		super().__init__(message)


class CreatingError(Exception):
	"""
	Ошибка при создании данных станции.
	"""
	def __init__(self, message="Station data creating error"):
		super().__init__(message)


class DeletingError(Exception):
	"""
	Ошибка при удалении данных станции.
	"""
	def __init__(self, message="Station data deleting error"):
		super().__init__(message)

