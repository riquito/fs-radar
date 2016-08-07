#!/usr/bin/env python

import argparse
import logging
from multiprocessing import Queue
import os
import sys
import threading

import chromalog

from fs_radar import FsRadar, FsRadarEvent
from fs_radar.cmd_launch_pad import CmdLaunchPad
from fs_radar.config import load_from_toml, ConfigException
from fs_radar.logging_config import BASE, VERBOSE, QUIET
from fs_radar.observer import Observer
from fs_radar.path_filter import makePathFilter, makeDirFilter

logger = logging.getLogger(__spec__.name)


class FsRadarException(Exception):
    pass


class NoPathsToWatchException(FsRadarException):
    pass


class BaseDirNotExistsExcpetion(FsRadarException):
    pass


def get_subdirs(path):
    '''Generator to iterate over the subdirectories under `path`.
    The root (`path`) is the first element yielded'''

    return (x[0] for x in os.walk(path))


def get_dirs_to_watch(basedir, path_filter):
    '''Generator to iterate over all the directories that are matched
    by `path_filter`'''

    for path in get_subdirs(basedir):
        if path_filter(path):
            yield path


def get_config(args):
    '''Get the watch configuration for FsRadar'''

    if args.config:
        return load_from_toml(args.config)
    else:
        cfg = {}
        cfg['basedir'] = args.basedir
        cfg['rules'] = args.include + \
            ['!' + x for x in args.exclude] + \
            ['+' + x for x in args.keep_excluded]
        cfg['cmd'] = args.command
        return cfg


def get_args_parser():
    '''Create the argument parser'''

    parser = argparse.ArgumentParser(prog='fs_radar', description='Run a program when a file change')
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
    return parser


def setup_logs(args):
    '''Load the correct logs' configuration'''

    if args.verbose:
        log_conf = VERBOSE
    elif args.quiet:
        log_conf = QUIET
    else:
        log_conf = BASE

    chromalog.basicConfig(**log_conf)


def start(cfg):
    '''Start the program.

    This function will continue to run until an exception is raised
    (commonly KeyboardInterrupt via CTRL-C).
    '''
    os.chdir(cfg['basedir'])

    omni_filter = makePathFilter(cfg['rules'])
    dir_filter = makeDirFilter(cfg['rules'])
    paths_to_watch = list(get_dirs_to_watch(cfg['basedir'], dir_filter))

    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logger.debug('Paths to watch: %r', list(paths_to_watch))

    if not paths_to_watch:
        raise NoPathsToWatchException('Nothing to watch')

    cmd_queue_in = Queue()
    end_event = threading.Event()
    cmd_launch_pad = CmdLaunchPad(cfg['cmd'], queue_in=cmd_queue_in, end_event=end_event)

    observer = Observer()
    observer.subscribe(FsRadarEvent.FILE_MATCH, lambda ev: cmd_queue_in.put(ev.data))

    with FsRadar(dir_filter, omni_filter, observer) as fsr:
        for path in paths_to_watch:
            fsr.add_watch(os.path.abspath(path))

        try:
            cmd_launch_pad.start()
            fsr.run_forever()
        finally:
            end_event.set()
            cmd_launch_pad.join()


def main(argv):
    parser = get_args_parser()
    args = parser.parse_args(argv[1:])

    setup_logs(args)
    logger.debug('Arguments: %r', args)

    cfg = get_config(args)
    logger.debug('Config: %r', cfg)

    if not os.path.exists(cfg['basedir']):
        raise BaseDirNotExistsExcpetion(cfg['basedir'])

    start(cfg)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        logger.error(e)
        sys.exit(1)
    finally:
        logging.shutdown()
