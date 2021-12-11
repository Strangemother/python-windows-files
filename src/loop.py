import asyncio
import monitor_files as monitor

import action

import json
import ticker

def run(*config):
    global runner
    print('run_loop')
    path_callback_set = tuple( (x, callback,) for x in config)

    #runner = action.create(path, settings)

    return run_loop(path_callback_set)

    # return thread_run_loops(path_callback_set)

def callback(entry):
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
    for x in path_callback_set:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                executor.map(stackless_monitor, x)


def stackless_monitor(*x):
    print(x[0])
    tasks = [monitor.start(config=x[0], callback=x[1])]
    return monitor_tasks(*tasks)


def run_loop(path_callback_set):
    """Start the async processes"""

    tasks = [monitor.start(config=x[0], callback=x[1]) for x in path_callback_set]
    return monitor_tasks(*tasks)


def monitor_tasks(*tasks):
    print('Loading', len(tasks), 'tasks')
    #ticker.start(5)
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True),)
    loop.close()
    return results
