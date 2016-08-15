#!/usr/bin/env python

import argparse
from itertools import chain
import logging
from multiprocessing import Queue
import os
from os.path import relpath
import sys
import threading

import chromalog

from fs_radar import FsRadar, FsRadarEvent
from fs_radar.cmd_launch_pad import CmdLaunchPad
from fs_radar.config import load_from_toml, ConfigException
from fs_radar.logging_config import BASE, VERBOSE, QUIET
from fs_radar.observer import Observer
from fs_radar.path_filter import makePathFilter, makeDirFilter
from fs_radar.picky_eater import PickyEater, bulk_consume

logger = logging.getLogger(__spec__.name)


class FsRadarException(Exception):
    pass


class NoPathsToWatchException(FsRadarException):
    pass


class BaseDirNotExistsException(FsRadarException):
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
        cfg = {'fs_radar': {'basedir': ''}, 'group': {'default': {}}}
        cfg['fs_radar']['basedir'] = args.basedir
        cfg['group']['default']['rules'] = args.include + \
            ['!' + x for x in args.exclude] + \
            ['+' + x for x in args.keep_excluded]
        cfg['group']['default']['cmd'] = args.command or ''
        return cfg


def get_dir_filter(groups):
    return makeDirFilter(sorted(set(chain(
        *(d['rules'] for d in groups.values())
    ))))


def make_launch_pads_notifier(picky_launch_pads, basedir):
    '''Request a command execution from each launch_pad whose
    filters match `path`'''
    return lambda ev: bulk_consume(picky_launch_pads, relpath(ev.data, basedir))


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


def get_pairs_filter2launch_pads(cfg):
    '''Generate a list o pairs (path_filter, launch pad)'''
    for name, group in cfg['group'].items():
        path_filter = makePathFilter(group['rules'])
        lp = CmdLaunchPad(group['cmd'], options={**group, 'name': name})
        yield (path_filter, lp)


def start(cfg):
    '''Start the program.

    This function will continue to run until an exception is raised
    (commonly KeyboardInterrupt via CTRL-C).
    '''
    basedir = cfg['fs_radar']['basedir']
    os.chdir(basedir)

    dir_filter = get_dir_filter(cfg['group'])

    paths_to_watch = list(get_dirs_to_watch(basedir, dir_filter))

    if not paths_to_watch:
        raise NoPathsToWatchException('Nothing to watch')

    logger.debug('Paths to watch: %r', paths_to_watch)

    picky_launch_pads = []
    launch_pads = []
    for path_filter, lp in get_pairs_filter2launch_pads(cfg):
        plp = PickyEater(path_filter, lp.add_item_to_process)

        launch_pads.append(lp)
        picky_launch_pads.append(plp)

    observer = Observer()
    on_file_match = make_launch_pads_notifier(picky_launch_pads, basedir)
    observer.subscribe(FsRadarEvent.FILE_MATCH, on_file_match)

    with FsRadar(dir_filter, observer) as fsr:
        for path in paths_to_watch:
            fsr.add_watch(os.path.abspath(path))

        try:
            end_event = threading.Event()
            for lp in launch_pads:
                lp.set_end_event(end_event)
                lp.start()

            fsr.run_forever()
        finally:
            end_event.set()
            [lp.join() for lp in launch_pads]


def main(argv):
    parser = get_args_parser()
    args = parser.parse_args(argv[1:])

    setup_logs(args)
    logger.debug('Arguments: %r', args)

    cfg = get_config(args)
    logger.debug('Config: %r', cfg)

    if not os.path.exists(cfg['fs_radar']['basedir']):
        raise BaseDirNotExistsException(cfg['fs_radar']['basedir'])

    start(cfg)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        sys.exit(130)
    except ConfigException as e:
        logger.error(e)
        sys.exit(2)
    except NoPathsToWatchException:
        logger.error('There isn\'t any path matching the configured routes')
        sys.exit(3)
    except BaseDirNotExistsException as e:
        logger.error('Path configured as `basedir` was not found: %s', e.args[0])
        sys.exit(4)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)
    finally:
        logging.shutdown()
