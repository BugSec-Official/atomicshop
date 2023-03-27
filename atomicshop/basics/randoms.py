# v1.0.0 - 16.02.2023 16:50
import random


def random_integer(minimum_int: int, maximum_int: int):
    return random.randint(minimum_int, maximum_int)


def random_float(minimum_float: float, maximum_float: float):
    return random.uniform(minimum_float, maximum_float)
