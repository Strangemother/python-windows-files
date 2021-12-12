import os
# import loop
# from concurrent.futures import  ThreadPoolExecutor

# import threading

from multiprocessing import Pool
from contextlib import closing
from monitor.win import sync_to_async_main
# import time


def main():
    return run()


def close(pool):
    pool.close()
    pool.join()


def run(settings=None):
    print('main.run', os.getpid())
    settings = settings or get_settings()
    pool = Pool(len(settings))

    try:
        with closing(pool) as p:
            p.map(sync_to_async_main, settings)
    except KeyboardInterrupt as e:
        close(pool)
    except Exception as e:
        print('Expection', e)
    finally:
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
