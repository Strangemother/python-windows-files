import unittest
import os
import sys
from action import Copy
import main
import tempfile
import shutil


TMP_STORE = True

TEST_DIR = os.path.abspath(os.path.dirname(__file__))

TEST_STORE = os.path.abspath(os.path.join(TEST_DIR, '..', 'test_src_store'))
if TMP_STORE:
    TEST_STORE = tempfile.mkdtemp()


class TestAction(unittest.TestCase):

    def setUp(self):
        # funcname = current_func_name()
        funcname = self._testMethodName
        self.src_dir = ensure_dir(funcname, 'src_location')
        self.dst_dir = ensure_dir(funcname, 'dst_location')

    def tearDown(self):
        pass # del_folder(ensure_dir(self._testMethodName))

    def assert_src_exists(self, filename, root_dir=None):
        fullpath = os.path.join(root_dir or self.src_dir, filename)
        self.assertTrue(
                os.path.exists(fullpath),
                (f'SRC path file "{filename}" '
                 f'does not exist in "{self.src_dir}"')
            )

    def assert_dst_exists(self, filename):
        return self.assert_src_exists(filename, self.dst_dir)

    def ensure_src_file(self, filename, size=128):
        return ensure_file(self.src_dir, filename, size)

    def ensure_dst_file(self, filename, size=128):
        return ensure_file(self.dst_dir, filename, size)

    def abs_dst(self, filename):
        """Return a filepath for the destination directory."""
        return os.path.join(self.dst_dir, filename)

    #@unittest.skip
    def test_simple_copy(self):
        """Ensure the Copy Action copies a file from src to dst"""
        filename = 'foo.txt'
        # Real file and its path
        path = self.ensure_src_file(filename, 1024)
        expected_dst_filepath = self.abs_dst(filename)

        copy_action = Copy(self.src_dir)

        # Provide the exposure, usually given by the loop.
        config = {'dst': self.dst_dir}
        copy_func = copy_action.exposed(config)

        # simulate an event.
        entry = (path, 'Created')
        success, to_path = copy_func(entry, config)

        self.assertTrue(success)
        self.assertEqual(to_path, expected_dst_filepath)

    #@unittest.skip
    def test_simple_sync_back(self):
        """Ensure Copy sync a file from dst upon wake.
        """
        src_filename = 'in_src.txt'
        src_file = self.ensure_src_file(src_filename, 1024)

        filename1 = 'in_dst1.txt'
        filename2 = 'in_dst2.txt'
        # Ensure something to detect
        path1 = self.ensure_dst_file(filename1, 1024)
        path2 = self.ensure_dst_file(filename2, 1024)

        copy_action = Copy(self.src_dir)
        config = dict(dst=self.dst_dir, init_sync_back=True, sync=True)
        copy_func = copy_action.exposed(config)

        # assert the two dst files exist in the src.
        self.assert_src_exists(filename1)
        self.assert_src_exists(filename2)

        # simulate an event, would usually be performed by the init loop
        # with a folder scan.
        entry = (src_file, 'Nothing')
        res = copy_func(entry, config)
        self.assert_dst_exists(src_filename)

    #@unittest.skip
    def test_simple_copy_perform_absolute(self):
        """Perform a event-like file copy, using the perform command and absolute
        filepath"""
        filename = 'foo.txt'
        # Real file and its path
        src_abspath = self.ensure_src_file(filename, 1024)
        dst_path = self.abs_dst(filename)

        copy_action = Copy(self.src_dir)
        res = copy_action.perform(src_abspath, self.dst_dir)
        self.assert_standard_one(res, dst_path, filename)

    def test_simple_copy_perform_relative(self):
        """Perform a copy, to a preloaded src and dst, with a relative filename
        """
        filename = 'foo.txt'
        # Real file and its path
        src_abspath = self.ensure_src_file(filename, 1024)
        dst_path = self.abs_dst(filename)

        copy_action = Copy(self.src_dir, self.dst_dir)
        # Copy relative file from src to dest.
        res = copy_action.perform(filename)
        self.assert_standard_one(res, dst_path, filename)

    def assert_standard_one(self, res, dst_path, filename):
        self.assertTrue(res[0])
        self.assertEqual(res[1], dst_path)
        self.assert_dst_exists(filename)


def current_func_name():
    return sys._getframe().f_back.f_code.co_name


def ensure_dir(*sub_root):
    """Ensure the given sub directory path exists within the test root storage
    location.
    Return the full path of the final directory
    """
    tdir = os.path.join(TEST_STORE, *sub_root)
    if os.path.isdir(tdir) is False:
        # print('Creating root test store', tdir)
        os.makedirs(tdir)
    return tdir


def del_folder(dirpath):
    return shutil.rmtree(dirpath)


def ensure_file(root_path, filename,size):
    """
    generate big binary file with the specified size in bytes
    :param filename: the filename
    :param size: the size in bytes
    :return:void
    """
    filepath = os.path.join(root_path, filename)
    with open(filepath, 'wb') as stream:
        stream.write(os.urandom(size)) #1
    # print(f'size {size} generated')
    return filepath
