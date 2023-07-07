import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from ..static.enums import RoleEnum


class UserBase(BaseModel):
	email: EmailStr = Field(
		title="Email",
		example="example@gmail.com"
	)
	first_name: str = Field(
		max_length=50,
		title="Имя",
		example="Ярослав"
	)
	last_name: str = Field(
		max_length=50,
		title="Фамилия",
		example="Иванов"
	)


class UserCreate(UserBase):
	password: str = Field(min_length=8)


class User(UserBase):
	id: int = Field(ge=1)
	role: RoleEnum = Field(
		title="Права пользователя",
		example=RoleEnum.MANAGER.value
	)
	disabled: bool = Field(
		title="False, если пользователь активен (не заблокирован)",
		default=False
	)
	registered_at: datetime.datetime = Field(
		title="Дата и время регистрации",
		example=datetime.datetime.now().isoformat()
	)
	last_action_at: Optional[datetime.datetime] = Field(
		title="Время последнего действия",
		example=datetime.datetime.now().isoformat()
	)
	email_confirmed: bool = Field(
		title="Подтвержден ли email"
	)

	class Config:
		orm_mode = True


class UserInDB(User):
	hashed_password: str = Field(
		title="Хэш пароля"
	)


class UserUpdate(BaseModel):
	email: Optional[EmailStr] = Field(
		title="Email",
		example="ijoech@gmail.com",
		default=None
	)
	first_name: Optional[str] = Field(
		max_length=50,
		title="Имя",
		example="Yaroslav",
		default=None
	)
	last_name: Optional[str] = Field(
		max_length=50,
		title="Фамилия",
		example="Ivanov",
		default=None
	)
	password: Optional[str] = Field(
		min_length=8,
		default=None
	)
	disabled: Optional[bool] = Field(
		description="False, если пользователь активен (не заблокирован)",
		default=None
	)
	role: Optional[RoleEnum] = Field(
		title="Права пользователя",
		example=RoleEnum.MANAGER.value,
		default=None
	)
