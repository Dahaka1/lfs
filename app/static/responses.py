from ..schemas.schemas_token import Token


token_responses = {
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

