#!/usr/bin/env python

import os
from re import search
from os.path import expanduser, join, abspath
from glob import glob
from inotify_simple import INotify, flags, masks
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

class FsRadar:
    def __init__(self):
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
            self.add_watch(new_dir_path)

            # If files have been added immediately to the directory we
            # missed the events, so we emit them artificially (with
            # the risk of having some repeated events)
            for fName in os.listdir(new_dir_path):
                self.on_file_write(join(new_dir_path, fName))
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

    def on_file_write(self, path):
        '''A write /directory at `path` was either unlinked, moved or unmounted'''
        logging.debug('File written, not necessarily modified: {}'.format(path))

    def on_file_gone(self, path):
        '''The file/directory at `path` was either unlinked, moved or unmounted'''
        logging.debug('File gone: {}'.format(path))

    def start(self, forever=False):
        while True:
            for event in self.inotify.read(read_delay=30):
                self.on_watch_event(event)

            if not forever:
                break


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

    paths_to_watch = list(get_paths_to_watch(args.include, args.exclude_by_path, args.exclude_by_regexp))

    with FsRadar() as fsr:
        for path in paths_to_watch:
            fsr.add_watch(abspath(path))

        try:
            fsr.start(forever=True)
        except KeyboardInterrupt:
            pass
