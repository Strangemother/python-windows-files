"""Detect file changes through the windows api
"""

import os

import win32event
import win32file
import win32con
import asyncio
import pywintypes
import threading


ACTIONS = {
    1 : "Created",
    2 : "Deleted",
    3 : "Updated",
    4 : "old name",
    5 : "new name"
}

# Thanks to Claudio Grondi for the correct set of numbers
FILE_LIST_DIRECTORY = 0x0001


l = asyncio.Lock()
master_lock = l

check_lock = asyncio.Lock()


keep = {}
_ignore = ['F:\\clients\\strangemother\\backblaze\\.git']
_ignore_dirs = ['F:\\clients\\strangemother\\backblaze\\.git']
top_content = {'step': 0}

# log = print
def log(*a, **kw): print(" > ", *a, **kw)
def log_callback(e, **kw): print("log_callback", e, **kw)



def sync_to_async_main(*a, **kw):
    asyncio.run(main(*a, **kw))


async def main(*a, **kw):
    p = 'C:/'
    await start(p)


async def start(watch_dir=None, config=None, callback=None):
    log('start')
    global late_task

    config = config or {}
    if watch_dir is None and isinstance(config, tuple):
        watch_dir = config[0]
        config = config[1]

    # scan = config.get('scan', -1) or 0
    #late_task = asyncio.get_running_loop().create_task(late_call())
    #watch_dir = watch_dir
    hDir = await get_hdir(watch_dir)

    await loop(hDir, watch_dir, callback or log_callback, config=config)
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
        log('monitor.start - FileError', e)
        hDir = None

    return hDir


async def loop(hDir, root_path, callback, config=None):
    log('loop', os.getpid(), hDir)
    log('config', config)
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
        should_continue = await step(hDir, root_path, callback, config=config)
        fails = 0
    except Exception as e:
        log('monitor.loop caught step exception:', str(e))
        fails += 1

    top_content['step'] += 1

    return should_continue, fails


def loger(tick):
    log('Timer tick', tick, top_content)
    top_content['step'] += 1
    return True


def ignore(action, file, full_filename):
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

    ok, results = await cancelable_handle_wait(hDir)

    if (results is None) or (ok is False):
        # kill the upper loop.
        log('- Result is None, This may occur if the file is deleted before analysis')
        log(root_path, hDir)
        return False

    if results is master_lock:
        # Don't kill the upper loop
        log('Received lock, will wait again')
        return True

    _actions = await iter_results(results, root_path, callback, config)

    if config is None:
        config = {}

    if config.get('callback_many'):
        config['callback_many'](_actions)
    log('monitor.step fall to end.')
    return True


async def iter_results(results, root_path, callback, config):
    log('Iterating', len(results), 'results')
    clean_actions = ()

    last = keep.get('last', None)
    for action, file in results:
        full_filename = os.path.join(root_path, file)

        if ignore(action, file, full_filename):
            log('x ', full_filename)
            continue

        _action = (full_filename, ACTIONS.get(action, "Unknown"))
        clean_actions += (_action, )
        if _action == last:
            log('Drop Duplicate')
            continue

        try:
            keep['last'] = await execute(_action, callback, config)
        except Exception as e:
            log('monitor.step caught exception.', _action, file)
            raise e

    return clean_actions


async def cancelable_handle_wait(hDir):
    try:
        results = await wait(hDir)
    except KeyboardInterrupt as e:
        log('Keyboard cancelled')
        return False

    await asyncio.sleep(.01)
    return True, results


async def lock_wait(hDir):
    async with check_lock:
        log('locked' if l.locked() else 'unlocked')
        await asyncio.ensure_future(l.acquire())
        log('now', 'locked' if l.locked() else 'unlocked')
        await wait(hDir)
    # await asyncio.sleep(1)
    l.release()
    return l


import winerror


async def wait(hDir, timeout=5000, watch_subtree=True):
    overlapped = pywintypes.OVERLAPPED()
    overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
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
        rc = win32event.WaitForSingleObject(overlapped.hEvent, timeout)
        buf = win32file.AllocateReadBuffer(8192)
        results = win32file.ReadDirectoryChangesW(
            hDir,
            8192, #1024,
            watch_subtree,
            win32con.FILE_NOTIFY_CHANGE_FILE_NAME
            | win32con.FILE_NOTIFY_CHANGE_DIR_NAME
            | win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES
            | win32con.FILE_NOTIFY_CHANGE_SIZE
            | win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
            | win32con.FILE_NOTIFY_CHANGE_SECURITY
            | win32con.FILE_NOTIFY_CHANGE_FILE_NAME,
            # ~ win32con.FILE_NOTIFY_CHANGE_CREATION |
            # ~ win32con.FILE_NOTIFY_CHANGE_LAST_ACCESS |
            # None,
            # overlapped,
        )



        rcache = None

        # wait for changes
        while rcache is None:
            try:
                print('testing overlap')
                rcache = win32file.GetOverlappedResult(
                    hDir,
                    overlapped,
                    False   # bWait
                )

            except pywintypes.error as err:
                if err.winerror == winerror.ERROR_IO_INCOMPLETE:
                    # not available yet, wait for a bit
                    print('incomplete - sleeping')
                    time.sleep(0.1)
                    continue
                raise err

        # get changes from buffer
        result = win32file.FILE_NOTIFY_INFORMATION(buf, rcache)

        print('Result complete', result)

        #log('watch', results, rc)
        if rc == win32event.WAIT_OBJECT_0:
            # got some data!  Must use GetOverlappedResult to find out
            # how much is valid!  0 generally means the handle has
            # been closed.  Blocking is OK here, as the event has
            # already been set.
            nbytes = win32file.GetOverlappedResult(hDir, overlapped, True)
            if nbytes:
                bits = win32file.FILE_NOTIFY_INFORMATION(buf, nbytes)

                log('nbytes', nbytes, bits)
            else:
                # This is "normal" exit - our 'tearDown' closes the
                # handle.
                # log "looks like dir handle was closed!"
                log('teardown')
                return
        else:
            log('Timeout', hDir, rc)
        #log('return', results)
        return results


    except pywintypes.error as e:
        log('monitor.start - FileError', e)
        return None


async def execute(result, callback, settings):
    try:
        return callback(result)
    except Exception as e:
        log(f'An exception has occured during callback execution: {e}')
        raise e
    # await asyncio.sleep(.3)
    # return result


async def late_call():
    log('late')


if __name__ == '__main__':
    sync_to_async_main()
