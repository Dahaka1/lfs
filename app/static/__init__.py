def app_description() -> str:
	with open("app/static/app_description.txt", encoding='utf-8') as f:
		return f.read()


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
