from tests.additional.stations import rand_serial
from tests.additional.strings import generate_string


test_create_station_with_advanced_params = dict(station={
	"name": generate_string(),
	"serial": rand_serial(),
	"wifi_name": "qwerty",
	"wifi_password": "qwerty",
	# "address": "Санкт-Петербург",
	"region": "Северо-западный",  # из енама регионов
	"is_active": True,
	"is_protected": True,
	"settings": {
			"station_power": True,
			"teh_power": True
		},
	"programs": [
			{
				"name": "Махра",
				"program_step": 11,
				"washing_agents": [
					{
						"agent_number": 1,
						"volume": 25
					},
					{
						"agent_number": 2,
						"volume": 15
					}
				]
			},
			{
				"name": "Махра цветная",
				"program_step": 12,
				"washing_agents": [
					1, 2, 3,
					{
						"agent_number": 4,
						"volume": 35
					}
				]
			}
		],
	"washing_agents": [
			{
				"agent_number": 1,
				"volume": 35
			},
			{
				"agent_number": 2
			},
			{
				"agent_number": 3,
				"volume": 40,
				"rollback": True
			},
			{
				"agent_number": 4
			}
		],
	"washing_machines": [
			{
				"machine_number": 1,
				"volume": 50
			},
			{
				"machine_number": 2,
				"is_active": False,
				"track_length": 4.5
			}
		]
})

get_default_programs = ("[['Махра белая', '1', '11', '[1]'], "
                    "['Махра белая', '1', '12', '[2]'], "
                    "['Махра белая', '1', '13', '[3]'], "
                    "['Махра белая', '1', '14', '[4]'], "
                    "['Махра белая', '1', '15', '[5]'], "
                    "['Махра цветная', '2', '21', '[1]'], "
                    "['Махра цветная', '2', '22', '[2]'],"
                    " ['Махра цветная', '2', '23', '[3]'], "
                    "['Махра цветная', '2', '24', '[4]'], "
                    "['Махра цветная', '2', '25', '[5]']] ",
					"['Махра цветная', '3', '31', '[1]'], "
					"['Махра цветная', '3', '32', '[2]'],"
					" ['Махра цветная', '3', '33', '[3]'], "
					"['Махра цветная', '3', '34', '[4]'], "
					"['Махра цветная', '3', '35', '[5]']] ")
