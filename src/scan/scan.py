'''Scan a directory and present the content to the next stage.

    py -i scan/scan.py "C:/Users/jay/Documents"
'''
import os
import time
from timeit import default_timer as timer
import asyncio
from pathlib import Path
import argparse


def main(directory=None):
    path = get_path(directory)

    start = timer()
    res = list_all(path)
    end = timer()
    print(f'{len(res):,}', end - start, 'ms')
    # print('done')
    #print(res)


def list_all(directory):
    """Iterate a directory and return list of files

    Arguments:
        directory {str} -- target directory to scan
    """
    res = ()

    for entry in os.scandir(directory):
        path = entry.path
        if entry.is_dir():
            res += list_all(path)
            continue
        res += (file_entry(entry),)

    return res


def file_entry(entry, path=None):
    stat = entry.stat()
    return path_stat(path or entry.path, stat)


def path_stat(path, stat=None):
    stat = stat or os.stat(path)
    # return (path,
    # int(stat.st_size),
    # int(stat.st_atime),
    # int(stat.st_mtime),
    # int(stat.st_ctime),)
    return (path, stat.st_size, stat.st_atime, stat.st_mtime, stat.st_ctime,)


def get_path(directory=None):
    directory = directory or os.path.join('..')
    return Path(directory).absolute()



parser = argparse.ArgumentParser()
parser.add_argument('dir', type=str, nargs='?', default='F:\\Program Files (x86)')


def async_main(directory=None, func=None, *a, stat_func=None, **kw):

    args = parser.parse_args()
    directory = directory or args.dir

    path = get_path(directory)
    print('Reading', path)
    func = func or async_list_all
    stat_func = stat_func or file_entry
    tasks = [func(path, *a, stat_func=stat_func, **kw)]
    if asyncio.get_event_loop().is_closed():
        asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    start = timer()

    res = loop.run_until_complete(asyncio.gather(*tasks))[0]
    end = timer()
    loop.close()
    # print(len(res), end - start, 'ms')
    print(f'{len(res):,}', end - start, 'ms')
    #print(res)
    return res


async def async_list_all(directory, stat_func=None):
    """Iterate a directory and return list of files

    Arguments:
        directory {str} -- target directory to scan
    """
    res = ()

    try:
        scanned = os.scandir(directory)
    except PermissionError:
        return res
    except FileNotFoundError as e:
        # interesting...
        print('FNF', directory)
        return res

    for entry in scanned:
        path = entry.path
        if entry.is_dir():
            res += await async_list_all(path, stat_func)
            continue
        res += (stat_func(entry, path), )
    return res


async def async_depth(directory, depth=2, _current=0, stat_func=None):
    res = ()
    stat_func = stat_func or file_entry

    try:
        scanned =  os.scandir(directory)
    except PermissionError as pe:
        print('Cannot access', directory, pe)
        return (stat_func(Path(directory), directory), )

    for entry in scanned:
        path = entry.path

        if (_current < depth) and entry.is_dir():
            res += await async_depth(path, depth, _current+1, stat_func=stat_func)
            continue
        res += (stat_func(entry, path), )
    return res


def create_record(content, filepath):
    res = ()
    for t_entry in content:
        tval = sum(t_entry[1:])
        res += ((id(t_entry[0]), tval, ), )
    return res


if __name__ == '__main__':
    res = async_main()
