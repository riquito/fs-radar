import hashlib
import logging
from multiprocessing import Event, Process, Queue
from queue import Empty as EmptyException
import re
import select
import subprocess
from threading import Thread
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

        self.queue_process = Queue()
        self.queue_in = Queue()
        self.end_event = end_event
        self.timed_out_event = Event()

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

        if not self.p:
            return

        self.p.terminate()
        self.p.join()
        self.p = None

        # the queue may have become corrupt after the use of terminate()
        # https://docs.python.org/3.5/library/multiprocessing.html#multiprocessing.Process.terminate
        self.queue_process = Queue()

    def run(self):
        '''Run an infinite loop that wait for requests to run a process.'''

        self.adapter.debug('Run cmd launch pad')
        while True:

            if self.end_event and self.end_event.is_set():
                self.adapter.debug('Terminate thread as requested')
                self.terminate_process()
                break
            elif self.timed_out_event.is_set():
                self.adapter.info('### END PROCESS - %s ###', error('timed out'))
                self.on_process_timed_out()

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

    def on_process_timed_out(self):
        self.timed_out_event.clear()
        self.p = None
        self.queue_process = Queue()

    def on_parameter_received(self, parameter):
        self.adapter.debug('Got parameter %s', parameter)

        if self.is_process_alive() and self.options['can_discard']:
            self.adapter.debug('Process already running, can discard')
            return

        if self.is_process_alive() and self.options['stop_previous_process']:
            self.adapter.debug('Stop previous process')
            self.terminate_process()

        if not self.is_process_alive():
            self.adapter.info('### START PROCESS ###')
            self.run_process(self.cmd_template, parameter)

    def on_process_queue_item_received(self, item):
        exit_status, output = item

        if exit_status is None:
            # process produced output and is still running
            self.adapter.info('%s', output.strip())
        else:
            if exit_status == 0:
                self.adapter.info('### END PROCESS - exit status %s ###', success(exit_status))
            else:
                self.adapter.info('### END PROCESS - exit status %s ###', error(exit_status))

            self.p = None

    def _normalize_cmd_substitution_token(self, cmd_template):
        '''Normalize the token to {}. cmd can hold '{}' or "{}" or {}'''
        return re.sub('\'\{\}\'|"\{\}"', '{}', cmd_template)

    def run_process(self, cmd_template, parameter):
        '''Run the command after replacing every occurrence
        of {} with `parameter`'''
        cmd_line = cmd_template.replace('{}', parameter)
        self.adapter.debug('Command line is %s', cmd_line)
        self.p = Process(target=run_command_with_queue, args=(
            cmd_line,
            self.options['timeout'],
            self.queue_process,
            self.timed_out_event
        ))
        self.p.start()
        # run_command_with_queue(cmd_line, self.queue_process)


def _make_callback_on_process_line_read(queue):
    return lambda exit_status, line: queue.put((exit_status, line))


def run_command_with_queue(cmd, timeout, queue, timed_out_event):
    '''Run `cmd` in a shell, put every line it outputs in the queue
    one line at a time.

    Each item put in the queue is a tuple (exit status (or None), cmd, line)

    @param string cmd the command to run
    @param int timeout max time to complete the process. If the timeout expires
               the process is killed and timed_out_event is set
    @param subprocess.Queue queue the queue where to put the data
    @param multiprocessing.Event timed_out_event event set if the process times out
    '''
    p = fs_radar.shell_process.popen_shell_command(cmd)
    callback = _make_callback_on_process_line_read(queue)
    try:
        fs_radar.shell_process.consume_output_line_by_line(p, callback, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out_event.set()
