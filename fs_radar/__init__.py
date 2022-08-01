from collections import namedtuple
import logging
import os
from os.path import join

from chromalog.mark.helpers.simple import important
from inotify_simple import INotify, flags, masks

logger = logging.getLogger(__spec__.name)

FsRadarEvent = namedtuple('FsRadarEvent', ['FILE_MATCH', 'FILE_GONE'])


class FsRadar:

    def __init__(self, dir_filter, observer):
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
        self.observer = observer

    def add_watch(self, path):
        if not ((self.watch_flags & flags.ONLYDIR) and not os.path.isdir(path)):
            wd = self.inotify.add_watch(path, self.watch_flags)
            self.wds[wd] = path
            logger.debug('Watch %s', important(path))

    def rm_watch(self, wd):
        logger.debug('Stop Watching %s', important(self.wds[wd]))
        self.inotify.rm_watch(wd)
        self.wds.pop(wd)

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
            # inotify_rm_watch was called automatically
            # (file/directory removed/unmounted)
            path = self.wds[event.wd]
            self.wds.pop(event.wd)
            self.on_file_gone(path)

    def on_new_dir(self, path):
        if self.dir_filter(path):
            self.add_watch(path)

            # If files have been added immediately to the directory we
            # missed the events, so we emit them artificially (with
            # the risk of having some repeated events)
            for fName in os.listdir(path):
                self.on_file_write(join(path, fName))

    def on_file_write(self, path):
        '''A write /directory at `path` was either unlinked, moved or unmounted'''
        self.observer.notify(FsRadarEvent.FILE_MATCH, path)

    def on_file_gone(self, path):
        '''The file/directory at `path` was either unlinked, moved or unmounted'''
        self.observer.notify(FsRadarEvent.FILE_GONE, path)

    def run_forever(self):
        while True:
            for event in self.inotify.read(read_delay=30, timeout=2000):
                self.on_watch_event(event)
