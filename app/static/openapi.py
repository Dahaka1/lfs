from pydantic import BaseModel
from ..schemas.schemas_token import Token
from ..schemas.schemas_users import User
from ..schemas.schemas_email_code import RegistrationCode
from ..schemas import schemas_logs as logs, schemas_users as users, schemas_stations as stations

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
	},
	{
		"name": "logs",
		"description": "Создание и чтение логов разного типа."
	},
	{
		"name": "maintenance_logs",
		"description": "Обслуживание станции: добавление лога об обслуживании и изменение статуса станции."
	},
	{
		"name": "users",
		"description": "Функционал для работы с пользовательскими данными."
	},
	{
		"name": "stations",
		"description": "Создание новой станции, чтение всех станций, чтение собственных данных станциями."
	},
	{
		"name": "station_creating",
		"description": "Создание станции."
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
	404: {
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

add_station_log_post_responses = {
	201: {
		"description": "Возвращается объект созданного лога выбранного типа.",
		"model": logs.ErrorLog | logs.StationProgramsLog | logs.WashingAgentUsingLog
	},
	403: {
		"description": "Inactive station / Station servicing"
	}
}

get_station_logs_get = {
	200: {
		"description": "Список логов выбранного типа.",
		"model": list[logs.ErrorLog] | list[logs.StationMaintenanceLog] | list[logs.ChangesLog] |
				list[logs.WashingAgentUsingLog] | list[logs.StationProgramsLog]
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	},
	404: {
		"description": "Station not found"
	}
}

station_maintenance_log_post = {
	201: {
		"description": "Созданный лог о начале обслуживания (смене статуса станции на \"обслуживание\").",
		"model": logs.StationMaintenanceLog
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	},
	404: {
		"description": "Station not found"
	},
	409: {
		"description": "Station status must be awaiting / Not ended station maintenance exists"
	}
}

station_maintenance_log_put = {
	200: {
		"description": "Завершенный лог об обслуживании (смене статуса станции на \"ожидание\").",
		"model": logs.StationMaintenanceLog
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	},
	404: {
		"description": "Station not found"
	},
	409: {
		"description": "Station maintenance not found"
	}
}

read_users_get = {
	200: {
		"description": "Список всех пользователей.",
		"model": list[users.User]
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	}
}

create_user_post = {
	201: {
		"description": "Созданный пользователь.",
		"model": users.User
	},
	409: {
		"description": "Email already registered"
	}
}

read_users_me_get = {
	200: {
		"description": "Данные пользователя.",
		"model": users.User
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	}
}

read_user_get = {
	200: {
		"description": "Данные пользователя.",
		"model": users.User
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	}
}

update_user_put = {
	200: {
		"description": "Обновленные данные пользователя.",
		"model": users.User
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	},
	404: {
		"description": "User not found"
	}
}


class DeletedUser(BaseModel):
	deleted_user: int


delete_user_delete = {
	200: {
		"description": "ИД удаленного пользователя.",
		"model": DeletedUser
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	},
	404: {
		"description": "User not found"
	}
}

read_all_stations_get = {
	200: {
		"description": "Все существующие станции (только их основные параметры, не все данные).",
		"model": list[stations.StationGeneralParams]
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	},
	422: {
		"description": "Invalid station *UUID* data"
	}
}

create_station_post = {
	201: {
		"description": "Созданная станция (полные данные)",
		"model": stations.Station
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed"
	}
}

read_stations_params_get = {
	200: {
		"description": "Запрошенные станцией данные",
		"model": stations.StationPartial
	},
	401: {
		"description": "Incorrect station UUID"
	},
	403: {
		"description": "Inactive station / Station servicing"
	},
	404: {
		"description": "Getting *DATATYPE* for station *UUID* error. DB data not found"
	}
}

read_stations_me_get = {
	200: {
		"description": "Полные данные станции",
		"model": stations.StationForStation
	},
	401: {
		"description": "Incorrect station UUID"
	},
	403: {
		"description": "Inactive station / Station servicing"
	},
	404: {
		"description": "Getting *DATATYPE* for station *UUID* error. DB data not found"
	}

}

for _ in [
	token_post_responses,
	confirm_email_post_responses,
	confirm_email_get_responses,
	add_station_log_post_responses,
	get_station_logs_get,
	station_maintenance_log_post,
	station_maintenance_log_put,
	read_users_get,
	read_users_me_get,
	read_user_get,
	update_user_put,
	delete_user_delete,
	read_all_stations_get,
	create_station_post
]:
	_.setdefault(401, {"description": "Could not validate credentials"})

