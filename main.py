import time
import sys
from config import STARTING_APP_FROM_CMD_DEBUG_ARG
import platform


def main():
	"""
	Синхронная подготовка к запуску приложения.
	На Windows доступен только debug-mode (Windows не поддерживается gunicorn-ом).
	"""
	if STARTING_APP_FROM_CMD_DEBUG_ARG not in sys.argv:
		if platform.system() == "Windows":
			error_text = "Starting error. App cannot be started in Non-debug mode in Windows platform.\n" \
						 "Please start the app with command-line argument: " \
						 f"{STARTING_APP_FROM_CMD_DEBUG_ARG} " \
						 f"(by command 'python main.py {STARTING_APP_FROM_CMD_DEBUG_ARG}')."
			raise RuntimeError(error_text)
		time.sleep(5)  # ожидание, пока БД инициализируется докером

	from app import database_init, start_app, execute_from_command_line
	# importing from app after load dotenv because
	# .env params are needed for database initializing

	starting_params = execute_from_command_line(*sys.argv)
	database_init()
	start_app(**starting_params)


if __name__ == '__main__':
	main()
