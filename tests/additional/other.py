import datetime
from random import randint


def generate_datetime() -> datetime.datetime:
	y = randint(2000, 2050)
	m = randint(1, 12)
	d = randint(1, 28)
	h = randint(1, 23)
	m_ = randint(1, 59)
	s = randint(1, 59)
	return datetime.datetime(y, m, d, h, m_, s)
