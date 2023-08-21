from tests.additional.stations import rand_serial


test_create_station_with_advanced_params = dict(station={
	"serial": rand_serial(),
	"wifi_name": "qwerty",
	"wifi_password": "qwerty",
	"address": "Санкт-Петербург",
	"region": "Северо-западный",  # из енама регионов
	"is_active": True,
	"is_protected": True,
	"settings": {
			"station_power": True,
			"teh_power": True
		},
	"programs": [
			{
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
