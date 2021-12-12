import asyncio
from monitor import win as monitor

import action

import json
import ticker


import os

os.add_dll_directory(
    'C:\\Users\\jay\\Documents\\projects\\file-monitor\\env\\Lib\\site-packages\\pywin32_system32'
)

def main():
    return run(
            'C:/',
            'D:/',
        )


def run(*paths, callback=None):
    global runner
    callback = callback or default_callback
    path_callback_set = tuple( (x, callback,) for x in paths)

    #runner = action.create(path, settings)

    return run_loop(path_callback_set)

    # return thread_run_loops(path_callback_set)


def default_callback(entry):
    """Called by the monitor loop on a file change."""
    print('loop::callback (should do something with)', entry)
    #runner.capture_run(entry)


def printer(tick):
    print('Timer tick', tick, top_content)
    top_content['step'] += 1
    return True

import concurrent.futures

def thread_run_loops(path_callback_set):
    #tasks = [threading.Tread(*x) for x in stackless_monitor]
    print(len(path_callback_set))
    # for x in path_callback_set:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(stackless_monitor, path_callback_set)


def stackless_monitor(*x):
    print("stackless_monitor:", x[0])
    tasks = [monitor.start(*x[0])]
    return monitor_tasks(*tasks)


def run_loop(path_callback_set):
    """Start the async processes"""
    tasks = [monitor.start(watch_dir=x[0], callback=x[1]) for x in path_callback_set]
    return monitor_tasks(*tasks)


def monitor_tasks(*tasks):
    print('Loading', len(tasks), 'tasks')
    #ticker.start(5)
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True),)
    loop.close()
    return results


if __name__ == '__main__':
    main()
