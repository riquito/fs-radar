import os
import pty
import select
import subprocess


def popen_shell_command(cmd, merge_stderr=True):
    '''Spawn a process to run `cmd`

    @param string cmd the command to run
    @param bool merge_stderr whether to read from stderr too (default True)
    @return object a Popen instance
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
        stderr=subprocess.STDOUT if merge_stderr else None,
        start_new_session=True
    )
    os.close(slave)  # no need to have slave open on master's process

    return p


def consume_output_line_by_line(p, callback, encoding='utf-8'):
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
    @param encoding the encoding of the running shell
    @return None
    '''

    while True:
        data = ''
        r, w, x = select.select([p.stdout], [], [], 10)
        if r:
            data = r[0].readline()
            if data:
                callback(None, data.decode(encoding).rstrip())

        if not data and p.returncode is not None:
            # Terminate when we've read all the output and the returncode is set
            break

        p.poll()  # updates returncode so we can exit the loop

    callback(p.returncode, '')
