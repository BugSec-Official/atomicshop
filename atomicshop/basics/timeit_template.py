import timeit

times_int = 1000

SETUP_CODE = '''
import psutil'''

TEST_CODE = '''
list(psutil.process_iter())'''

times = timeit.timeit(setup=SETUP_CODE, stmt=TEST_CODE, number=times_int)
print('list: {}'.format(times))

TEST_CODE = '''
frozenset(psutil.process_iter())'''

times = timeit.timeit(setup=SETUP_CODE, stmt=TEST_CODE, number=times_int)
print('frozenset: {}'.format(times))
