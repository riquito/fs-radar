#!/usr/bin/env python

import os
from re import search
from os.path import expanduser, join, abspath
from glob import glob
from inotify_simple import INotify, flags, masks
import logging
from .path_filter import makePathFilter, makeDirFilter
from .config import load_from_toml, ConfigException
from itertools import chain


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


class FsRadar:
    def __init__(self, dir_filter, file_filter):
        self.inotify = INotify()
        self.watch_flags = flags.CREATE | flags.DELETE | flags.MODIFY | flags.DELETE_SELF
        self.watch_flags = masks.ALL_EVENTS
        self.watch_flags = \
            flags.CREATE | \
            flags.DELETE | \
            flags.DELETE_SELF | \
            flags.CLOSE_WRITE | \
            flags.MOVE_SELF | \
            flags.MOVED_FROM | \
            flags.MOVED_TO | \
            flags.EXCL_UNLINK

        self.wds = {}
        self.dir_filter = dir_filter
        self.file_filter = file_filter

    def add_watch(self, path):
        if not ((self.watch_flags & flags.ONLYDIR) and not os.path.isdir(path)):
            wd = self.inotify.add_watch(path, self.watch_flags)
            self.wds[wd] = path
            logging.debug('Start watching {}'.format(path))

    def rm_watch(self, wd):
        logging.debug('Stop Watching {}'.format(self.wds[wd]))
        inotify.rm_watch(self.wds[wd])
        delete(self.wds[wd])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        logging.debug('Close inotify descriptor')
        return self.inotify.close()

    def on_watch_event(self, event):
        MASK_NEW_DIR = flags.CREATE | flags.ISDIR

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug('New event: {}'.format(event))
            for flag in flags.from_mask(event.mask):
                logging.debug('-> flag: {}'.format(flag))

        if MASK_NEW_DIR == MASK_NEW_DIR & event.mask:
            new_dir_path = join(self.wds[event.wd], event.name)
            self.on_new_dir(new_dir_path)
        elif flags.CLOSE_WRITE & event.mask and event.name:
            # we are watching a directory and a file inside of it has been touched
            logging.debug('Watching dir, file touched')
            self.on_file_write(join(self.wds[event.wd], event.name))
        elif flags.CLOSE_WRITE & event.mask and not event.name:
            # we are watching a file
            logging.debug('Watching file, file touched')
            self.on_file_write(self.wds[event.wd])
        elif flags.IGNORED & event.mask:
            # file/directory removed/moved/unmounted
            path = self.wds[event.wd]
            self.rm_watch(event.wd)
            self.on_file_gone(path)

    def on_new_dir(self, path):
        if self.dir_filter(path):
            self.add_watch(path)

            # If files have been added immediately to the directory we
            # missed the events, so we emit them artificially (with
            # the risk of having some repeated events)
            for fName in os.listdir(path):
                self.on_file_write(join(new_dir_path, fName))

    def on_file_write(self, path):
        '''A write /directory at `path` was either unlinked, moved or unmounted'''
        logging.debug('File written, not necessarily modified: {}'.format(path))
        if self.file_filter(path):
            logging.debug('... and it matches the rules')

    def on_file_gone(self, path):
        '''The file/directory at `path` was either unlinked, moved or unmounted'''
        logging.debug('File gone: {}'.format(path))

    def start(self, forever=False):
        while True:
            for event in self.inotify.read(read_delay=30):
                self.on_watch_event(event)

            if not forever:
                break


def get_subdirs(path):
    """Generator to iterate over the subdirectories under `path`.
    The root (`path`) is the first element yielded"""

    return (x[0] for x in os.walk(path))


def get_dirs_to_watch(basedir, path_filter):
    for path in get_subdirs(basedir):
        if path_filter(path):
            yield path


def get_path_filter():
    rules = (x for x in cfg['rules'].split('\n') if x.strip())
    omni_filter = makePathFilter(rules)
    return omni_filter


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Run a program when a file change')
    parser.add_argument('-b', '--basedir', action='store',
                              default=os.path.abspath(os.getcwd()),
                              help='the base directory of the files to watch')
    parser.add_argument('-c', '--config', action='store', default=None,
                              help='path to a config file')
    parser.add_argument('-i', '--include', action='append', default=[],
                              help='include this path')
    parser.add_argument('-e', '--exclude', action='append', default=[],
                              help='exclude this path (include first, then exclude)')
    parser.add_argument('-k', '--keep-excluded', action='append', default=[],
                              help='ignore exclusion rule for this path')
    parser.add_argument('-v', '--verbose', action='store_true',
                              help='verbose output')
    parser.add_argument('-s', '--static', action='store_true', default=False,
                              help='Watch only the files existing at program start')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    logging.debug('Arguments: {!r}'.format(args))

    if args.config:
        try:
            cfg = load_from_toml(args.config)
        except ConfigException as e:
            print(e, file=sys.stderr)
            sys.exit(1)
    else:
        cfg = {}
        cfg['basedir'] = args.basedir
        cfg['rules'] = args.include + \
            ['!' + x for x in args.exclude] + \
            ['+' + x for x in args.keep_excluded]

    logging.debug('Config: {!r}'.format(cfg))

    if not os.path.exists(cfg['basedir']):
        print('Basedir does not exists: {}'.format(cfg['basedir']), file=sys.stderr)
        sys.exit(1)

    os.chdir(cfg['basedir'])

    omni_filter = makePathFilter(cfg['rules'])
    dir_filter = makeDirFilter(cfg['rules'])
    paths_to_watch = list(get_dirs_to_watch(cfg['basedir'], dir_filter))

    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug('Paths to watch: {!r}'.format(list(paths_to_watch)))

    if not paths_to_watch:
        print('Nothing to watch, exiting', file=sys.stderr)
        sys.exit(1)

    with FsRadar(dir_filter, omni_filter) as fsr:
        for path in paths_to_watch:
            fsr.add_watch(abspath(path))

        try:
            fsr.start(forever=True)
        except KeyboardInterrupt:
            pass
