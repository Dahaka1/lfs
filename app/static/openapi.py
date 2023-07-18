from ..schemas.schemas_token import Token
from ..schemas.schemas_users import User
from ..schemas.schemas_email_code import RegistrationCode

tags_metadata = [
	{
		"name": "authentication",
		"description": "Аутентификация/регистрация/авторизация в приложении"
	},
	{
		"name": "token",
		"description": "Проверка данных пользователя для входа и получение им аутентификационных токенов"
	},
	{
		"name": "confirming_email",
		"description": "Подтверждение собственного email пользователем посредством получения и ввода проверочных кодов"
	}
]


token_post_responses = {
	200: {
		"description": "Валидный токен пользователя",
		"model": Token
	},
	401: {
		"description": "Incorrect username or password"
	},
	403: {
		"description": "Disabled user"
	}
}

confirm_email_post_responses = {
	200: {
		"description": "При успешном подтверждении кода возвращаются объекты пользователя и кода (с обновленными данными)",
		"model": dict[str, User | RegistrationCode]
	},
	400: {
		"description": "User code not found"
	},
	403: {
		"description": "User email already confirmed / Disabled user / Invalid confirmation code"
	},
	408: {
		"description": "Confirmation code expired"
	}
}

confirm_email_get_responses = {
	200: {
		"description": "Пустой положительный ответ в случае успешного подтверждения кода пользователем."
	},
	403: {
		"description": "User email already confirmed / Disabled user"
	},
	425: {
		"description": "Active user confirmation code already exists"
	}
}


for _ in [
	token_post_responses,
	confirm_email_post_responses,
	confirm_email_get_responses
]:
	_.setdefault(401, {"description": "Could not validate credentials"})

