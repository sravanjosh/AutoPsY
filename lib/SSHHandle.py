#! /usr/bin/python -tt
import os
import socket
import threading
import time

import paramiko
from paramiko.ssh_exception import SSHException

from lib.core import autopsy_globals
from lib.core.autopsy_globals import autopsy_logger

__author__ = 'joshisk'


class SSHError(Exception):
    pass


class SFTPClientExtended:
        def __init__(self, parent):
            self.parent = parent
            self.sftp_client = None

        def __enter__(self):
            self.parent.max_session_lock.acquire()

            if not self.parent.isConnected():
                self.parent.connect()

            self.sftp_client = self.parent.handle.open_sftp()
            return self.sftp_client

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.sftp_client:
                self.sftp_client.close()

            self.parent.max_session_lock.release()


class SSHHandle:
    """ Simple SSHHandle to connect to an SSH server
        and execute commands
    """
    PASSWORD_BASED = 0
    PKEY_BASED = 1
    # Seconds
    EXEC_TIMEOUT = 5 * 60
    SSH_PORT = 22

    def __init__(self, host, user, password=None,
                 pkey_file=None, root_password=None,
                 hostname=None, port=SSH_PORT, max_sessions=7):
        """
        :param host: IP address (or DNSable hostname)
        :param user: Username to login to SSH
        :param password: Password to Login to SSH
        :param pkey_file: Key File to login to SSH for password less
        :param root_password: Root password for Sudo Commands
        :param hostname: Hostname for textual representation of this machine
        :param port: If you want to use non-default SSH Port
        :param max_sessions: Maximum simultaneous sessions to be allowed over this handle
        :return:
        """
        self.host = host
        self.user = user
        self.exit_status_last_command = False
        self.last_executed_command = ""
        self.last_executed_command_inp_values = []
        self.shell_channel = None
        self.connected = False
        self.stderr_last_command = ""
        self.stdout_last_command = ""
        self.hostname = hostname
        self.port = port if port else SSHHandle.SSH_PORT
        self.max_session_lock = threading.Semaphore(max_sessions)
        self.connect_lock = threading.RLock()

        if pkey_file is not None:
            if os.path.exists(pkey_file):
                if not os.path.isfile(pkey_file):
                    pkey_file = None
            else:
                if os.path.exists(autopsy_globals.autopsy_keys_location + "/" + pkey_file):
                    if os.path.isfile(autopsy_globals.autopsy_keys_location + "/" + pkey_file):
                        pkey_file = autopsy_globals.autopsy_keys_location + "/" + pkey_file
                    else:
                        autopsy_logger.critical("No password or couldn't find key file.")
                        pkey_file = None
                else:
                    autopsy_logger.critical("No password or couldn't find key file.")
                    pkey_file = None

        if (password is None or str(password).strip() == '') \
                and (pkey_file is None or str(pkey_file).strip() == ''):
            autopsy_logger.critical("Check you properly set AUTOPSY_KEY_LOCATION environment variable")
            raise SSHError("Both password and private key can't be None/Empty")

        if password is not None:
            self.conn_type = self.PASSWORD_BASED
            self.password = password

        if pkey_file is not None:
            self.conn_type = self.PKEY_BASED
            self.pkey_file = pkey_file
            self.pkey = paramiko.RSAKey.from_private_key_file(self.pkey_file)

        if root_password is not None:
            self.root_password = root_password
        else:
            self.root_password = password

        self.handle = paramiko.SSHClient()

        self.handle.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self, retries=3, timeout=10):
        """ Connect to the SSH server
        :param timeout:
        :param retries:
        :return: Returns nothing
        """
        with self.connect_lock:
            if self.isConnected():
                return

            autopsy_logger.debug("Connecting to host: " + self.host)

            while retries > 0:
                try:
                    self.connected = False

                    if self.conn_type == self.PASSWORD_BASED:
                        self.handle.connect(hostname=self.host, username=self.user,
                                            password=self.password, timeout=timeout, port=self.port)
                    else:
                        self.handle.connect(hostname=self.host, username=self.user,
                                            pkey=self.pkey, timeout=timeout, port=self.port)

                    self.connected = True

                    return
                except paramiko.AuthenticationException as e:
                    autopsy_logger.critical("Authentication failed:" + e.message)
                    self.connected = False
                    raise e
                except (socket.error, SSHException) as e:
                    if retries > 1:
                        autopsy_logger.critical("Error connecting to {0}, retrying...: ".format(self.host) + e.message)
                    elif retries == 1:
                        autopsy_logger.critical("Error connecting to {0}, exiting...: ".format(self.host) + e.message)
                        self.connected = False
                        raise e

                time.sleep(2)
                retries -= 1

    def close_async(self):
        """
        To close async channel of this handle and stop all the async or background processes started using
        execute_async API

        :return:
        """
        if self.shell_channel:
            self.shell_channel.close()
            self.shell_channel = None
            self.max_session_lock.release()

    def execute_async(self, commands, timeout=EXEC_TIMEOUT):
        """
        This API allows to open a shell to the server and execute all the 'commands' to be run in background
         and in parellel

        As there might be multiple commands to be executed in parellel there will not be any
         stdout, stderr channels given to the caller. This API is primarily used to send multiple commands
         to the server to be run in background and not much interested in their output

        You can use close_async API to stop all the processes running in background

        :param commands: List of commands to execute in parellel
        :param timeout: Timeout for each command you execute (Not tested)
        :return:
        """
        if not commands:
            return

        if type(commands) is not list:
            commands = [commands]

        if not self.isConnected():
            # Retrying 10 times, when this host was connected some time back and
            #    now reconnecting because of some problem.
            # Otherwise, if it is first time being connected retry only 2 times as
            #    it doesn't make much sense to waste time.
            # Same is the case with timeout
            self.connect(retries=10 if self.connected else 1,
                         timeout=min(timeout, (60 if self.connected else 10)))

        if not self.shell_channel:
            self.max_session_lock.acquire()
            self.shell_channel = self.handle.invoke_shell()

        for command in commands:
            self.shell_channel.send(command + "& \n")

    def execute(self, command, inputValues=None,
                timeout=EXEC_TIMEOUT, quiet=False, sudo=False):
        """
        :param sudo:
        :param inputValues: List if you need to answer some interactive questions
                        in the command. Pass in the same order they may occur in command output
        :param quiet:
        :param timeout: Timeout if the command is taking long time to return
        :param command: Command to execute in the SSH terminal
                        Connects to SSH if not already connected

                        If you are looking for polling a command output or
                        the command has interactiveness, you can use 'run'
                        proc instead of this.

                        Pass 'inputValues' list if you need to answer some interactive questions
                        in the command. Pass in the same order they may occur in command output

        :return: Returns the output of the command
        """

        with self.max_session_lock:
            if not self.isConnected():
                # Retrying 10 times, when this host was connected some time back and
                #    now reconnecting because of some problem.
                # Otherwise, if it is first time being connected retry only 2 times as
                #    it doesn't make much sense to waste time.
                # Same is the case with timeout
                self.connect(retries=10 if self.connected else 1,
                             timeout=min(timeout, (60 if self.connected else 10)))

            if not inputValues:
                inputValues = []

            if type(inputValues) is not list:
                inputValues = [inputValues]

            if command.startswith("sudo"):
                command = command.replace("sudo ", "")
                sudo = True

            feed_password = False
            if sudo and self.user != "root":
                if "bash " in command:
                    autopsy_logger.critical("Executing sudo commands with bash is not supported")
                    return "Executing sudo commands with bash is not supported"

                # Escape double-quotes if the command is having double quotes in itself
                command = command.replace('"', '\\"')
                command = "sudo -k -S -p '' bash -c \"{0}\"".format(command)
                feed_password = self.root_password is not None and len(self.root_password) > 0

            self.last_executed_command = command
            self.last_executed_command_inp_values = inputValues

            retries = 3
            stdin, stdout, stderr = None, None, None

            while retries > 0:
                try:
                    if not quiet:
                        autopsy_logger.info("Exec Cmd" +
                                            ((" (" + self.hostname + "): ") if self.hostname else ": ") + command, bold=True)
                    else:
                        autopsy_logger.debug("Executing command " +
                                             ((" (" + self.hostname + "): ") if self.hostname else ": ") + command, bold=True)
                    stdin, stdout, stderr = self.handle.exec_command(command=command,
                                                                     timeout=timeout if timeout is not None
                                                                     else self.EXEC_TIMEOUT, get_pty=True)

                    if stdin and stdout and stderr:
                        break
                except (SSHException, socket.timeout, socket.error, EOFError) as e:
                    if retries == 0:
                        autopsy_logger.error("Error executing command even after retries")
                        self.connected = False
                        raise e

                    autopsy_logger.debug("Exception executing command, retrying")

                retries -= 1
                time.sleep(0.1)

            if retries <= 0:
                autopsy_logger.critical("Couldn't execute the command. Probably n/w issue or timeout: " + command)
                self.connected = False
                raise SSHError("Error executing command")

            # Give a bit of time for the prompt to show up.
            # It works even without this sleep. But if we send the password before prompt, it
            #   gets reflected back on to stdout and password is visible
            # Same is the case with any interactive inputs too.
            time.sleep(0.1)

            try:
                if feed_password and stdin:
                    stdin.write(self.root_password + "\n")
            except socket.error:
                pass

            try:
                if inputValues is not None and len(inputValues) > 0 and stdin:
                    for inp in inputValues:
                        # Same as above sleep for root password
                        time.sleep(0.1)
                        if len(inp) == 1 and ord(inp) < 32:
                            # This IF condition means the input is a special character like, Ctrl + '['
                            # But we need to wait a little more time otherwise this command gets executed so fast that
                            #   even the required prompt will be taken off for the previous command to get executed.
                            #
                            #   e.g., dlpause 1, dlclose 1, Ctrl + '[', quit
                            #      In the above commands, dlclose 1 may be skipped as the next command executed fast and
                            #   left the prompt.

                            time.sleep(1)
                            stdin.write(inp)
                        else:
                            autopsy_logger.debug("Inputting ----> : " + inp)
                            stdin.write(inp + "\n")

                        stdin.flush()

            except socket.error:
                autopsy_logger.warning("Command finished before taking all the input values")

            output = stdout.read() if stdout else ""
            error = stderr.read() if stderr else ""
            output = output.strip() if output is not None else ""
            error = error.strip() if error is not None else ""

            self.exit_status_last_command = stdout.channel.recv_exit_status()
            self.stderr_last_command = error
            self.stdout_last_command = output

            if not quiet:
                autopsy_logger.info(output)
            else:
                autopsy_logger.debug(output)

            if self.exit_status_last_command != 0:
                if error:
                    autopsy_logger.info(error)

            return output

    def get_sftp_connection(self):
        return SFTPClientExtended(self)

    def disconnect(self):
        """ Disconnect from SSH server
        :return: Returns nothing
        """
        if not self.isConnected():
            return

        autopsy_logger.info("Disconnecting host: " + self.host)

        self.close_async()
        if self.handle:
            self.handle.close()

    def isConnected(self):
        """
        :return: True if connected to SSH else returns False
        """

        if not self.connected:
            return False

        transport = self.handle.get_transport() if self.handle else None
        if not (transport and transport.is_active()):
            return False

        try:
            transport.send_ignore()
        except EOFError:
            return False

        try:
            self.handle.exec_command('', timeout=5)
        except (SSHException, socket.timeout, socket.error, EOFError):
            return False

        return True
