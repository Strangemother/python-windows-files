import os
import loop
from concurrent.futures import  ThreadPoolExecutor

import threading

from multiprocessing import Pool
from contextlib import closing
import time


def main():
    return run()


def run(settings=None):
    print('main.run', os.getpid())
    print('Use callback')
    settings = settings or get_settings()
    pool = Pool(len(settings))

    try:
        with closing(pool) as p:
            print(p.map(loop.run, settings))
    except Exception as e:
        print('Expection', e)
    finally:
        pool.close()
        pool.join()
    # executor = ThreadPoolExecutor(max_workers=1)
    # setting = get_settings()
    # future = executor.submit(loop.run, setting)
    # future.add_done_callback(lambda f: print(f.result()))

    # print('waiting for callback')

    # executor.shutdown(False)  # non-blocking

    # print('shutdown invoked')
    #, get_settings()[0])
    #return loop.run(*settings)


def load_json(filepath):
    with open(filepath, 'r') as stream:
        return json.load(stream)


def save_json(filepath, data):
    with open(filepath, 'w') as stream:
        json.dump(data, stream, indent=4)


def get_settings():
    test = (
        "C:\\",
        (
            ('copy', dict(
                dst='F:\\tmp3',
                # Enable syncing.
                sync=True,
                # Push all source files to dest on wake
                init_sync_to=True,
                # False: only sync if dest file is missing.
                # True: at every instance wakr
                init_sync_force=False,
                # copy from dst to src if a dst is newer during init_sync_to
                init_sync_back=True,
                # Attributes to detect changes upon dest file.
                # Using 'created' is not a good idea for 'init'
                init_sync_back_on=['size', 'modified'],
                # copy dst to src if the initial file does not exist in src.
                init_sync_back_missing=True,
                record=True,
                dry=True,
                ignore=[
                    '*.pyc',
                    '**/env/*',
                    '.git/**/*',
                    '.git/*',
                    r'![.]git(\\|/)*.*'
                ]

                ),
            ),
             ('copy', dict(
                dst='F:\\tmp2',
                sync=True,
                init_sync_to=False,
                init_sync_force=False,
                init_sync_back=True,
                init_sync_back_on=['size', 'modified'],
                init_sync_back_missing=True,
                ),
            ),
        ),
    )

    other_test = (
        "L:\\",
        (
             ('copy', dict(
                dst='F:\\tmp2',
                sync=True,
                scan=20,
                watch=False,
                ),
            ),
        ),
    )

    g_test = (
        "G:\\",
        (
             ('copy', dict(
                dst='F:\\tmp2',
                sync=True,
                scan=20,
                watch=False,
                ),
            ),
        ),
    )

    return (other_test, g_test, test)


if __name__ == '__main__':
    main()
