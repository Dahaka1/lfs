from typing import Literal

import config


def log_request_handling_time(**kwargs) -> None:
	"""
	Логирует время выполнения запроса от станции/пользователя/...
	"""
	try:
		result = config.RESPONSE_TIME_LOGGING_FORMAT.format(**kwargs)
	except KeyError as e:
		raise ValueError("Logging arguments getting error: ", str(e))

	def log(mode: Literal["a", "w"]):
		with open(config.RESPONSE_TIME_LOGGING_PATH, mode, encoding="utf-8") as log_output:
			log_output.write(result + "\n")

	try:
		log("a")
	except FileNotFoundError:
		log("w")
