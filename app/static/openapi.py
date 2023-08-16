from pydantic import BaseModel

from ..schemas import schemas_logs as logs, schemas_users as users, schemas_stations as stations, \
	schemas_washing as washing, schemas_token as tokens
from ..schemas.schemas_email_code import RegistrationCode
from ..schemas.schemas_users import User

tags_metadata = [
	{
		"name": "authentication",
		"description": "Аутентификация/авторизация пользователя в приложении"
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
	},
	{
		"name": "stations_management",
		"description": "Управление данными станции."
	},
	{
		"name": "washing_services_management",
		"description": "Управление данными стиральных средств, стиральных машин."
	}
]

main_responses = {
	200: {
		"description": "Приветственное сообщение (сервер доступен)",
		"content": {
			"application/json": {
				"example": {"message": "Server is available"}
			}
		}
	}
}


login_post = {
	200: {
		"description": "Refresh (body) и Access (body) токены пользователя",
		"model": tokens.RefreshToken
	},
	401: {
		"description": "Incorrect username or password"
	},
	403: {
		"description": "Disabled user"
	}
}

refresh_access_token_get = {
	200: {
		"description": "Обновленные токены пользователя",
		"model": tokens.RefreshToken
	},
	403: {
		"description": "Disabled user"
	}
}

logout_get = {
	200: {
		"description": "ИД пользователя в случае успешного выхода",
		"content": {
			"application/json": {
				"example": {"logout": "user_id"}
			}
		}
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
		"description": "Пустой положительный ответ в случае успешной отправки кода пользователю."
	},
	403: {
		"description": "User email already confirmed / Disabled user"
	},
	425: {
		"description": "Active user confirmation code already exists"
	}
}
#
# create_log_post = {
# 	201: {
# 		"description": "Созданный лог.",
# 		"model": logs.Log
# 	},
# 	401: {
# 		"description": "Incorrect station UUID"
# 	},
# 	403: {
# 		"description": "Inactive station / Station servicing"
# 	},
# 	404: {
# 		"description": "Getting station data error"
# 	}
# }
#
# create_error_post = {
# 	201: {
# 		"description": "Созданная ошибка.",
# 		"model": logs.Error
# 	},
# 	401: {
# 		"description": "Incorrect station UUID"
# 	},
# 	403: {
# 		"description": "Inactive station / Station servicing"
# 	},
# 	404: {
# 		"description": "Getting station data error"
# 	}
# }

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
		"model": stations.StationGeneralParamsForStation | stations.StationControl | \
				stations.StationSettings | list[stations.StationProgram] | list[washing.WashingAgent] | list[washing.WashingMachine]
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

read_station_partial_by_user_get = {
	200: {
		"description": "Запрошенные данные станции",
		"model": stations.StationGeneralParams | stations.StationControl | \
				stations.StationSettings | list[stations.StationProgram] | list[washing.WashingAgent] | list[washing.WashingMachine]
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	}
}

read_station_all_by_user = {
	200: {
		"description": "Все данные по станции",
		"model": stations.Station
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	}
}

update_station_general_put = {
	200: {
		"description": "Обновленные основные параметры станции (если изменились данные WiFi - обновленные выведутся)",
		"model": stations.StationGeneralParams | stations.StationGeneralParamsForStation
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	}
}

update_station_control_put = {
	200: {
		"description": "Обновленные параметры текущего состояния станции",
		"model": stations.StationControl
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	},
	409: {
		"description": "Updating error (data conflict)"
	}
}

update_station_settings_put = {
	200: {
		"description": "Обновленные настройки станции",
		"model": stations.StationSettings
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	},
	409: {
		"description": "Updating error (data conflict)"
	}
}

create_station_program_post = {
	201: {
		"description": "Созданные программы станции",
		"model": list[stations.StationProgram]
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found / "
					   "Washing agent №*NUMBER* not found in station washing agents"
	},
	409: {
		"description": "Creating error (data conflict)"
	}
}

update_station_program_put = {
	200: {
		"description": "Обновленная программа станции",
		"model": stations.StationProgram
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found /"
					   "Got an non-existing washing agent number"
	},
	409: {
		"description": "Updating error (data conflict)"
	}
}

delete_station_program_delete = {
	200: {
		"description": "ИД удаленной программы, ИД станции"
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	},
	409: {
		"description": "Deleting error (data conflict)"
	}
}

delete_station_delete = {
	200: {
		"description": "ИД удаленной станции"
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	}
}

create_station_washing_services_post = {
	201: {
		"description": "Созданный объект (стиральная машина / стиральное средство)",
		"model": washing.WashingAgentCreate | washing.WashingMachineCreate
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found"
	},
	409: {
		"description": "Creating error (data conflict)"
	}
}

update_station_washing_agent_put = {
	200: {
		"description": "Обновленное стиральное средство",
		"model": washing.WashingAgent
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found / "
					   "Washing agent not found"
	},
	409: {
		"description": "Updating error (data conflict)"
	}
}

update_station_washing_machine_put = {
	200: {
		"description": "Обновленная стиральная машина",
		"model": washing.WashingMachine
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found / "
					   "Washing machine not found"
	},
	409: {
		"description": "Updating error (data conflict)"
	}
}

delete_station_washing_services_delete = {
	200: {
		"description": "ИД удаленной стиральной машины / удаленного стирального средства"
	},
	403: {
		"description": "Permissions error / Disabled user / User email not confirmed / Station servicing"
	},
	404: {
		"description": "Station not found / Getting *DATASET* for station *UUID* error. DB data not found / "
					   "WashingAgent not found / WashingMachine not found"
	},
	409: {
		"description": "Deleting error (data conflict)"
	}
}

for _ in [
	login_post,
	refresh_access_token_get,
	logout_get,
	confirm_email_post_responses,
	confirm_email_get_responses,
	read_users_get,
	read_users_me_get,
	read_user_get,
	update_user_put,
	delete_user_delete,
	read_all_stations_get,
	create_station_post,
	read_station_partial_by_user_get,
	read_station_all_by_user,
	update_station_general_put,
	update_station_control_put,
	update_station_settings_put,
	create_station_program_post,
	update_station_program_put,
	delete_station_program_delete,
	create_station_washing_services_post,
	update_station_washing_agent_put,
	update_station_washing_machine_put,
	delete_station_washing_services_delete
]:
	_.setdefault(401, {"description": "Could not validate credentials"})

