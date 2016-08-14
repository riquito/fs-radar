import hashlib
import logging
from multiprocessing import Queue, Process
from queue import Empty as EmptyException
import os
import pty
import re
import select
import subprocess
from threading import Thread
from time import time, sleep

from chromalog.mark.helpers.simple import success, error, important

logger = logging.getLogger(__name__)


class CommandNameLogAdapter(logging.LoggerAdapter):
    """This adapter expects the passed in dict-like object to have a 'cmd_name'
    key, whose value in brackets is prepended to the log message.
    """

    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['cmd_name'], msg), kwargs


class CmdLaunchPad(Thread):

    def __init__(self, cmd_template, options=None, end_event=None, name=''):
        super(CmdLaunchPad, self).__init__()
        self.options = {**{
            'stop_previous_process': False,
            'can_discard': True,
            'timeout': 30,
        }, **(options or {})}
        self.p = None
        self.process_start_time = 0

        self.queue_process = Queue()
        self.queue_in = Queue()
        self.end_event = end_event

        self.cmd_template = self._normalize_cmd_substitution_token(cmd_template)

        if not name:
            name = hashlib.sha1(cmd_template.encode('utf-8')).hexdigest()[:6]

        self.adapter = CommandNameLogAdapter(logger, {'cmd_name': name})

    def add_item_to_process(self, item):
        self.queue_in.put(item)

    def set_end_event(self, event):
        self.end_event = event

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

        self.adapter.debug('Run cmd launch pad')
        while True:
            try:
                exit_status, cmd, output = self.queue_process.get(block=False)
                if exit_status is None:
                    # process produced output and is still running
                    self.adapter.info('[%s] %s', self.name, output.strip())
                elif exit_status == 0:
                    self.adapter.info('Process ended:\ncommand was: %s\nexit status: %s, output (from the next line):\n%s', *[success(i) for i in (cmd, exit_status, output)])  # noqa
                else:
                    self.adapter.warn('Process ended:\ncommand was: %s\nexit status: %s, output (from the next line):\n%s', *[error(i) for i in (cmd, exit_status, output)])  # noqa

            except EmptyException as e:
                pass

            try:
                parameter = self.queue_in.get(block=True, timeout=1)
            except EmptyException as e:
                if self.end_event and self.end_event.is_set():
                    self.adapter.debug('Terminate thread as requested')
                    break
                else:
                    continue

            self.adapter.debug('Got parameter %s', parameter)

            if self.is_process_alive() and self.options['stop_previous_process']:
                self.adapter.debug('Stop previous process')
                self.terminate_process()

            if self.is_process_alive() and self.options['can_discard']:
                self.adapter.debug('Process already running, can discard')
                continue

            if self.is_process_alive():
                # There is a running process and I couldn't neither interrupt it
                # nor discard the new event: let's wait for the process to end.

                time_left = self.get_seconds_until_process_timeout()
                self.adapter.debug('Wait at most %d seconds for the process to time out', time_left)
                while time_left > 0:
                    sleep(1)
                    time_left -= 1
                    if not self.is_process_alive():
                        break

                if self.p.is_alive():
                    self.adapter.warn('Process timed out')
                    self.terminate_process()
                else:
                    self.adapter.debug('Process terminated naturally')

            self.adapter.debug('Start a new process')
            self.run_process(self.cmd_template, parameter)

    def _normalize_cmd_substitution_token(self, cmd_template):
        '''Normalize the token to {}. cmd can hold '{}' or "{}" or {}'''
        return re.sub('\'\{\}\'|"\{\}"', '{}', cmd_template)

    def run_process(self, cmd_template, parameter):
        '''Run the command after replacing every occurrence
        of {} with `parameter`'''
        self.process_start_time = time()
        cmd_line = cmd_template.replace('{}', parameter)
        self.adapter.debug('Command line is %s', cmd_line)
        self.p = Process(target=run_command_with_queue, args=(cmd_line, self.queue_process))
        self.p.start()


def run_command(cmd):
    '''Spawn a blocking process to run `cmd`

    @param string cmd the command to run
    @return tuple (exit status code, output as a string)
    '''

    # 1. /usr/bin/env bash because not everyone has bash in /bin/
    # 2. -l because we want to read .bash_profile or brothers
    # 3. -i because -l isn't enough
    # 4. use a pty because it's required by using -i
    # 5. start_new_session because otherwise we get
    # bash: cannot set terminal process group (-1): Inappropriate ioctl for device
    # bash: no job control in this shell
    # (it also sets a process group so if we kill the shell we kill
    # the subprocess too)
    master, slave = pty.openpty()
    args = ['/usr/bin/env', 'bash', '-i', '-l', '-c', cmd]
    p = subprocess.Popen(
        args,
        stdin=slave,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    os.close(slave)  # close slave on master's process

    return p


def run_command_with_queue(cmd, queue):
    '''Spawn a blocking process to run `cmd`, set his result in the `queue`.

    The queue will receive a tuple (exit status code, cmd, output as a string)
    when the process end.

    @param string cmd the command to run
    @param Queue queue where to put the data when the process end
    '''

    p = run_command(cmd)

    while True:
        data = ''
        r, w, x = select.select([p.stdout], [], [], 10)
        if r:
            data = r[0].readline()
            if data:
                queue.put((None, cmd, data.decode('utf-8').rstrip()))

        if not data and p.returncode is not None:
            # Terminate when we've read all the output and the returncode is set
            break

        p.poll()  # updates returncode so we can exit the loop

    queue.put((p.returncode, cmd, ''))
    queue.close()
