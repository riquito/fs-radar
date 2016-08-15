import hashlib
import logging
from multiprocessing import Queue, Process
from queue import Empty as EmptyException
import re
import select
from threading import Thread
from time import time, sleep
import fs_radar.shell_process

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

        try:
            # empty queue_process queue, we don't want to keep
            # old unread output around
            while True:
                self.queue_process.get(block=False)
        except EmptyException:
            pass

    def get_seconds_until_process_timeout(self):
        '''Return the number of seconds remaining until the process
        is to be considered as timed out.'''
        return max(0, self.process_start_time + self.options['timeout'] - time())

    def run(self):
        '''Run an infinite loop that wait for requests to run a process.'''

        self.adapter.debug('Run cmd launch pad')
        while True:

            if self.end_event and self.end_event.is_set():
                self.adapter.debug('Terminate thread as requested')
                break

            readers = [
                self.queue_process._reader,
                self.queue_in._reader
            ]

            r, w, x = select.select(readers, [], [], 1)
            for ready in r:
                if ready == self.queue_process._reader:
                    self.on_process_queue_item_received(self.queue_process.get(block=True))
                elif ready == self.queue_in._reader:
                    self.on_parameter_received(self.queue_in.get(block=True))
                else:
                    raise Error('Unexpected input')

    def on_parameter_received(self, parameter):
        self.adapter.debug('Got parameter %s', parameter)

        if self.is_process_alive() and self.options['stop_previous_process']:
            self.adapter.debug('Stop previous process')
            self.terminate_process()

        if self.is_process_alive() and self.options['can_discard']:
            self.adapter.debug('Process already running, can discard')
            return

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

        self.adapter.info('### START PROCESS ###')
        self.run_process(self.cmd_template, parameter)

    def on_process_queue_item_received(self, item):
        exit_status, cmd, output = item

        if exit_status is None:
            # process produced output and is still running
            self.adapter.info('%s', output.strip())
        elif exit_status == 0:
            self.adapter.info('### END (status %s) ###', success(exit_status))
        else:
            self.adapter.info('### END (status %s) ###', error(exit_status))

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


def _make_callback_on_process_line_read(cmd, queue):
    return lambda exit_status, line: queue.put((exit_status, cmd, line))


def run_command_with_queue(cmd, queue):
    '''Run `cmd` in a shell, put every line it outputs in the queue
    one line at a time.

    Each item put in the queue is a tuple (exit status (or None), cmd, line)

    @param string cmd the command to run
    @param subprocess.Queue queue the queue where to put the data
    '''
    p = fs_radar.shell_process.popen_shell_command(cmd)
    callback = _make_callback_on_process_line_read(cmd, queue)
    fs_radar.shell_process.consume_output_line_by_line(p, callback)
