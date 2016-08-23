import pytest
import unittest

from fs_radar.path_filter import makePathFilter, makeDirFilter


class MakePathFilterTest(unittest.TestCase):

    def test_empty_rules(self):
        f = makePathFilter([])

        assert f('') is False
        assert f('foo.txt') is False

    def test_file_at_any_depth(self):
        f = makePathFilter([
            'foo.txt'
        ])

        assert f('foo.txt')
        assert f('./foo.txt')
        assert f('a/b/foo.txt')

    def test_asterisk_for_file_at_any_depth(self):
        f = makePathFilter([
            '*.txt'
        ])

        assert f('foo.txt')
        assert f('./foo.txt')
        assert f('a/b/foo.txt')

    def test_file_pattern_must_not_used_as_prefix(self):
        f = makePathFilter([
            '.doc'
        ])

        assert f('foo.docx') is False

    def test_match_only_at_relative_root(self):
        f = makePathFilter([
            './foo.txt'
        ])

        assert f('./foo.txt')
        assert f('foo.txt')
        assert f('/foo.txt') is False
        assert f('a/b/foo.txt') is False

    def test_match_only_absolute_path(self):
        f = makePathFilter([
            '/a/b/foo.txt'
        ])

        assert f('/a/b/foo.txt')
        assert f('a/b/foo.txt') is False

    def test_match_directory_and_any_file_underneath(self):
        f = makePathFilter([
            'a/b/'
        ])

        assert f('a/b/')
        assert f('a/b')
        assert f('a/b/foo.txt')
        assert f('a/b/c/')
        assert f('a/b/c/bar')

    def test_do_not_use_directory_as_prefix(self):
        f = makePathFilter([
            'a/b/'
        ])

        assert f('a/bo') is False

    def test_just_asterisk(self):
        f = makePathFilter([
            '*'
        ])

        assert f('') is False
        assert f('foo.txt')
        assert f('a/b/')

    def test_start_with_asterisk(self):
        f = makePathFilter([
            '*a',
            '*b/foo'
        ])

        assert f('a')
        assert f('xyza')
        assert f('b') is False
        assert f('b/foo')
        assert f('xb/foo')

    def test_single_asterisk(self):
        f = makePathFilter([
            'a/*foo/a',
            'b/bar*/b',
            'c/*baz*/c',
        ])

        assert f('a/foo/a')
        assert f('a/xfoo/a')

        assert f('b/bar/b')
        assert f('b/barx/b')

        assert f('c/baz/c')
        assert f('c/xbaz/c')
        assert f('c/bazx/c')
        assert f('c/xbazx/c')

        assert f('abcdfoo/a') is False

    def test_just_multi_asterisks(self):
        f = makePathFilter([
            '**'
        ])

        assert f('') is False
        assert f('foo.txt')
        assert f('a/b/')

    def test_file_start_multi_asterisks(self):
        f = makePathFilter([
            '**a'
        ])

        assert f('foo.txt') is False
        assert f('ba')
        assert f('bar') is False
        assert f('ba/example/') is False
        assert f('x/y/a')

    def test_dir_start_multi_asterisks(self):
        f = makePathFilter([
            '**a/'
        ])

        assert f('ba')
        assert f('bar') is False
        assert f('ba/example/')
        assert f('x/y/a/')

    def test_multi_asterisks(self):
        f = makePathFilter([
            'a/**/x'
        ])

        assert f('a/x') is False
        assert f('a/one-level/x')
        assert f('a/multi/level/deep/x')
        assert f('a/b/c') is False

    def test_exclusion(self):
        f = makePathFilter([
            "app/cache/*",
            "!app/cache/*.txt",
            "+app/cache/do-not-exclude-me.txt"
        ])

        assert f('app/cache/include-me')
        assert f('app/cache/exclude-me.txt') is False
        assert f('app/cache/do-not-exclude-me.txt')

    def test_working_directory_just_dot(self):
        f = makePathFilter([
            '.'
        ])

        assert f('.')
        assert f('./')
        assert f('foo.txt')
        assert f('./foo.txt')
        assert f('a/b/')

    def test_working_directory_dot_slash(self):
        f = makePathFilter([
            '././'
        ])

        assert f('.')
        assert f('./')
        assert f('foo.txt')
        assert f('./foo.txt')
        assert f('a/b/')


class MakeDirFilterTest(unittest.TestCase):

    def test_empty_rules(self):
        f = makeDirFilter([])

        assert f('') is False
        assert f('a/') is False

    def test_dir_at_any_depth(self):
        f = makeDirFilter([
            'a/'
        ])

        assert f('a/')
        assert f('./a')
        assert f('b/a/')

    def test_ignore_file_keep_dir(self):
        f = makeDirFilter([
            'a/foo.txt'
        ])

        assert f('a/')
        assert f('./a')
        assert f('b/a/')

    def test_excluded_dir(self):
        f = makeDirFilter([
            'a/',
            '!a/b/',
            '!a/c/foo.txt',
            '!a/d/',
            '+a/d/baz.txt'
        ])

        assert f('a/')
        assert f('a/b/') is False
        assert f('a/c/')
        assert f('a/d/')

    def test_working_directory_just_dot(self):
        f = makeDirFilter([
            '.'
        ])

        assert f('.')
        assert f('./')
        assert f('foo.txt')
        assert f('./foo.txt')
        assert f('a/b/')

    def test_working_directory_dot_slash(self):
        f = makeDirFilter([
            '././'
        ])

        assert f('.')
        assert f('./')
        assert f('foo.txt')
        assert f('./foo.txt')
        assert f('a/b/')

    def test_single_asterisk_in_a_path_starting_with_dot(self):
        f = makeDirFilter([
            './a/*/c/'
        ])

        assert f('./a/b/c')
        assert f('./a/b/d') is False
        assert f('a/b/c')
        assert f('a/b/d') is False

    def test_double_asterisk_in_a_path_starting_with_dot(self):
        f = makeDirFilter([
            './a/**/c/'
        ])

        assert f('./a/b/c')
        assert f('./a/b1/b2/c')
        assert f('./a/b/d') is False
        assert f('a/b/c')
