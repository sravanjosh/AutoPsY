from threading import Thread
import datetime
import time

from lib.core.autopsy_globals import autopsy_logger

__author__ = 'joshisk'


class SSHbgCommandHandler(Thread):
    """ Command handler for long running commands (e.g., polling a file for changes using tail -f)
    to execute them in a thread
    """
    def __init__(self, sshHandle, command, fileName=None, timeout=0, name=None, input_data=None):
        """
        :param sshHandle: SSH Handle
        :param command: Command to execute
        :param timeout: Timeout to wait for the command to complete, 0 forever till cancel explicitly
        :return:
        """
        Thread.__init__(self)
        self.name = name
        self.sshHandle = sshHandle
        self.command = command
        self.timeout = timeout
        self.input_data = input_data
        self.fileName = fileName
        self.file = None
        self.is_stop = False
        self.output = ''
        self.incremental_output = ''
        self.transport = None
        self.bufsize = 65536

    def __del__(self):
        if self.file is not None:
            self.file.close()

    def run(self):
        """
        Run a command with optional input data.

        Here is an example that shows how to run commands with no input:

            ssh = MySSH()
            ssh.connect('host', 'user', 'password')
            status, output = ssh.run('uname -a')
            status, output = ssh.run('uptime')

        Here is an example that shows how to run commands that require input:

            ssh = MySSH()
            ssh.connect('host', 'user', 'password')
            status, output = ssh.run('sudo uname -a', '<sudo-password>')

        @param cmd         The command to run.
        @param input_data  The input data (default is None).
        @param timeout     The timeout in seconds (default is 10 seconds).
        @returns The status and the output (stdout and stderr combined).
        """

        if not self.sshHandle.isConnected():
            self.sshHandle.connect()
        autopsy_logger.info('running command: ({0}) {1}'.format(self.timeout, self.command))
        self.transport = self.sshHandle.handle.get_transport()

        if self.transport is None:
            autopsy_logger.info('no connection to host')
            return -1, 'ERROR: connection not established\n'

        # Fix the input data.
        input_data = self._run_fix_input_data(self.input_data)

        autopsy_logger.info("Creating file: " + self.fileName)

        self.file = open(self.fileName, 'a+')
        # Initialize the session.
        autopsy_logger.info('initializing the session')

        session = self.transport.open_session()
        session.set_combine_stderr(True)
        session.get_pty()
        session.exec_command(self.command)

        self._run_poll(session, self.timeout, input_data)
        status = session.recv_exit_status()
        autopsy_logger.info('output size %d' % (len(self.output)))
        autopsy_logger.info('status %d' % (status))
        return status, self.output

    def _run_fix_input_data(self, input_data):
        """
        Fix the input data supplied by the user for a command.

        @param input_data  The input data (default is None).
        @returns the fixed input data.
        """
        if input_data is not None:
            if len(input_data) > 0:
                if '\\n' in input_data:
                    # Convert \n in the input into new lines.
                    lines = input_data.split('\\n')
                    input_data = '\n'.join(lines)
            return input_data.split('\n')
        return []

    def _run_send_input(self, session, stdin, input_data):
        """
        Send the input data.

        @param session     The session.
        @param stdin       The stdin stream for the session.
        @param input_data  The input data (default is None).
        """
        if input_data is not None:
            autopsy_logger.info('session.exit_status_ready() {0}'.format(str(session.exit_status_ready())))
            autopsy_logger.info('stdin.channel.closed {0}'.format(str(stdin.channel.closed)))
            if stdin.channel.closed is False:
                autopsy_logger.info('sending input data')
                stdin.write(input_data)

    def _run_poll(self, session, timeout, input_data):
        """
        Poll until the command completes.

        @param session     The session.
        @param timeout     The timeout in seconds.
        @param input_data  The input data.
        @returns the output
        """
        interval = 0.1
        maxseconds = timeout
        maxcount = maxseconds / interval

        # Poll until completion or timeout
        # Note that we cannot directly use the stdout file descriptor
        # because it stalls at 64K bytes (65536).
        input_idx = 0
        timeout_flag = False
        autopsy_logger.debug('polling (%d, %d)' % (maxseconds, maxcount))
        start = datetime.datetime.now()
        start_secs = time.mktime(start.timetuple())
        # output = ''
        session.setblocking(0)
        while True and not self.is_stop:
            if session.recv_ready():
                data = session.recv(self.bufsize)
                self.output += data
                self.incremental_output += data
                autopsy_logger.debug(data)
                self.file.write(data)
                self.file.flush()
                autopsy_logger.debug('read %d bytes, total %d' % (len(data), len(self.output)))

                if session.send_ready():
                    # We received a potential prompt.
                    # In the future this could be made to work more like
                    # pexpect with pattern matching.
                    if input_idx < len(input_data):
                        data = input_data[input_idx] + '\n'
                        input_idx += 1
                        autopsy_logger.info('sending input data {0}'.format(len(data)))
                        session.send(data)

            autopsy_logger.debug('session.exit_status_ready() = {0}'.format(str(session.exit_status_ready())))
            if session.exit_status_ready():
                break
            if timeout != 0:
                # Timeout check
                now = datetime.datetime.now()
                now_secs = time.mktime(now.timetuple())
                et_secs = now_secs - start_secs
                autopsy_logger.debug('timeout check %d %d' % (et_secs, maxseconds))
                if et_secs > maxseconds:
                    autopsy_logger.info('polling finished - timeout')
                    timeout_flag = True
                    break

        autopsy_logger.info('polling loop ended')
        if session.recv_ready():
            data = session.recv(self.bufsize)
            self.output += data
            self.incremental_output += data
            autopsy_logger.info('read %d bytes, total %d' % (len(data), len(self.output)))

        autopsy_logger.info('polling finished - %d output bytes' % (len(self.output)))
        if timeout_flag:
            autopsy_logger.info('appending timeout message')
            session.close()

    def stop(self):
        self.is_stop = True

    def prune(self):
        """
        Clear incremental output
        """
        self.incremental_output = ''