# import datetime
# from typing import Optional
#
# from pydantic import BaseModel, EmailStr
#
#
# class RegistrationCode(BaseModel):
# 	"""
# 	Модель отправленного пользователю Email-кода.
#
# 	Описание полей - в models.auth.
# 	"""
# 	user_id: int
# 	sended_to: EmailStr
# 	sended_from: EmailStr
# 	sended_at: datetime.datetime
# 	is_confirmed: bool
# 	confirmed_at: Optional[datetime.datetime]
# 	expires_at: datetime.datetime
#
#
# class RegistrationCodeInDB(RegistrationCode):
# 	"""
# 	В основной модели передавать хэш кода не нужно =)
# 	"""
# 	hashed_code: str
