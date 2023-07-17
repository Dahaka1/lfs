from email.message import EmailMessage

import smtplib
from loguru import logger

from .schemas.schemas_users import User
from .models.auth import RegistrationCode
import services


def send_verifying_email_code(registering_user: User):
	"""
	Отправка email-кода верификации зарегистрированному пользователю.
	Запись в БД информации об отправке (RegistrationCode.create_obj).

	Пришлось сделать эту функцию синхронной, ибо асинхронные фоновые задачи
	 фастапи блокируют основной поток (доп. воркеры не помогли).

	Генерирует шаблон сообщения.
	TODO: разработать шаблон.
	"""
	code = RegistrationCode.generate_code()

	message = EmailMessage()
	message["From"] = services.SMTP_USER
	message["To"] = registering_user.email
	message["Subject"] = "LFS - код подтверждения Email"
	message.set_content(
		RegistrationCode.generate_message_template(user=registering_user, code=code),
		subtype="html"
	)

	with smtplib.SMTP(host=services.SMTP_HOST, port=services.SMTP_PORT) as smtp_server:
		smtp_server.starttls()
		smtp_server.login(user=services.SMTP_USER, password=services.SMTP_PASSWORD)
		try:
			smtp_server.send_message(msg=message)
			RegistrationCode.create_obj(
				email_message=message, verification_code=code, user=registering_user
			)
			logger.info(f"Registration code was successfully sended to user email "
						f"{registering_user.email} from {services.SMTP_USER}.")
		except Exception as e:
			logger.error(f"Registration code wasn't sended to user email {registering_user.email} "
						f"from {services.SMTP_USER}. "
						f"Error: {e}")
