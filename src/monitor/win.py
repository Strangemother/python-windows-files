"""Detect file changes through the windows api
"""

import os
import asyncio
import winerror
import win32con
import threading
import os

os.add_dll_directory(
    'C:\\Users\\jay\\Documents\\projects\\file-monitor\\env'
)

try:
    import win32file
except ImportError as e:
    print('Cannot import win32file', e)

try:
    import win32event
except ImportError as e:
    print('Cannot import win32event', e)

import pywintypes
import time
import traceback
import win32api


ACTIONS = {
    1 : "created",
    2 : "deleted",
    3 : "updated",
    4 : "rename_old",
    5 : "rename_new",
}

FILE_LIST_DIRECTORY = 0x0001


l = asyncio.Lock()
master_lock = l

check_lock = asyncio.Lock()


keep = {'total': 0}
_ignore = []
_ignore_dirs = []
top_content = {'step': 0}

# log = print
def log(*a, **kw): print(" > ", *a, **kw)


def log_callback(results, **kw):

    return table_print(results, **kw)

    # for item in results:
    #     print(f' -- {item}')


def table_print(results, **kw):
    rows = ()

    t = time.strftime('%H:%M:%S')
    for i, item in enumerate(results):
        action = item[1]
        keep['total'] += len(item[0])
        l = len(str(keep['total'])) + 1
        count = f"{keep['total']:<7,}"# if i == 0 else '  '
        first = '--' if i == 0 else '  '
        rows += (f' {first} {count} {action:<10} {t:<10} {item[0]}', )

    for r in rows:
        print(r)


def sync_to_async_main(*a, **kw):
    asyncio.run(main(*a, **kw), debug=False)


async def main(path='C:/', *a, **kw):
    await start(watch_dir=path, *a, **kw)


async def start(watch_dir=None, config=None, callback=None):
    log('start', watch_dir)
    # global late_task

    config = config or {}
    callback = callback or log_callback

    if watch_dir is None and isinstance(config, tuple):
        """start(("", {},), callback=None)"""
        watch_dir, config = config[0], config[1]

    # scan = config.get('scan', -1) or 0
    #late_task = asyncio.get_running_loop().create_task(late_call())
    #watch_dir = watch_dir
    hDir = await get_hdir(watch_dir)

    await loop(hDir, watch_dir, callback, config=config)
    log('monitor.start Done')


async def get_hdir(watch_dir):
    share_mode = (win32con.FILE_SHARE_READ
                  | win32con.FILE_SHARE_WRITE
                  | win32con.FILE_SHARE_DELETE)
    """
       win32file.CreateFile
        PyHANDLE = CreateFile(fileName, desiredAccess , shareMode ,
                            attributes , CreationDisposition , flagsAndAttributes ,
                            hTemplateFile )

        Creates or opens the a file or other object and returns a handle
        that can be used to access the object.
    """
    try:
        hDir = win32file.CreateFile(
            watch_dir,
            FILE_LIST_DIRECTORY,
            share_mode,
            None,
            win32con.OPEN_EXISTING,
            (win32con.FILE_FLAG_BACKUP_SEMANTICS
              | win32con.FILE_FLAG_OVERLAPPED), # async ,
            None
        )
    except pywintypes.error as e:
        # (2, 'CreateFile', 'The system cannot find the file specified.')
        log('hdir creation error:', e)
        hDir = None

    return hDir


async def loop(hDir, root_path, callback, config=None):
    log(f'loop PID: {os.getpid()}, Handle: {hDir}, config', config)
    run = 1
    fails = 0

    while run:
        run, fails = await loop_step(hDir, root_path, callback, fails, config=None)

        if fails >= 3:
            log(f'\nToo many failures: {fails}. Killing with last failure\n')
            run = False

        if run is False:
            log('Result is false; stopping monitor.loop for', root_path)

    log('Loop complete')


async def loop_step(hDir, root_path, callback, fails=0, config=None):
    log('Back into step', root_path)
    should_continue = False
    try:
        should_continue, results = await step(hDir, root_path, callback, config=config)
        fails = 0
    except Exception as e:
        log('monitor.loop caught step exception:\n',)
        traceback.print_exc()

        fails += 1
        results = ()

    top_content['step'] += 1

    await execute(results, callback, config)

    return should_continue, fails


def loger(tick):
    log('Timer tick', tick, top_content)
    top_content['step'] += 1
    return True


def early_ignore(action, file, full_filename):
    if file in _ignore:
       return True

    if full_filename in _ignore:
        return True

    if file in _ignore:
       return True

    for _dir in _ignore_dirs:
        if file.startswith(_dir): return True
        if full_filename.startswith(_dir): return True


async def step(hDir, root_path, callback, config=None):
    """Wait until the handle yields a result
    return boolean for _should continue_. If false, the upper loop should not run.
    """

    #
    # ReadDirectoryChangesW takes a previously-created
    # handle to a directory, a buffer size for results,
    # a flag to indicate whether to watch subtrees and
    # a filter of what changes to notify.
    #
    # NB Tim Juchcinski reports that he needed to up
    # the buffer size to be sure of picking up all
    # events when a large number of files were
    # deleted at once.

    # results = wait(hDir)
    # async for item in results:
    #     log(item)
    #     for action, file in item:
    #         full_filename = os.path.join(path_to_watch, file)
    #         log(full_filename, ACTIONS.get(action, "Unknown"))

    log('>..', end='')

    ok, results = await cancelable_handle_wait(hDir,
            win_async=True,
            root_path=root_path,
            callback=callback)

    if (results is None) or (ok is False):
        # kill the upper loop.
        log('- Result is None, This may occur if the file is deleted before analysis')
        log(root_path, hDir)
        return False, ()

    _actions = await process_results(results, root_path, callback, config)

    return True, _actions


async def process_results(results, root_path, callback, config):

    if results is master_lock:
        # Don't kill the upper loop
        log('Received lock, will wait again')
        return ()

    try:
        _actions = await iter_results(results, root_path, callback, config)
    except Exception as e:
        log('monitor.step caught exception.', _action, file)
        # raise e

    return _actions


async def iter_results(results, root_path, callback, config):
    # log('Iterating', len(results), 'results')
    clean_actions = ()

    last = keep.get('last', None)
    for action, file in results:
        full_filename = os.path.join(root_path, file)

        if early_ignore(action, file, full_filename):
            log('x ', full_filename)
            continue

        _action = (full_filename, ACTIONS.get(action, "Unknown"))
        clean_actions += (_action, )

        # try:
        # except Exception as e:
        #     log('monitor.step caught exception.', _action, file)
        #     raise e

    return clean_actions


async def cancelable_handle_wait(hDir, win_async=True, **kw):
    try:
        func = async_wait if win_async else wait
        # results = await async_wait(hDir, **kw)
        results = await func(hDir, **kw)
    except KeyboardInterrupt as e:
        log('Keyboard cancelled')
        return False, None
        # try:
    except Exception as e:
        log('monitor.step caught exception.', e)
        raise e

    await asyncio.sleep(.01)
    return True, results


async def async_wait(hDir, root_path=None, callback=None, config=None, timeout=5000,
    watch_subtree=True, buffer_size=8192, loop_delay=.3):

    buf = win32file.AllocateReadBuffer(buffer_size)
    overlapped = get_overlapped_event()
    run = True
    count = 0
    # results = get_win_changew(hDir, watch_subtree, buffer_size)

    while run:
        handle, buf = get_win_async_changew(hDir, overlapped, watch_subtree, buffer_size)
        count += 1

        # rc = win_wait_for_object(overlapped, timeout)
        rc = win_wait_for_many_objects(overlapped, timeout=win32event.INFINITE)
        results = process_async_handle(hDir, overlapped, rc, buf)
        _actions = await process_results(results, root_path, callback, config)
        await execute(_actions, callback, config)
        run = rc in [win32event.WAIT_OBJECT_0, win32event.WAIT_TIMEOUT]
        # By adding a sleep here we reduce the response rate of the async
        # waiting. Lesser wait == less events.
        await asyncio.sleep(loop_delay)
        # if count > 40:
        #     print('hard kill')
        #     run = False

    print("Received {:d}. Exiting".format(rc))
    close_overlapped_event(overlapped)


def process_async_handle(hDir, overlapped, rc, buf):
    if rc == win32event.WAIT_OBJECT_0:
        over_res = win32file.GetOverlappedResult(hDir, overlapped, True)
        results = win32file.FILE_NOTIFY_INFORMATION(buf, over_res)
        return results
    return ()


def get_overlapped_event():
    overlapped = pywintypes.OVERLAPPED()
    overlapped.hEvent = win32event.CreateEvent(None, False, 0, None)
    return overlapped


def close_overlapped_event(overlapped):
    return win32api.CloseHandle(overlapped.hEvent)


async def lock_wait(hDir):
    async with check_lock:
        log('locked' if l.locked() else 'unlocked')
        await asyncio.ensure_future(l.acquire())
        log('now', 'locked' if l.locked() else 'unlocked')
        await wait(hDir)
    # await asyncio.sleep(1)
    l.release()
    return l


async def wait(hDir, timeout=1000, watch_subtree=True, buffer_size=8192, **kw):
    overlapped = get_overlapped_event()
    results = get_win_changew(hDir, watch_subtree, buffer_size)
    # results, buf = get_win_changew(hDir, watch_subtree, buffer_size)
    rc = win_wait_for_object(overlapped, timeout)
    print('End wait', rc)
    return results


def x_wait(hDir, timeout=1000, watch_subtree=True, buffer_size=8192):
    try:
        """
            handle : PyHANDLE
                Handle to the directory to be monitored.
                This directory must be opened with the
                FILE_LIST_DIRECTORY access right.
            size : int
                Size of the buffer to allocate for the results.
            bWatchSubtree : int
                Specifies whether the ReadDirectoryChangesW function
                will monitor the directory or the directory tree.
                If TRUE is specified, the function monitors the
                directory tree rooted at the specified directory.
                If FALSE is specified, the function monitors only
                the directory specified by the hDirectory parameter.
            dwNotifyFilter : int
                Specifies filter criteria the function checks to
                determine if the wait operation has completed.
                This parameter can be one or more of the
                FILE_NOTIFY_CHANGE_* values.
            overlapped=None : PyOVERLAPPED
                An overlapped object. The directory must also be
                opened with FILE_FLAG_OVERLAPPED.
        """
        # buf = win32file.AllocateReadBuffer(buffer_size)
        # flags = get_flags()
        # results = win32file.ReadDirectoryChangesW(
        #     hDir, buffer_size, watch_subtree, flags, None, None)
        results = get_win_changew(hDir, watch_subtree, buffer_size)
        # results, buf = get_win_changew(hDir, watch_subtree, buffer_size)
        rc = win_wait_for_object(overlapped, timeout)

        # if rc == win32event.WAIT_OBJECT_0:
            # got some data!  Must use GetOverlappedResult to find out
            # how much is valid!  0 generally means the handle has
            # been closed.  Blocking is OK here, as the event has
            # already been set.
            # nbytes = win32file.GetOverlappedResult(hDir, overlapped, True)
            # if nbytes:
            #     bits = win32file.FILE_NOTIFY_INFORMATION(buf, nbytes)
            #     log('nbytes', nbytes, bits)
            # else:
            #     # This is "normal" exit - our 'tearDown' closes the
            #     # handle.
            #     # log "looks like dir handle was closed!"
            #     log('teardown')
            #     return
        # else:
        #     log('Timeout', hDir, rc)
        #log('return', results)
        return results

    except pywintypes.error as e:
        log('monitor.start - FileError', e)
        return None


def win_wait_for_object(overlapped, timeout=5000):
    return win32event.WaitForSingleObject(overlapped.hEvent, timeout)


def win_wait_for_many_objects(*overlapped, timeout=0):
    v = [x.hEvent for x in overlapped]
    return win32event.WaitForMultipleObjects(v, 0, win32event.INFINITE)

    # if result != win32event.WAIT_TIMEOUT:
    #     # result = win32file.GetOverlappedResult(self.handle, self.overlapped, False)
    #     return True
    # else:
    #     return False

def get_flags():
    return (
             win32con.FILE_NOTIFY_CHANGE_FILE_NAME
             | win32con.FILE_NOTIFY_CHANGE_DIR_NAME
             | win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES
             | win32con.FILE_NOTIFY_CHANGE_SIZE
             | win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
             | win32con.FILE_NOTIFY_CHANGE_SECURITY)
             # ~ win32con.FILE_NOTIFY_CHANGE_CREATION |
             # ~ win32con.FILE_NOTIFY_CHANGE_LAST_ACCESS |)


def get_win_changew(hDir, watch_subtree=True, buffer_size=8192):
    """
        handle : PyHANDLE
            Handle to the directory to be monitored.
            This directory must be opened with the
            FILE_LIST_DIRECTORY access right.
        size : int
            Size of the buffer to allocate for the results.
        bWatchSubtree : int
            Specifies whether the ReadDirectoryChangesW function
            will monitor the directory or the directory tree.
            If TRUE is specified, the function monitors the
            directory tree rooted at the specified directory.
            If FALSE is specified, the function monitors only
            the directory specified by the hDirectory parameter.
        dwNotifyFilter : int
            Specifies filter criteria the function checks to
            determine if the wait operation has completed.
            This parameter can be one or more of the
            FILE_NOTIFY_CHANGE_* values.
        overlapped=None : PyOVERLAPPED
            An overlapped object. The directory must also be
            opened with FILE_FLAG_OVERLAPPED.
    """
    # buf = win32file.AllocateReadBuffer(buffer_size)
    flags = get_flags()
    h = win32file.ReadDirectoryChangesW(
        hDir, buffer_size, watch_subtree, flags, None, None)

    return h


def get_win_async_changew(hDir, overlapped, watch_subtree=True, buffer_size=8192):
    buf = win32file.AllocateReadBuffer(buffer_size)
    flags = get_flags()

    h = win32file.ReadDirectoryChangesW(
        hDir, buf, watch_subtree, flags, overlapped, None)

    return h, buf


async def execute(results, callback, settings):
    try:
        return callback(results)
    except Exception as e:
        log(f'An exception has occured during callback execution: {e}')
        raise e
    # await asyncio.sleep(.3)
    # return result


async def late_call():
    log('late')


if __name__ == '__main__':
    sync_to_async_main()
