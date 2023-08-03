import random
from string import ascii_letters


def generate_string(length: int = 20) -> str:
	"""
	Возвращает случайную строку
	"""
	return ''.join(
		(random.choice(ascii_letters) for _ in range(length))
	)


