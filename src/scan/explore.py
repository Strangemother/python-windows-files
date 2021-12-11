
from . import scan

def stat_func(entry, path):
    """return the content for each entry for the given directory.
    The return item is the 'file info' from the scan.
    """
    return [
        entry.name,
        int(entry.is_file()),
    ]

def get_list(directory, depth=1):
    return scan.async_main(directory, scan.async_depth, depth=depth,
                           stat_func=stat_func)
