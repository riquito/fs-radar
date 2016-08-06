#!/usr/bin/env python

import logging
import chromalog
from chromalog.mark.helpers.simple import important, success, error
import os
from collections import namedtuple
from os.path import join, abspath
from inotify_simple import INotify, flags, masks
from .path_filter import makePathFilter, makeDirFilter
from .config import load_from_toml, ConfigException
from .observer import Observer
from .cmd_launch_pad import CmdLaunchPad
from multiprocessing import Queue
import threading
from select import select
from src.logging_config import BASE, VERBOSE, QUIET

FsRadarEvent = namedtuple('FsRadarEvent', ['FILE_MATCH'])

logger = logging.getLogger(__spec__.name)


class FsRadar:
    def __init__(self, dir_filter, file_filter, observer):
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
        self.observer = observer

    def add_watch(self, path):
        if not ((self.watch_flags & flags.ONLYDIR) and not os.path.isdir(path)):
            wd = self.inotify.add_watch(path, self.watch_flags)
            self.wds[wd] = path
            logger.debug('Watch %s', important(path))

    def rm_watch(self, wd):
        logger.debug('Stop Watching %s', important(self.wds[wd]))
        inotify.rm_watch(self.wds[wd])
        delete(self.wds[wd])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        logger.debug('Close inotify descriptor')
        return self.inotify.close()

    def on_watch_event(self, event):
        MASK_NEW_DIR = flags.CREATE | flags.ISDIR

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logger.debug('New event: %r', event)
            for flag in flags.from_mask(event.mask):
                logger.debug('-> flag: %s', flag)

        if MASK_NEW_DIR == MASK_NEW_DIR & event.mask:
            new_dir_path = join(self.wds[event.wd], event.name)
            self.on_new_dir(new_dir_path)
        elif flags.CLOSE_WRITE & event.mask and event.name:
            # we are watching a directory and a file inside of it has been touched
            logger.debug('Watching dir, file touched')
            self.on_file_write(join(self.wds[event.wd], event.name))
        elif flags.CLOSE_WRITE & event.mask and not event.name:
            # we are watching a file
            logger.debug('Watching file, file touched')
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
        logger.debug('File written (not necessarily modified): %s', important(path))
        if self.file_filter(path):
            logger.info('Watched file written: %s', path)
            self.observer.notify(FsRadarEvent.FILE_MATCH, path)

    def on_file_gone(self, path):
        '''The file/directory at `path` was either unlinked, moved or unmounted'''
        logger.debug('File gone: %s', path)

    def run_forever(self):
        while True:
            for event in self.inotify.read(read_delay=30, timeout=2000):
                self.on_watch_event(event)


def get_subdirs(path):
    """Generator to iterate over the subdirectories under `path`.
    The root (`path`) is the first element yielded"""

    return (x[0] for x in os.walk(path))


def get_dirs_to_watch(basedir, path_filter):
    for path in get_subdirs(basedir):
        if path_filter(path):
            yield path


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
    parser.add_argument('-x', '--command', action='store',
                              help='Execute the command when a matching file has changed.\n'
                                   'Any occurrence of {} is replaced by the path of the file')
    parser.add_argument('-q', '--quiet', action='store_true', default=False,
                              help='Keep output to a minimum')

    args = parser.parse_args()

    if args.verbose:
        log_conf = VERBOSE
    elif args.quiet:
        log_conf = QUIET
    else:
        log_conf = BASE

    chromalog.basicConfig(**log_conf)

    logger.debug('Arguments: %r', args)

    if args.config:
        try:
            cfg = load_from_toml(args.config)
        except ConfigException as e:
            logger.error(e)
            sys.exit(1)
    else:
        cfg = {}
        cfg['basedir'] = args.basedir
        cfg['rules'] = args.include + \
            ['!' + x for x in args.exclude] + \
            ['+' + x for x in args.keep_excluded]
        cfg['cmd'] = args.command

    logger.debug('Config: %r', cfg)

    if not os.path.exists(cfg['basedir']):
        logger.error('Basedir does not exist: %s', important(cfg['basedir']))
        sys.exit(1)

    os.chdir(cfg['basedir'])

    omni_filter = makePathFilter(cfg['rules'])
    dir_filter = makeDirFilter(cfg['rules'])
    paths_to_watch = list(get_dirs_to_watch(cfg['basedir'], dir_filter))

    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logger.debug('Paths to watch: %r', list(paths_to_watch))

    if not paths_to_watch:
        logger.error('Nothing to watch')
        sys.exit(1)

    cmd_queue_in = Queue()
    end_event = threading.Event()
    cmd_launch_pad = CmdLaunchPad(cfg['cmd'],
                                  queue_in=cmd_queue_in,
                                  end_event=end_event)

    observer = Observer()
    observer.subscribe(FsRadarEvent.FILE_MATCH, lambda ev: cmd_queue_in.put(ev.data))

    with FsRadar(dir_filter, omni_filter, observer) as fsr:
        for path in paths_to_watch:
            fsr.add_watch(abspath(path))

        try:
            cmd_launch_pad.start()
            fsr.run_forever()
        except KeyboardInterrupt:
            end_event.set()
            cmd_launch_pad.join()
            logging.shutdown()
