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

