import logging
import re
import subprocess
from multiprocessing import Queue, Process
from queue import Empty as EmptyException
from threading import Thread
import shlex
from time import time, sleep

from chromalog.mark.helpers.simple import success, error, important

logger = logging.getLogger(__name__)


class CmdLaunchPad(Thread):
    def __init__(self, cmd_template, queue_in, options=None, end_event=None):
        super(CmdLaunchPad, self).__init__()
        self.options = {**{
            'stop_previous_process': False,
            'can_discard': True,
            'timeout': 30,
        }, **(options or {})}
        self.p = None
        self.process_start_time = 0

        self.queue_process = Queue()
        self.queue_in = queue_in
        self.end_event = end_event

        self.cmd_template = self._normalize_cmd_substitution_token(cmd_template)

    def is_process_alive(self):
        '''Is the process still running?

        @return bool whether the process is running or not
        '''
        return bool(self.p and self.p.is_alive())

    def terminate_process(self):
        '''Kill the process sending to it a SIGTERM signal.

        Also reset process related variables.'''
        self.p.terminate()
        self.p = None
        self.process_start_time = 0

    def get_seconds_until_process_timeout(self):
        '''Return the number of seconds remaining until the process
        is to be considered as timed out.'''
        return max(0, self.process_start_time + self.options['timeout'] - time())

    def run(self):
        '''Run an infinite loop that wait for requests to run a process.'''

        logger.debug('Run cmd launch pad')
        while True:
            logger.debug('Waiting for a new request to run the command')

            try:
                exit_status, cmd, output = self.queue_process.get(block=False)
                if exit_status == 0:
                    logger.info('Process ended:\ncommand was: %s\nexit status: %s, output (from the next line):\n%s', *[success(i) for i in (cmd, exit_status, output)])  # noqa
                else:
                    logger.warn('Process ended:\ncommand was: %s\nexit status: %s, utput (from the next line):\n%s', *[error(i) for i in (cmd, exit_status, output)])  # noqa

            except EmptyException as e:
                pass

            try:
                parameter = self.queue_in.get(block=True, timeout=1)
            except EmptyException as e:
                if self.end_event.is_set():
                    logger.debug('Terminate thread as requested')
                    break
                else:
                    continue

            logger.debug('Got parameter %s', parameter)

            if self.is_process_alive() and self.options['stop_previous_process']:
                logger.debug('Stop previous process')
                self.terminate_process()

            if self.is_process_alive() and self.options['can_discard']:
                logger.debug('Process already running, can discard')
                continue

            if self.is_process_alive():
                # There is a running process and I couldn't neither interrupt it
                # nor discard the new event: let's wait for the process to end.

                time_left = self.get_seconds_until_process_timeout()
                logger.debug('Wait %d seconds for the process to time out', time_left)
                sleep(time_left)

                if self.p.is_alive():
                    logger.warn('Process timed out')
                    self.terminate_process()
                else:
                    logger.debug('Process terminated naturally')

            logger.debug('Start a new process')
            self.run_process(self.cmd_template, parameter)

    def _normalize_cmd_substitution_token(self, cmd_template):
        '''Normalize the token to {}. cmd can hold '{}' or "{}" or {}'''
        return re.sub('\'\{\}\'|"\{\}"', '{}', cmd_template)

    def run_process(self, cmd_template, parameter):
        '''Run the command after replacing every occurrence
        of {} with `parameter`'''
        self.process_start_time = time()
        cmd_line = cmd_template.replace('{}', parameter)
        logger.debug('Command line is %s', cmd_line)
        self.p = Process(target=run_command_with_queue, args=(cmd_line, self.queue_process))
        self.p.start()


def run_command(cmd):
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd

    exit_status = 0

    try:
        output_b = subprocess.check_output(args, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        output_b = e.output
        exit_status = e.returncode

    output = output_b.decode('utf-8')

    return (exit_status, output)


def run_command_with_queue(cmd, queue):
    exit_status, output = run_command(cmd)
    queue.put((exit_status, cmd, output))
    queue.close()
