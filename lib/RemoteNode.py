#! /usr/bin/python -tt
import os
import random
import re
import socket
import stat
import time

from expiringdict import ExpiringDict
from paramiko.ssh_exception import SSHException

from lib.SSHHandle import SSHHandle
from lib.commons import Utilities
from lib.commons.Utilities import waitOnProcCondition, synchronized_block
from lib.commons.tc_netem import generate_tc_cmd
from lib.core.autopsy_globals import autopsy_logger

__author__ = 'joshisk'


def on_active_connection(func):
    """
    Decorator for Node Class methods where the method requires the active connection to be present
    before proceeding
    :param func:
    :return:
    """

    def new_func(self, *args, **kwds):
        self.connect()
        return func(self, *args, **kwds)

    return new_func


def with_sftp_connection(func):
    """
    Decorator
    All RemoteNodes functions which operate on SFTP connection can decorate themselves with this decorator
    First argument after self should be the one taking sftp connection and should start with sftp
    :param func:
    :return:
    """

    def new_func(self, *args, **kwds):
        with self.ssh_client.get_sftp_connection() as sftp:
            return func(self, sftp, *args, **kwds)

    return new_func


class RemoteNode(object):
    """ Linux Node.
    Not tested with any other operating system and I am sure it won't work.
    """

    def __init__(self, hostname, ipAddress,
                 username='ubuntu', password=None, pkeyFile=None, alias=None,
                 ssh_port=SSHHandle.SSH_PORT):

        self.hostname = hostname
        self.ipAddress = ipAddress
        self.exit_status_last_command = 0
        self.password = None
        self.pkeyFile = None

        # To Identify a file in the node is a directory or cache we call isDirectory API.
        # But as this operation is required everytime we create a job as create job api requires this flag
        #   we can have a cached entry instead of getting it from SSH always. And for parallel jobs it fails
        #   as SSH Server may not allow that many parallel connections. And using locks make them not parallel
        self.is_dir_file_cache = ExpiringDict(max_len=30, max_age_seconds=1 * 60)

        # Making sure username is atleast 'ubuntu' as for the cloud machines it is mandatory
        #   to have username else it will not connect

        self.username = username if username is not None else 'ubuntu'

        if alias is None:
            self.alias = hostname
        else:
            self.alias = alias

        if (password is None or str(password).strip() == '') \
                and (pkeyFile is None or str(pkeyFile).strip() == ''):
            autopsy_logger.critical("Both password and private key can't be None/Empty: " + hostname)
            return

        if password is not None:
            self.password = password
            # self.ssh_client = SSHHandle(host=self.ipAddress, user=self.username,
            #                             password=self.password, hostname=self.hostname, port=ssh_port)

        if pkeyFile is not None:
            self.pkeyFile = pkeyFile

        self.ssh_client = SSHHandle(host=self.ipAddress, user=self.username, password=self.password,
                                    pkey_file=self.pkeyFile, hostname=self.hostname, port=ssh_port)

    def __str__(self):
        return "Hostname: " + self.hostname + \
               "\nIP      : " + self.ipAddress + \
               "\nType    : " + self.__class__.__name__

    def connect(self, retries=3):
        if not self.ssh_client.isConnected():
            self.ssh_client.connect(retries=retries)

    def disconnect(self):
        if self.ssh_client:
            self.ssh_client.disconnect()

    def execute_async(self, commands=None, timeout=SSHHandle.EXEC_TIMEOUT):
        """
        This API allows to open a shell to the server and execute all the 'commands' to be run in background
         and in parellel

        As there might be multiple commands to be executed in parellel there will not be any
         stdout, stderr channels given to the caller. This API is primarily used to send multiple commands
         to the server to be run in background and not much interested in their output

        You can use close_async API to stop all the processes running in background

        :param commands: List of commands to execute in parellel
        :param timeout:
        :return:
        """

        self.ssh_client.execute_async(commands, timeout=timeout)

    def close_async(self):
        if self.ssh_client.shell_channel:
            self.ssh_client.close_async()

    def change_ssh_port(self, new_port):
        if new_port:
            self.ssh_client.port = new_port
        else:
            autopsy_logger.debug("Not updating as new_port is empty/None")
            return

        self.ssh_client.disconnect()

    @on_active_connection
    def execute(self, command, input=None, timeout=SSHHandle.EXEC_TIMEOUT, quiet=False, sudo=False):

        if input is None:
            input = []

        try:
            output = self.ssh_client.execute(command, inputValues=input, timeout=timeout,
                                             quiet=quiet, sudo=sudo)
            self.exit_status_last_command = self.ssh_client.exit_status_last_command

            return output.strip()
        except socket.timeout as e:
            autopsy_logger.exception("Timed out executing the command: " + command)
            self.exit_status_last_command = -1
            raise e

    @with_sftp_connection
    def isFileExists(self, sftp, f):
        try:
            sftp.stat(f)
            return True
        except IOError:
            return False

    @with_sftp_connection
    def isDirectory(self, sftp, f, fresh=False):
        """
        :param f: File/Directory to ascertain
        :param fresh: To invalidate any cached entry and get the data fresh
        :return:
        """
        with synchronized_block(self):
            if not fresh:
                if f in self.is_dir_file_cache:
                    return self.is_dir_file_cache[f]

        try:
            s = sftp.stat(f)
            value = stat.S_ISDIR(s.st_mode)
            self.is_dir_file_cache[f] = value
            return value
        except IOError:
            return False

    @with_sftp_connection
    def get_file_size(self, sftp, filename):
        """ Get File size in bytes
        :param filename:
        :return:
        """
        info = sftp.stat(filename)
        return info.st_size

    @with_sftp_connection
    def get_file_m_time(self, sftp, filename):
        """ Get modify time of file, if present in the filesystem
        :param filename:
        :return:
        """
        info = sftp.stat(filename)
        return info.st_mtime

    @with_sftp_connection
    def getFilesInDir(self, sftp, dir, pattern=None):
        """  Get all files in the given directory. Files with matching pattern if not 'None'
        :param dir:
        :param pattern: Pattern is just a substring as of now
        :return: List of files present matching with the given pattern
        """
        output = sftp.listdir(dir + "/")
        if pattern is not None:
            output = [item for item in output if pattern in item]

        return output

    @with_sftp_connection
    def getFileContent(self, sftp, filePath):
        sftpFile = None
        try:
            sftpFile = sftp.file(filePath)
            return sftpFile.read()
        except IOError as e:
            autopsy_logger.warning("Couldn't read file {0}: {1}".format(filePath, e.message))
        finally:
            if sftpFile:
                sftpFile.close()

        return ""

    @with_sftp_connection
    def writeFileContent(self, sftp, filePath, newContent):
        sftpFile = None
        try:
            sftpFile = sftp.file(filePath, mode="w")
            sftpFile.write(newContent)

            return True
        except IOError as e:
            autopsy_logger.warning("Couldn't read file {0}: {1}".format(filePath, e.message))
        finally:
            if sftpFile:
                sftpFile.close()

        return False

    @with_sftp_connection
    def appendFileContent(self, sftp, filePath, newContent):
        sftpFile = None
        try:
            sftpFile = sftp.file(filePath, mode="a")
            sftpFile.write(newContent)

            return True
        except IOError as e:
            autopsy_logger.warning("Couldn't read file {0}: {1}".format(filePath, e.message))
        finally:
            if sftpFile:
                sftpFile.close()

        return False

    @on_active_connection
    def uploadFile(self, localFile, remoteFile):
        if not localFile:
            autopsy_logger.error("LocalFile can't be empty/None")
            return False

        if not os.path.basename(localFile):
            autopsy_logger.error("Directory upload is not supported.")
            return False

        if not remoteFile:
            remoteFile = os.path.basename(localFile)

        with self.ssh_client.get_sftp_connection() as sftp:
            try:
                sftp.put(localFile, remoteFile)
                return True
            except IOError as e:
                autopsy_logger.exception("Couldn't upload file: Local - {0}, Remote - {1}".format(localFile, remoteFile))
                raise e

    @on_active_connection
    def downloadFile(self, remoteFile, localFile):
        if not remoteFile:
            autopsy_logger.error("RemoteFile can't be empty/None.")
            return False

        if not os.path.basename(remoteFile):
            autopsy_logger.error("Directory download is not supported.")
            return False

        if not localFile:
            localFile = os.path.basename(remoteFile)

        with self.ssh_client.get_sftp_connection() as sftp:
            try:
                sftp.get(remoteFile, localFile)
                return True
            except IOError as e:
                autopsy_logger.exception("Couldn't Download file: Local - {0}, "
                                       "Remote - {1}".format(localFile, remoteFile))

    def get_file_checksum(self, filename):
        """
        Get md5 check sum of the file
        :param filename:
        """
        # Escape for any special characters
        filename = "\'" + filename + "\'"
        return self.execute("md5sum " + filename + "  | awk '{print $1}'", timeout=3600, quiet=True)

    def get_pid(self, procSubString, ignore=None):
        if ignore is None:
            ignore = []

        ignore.append("grep")
        ignore_string = "|".join(ignore)

        proc_id = self.execute("ps -eaf | grep '" + procSubString +
                               "' | grep -vP '" + ignore_string + "' | awk '{print $2}'")
        return proc_id.split()

    def fill_root_fs(self):
        fileName = "fill-file-" + str(random.randint(0, 999))

        if self.createFile(filePath="/tmp",
                           fileName=fileName,
                           size=self.getAvailSpaceOfFileSystem("/"),
                           randomData=False):
            return "/tmp/" + fileName

        return None

    def createDir(self, dirPath, dirName, createNonExistingParents=False):
        if not dirName:
            autopsy_logger.error("DirName can't be empty or None")
            return False

        if not dirPath:
            dirPath = "~"

        if createNonExistingParents:
            self.execute("mkdir -p {0}/{1}".format(dirPath, dirName))
        else:
            self.execute("mkdir {0}/{1}".format(dirPath, dirName))

        if self.ssh_client.exit_status_last_command == 0:
            return True

        return False

    def createFile(self, filePath, fileName, size=0, randomData=True, umask="777", append=False):
        """
        Create a file
        :param append: If True, the content will be appended to the existing file. If False, file will be overwritten
         or created
        :param filePath:
        :param fileName:
        :param size: Can be in Bytes or in the format of "1M", "5G" ...etc
        :param randomData: Boolean. To have random data or not in the file created.
        Random data takes a while to create.
        :param umask:
        :return: True/False
        """

        if not fileName:
            autopsy_logger.error("FileName can't be empty or None")
            return False

        if not filePath:
            filePath = "~"

        if size == 0:
            self.execute("touch {0}/{1}".format(filePath, fileName))
            return self.ssh_client.exit_status_last_command == 0

        if randomData:
            inFile = "/dev/urandom"
        else:
            if self.getFileSystemType(filePath + "/") == 'ext4':
                self.execute("fallocate -l {0} {1}".format(size, filePath + "/" + fileName), sudo=True)

                if self.ssh_client.exit_status_last_command != 0:
                    autopsy_logger.error("Error creating file {0}".format(filePath + "/" + fileName))
                    return False

                self.execute("chmod {0} {1}".format(umask, filePath + "/" + fileName),
                             sudo=True, quiet=True)
                return True
            else:
                inFile = "/dev/zero"

        remainder = Utilities.convertToBytes(size)
        value = 2
        bsValues = ["1M", "1K", "1"]

        isFirst = not append

        while remainder > 0 and value >= 0:
            quotient = remainder // (pow(1024, value))
            remainder %= (pow(1024, value))

            if quotient > 0:
                if isFirst:
                    self.execute("dd if={0} bs={3} count={2} > {1}".format(inFile,
                                                                           filePath + "/" + fileName,
                                                                           quotient,
                                                                           bsValues[len(bsValues) - value - 1]),
                                 sudo=True, quiet=True, timeout=3600)
                    if self.ssh_client.exit_status_last_command != 0:
                        autopsy_logger.error(
                            "Error doing dd command for file {0}: Exiting...".format(filePath + "/" + fileName))
                        return False
                    isFirst = False
                else:
                    self.execute("dd if={0} bs={3} count={2} >> {1}".format(inFile,
                                                                            filePath + "/" + fileName,
                                                                            quotient,
                                                                            bsValues[len(bsValues) - value - 1]),
                                 sudo=True, quiet=True, timeout=3600)
                    if self.ssh_client.exit_status_last_command != 0:
                        autopsy_logger.error(
                            "Error doing dd command for file {0}: Exiting...".format(filePath + "/" + fileName))
                        return False
            value -= 1

        return True

    def removeFile(self, file):
        """
        :param file: Removes a file or multiple files matching the pattern
        :return:
        """
        #     self.ssh_client.connect()

        try:
            # Don't escape for special characters as wildcard chars will be ignored
            self.execute("sudo rm -rf " + file)
            if self.ssh_client.exit_status_last_command != 0:
                return False

            return True
        except IOError as e:
            autopsy_logger.exception("Couldn't delete file: " + e.message)

        return False

    def renameFile(self, oldName, newName=None):
        """

        :param newName:
        :param oldName:
        :return:
        """
        #     self.ssh_client.connect()

        if not newName:
            newName = "Random" + random.randint(1111, 9999)

        try:
            self.execute("sudo mv " + oldName + " " + newName)

            if self.ssh_client.exit_status_last_command != 0:
                return False

            return True
        except IOError as e:
            autopsy_logger.exception("Couldn't rename this file: " + e.message)

        return False

    def getIpAddress(self, iface):

        if not iface:
            autopsy_logger.error("Interface name cannot be empty")
            return False

        autopsy_logger.info("Checking ip for interface: " + iface)
        ifcfg = self.execute("sudo ifconfig {0}".format(iface), quiet=True)

        # TODO - We need to make this condition more robust
        if iface in ifcfg:
            ip = re.search(r'inet addr:(\S+)', ifcfg)
            if ip:
                ip_address = ip.group(1)

                return ip_address

        elif iface not in ifcfg:
            autopsy_logger.error("Interface:".format(iface) + " does not exist on this machine")
            return False

        return False

    def download_all_logs(self, local):
        self.downloadFile("/var/log/syslog", local + "/" + self.hostname + "-syslog.log")

    def stop_service(self, serviceName):
        """
        Stops a service
        :param serviceName:

        """
        if not serviceName:
            return False

        autopsy_logger.debug(self.hostname + ":" + "Stopping service: " + serviceName)
        output = self.execute("sudo service {0} stop".format(serviceName), quiet=True)

        if self.ssh_client.exit_status_last_command != 0:
            if "Unknown instance" not in output and "Job has already been stopped" not in output:
                autopsy_logger.error("Error stopping the service")
                return False

        return True

    def start_service(self, serviceName):
        """
        Starts a service
        :param serviceName:

        """
        if not serviceName:
            return False

        autopsy_logger.debug(self.hostname + ":" + "Starting service: " + serviceName)
        output = self.execute("sudo service {0} start".format(serviceName), quiet=True)
        if self.ssh_client.exit_status_last_command != 0:
            if "already running" not in output:
                autopsy_logger.error("Error starting the service \'{0}\'".format(serviceName))
                return False

        return True

    def restart_service(self, serviceName):
        if not serviceName:
            return False
        autopsy_logger.debug(self.hostname + ":" + "Restarting service: " + serviceName)
        output = self.execute("sudo service {0} restart".format(serviceName), quiet=True)
        if self.ssh_client.exit_status_last_command != 0:
            if "already running" not in output:
                autopsy_logger.error("Error restarting the service")
                return False

        return True

    def kill_process(self, procSubString, force=False, signal="9", ignore=None):
        """ Kills a process matching given substring.
            Kills only if the match returns one process (To limit not to kill wrong process by mistake).
            Use force to kill all matching processes. Use this with caution
            Returns True if successful, False otherwise
            :param ignore:
            :param signal:
            :param force:
            :param procSubString:
        """

        if ignore is None:
            ignore = []

        proc_id = self.get_pid(procSubString, ignore=ignore)

        if (not force) and len(proc_id) > 1:
            autopsy_logger.error("Multiple processes detected for string: '" + procSubString +
                               "', can't kill, Use force=True to kill multiple process")
            return False

        if len(proc_id) == 0:
            autopsy_logger.warning("No processes found with string: '" + procSubString + "', just ignoring")
            return False

        self.execute("sudo kill -{0} {1} ".format(signal, str(' '.join(proc_id))))

        if self.ssh_client.exit_status_last_command != 0:
            autopsy_logger.error("Error killing the process")
            return False

        return True

    def reboot(self, timeout=750):

        autopsy_logger.info("Rebooting the device: " + self.hostname)

        self.execute("sudo /sbin/reboot", quiet=True, timeout=timeout)

        if self.ssh_client.exit_status_last_command != 0:
            return False

        # To check if the reboot sequence has been initiated
        waittime = time.time() + 30

        while waittime >= time.time():
            try:
                self.connect(retries=1)
                time.sleep(2)
            except:
                # Sleeping. No point in connecting immediately
                time.sleep(10)
                break

        # Reducing 10 seconds as we already slept for 10 secs in above loop
        waittime = time.time() + timeout - 10

        while waittime >= time.time():
            try:
                self.connect(retries=1)
                return True
            except (socket.error, SSHException) as e:
                autopsy_logger.debug("Device didn't comeup, retry..")
                time.sleep(10)

        return False

    def grep_file(self, filePath, pattern):
        if not filePath.strip():
            autopsy_logger.error("File can't be None/empty")
            return
        if not pattern.strip():
            autopsy_logger.error("Pattern can't be None/empty")
            return

        output = self.execute("grep -P '{0}' {1}".format(pattern, filePath), sudo=True)

        if "No such file or directory" in output:
            autopsy_logger.warning("File {0} doesn't exist".format(filePath))
            return ""

        return output

    def is_interface_up(self, interface):
        if not interface:
            autopsy_logger.error("Interface can't be None/Empty")
            return False

        output = self.execute("sudo ifconfig {0}".format(interface), quiet=True)

        if not output or "Device not found" in output:
            return False

        return True

    # Careful not to use this to shut main physical interface as you can't connect to the machine again
    def interface_down(self, interface):
        if not interface:
            autopsy_logger.error("Interface can't be None/Empty")
            return False

        self.execute("sudo ifconfig {0} down".format(interface), quiet=True)

        if self.ssh_client.exit_status_last_command != 0:
            return False
        else:
            return True

    def interface_up(self, interface):
        if not interface:
            autopsy_logger.error("Interface can't be None/Empty")
            return False

        self.execute("sudo ifconfig {0} up".format(interface), quiet=True)

        if self.ssh_client.exit_status_last_command != 0:
            return False
        else:
            return True

    def flap_interface(self, interface, downtime=10,
                       repeat=1, repeat_gap=20):
        if not interface:
            autopsy_logger.error("Interface can't be None/Empty")
            return False

        for i in range(1, repeat + 1):
            self.execute("sudo ifdown {0};sleep {1}; ifup {0}".format(interface, downtime))

            if i != repeat:
                time.sleep(repeat_gap)

        return True

    def ping(self, host, count=5, interval=2):

        if not host:
            return -1

        output = self.execute("ping -c {count} -i {interval} {host}"
                              .format(count=count, interval=interval, host=host), quiet=True)

        match = re.match(".*,[\s]+([0-9]+)%[\s]+packet[\s]+loss.*", output, flags=re.DOTALL)

        percentLoss = 101
        if match:
            percentLoss = int(match.group(1))

        return 100 - percentLoss

    def wait_for_ping(self, host, percent=80):
        """
        :param host: Host to ping
        :param percent: Wait till the percent of ping success out of 10 pings is atleast this percent
        :return:
        """

        return waitOnProcCondition(self.ping, lambda_func=lambda output: output >= percent, timeout=60,
                                   args=[host, 10])

    def setBwInterface(self, interface, downSpeed, upSpeed, unit="kbit"):
        """
        :param interface:
        :param downSpeed:
        :param upSpeed:
        :param unit: Valid units are "kbps" - Kilo Bytes/s, "mbps" - Mega Bytes/s ,
                                     "kbit" - Kilo Bits/s , "mbit" - Mega Bits/s , "bps" - Bytes/s
        :return:
        """
        if not interface:
            autopsy_logger.error("Interface can't be None/Empty")
            return False

        autopsy_logger.info("Setting (up/down) speed on interface : ({0}/{1}), {2}".format(upSpeed, downSpeed, interface))
        # self.execute("sudo wondershaper {0} {1} {2}".format(interface, downSpeed, upSpeed))
        self.execute("sudo tc qdisc del dev {2} root;"
                     "sudo tc qdisc add dev {2} root handle 1: htb default 99;"
                     "sudo tc class add dev {2} classid 1:99 htb rate {0}{1} ceil {0}{1} burst 1000k;"
                     "sudo tc class add dev {2} classid 1:1 htb rate 10mbit ceil 10mbit burst 1000k;"
                     "sudo tc filter add dev {2} protocol ip parent 1:0 prio 0 u32 match ip sport 22 0xffff flowid 1:1"
                     .format(upSpeed, unit, interface), quiet=True)

        if self.ssh_client.exit_status_last_command != 0:
            autopsy_logger.error("Error setting bw limits, exiting...")
            return False

        return True

    def clearBwInterface(self, interface):
        if not interface:
            autopsy_logger.error("Interface can't be None/Empty")
            return False

        autopsy_logger.info("Clear BW params on interface " + interface)
        self.execute("sudo tc qdisc del dev {0} root".format(interface), quiet=True)

        if self.ssh_client.exit_status_last_command != 0:
            autopsy_logger.error("Error clearing bw limits, exiting...")
            return False

        return True

    def getRamDetails(self):
        out = self.execute("free -m | grep Mem", quiet=True)

        if out:
            out = out.split()
            return {"total": out[1], "used": out[2], "free": out[3]}

        return {}

    def getAvailSpaceOfFileSystem(self, mount_point="/"):
        out = self.execute("df --output=avail {0}| sed 1d".format(mount_point), quiet=True)

        if out:
            out = out.strip()
            try:
                return int(out) * 1024
            except ValueError:
                return -1

        return -1

    def getFlashDetails(self):
        out = self.execute("df -h | grep /dev/sda1", quiet=True)

        if out:
            out = out.split()
            return {"total": out[1], "used": out[2], "free": out[3]}

        return {}

    def simulate_nw_down(self, interface=None):
        """ Node should have iptables to use this
        :return:
        """
        self.clear_ip_tables()

        local_ip = self.ssh_client.handle.get_transport().sock.getsockname()[0]

        self.ssh_client.execute("iptables --insert INPUT  --source {0}/32 --jump ACCEPT".format(local_ip),
                                sudo=True)
        if self.ssh_client.exit_status_last_command != 0:
            autopsy_logger.error("Couldn't simulate nw down, probably 'iptables' cmd not present in this node")
            return False

        self.ssh_client.execute("iptables --append INPUT  --protocol tcp --dport 22 --jump ACCEPT", sudo=True)
        self.ssh_client.execute("iptables --append INPUT  --protocol tcp --sport 1515 --jump ACCEPT", sudo=True)

        self.ssh_client.execute("iptables --insert OUTPUT --destination {0}/32 --jump ACCEPT".format(local_ip),
                                sudo=True)
        self.ssh_client.execute("iptables --append OUTPUT --protocol tcp --sport 22 --jump ACCEPT", sudo=True)
        self.ssh_client.execute("iptables --append OUTPUT --protocol tcp --dport 1515 --jump ACCEPT", sudo=True)

        if interface:
            int_ip = self.getIpAddress(interface)

            self.ssh_client.execute("iptables --append INPUT  --destination {0}/32 --jump DROP".format(int_ip),
                                    sudo=True)
            self.ssh_client.execute("iptables --append OUTPUT --source {0}/32 --jump DROP".format(int_ip), sudo=True)
        else:
            self.ssh_client.execute("iptables --append INPUT  --jump DROP", sudo=True)
            self.ssh_client.execute("iptables --append OUTPUT --jump DROP", sudo=True)

        return True

    def clear_ip_tables(self):
        self.ssh_client.execute("iptables --flush", sudo=True)
        if self.ssh_client.exit_status_last_command != 0:
            autopsy_logger.error("Couldn't clear iptable entries, probably 'iptables' cmd not present in this node")
            return False

        return True

    def adjust_qos_param(self, interface, operation,
                         packet_limit=None, delay_time=None, delay_jitter=None, delay_correlation=None,
                         corrupt_percent=None, corrupt_correlation=None,
                         duplicate_percent=None, duplicate_correlation=None,
                         loss_percent=None, loss_correlation=None,
                         delay_distribution=None,
                         reorder_percent=None, reorder_correlation=None, reorder_gap=None
                         ):
        cmd = generate_tc_cmd(interface, operation,
                              packet_limit=packet_limit, delay_time=delay_time, delay_jitter=delay_jitter,
                              delay_correlation=delay_correlation,
                              corrupt_percent=corrupt_percent, corrupt_correlation=corrupt_correlation,
                              duplicate_percent=duplicate_percent, duplicate_correlation=duplicate_correlation,
                              loss_percent=loss_percent, loss_correlation=loss_correlation,
                              delay_distribution=delay_distribution,
                              reorder_percent=reorder_percent, reorder_correlation=reorder_correlation,
                              reorder_gap=reorder_gap)

        out = self.execute(cmd, sudo=True)

        if self.ssh_client.exit_status_last_command != 0:
            if "File exists" in out and operation.lower() == "add":
                operation = "change"
                cmd = generate_tc_cmd(interface, operation,
                                      packet_limit=packet_limit, delay_time=delay_time, delay_jitter=delay_jitter,
                                      delay_correlation=delay_correlation,
                                      corrupt_percent=corrupt_percent, corrupt_correlation=corrupt_correlation,
                                      duplicate_percent=duplicate_percent, duplicate_correlation=duplicate_correlation,
                                      loss_percent=loss_percent, loss_correlation=loss_correlation,
                                      delay_distribution=delay_distribution,
                                      reorder_percent=reorder_percent, reorder_correlation=reorder_correlation,
                                      reorder_gap=reorder_gap)
                out = self.execute(cmd, sudo=True)
                if self.ssh_client.exit_status_last_command != 0:
                    autopsy_logger.error("Error applying qos parameters on {0}".format(self.hostname))
            elif "No such file" in out and operation.lower() == "change":
                operation = "add"
                cmd = generate_tc_cmd(interface, operation,
                                      packet_limit=packet_limit, delay_time=delay_time, delay_jitter=delay_jitter,
                                      delay_correlation=delay_correlation,
                                      corrupt_percent=corrupt_percent, corrupt_correlation=corrupt_correlation,
                                      duplicate_percent=duplicate_percent, duplicate_correlation=duplicate_correlation,
                                      loss_percent=loss_percent, loss_correlation=loss_correlation,
                                      delay_distribution=delay_distribution,
                                      reorder_percent=reorder_percent, reorder_correlation=reorder_correlation,
                                      reorder_gap=reorder_gap)
                out = self.execute(cmd, sudo=True)
                if self.ssh_client.exit_status_last_command != 0:
                    autopsy_logger.error("Error applying qos parameters on {0}".format(self.hostname))
            elif "Invalid argument" in out and operation.lower() == "del":
                pass
            else:
                autopsy_logger.error("Error applying qos parameters on {0}".format(self.hostname))

    def simulate_wan_characteristics(self, interface, operation, wan_type="good"):
        """
        :param interface: interface of the node
        :param operation: "add", "del", "change"
        :param wan_type: "good", "bad", "worse"
        :return:
        """
        if wan_type.lower() == "good":
            self.adjust_qos_param(interface, operation,
                                  delay_time="20ms", delay_jitter="10ms", delay_correlation="50%")
        elif wan_type.lower() == "bad":
            self.adjust_qos_param(interface, operation,
                                  delay_time="100ms", delay_jitter="50ms", delay_correlation="30%",
                                  loss_percent="2%", reorder_percent="5%")
        elif wan_type.lower() == "worse":
            self.adjust_qos_param(interface, operation,
                                  delay_time="300ms", delay_jitter="100ms", delay_correlation="30%",
                                  loss_percent="5%", corrupt_percent="2%", reorder_percent="15%",
                                  duplicate_percent="1%")

    def getFileSystemType(self, f):
        device = self.execute("df -k {0} | grep -v Filesystem".format(f)).rsplit(' ')[0]
        fileSystemType = self.execute("mount | grep {0}".format(device), sudo=True).rsplit(' ')[4]

        return fileSystemType

    def injectErrorsinfile(self, f):
        fileLocation = f.rsplit('/', 2)[0]
        fileName = f.rsplit('/', 1)[-1]
        mountPoint = self.execute("df -k {0}".format(f))
        mountPoint = mountPoint.rsplit('\n')[1].rsplit(' ')[0]

        if not f:
            autopsy_logger.error("Please Provide a file to inject errors into...")
            return False

        # self.ssh_client.connect()

        if not self.isFileExists(f):
            autopsy_logger.info("Creating file as it doesn't exist on source...")
            self.createFile(filePath=fileLocation, fileName=fileName, size="1G", randomData=True)

        diskSize = self.execute("blockdev --getsz {0}".format(mountPoint), sudo=True)

        autopsy_logger.info("Creating linear device...")

        self.execute("umount {0}".format(fileLocation))

        self.execute("dmsetup create img 0 {0} linear {1} 0".format(diskSize, mountPoint))

        self.execute("dmsetup table img")

        self.execute("mount /dev/mapper/img {0} && cd {0}".format(fileLocation), sudo=True)

        fileDetails = self.execute("hdparm {0}".format(f))

        columns = fileDetails.split(' ')

        autopsy_logger.info("Introducing errors in last 64K of the file")

        self.execute("umount {0}".format(fileLocation), sudo=True)

        beginErrorAt = columns[1].split('\n')[-1]
        beginErrorRange = columns[3].split('\n')[-1]
        endErrorStart = int(columns[2].split('\n')[-1]) + 1
        endErrorRange = int(diskSize) - endErrorStart

        cmd = "echo -e 0 {0} linear {1} 0\n" \
              "{0} {2} error\n{3} {4} linear /dev/sdb1 {3}" \
              " | dmsetup load img".format(beginErrorAt, mountPoint, beginErrorRange, endErrorStart, endErrorRange)

        self.execute(cmd, sudo=True)

        self.execute("dmsetup resume img", sudo=True)
        self.execute("dmsetup load img", sudo=True)

        self.execute("mount /dev/mapper/img {0}".format(fileLocation))

    def get_rx_tx_bytes(self, iface):
        """
        will return the received and transferred bytes on the particular interface
        """
        if not iface:
            autopsy_logger.error("Interface name can not be empty")
            return False
        ifcfg = self.execute("sudo ifconfig {0}".format(iface), quiet=True)

        rx = re.search(r'RX bytes:(\S+)', ifcfg)
        tx = re.search(r'TX bytes:(\S+)', ifcfg)
        if rx and tx:
            rx = rx.group(1)
            tx = tx.group(1)
            return [True, int(rx), int(tx)]
        else:
            autopsy_logger.error("Interface: {0} ".format(iface) + "does not exist on this machine")
            return False

