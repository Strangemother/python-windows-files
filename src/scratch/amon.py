import sys
import msvcrt
import pywintypes
import win32file
import win32con
import win32api
import win32event


FILE_LIST_DIRECTORY = 0x0001
FILE_ACTION_ADDED = 0x00000001
FILE_ACTION_REMOVED = 0x00000002

ASYNC_TIMEOUT = 5000

BUF_SIZE = 65536


def main():
    print("Python {:s} on {:s}\n".format(sys.version, sys.platform))
    asynch = True
    z = "As" if asynch else "S"
    print("Attempting {}ynchronous mode using a buffer {:d} bytes long...".format(z, BUF_SIZE))
    monitor_dir("C:/", asynch=asynch)


def get_dir_handle(dir_name, asynch):
    flags_and_attributes = win32con.FILE_FLAG_BACKUP_SEMANTICS
    if asynch:
        flags_and_attributes |= win32con.FILE_FLAG_OVERLAPPED
    dir_handle = win32file.CreateFile(
        dir_name,
        FILE_LIST_DIRECTORY,
        (win32con.FILE_SHARE_READ |
         win32con.FILE_SHARE_WRITE |
         win32con.FILE_SHARE_DELETE),
        None,
        win32con.OPEN_EXISTING,
        flags_and_attributes,
        None
    )
    return dir_handle


def read_dir_changes(dir_handle, size_or_buf, overlapped):
    return win32file.ReadDirectoryChangesW(
        dir_handle,
        size_or_buf,
        True,
        (win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
         win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
         win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
         win32con.FILE_NOTIFY_CHANGE_SIZE |
         win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
         win32con.FILE_NOTIFY_CHANGE_SECURITY),
        overlapped,
        None
    )


def handle_results(results):
    for item in results:
        print("    {} {:d}".format(item, len(item[1])))
        _action, _ = item
        if _action == FILE_ACTION_ADDED:
            print("    found!")
        if _action == FILE_ACTION_REMOVED:
            print("    deleted!")


def esc_pressed():
    return msvcrt.kbhit() and ord(msvcrt.getch()) == 27


def monitor_dir_sync(dir_handle):
    idx = 0
    while True:
        print("Index: {:d}".format(idx))
        idx += 1
        results = read_dir_changes(dir_handle, BUF_SIZE, None)
        handle_results(results)
        if esc_pressed():
            break


def monitor_dir_async(dir_handle):
    idx = 0
    buffer = win32file.AllocateReadBuffer(BUF_SIZE)
    overlapped = pywintypes.OVERLAPPED()
    overlapped.hEvent = win32event.CreateEvent(None, False, 0, None)
    while True:
        print("Index: {:d}".format(idx))
        idx += 1
        read_dir_changes(dir_handle, buffer, overlapped)
        rc = win32event.WaitForSingleObject(overlapped.hEvent, ASYNC_TIMEOUT)
        if rc == win32event.WAIT_OBJECT_0:
            bufer_size = win32file.GetOverlappedResult(dir_handle, overlapped, True)
            results = win32file.FILE_NOTIFY_INFORMATION(buffer, bufer_size)
            handle_results(results)
        elif rc == win32event.WAIT_TIMEOUT:
            #print("    timeout...")
            pass
        else:
            print("Received {:d}. Exiting".format(rc))
            break
        if esc_pressed():
            break
    win32api.CloseHandle(overlapped.hEvent)


def monitor_dir(dir_name, asynch=False):
    dir_handle = get_dir_handle(dir_name, asynch)
    if asynch:
        monitor_dir_async(dir_handle)
    else:
        monitor_dir_sync(dir_handle)
    win32api.CloseHandle(dir_handle)



if __name__ == "__main__":
    main()
