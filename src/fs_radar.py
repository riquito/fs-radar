#!/usr/bin/env python

from re import search
from os.path import expanduser
from glob import glob
import logging


def expand_glob_generator(glob_path_list):
    """Given a list of glob pattern, search for matching files.
    Yield matching files.
    """
    for glob_path in glob_path_list:
        for path in glob(expanduser(glob_path), recursive=True):
            yield path


def match_any(text, regexps):
    """Return True if `text` matches any of the `regexps`, False otherwise."""
    for regexp in regexps:
        if search(regexp, text):
            return True
    else:
        return False


def get_paths_to_watch(includes, excludes=None, exclusion_regexps=None):
    """Return a list of paths to watch.

    includes is a list of paths to include
    excludes is a list of paths to remove (include first, then exclude)
    exclusion_regexps is a list of regexps, any matching path is excluded

    Includes and excludes may contain the expansion variables *, **
    """

    includes = expand_glob_generator(includes or [])
    excludes = expand_glob_generator(excludes or [])

    for path in set(includes) - set(excludes):
        if not exclusion_regexps or not match_any(path, exclusion_regexps):
            yield path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run a program when a file change')
    parser.add_argument('-i', '--include', action='append', required=True,
                              help='include this path')
    parser.add_argument('-p', '--exclude-by-path', action='append', default=[],
                              help='exclude this path (include first, then exclude)')
    parser.add_argument('-e', '--exclude-by-regexp', action='append', default=[],
                              help='exclude paths that match these regexp')
    parser.add_argument('-v', '--verbose', action='store_true',
                              help='verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    paths_to_watch = get_paths_to_watch(args.include, args.exclude_by_path, args.exclude_by_regexp)

    for path in paths_to_watch:
        print(path)
