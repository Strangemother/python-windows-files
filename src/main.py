import os
# import loop
# from concurrent.futures import  ThreadPoolExecutor

# import threading

from multiprocessing import Pool
from contextlib import closing
from monitor.awin import sync_to_async_main, set_keep, death_pill
from monitor import win
# import time
import sys
import multiprocessing

import time
import signal
from multiprocessing import Pool


## Multiproces head correction for
# environment bound multprocess Pool (map)
multiprocessing.set_executable(sys.executable)
multiprocessing.freeze_support()


def main():
    return run()


def close(pool):
    pool.close()
    pool.join()


def sigin(*a, **kw):
    print('signal SIGINT', a, kw)
    death_pill()
    return 9
    # return signal.SIG_IGN(*a, **kw)

def initializer():
    """Ignore CTRL+C in the worker process."""
    # pass
    pass
    # signal.signal(signal.SIGINT, sigin)
    ## https://docs.python.org/3/library/signal.html#signal.SIG_IGN
    # signal.signal(signal.SIGINT, signal.SIG_IGN)


# pool = Pool(initializer=initializer)
def pool_worker(settings):
    r = sync_to_async_main(settings)
    print('Pool worker complete')
    return 0

def run(settings=None):
    print('main.run', os.getpid())
    settings = settings or get_settings()
    pool = Pool(len(settings), initializer=initializer)

    try:
        with closing(pool) as p:
            p.map(pool_worker, settings)
    except KeyboardInterrupt as e:
        print('Top Kill', e)
        pool.terminate()
        pool.join()
    finally:
        print('Closing')
        time.sleep(1)
        if pool:
            close(pool)
    # executor = ThreadPoolExecutor(max_workers=1)
    # setting = get_settings()
    # future = executor.submit(loop.run, setting)
    # future.add_done_callback(lambda f: print(f.result()))

    # print('waiting for callback')

    # executor.shutdown(False)  # non-blocking

    # print('shutdown invoked')
    #, get_settings()[0])
    #return loop.run(*settings)


def get_settings():
    test = ("C:/", "D:/", )
    return test


def load_json(filepath):
    with open(filepath, 'r') as stream:
        return json.load(stream)


def save_json(filepath, data):
    with open(filepath, 'w') as stream:
        json.dump(data, stream, indent=4)


if __name__ == '__main__':
    main()
