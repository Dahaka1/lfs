from email.message import EmailMessage

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from .schemas.schemas_users import User
from .models.auth import RegistrationCode
import services


async def send_verifying_email_code(registering_user: User, db: AsyncSession):
	"""
	Отправка email-кода верификации зарегистрированному пользователю.
	Запись в БД информации об отправке (RegistrationCode.create_obj).

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

	async with aiosmtplib.SMTP(hostname=services.SMTP_HOST, port=services.SMTP_PORT) as smtp_server:
		await smtp_server.login(username=services.SMTP_USER, password=services.SMTP_PASSWORD)
		sending_result = await smtp_server.send_message(message=message)
		sending_errors: dict = sending_result[0]
		if not any(sending_errors):
			await RegistrationCode.create_obj(
				email_message=message, verification_code=code, user=registering_user, db=db
			)
			logger.info(f"Registration code was successfully sended to user email "
						f"{registering_user.email} from {services.SMTP_USER}.")
		else:
			logger.info(f"Registration code wasn't sended to user email {registering_user.email} "
						f"from {services.SMTP_USER}. "
						f"Please, check the sending functions or SMTP server connection for errors.")
