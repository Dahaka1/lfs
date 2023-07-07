def validate_program_step(program_step: int) -> int:
	"""
		Этап программы станции заканчивается на 1-5.
	"""
	if str(program_step)[1] not in range(1, 6):
		raise ValueError("Program step number must ends with 1 or 5.")
	return program_step
