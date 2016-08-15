from time import time
import os
import pty
import select
import subprocess


def popen_shell_command(cmd, merge_stderr=True, bash_profile=None):
    '''Spawn a process to run `cmd`

    @param string cmd the command to run
    @param bool merge_stderr whether to read from stderr too (default True)
    @return object a Popen instance
    '''

    bash_profile_opts = []
    if bash_profile is True:
        bash_profile_opts = ['-l']
    elif isinstance(bash_profile, str):
        bash_profile_opts = ['--init-file', bash_profile]

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
    args = ['/usr/bin/env', 'bash', *bash_profile_opts, '-i', '-c', cmd]
    p = subprocess.Popen(
        args,
        stdin=slave,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else None,
        start_new_session=True
    )

    p.start_time = time()

    os.close(slave)  # no need to have slave open on master's process

    return p


def consume_output_line_by_line(p, callback, timeout=None, encoding='utf-8'):
    '''
    Read a process' output.
    Every time a line is read call `callback` with two arguments,
    the current exit status code and the read line.
    As long as the process is running the exit status code is None and
    the line is non-empty. When the process terminates `callback` will be
    called one last time with the exit status code and an empty-string.

    @param string cmd the command to run
    @param func callback the function to run on each line read. It will receive
                two arguments, the exit status code (or None) and the line read
    @param int timeout max time to complete the process. If the timeout expires
               the process is killed and subprocess.TimeoutExpired is raised
    @param encoding the encoding of the running shell
    @return None
    '''

    start_time = p.start_time or time()

    while True:
        data = ''
        r, w, x = select.select([p.stdout], [], [], 1)
        if r:
            data = r[0].readline()
            if data:
                callback(None, data.decode(encoding).rstrip())

        time_left = timeout is not None and max(0, start_time + timeout - time())

        if not data and p.returncode is not None:
            # Terminate when we've read all the output and the returncode is set
            break
        elif timeout is not None and time_left == 0:
            _stop_process(p)
            raise subprocess.TimeoutExpired(p.args, timeout)

        p.poll()  # updates returncode so we can exit the loop

    callback(p.returncode, '')


def _stop_process(p):
    try:
        # give the process a chance to exit cleanly
        p.terminate()
        p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        p.kill()
