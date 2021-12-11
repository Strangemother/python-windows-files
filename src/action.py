"""An action performs an event upon a given fullpath.
"""
import os
import shutil
from collections import defaultdict
from functools import partial
import scan
import pathlib
import re
import logging

# 21
class Action(object):
    """A procedure for an event to action upon changes to the filesystem.
    """

    def __init__(self, path, settings):
        actions = (Copy, )
        self.path = path
        self.settings = settings

        flat = defaultdict(tuple)
        for name, conf in settings:
            flat[name] += (conf,)
            setattr(self, name, partial(self.multi_caller, name))
        self.flat_settings = flat

        callers = defaultdict(list)
        for _Action in actions:
            act = _Action(self.path)
            name = act.name
            items = self.flat_settings.get(name)
            self.log('Exposing actions', len(items), name)
            # Apply a caller to this action, allowing the iter
            # of the callers.

            for conf in items:
                callers[name].append(act.exposed(conf))

        self.callers = callers

    def multi_caller(self, name, entry, config):
        for exposed in self.callers[name]:
            exposed(entry, config)

    def exposed(self, configs):
        """return a method to call upon an action given a tuple of
        configs for each unique action the Action instance will
        perform. The order isn't preserved.

        Upon calling your exposed method, the chosen config is supplied,
        """
        pass

    def capture_run(self, entry):
        '''Given a base entry item perform the allocated routines.
        '''
        for action, conf in self.settings:
            process = getattr(self, action, None)
            if process is None:
                self.log('capture_run received unknown action', action)
                continue
            self.log('process', entry)
            process(entry, conf)

    def log(self, *a):
        print(*a)

    def dry_perform(self, name, src, dst):
        print(f'DRY action {name}\n{src} ==> {dst}')


class StorageBase(Action):

    dry = False

    def isdir(self, path):
        return os.path.isdir(path)

    def copy_tree(self, src, dst):
        """Copy an entire src tree to the dst folder. The destination
        nest probably did not exist for a standard file copy2.

        Retur tuple: success Bool, shutil.copytree result
        """
        if self.dry:
            self.dry_perform('copytree', src, dst)
        return True, shutil.copytree(src, dst)

    def clone_files(self, src, dst, files_relative, only=None, ignore=None, ):
        self.log(f'copy {len(files_relative)} files')

        results = ()
        for filepath in files_relative:
            remote_src = os.path.join(dst, filepath)
            local_dst = os.path.join(src, filepath)
            self.log('copy back', remote_src, local_dst)
            success, reason = self.copy_file(remote_src, local_dst,
                only=only, ignore=ignore, rel_src=filepath)
            results += (success,)
        return results

    def copy_allowed(self, src, only=None, ignore=None, default=True):
        part, ext = os.path.splitext(src)
        ignore = ignore or ()
        _only = only or ()
        # flat deny
        if ext in ignore: return 'ignore'
        # flat allow
        if ext in _only: return 'True'
        # pramatic knowledge
        p_sets = (
                (ignore, 'pattern-ignore',),
                (_only, True,),
            )

        for _list, res in p_sets:
            for pattern in _list:
                if pattern[0] == '!':
                    if re.fullmatch(pattern[1:], src, re.IGNORECASE | re.VERBOSE):
                        return f'regex-{res}'
                    continue
                if pathlib.PurePath(src).match(pattern):
                    #self.log(f'file pattern: {pattern} "{src}" allowed:', res)
                    return res

        if only is not None:
            return 'only-deny'

        #self.log(f'unknown copy allowed "{src}", default: {default}',)

        # if ext != '.py':
        #     print(ignore)
        #     print(src)

        return default

    def copy_file(self, src, dst, only=None, ignore=None, rel_src=None):
        """Copy a file from the src to dst, creating a nested
        directory if required

        Arguments:
            src {str} -- the full filepath of the source file
            dst {str} -- the full filepath of the destination file

        Returns:
            tuple (success {Bool}, result) - the result from copy2 function
        """
        _src = rel_src or src
        allowed = self.copy_allowed(_src, only, ignore)
        if allowed is not True:
            #self.log('copy_allowed said no:', allowed, _src)
            return False, allowed

        self.ensure_dir(dst)
        return self.system_perform(src, dst)

    def system_perform(self, src, dst):
        """The last method to call when copying a file.
        """
        if self.dry:
            return True, self.dry_perform('copy2', src, dst)
        try:
            return True, self.shutil_copy(src, dst)
        except PermissionError as e:
            return False, None

    def shutil_copy(self, src, dst):
        return shutil.copy2(src, dst)

    def ensure_dir(self, dst):
        abs_dst_dir = os.path.dirname(dst)
        #self.log('action::Action::copy_file', src)

        if self.exists(abs_dst_dir) is False:
            self.log('making', abs_dst_dir)
            if self.dry:
                self.dry_perform('makedirs', abs_dst_dir)
                return True
            os.makedirs(abs_dst_dir)
            return True
        return False

    def exists(self, path):
        return os.path.exists(path)

    def get_files(self, path):
        return scan.list_all(path)

    def perform(self, src_file, dest_dir=None, **kw):
        kw.setdefault('dst', dest_dir or self._dst_dir)
        copy_func = self.exposed(kw)
        entry = (src_file, 'Copy',)
        success, to_path = copy_func(entry, kw)
        return success, to_path


class Copy(StorageBase):
    name = 'copy'
    val_map = {
        'size': ('st_size', 1),
        'access': ('st_atime', 2),
        'modified': ('st_mtime', 3),
        'created': ('st_ctime', 4),
    }

    def __init__(self, path, dst_dir=None):
        self.src = path
        self._dst_dir = dst_dir

    def exposed(self, config):
        dst = config.setdefault('dst', self._dst_dir)
        self.log('Exposing copy', dst)
        self.copy_sync(config)
        return self.safe_copy

    def safe_copy(self, entry, config):
        abs_src = entry[0]
        # Ensure  the given path is absolute. This should be if given from the
        # hwnd loop, but if a user passes a relative entry, correct it.
        if os.path.isabs(abs_src) is False:
            new_abs_path = os.path.join(self.src, abs_src)

            if (os.path.exists(os.path.abspath(abs_src)) is False) \
                and os.path.exists(new_abs_path):
                # Entry is relative not abspath, warn and change.
                logging.warning('copy received relative path but expected absolute path - changed.')
                #abs_src = new_abs_path
                #rel_src = os.path.relpath(new_abs_path, self.src)
                entry = (new_abs_path, entry[1], )

        return self.copy(entry, config)

    def copy(self, entry, config):
        """If the given entry[0] is a file, copy the file to the
        target destination using the config.
        """
        if self.isdir(entry[0]):
            return

        abs_src = entry[0]
        rel_src = os.path.relpath(abs_src, self.src)

        abs_dst = os.path.join(config['dst'], rel_src)
        self.dry = config.get('dry', self.dry)
        self.log('action::Action::copy', rel_src)
        # abs_dst_dir = os.path.dirname(abs_dst)
        # if self.exists(abs_dst_dir) is False:
        #     self.log('making', abs_dst_dir)
        #     os.makedirs(abs_dst_dir)
        return self.copy_file(abs_src, abs_dst,
            rel_src=rel_src,
            ignore=config.get('ignore'),
            only=config.get('only'),
            )

    def copy_sync(self, config):
        """
        If config[sync] is true, test the config[dst] for file changes
        If a newer file exists at the config[dst], the file is copied into the target directory.
        If the config[dst] does not exist, Copy over.

        sync                    if False, do nothing.
        init_sync_back_missing  immediately copy any files from `dst` of which
                                do not exist in `src`. Default `False`
        init_sync_back          immediately perform a natural sync from `dst`
                                using all rules for the syncing process. Default
                                `True`.
        init_sync_back_on       A list of attributes to utilise for syncing:
                                e.g. ['modified', 'size']
        init_sync_to            Flag 'copy eveything' upon first wake, skipping
                                the scan and comparison step using for 'init_sync_back'
        """
        g = config.get
        dst = g('dst')
        src = self.src

        self.log('copy_sync', dst)
        if g('sync', False) is False:
            self.log(f'No copy_sync {dst}')
            return

        # if init sync, push missing files from src to dst.
        init_sync_back_missing = g('init_sync_back_missing', False)

        if init_sync_back_missing:
            self.copy_missing_from(dst, src)


        init_sync_back = g('init_sync_back', False)
        attrs = g('init_sync_back_on', [])
        init_sync_to =  g('init_sync_to', False)

        if init_sync_back is True and (init_sync_to is False):
            self.log('Copy_sync - copy changes from remote')
            count = 0
            for entry in scan.list_all(dst):
                # The remote folder, the file to copy back into local
                abs_src = entry[0]

                rel_src = os.path.relpath(abs_src, dst)
                # the local folder - the destination of the sync-back,
                abs_dst = os.path.join(src, rel_src)
                # the local entry = the file to overwrite if required
                try:
                    _entry = scan.path_stat(abs_dst)
                    ok = self.copy_from_soft(abs_src, abs_dst, _entry, attrs)
                except FileNotFoundError:
                    logging.warn(f'no backref DST file: {abs_dst}')
                    # Entry is not available, as the dest to write-over (and copy
                    # attributes) does not exist; Perform a basic copy.
                    ok = self.copy_file(
                        abs_src, abs_dst
                        #rel_src=None, only=None, ignore
                        )
                # dst_entry = (abs_dst, _entry,)
                count += 1 if ok else 0
            print(f'Synced back {count} files')

        if init_sync_to:
            self.copy_all_to(config,
                init_sync_back_missing=(not init_sync_back_missing))

    def copy_missing_from(self, dst, src, only=None, ignore=None):
        # Iterate the dst and copy back anything
        # missing from src.
        self.log('sync back missing', dst)
        rp = os.path.relpath
        src_all = scan.list_all(src)
        dst_all = scan.list_all(dst)
        rel_dst_all = set([rp(x[0], dst) for x in dst_all])
        rel_src_all = set([rp(x[0], src) for x in src_all])
        copy_back = rel_dst_all - rel_src_all
        #self.log(rel_dst_all)
        self.clone_files(src, dst, copy_back, only=only, ignore=ignore)

    def copy_all_to(self, config, src=None, init_sync_back_missing=None):
        """Copy all the files from the given (or self.src) directory
        to the expressive config[dst] and content.

        This function ensures backward copy, syncing new and
        full src to dst copy.
        """
        if init_sync_back_missing is None:
            init_sync_back_missing = config.get('init_sync_back_missing', False)

        dst = config["dst"]
        src = src or self.src
        pushed = 0

        self.log(f'Copy all from {src} to {dst}')
        if self.isdir(dst) is False:
            pushed += 1
            return self.copy_tree(src, dst)

        if init_sync_back_missing:
            self.log('copy_all_to - performing init_sync_back_missing')
            self.copy_missing_from(dst, src,
                only=config.get('only'),
                ignore=config.get('ignore'),
                )

        pushed += self.copy_files_soft(src, dst, config,
            only=config.get('only'),
            ignore=config.get('ignore'),
            )
        self.log(f'done. Sent {pushed}: {src} to {dst}')

    def copy_files_soft(self, src, dst, config, only=None, ignore=None):
        src_all = self.get_files(src)
        self.log(f'Looking at {len(src_all)} entries')

        pushed = 0
        for entry in src_all:
            ok = self.copy_entry(entry, config, src, dst)
            pushed += 1 if ok else 0
        return pushed

    def copy_entry(self, entry, config, root_src, root_dst):
        init_sync_back = config.get('init_sync_back', False)
        force = config.get('init_sync_force', False)
        init_sync_back_on = config.get('init_sync_back_on', [])

        abs_src = entry[0]
        rel_src = os.path.relpath(abs_src, root_src)
        abs_dst = os.path.join(root_dst, rel_src)
        rel_dst = os.path.relpath(abs_dst, root_dst)

        # copy to dest.
        # If dest exists; check for force -
        if self.exists(abs_dst) is False:
            self.copy_file(abs_src, abs_dst,
                rel_src=rel_src,
                only=config.get('only'),
                ignore=config.get('ignore'),
                )
            return True

        #   if force: copy,
        if force is True: #init_sync_force=True
            self.log('overwrite dst')
            self.copy(entry, config)
            return True

        if init_sync_back is True:
            # for each possible val_map
            # check if the value is different
            # and copy.
            success = self.copy_from_soft(abs_dst, abs_src, entry,
                init_sync_back_on,
                rel_src=rel_src,
                only=config.get('only', None),
                ignore=config.get('ignore', None),
                )
            if success:
                return True

        success = self.copy_soft(entry, abs_dst, init_sync_back_on,
                rel_src=rel_src,
                only=config.get('only', None),
                ignore=config.get('ignore', None),
                )
        if success:
            print('Copied src to dst:\n\t', rel_src, rel_dst)
        return success

    def copy_soft(self, src_entry, abs_dst, init_sync_back_on, rel_src=None, only=None, ignore=None):
        """Copy the src_entry file to the abs_dst if the stats match a change
        """
        dst_stat = os.stat(abs_dst)
        abs_src = src_entry[0]
        success = False
        for key in init_sync_back_on:
            attr = self.val_map.get(key, None)
            dst_val = getattr(dst_stat, attr[0], None)
            src_val = src_entry[attr[1]]
            if dst_val != src_val:
                success, reason = self.copy_file(abs_src, abs_dst,
                                                 rel_src=rel_src,
                                                 only=only,
                                                 ignore=ignore)

        if success:
            self.log('change to', abs_src)

        return success

    def copy_from_soft(self, abs_dst, abs_src, entry, init_sync_back_on, rel_src=None, only=None, ignore=None):
        """Copy the abs_dst to abs_src if the entry content does not
        match the dst_stat object with the given init_sync_back_on keys list
        """
        dst_stat = os.stat(abs_dst)
        success = False

        for key in init_sync_back_on:
            attr = self.val_map.get(key, None)
            if attr is None:
                self.log(f'Key "{key}" is not a valid attribute map')
                self.log(list(self.val_map.keys()))
                continue

            dst_val = getattr(dst_stat, attr[0], None)
            src_val = entry[attr[1]]
            if dst_val > src_val:
                #self.log(f'dst to src - key "{key}"', dst_val, src_val)
                # dst overwrite src.
                success, reason = self.copy_file(abs_dst, abs_src,
                        rel_src=rel_src,
                        only=only,
                        ignore=ignore
                        )
                if success is False:
                    self.log('copy_from_soft failed copy_file', reason)
        if success:
            self.log('change to', abs_src)

        return success


def create(path, settings):

    runner = Action(path, settings)
    return runner

