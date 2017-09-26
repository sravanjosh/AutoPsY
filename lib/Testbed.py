import json
import os
import threading

from lib.RemoteNode import RemoteNode
from lib.commons.Utilities import progressBar
from lib.core import autopsy_globals
from lib.core.autopsy_globals import autopsy_logger

__author__ = 'joshisk'


class TestbedNotFoundException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class Testbed:
    def __init__(self, tbContent):
        self.tbname = None
        self.tbFileName = None
        self.userid = None
        self.tenantid = None
        self.emailid = None
        self.host = None

        self.no_download_logs = False
        self.__im1_lock = threading.RLock()

        autopsy_logger.info("Building testbed")
        if type(tbContent) is dict:
            self.parse_json(tbContent)
            self.tbFileName = self.tbname
        elif type(tbContent) is str:
            self.tbFileName = os.path.basename(tbContent)
            try:
                tbfile = open(tbContent)
            except IOError as e:
                autopsy_logger.critical("Testbed file doesn't exist: {0}".format(tbContent))
                raise TestbedNotFoundException("Testbed file doesn't exist: {0}".format(tbContent))
            try:
                self.parse_json(json.loads((tbfile.read())))
            except ValueError as e:
                autopsy_logger.critical("Testbed JSON file is not well formatted. Please check and try again")
                raise e

                # self.createDeviceLogDir()

    def createDeviceLogDir(self):
        try:
            os.makedirs(autopsy_globals.autopsy_logloc + "/" + self.tbname + "/")
        except OSError as e:
            if "File exists" in e.message:
                autopsy_globals.autopsy_logger.debug("Dir already exists, continuing..")
            else:
                autopsy_globals.autopsy_logger.critical("Error creating directory: " + e.message)

    def openConnections(self):
        if not autopsy_globals.autopsy_quick_run:
            if self.host:
                map(lambda node: node.connect() if node else "", self.host)

        return True

    def parse_json(self, json_dict):
        hosts = json_dict['host'] if 'host' in json_dict else []

        self.tbname = json_dict['tbname'] if 'tbname' in json_dict else "My_Testbed"
        self.host = []

        for l_host in hosts:
            self.host.append(RemoteNode(hostname=l_host['name'],
                                        ipAddress=l_host['ip'],
                                        pkeyFile=l_host['key'] if 'key' in l_host else None,
                                        username=l_host['username'] if 'username' in l_host else 'ubuntu',
                                        password=l_host['password'] if 'password' in l_host else None,
                                        alias=l_host['alias'],
                                        ssh_port=int(l_host['ssh_port'] if 'ssh_port' in l_host else 22)))

    def __del__(self):
        if autopsy_globals is None:
            return
        self.close_connections(quick=autopsy_globals.autopsy_quick_run)

    def close_connections(self, quick=False):
        autopsy_logger.debug("Closing all connections of testbed")

        if not (quick or self.no_download_logs):
            autopsy_logger.info("Downloading all logs, please wait....")

            progressBar(0, 1)
            if self.host:
                map(lambda node: node.download_all_logs(autopsy_globals.autopsy_logfile), self.host)
            progressBar(1, 1)

        if self.host:
            map(lambda node: node.disconnect() if node else "", self.host)
