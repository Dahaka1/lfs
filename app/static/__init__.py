def app_description() -> str:
	with open("app/static/app_description.txt", encoding='utf-8') as f:
		return f.read()
