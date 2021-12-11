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

async def main():
    p = 'C:/'
    await start(p)

# log = print

def log(*a, **kw):
    print(" > ", *a, **kw)


def log_callback(e, **kw):
    print("log_callback", e, **kw)


l = asyncio.Lock()
check_lock = asyncio.Lock()


keep = {}
_ignore = ['F:\\clients\\strangemother\\backblaze\\.git']
_ignore_dirs = ['F:\\clients\\strangemother\\backblaze\\.git']
top_content = {'step': 0}


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
    try:
        hDir = win32file.CreateFile(
            watch_dir,
            FILE_LIST_DIRECTORY,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
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
        log('Back into step', root_path)
        try:
            should_continue = await step(hDir, root_path, callback, config=config)
            fails = 0
        except Exception as e:
            log('monitor.loop caught step exception:', str(e))
            fails += 1
            should_continue = False if (fails >= 3) else True
            if should_continue is False:
                log(f'\nToo many failures: {fails}. Killing with last failure\n')
                log(e)
        top_content['step'] += 1
        if should_continue is False:
            log('Result is false; stopping monitor.loop for', root_path)
            run = False
            continue
    log('Loop complete')


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
    last = keep.get('last', None)
    try:
        results = await wait(hDir)
    except KeyboardInterrupt:
        log('Keyboard cancelled')
        return False

    await asyncio.sleep(.01)

    if results is None:
        log('- Result is None, This may occur if the file is deleted before analysis')
        log(root_path, hDir)
        return False

    if results is l:
        log('Received lock, will wait again')
        return True

    log('Iterating', len(results), 'results')
    clean_actions = ()
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

    if config.get('callback_many'):
        config['callback_many'](clean_actions)

    log('monitor.step fall to end.')


async def lock_wait(hDir):
    async with check_lock:
        log('locked' if l.locked() else 'unlocked')
        await asyncio.ensure_future(l.acquire())
        log('now', 'locked' if l.locked() else 'unlocked')
        await wait(hDir)
    # await asyncio.sleep(1)
    l.release()
    return l


async def wait(hDir):
    overlapped = pywintypes.OVERLAPPED()
    overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
    try:
        rc = win32event.WaitForSingleObject(overlapped.hEvent, 5000)
        results = win32file.ReadDirectoryChangesW(
            hDir,
            8192, #1024,
            True,
            win32con.FILE_NOTIFY_CHANGE_FILE_NAME
            | win32con.FILE_NOTIFY_CHANGE_DIR_NAME
            | win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES
            | win32con.FILE_NOTIFY_CHANGE_SIZE
            | win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
            | win32con.FILE_NOTIFY_CHANGE_SECURITY
            | win32con.FILE_NOTIFY_CHANGE_FILE_NAME,
            # ~ win32con.FILE_NOTIFY_CHANGE_CREATION |
            # ~ win32con.FILE_NOTIFY_CHANGE_LAST_ACCESS |
            None,
            None
        )

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
    asyncio.run(main())
