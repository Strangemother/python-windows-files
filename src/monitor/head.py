
import os
import sys
import time
import asyncio
import winerror
import win32con
import threading
import traceback
import pywintypes

try:
    import win32file
except ImportError as e:
    print('install dll loc:', sys.exec_prefix)
    os.add_dll_directory(sys.exec_prefix)


try:
    import win32file
except ImportError as e:
    print('import win32file (second attempt)', e)


try:
    import win32event
except ImportError as e:
    print('Cannot import win32event', e)

import win32api
