import time
from typing import Callable, Literal, Awaitable, Any
import datetime

from fastapi import Request, Response

from .utils.logs import log_request_handling_time
from .static.typing import PathOperation


class CustomMiddleware:
	"""
	Миддлваря =)
	"""
	_process: Callable[[tuple[Any, ...]], Awaitable[Any]]

	def __init__(self, request: Request, call_next: PathOperation, *args, **kwargs):
		self.request = request
		self.call_next = call_next
		self.args = args
		self.kwargs = kwargs

	async def __aenter__(self) -> Response:
		return await self._process(*self.args, **self.kwargs)

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		pass


class ProcessTimeLogMiddleware(CustomMiddleware):
	async def _process(self, request_from: Literal["Station", "User"], request_from_id: str = "undefined") -> Response:
		"""
		Логирование времени обработки запроса.
		"""
		start_time = time.time()
		response: Response = await self.call_next(self.request)
		if response.status_code in range(200, 300):
			process_time = time.time() - start_time
			log_request_handling_time(
				request_from=request_from, time=str(datetime.datetime.now()), method=self.request.method,
				request_from_id=request_from_id, result=process_time, url=self.request.url
			)
		return response
