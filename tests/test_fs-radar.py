import pytest
import unittest

from src.fs_radar import get_paths_to_watch


class FsRadatTest(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def initdir(self, tmpdir):
        tmpdir.chdir()  # change to pytest-provided temporary directory

        tmpdir.ensure('file_zero.txt')

        sub1 = tmpdir.join('sub1').mkdir()
        sub1.ensure('file_a.gz')
        sub1.ensure('file_b.tgz')

        sub2 = tmpdir.join('sub2').mkdir()
        sub2.ensure('file_c.gz')
        sub2.ensure('file_d.tgz')

        sub2_1 = sub2.join('sub2_1').mkdir()
        sub2_1.ensure('file_e.gz')
        sub2_1.ensure('file_f.tgz')

    def test_include_nothing(self):
        assert set(get_paths_to_watch([])) == set()

    def test_include_unexistent_file(self):
        """Do not accept a non existent path"""
        includes = ['a']
        result = get_paths_to_watch(includes)

        assert set(result) == set([])

    def test_include_unexistent_glob(self):
        """Ignore path expressions with globs that do not match anything"""
        includes = ['foo/bar/*']
        result = get_paths_to_watch(includes)

        assert set(result) == set([])

    def test_include_single_file_at_root(self):
        includes = ['file_zero.txt']
        result = get_paths_to_watch(includes)

        assert set(result) == set(['file_zero.txt'])

    def test_include_single_file_deep(self):
        includes = ['sub1/file_a.gz']
        result = get_paths_to_watch(includes)

        assert set(result) == set(['sub1/file_a.gz'])

    def test_include_glob_single_directory(self):
        includes = ['*']
        result = get_paths_to_watch(includes)

        assert set(result) == set(['file_zero.txt', 'sub1', 'sub2'])

    def test_include_glob_recursive(self):
        includes = ['**']
        result = get_paths_to_watch(includes)

        assert set(result) == set([
            'file_zero.txt',
            'sub1',
            'sub1/file_a.gz',
            'sub1/file_b.tgz',
            'sub2',
            'sub2/file_c.gz',
            'sub2/file_d.tgz',
            'sub2/sub2_1',
            'sub2/sub2_1/file_e.gz',
            'sub2/sub2_1/file_f.tgz'
        ])

    def test_exclude_path(self):
        includes = ['sub1/file_a.gz', 'sub1/file_b.tgz']
        excludes = ['sub1/file_b.tgz']
        result = get_paths_to_watch(includes, excludes)

        assert set(result) == set(['sub1/file_a.gz'])

    def test_exclude_glob(self):
        includes = ['sub1/file_a.gz', 'sub1/file_b.tgz']
        excludes = ['sub1/*tgz']
        result = get_paths_to_watch(includes, excludes)

        assert set(result) == set(['sub1/file_a.gz'])

    def test_exclude_by_regexp_match(self):
        includes = ['sub1/file_a.gz', 'sub1/file_b.tgz']
        regexps = ['foo', '[a-z]gz$']
        result = get_paths_to_watch(includes, exclusion_regexps=regexps)

        assert set(result) == set(['sub1/file_a.gz'])
