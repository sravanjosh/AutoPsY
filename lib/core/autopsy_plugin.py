""" Plugin for Autopsy automation framework
which handles auto logging of tests, sending mail..etc
"""

import codecs
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import inspect
import os
import pdb
import sys
import smtplib
import socket
from time import time
import re

from nose.plugins import Plugin
from nose.pyversion import format_exception

from lib.core.autopsy_globals import autopsy_logger
from lib.core import TestCore, autopsy_globals
from lib.core.TestCore import is_pause_test_run, is_pause_on_fail

__author__ = 'joshisk'
# TODO: Need to optimize this plugin a lot. This is made very raw during initial days of this framewok dev


class AutopsyPlugin(Plugin):
    name = 'autopsy-auto'
    score = 3000
    encoding = 'UTF-8'
    currTestDescription = ''

    def __init__(self):
        super(AutopsyPlugin, self).__init__()
        self.total_run_time = 0
        self.mail_subject = ""

    def reindent(self, s, numSpaces):
        s = str(s)
        s = str.split(s, '\n')
        s = [(numSpaces * ' ') + line for line in s]
        s = '\n'.join(s)
        return s

    def _timeTaken(self):
        if hasattr(self, '_timer'):
            taken = time() - self._timer
        else:
            # test died before it ran (probably error in setup())
            # or success/failure added before test started probably
            # due to custom TestResult munging
            taken = 0.0
        return taken

    def sendmail(self, msg):
        if self.mailto is None or self.mailto == '':
            return

        me = "autopsy@gmail.com"
        you = re.split(r'[;,\s]\s*', self.mailto)

        # Create message container - the correct MIME type is multipart/alternative.
        mime = MIMEMultipart('alternative')
        mime['Subject'] = self.mail_subject
        mime['From'] = me
        mime['To'] = self.mailto

        htmlMsg = "<html> <pre> " + msg + "</pre> </html>"
        part1 = MIMEText(msg, 'plain')
        part2 = MIMEText(htmlMsg, 'html')
        mime.attach(part1)
        mime.attach(part2)

        try:
            autopsy_logger.info("Sending mail to: " + self.mailto)
            server = smtplib.SMTP('localhost')
            server.set_debuglevel(0)

            server.sendmail(me, you, mime.as_string())
            server.quit()
        except socket.error as e:
            autopsy_logger.error("Couldn't send mail, check your local SMTP client: " + str(e))

    def sortTestCasesByName(self):
        autopsy_globals.test_list.sort(key=lambda x: x.name)

    def getTestByName(self, name):
        for test in autopsy_globals.test_list:
            if test.name == name:
                return test

        return None

    def options(self, parser, env):
        """Sets additional command line options.
        :param env:
        :param parser:
        """
        Plugin.options(self, parser, env)
        parser.add_option(
            '--autopsy-summary-log', action='store',
            dest='autopsy_summary_file', metavar="FILE",
            default=env.get('AUTOPSY_AUTO_FILE', 'summary.txt'),
            help=(""))
        parser.add_option(
            '--autopsy-mailto', action='store',
            dest='mailto', metavar="FILE",
            default=env.get('AUTOPSY_MAIL_TO', ''),
            help=(""))

    def nice_to_see_time(self,secs):
        secs = int(secs)
        days = secs // (24 * 60 * 60)
        secs %= (24 * 60 * 60)
        hours = secs // (60 * 60)
        secs %= (60 * 60)
        mins = secs // 60
        secs %= 60

        result_str = ''

        if days > 0:
            result_str += str(days) + ' d  '
        if hours > 0:
            result_str += str(hours) + ' h  '
        if mins > 0:
            result_str += str(mins) + ' m  '
        if secs >= 0:
            result_str += str(secs) + ' sec  '

        return result_str

    def report(self, stream):
        self.log_file = codecs.open(self.log_file_name, 'w',
                                    self.encoding, 'replace')

        ipaddr = ''
        try:
            ipaddr = socket.gethostbyname(socket.gethostname())
        except Exception as e:
            autopsy_logger.error(e.message)
        self.report_string1  = "\n                                  AUTOMATION SUMMARY REPORT\n"
        self.report_string1 += "                                  -------------------------\n\n"
        self.report_string1 += "\nLog Loc   : {0}".format(self.archive_loc) + "/"
        self.report_string1 += "\nTestbed   : {0}".format(autopsy_globals.autopsy_testbed.tbname)
        self.report_string1 += "\nRun Time  : {0}".format(self.nice_to_see_time(self.total_run_time))
        self.report_string1 += "\nCmd Line  : {0}".format(str(' '.join(sys.argv)))
        self.report_string1 += "\nExec Host : {0}".format(ipaddr)
        self.report_string1 += "\n"
        self.report_string1 += "\nTotal     : {0}".format(self.stats['total'])
        self.report_string1 += "\nPass      : {0}".format(self.stats['pass'])
        self.report_string1 += "\nFail      : {0}".format(self.stats['fail'])
        self.report_string1 += "\nError     : {0}".format(self.stats['error'])
        self.report_string1 += "\n"
        self.report_string += '\n ' + '-' * 159

        self.mail_subject = 'Automation Report - ({4}) - Total: {0}, Pass: {1}, Fail: {2}, Err: {3}'\
                                .format(self.stats['total'], self.stats['pass'], self.stats['fail'], self.stats['error'],
                                        ", ".join(autopsy_globals.autopsy_test_suites))

        self.report_string = self.report_string1 + self.report_string

        if self.fail_report_string != '':
            self.fail_report_string = '\n\n                     Diagnostics of Failed Tests' \
                                      + '\n                     ---------------------------\n' \
                                      + self.fail_report_string
            self.fail_report_string += '\n------------------------------------------------------------------------------------------------------\n\n'

        if self.err_report_string != '':
            self.err_report_string = '\n                     Diagnostics of Errored Tests' \
                                     + '\n                     ----------------------------\n' \
                                     + self.err_report_string
            self.err_report_string += '\n------------------------------------------------------------------------------------------------------\n\n'

        if self.pass_report_string != '':
            self.pass_report_string = '\n                     Diagnostics of Passed Tests' \
                                      + '\n                     ---------------------------\n' \
                                      + self.pass_report_string
            # self.pass_report_string += '\n------------------------------------------------------------------------------------------------------\n\n'

        self.report_string += self.fail_report_string
        self.report_string += self.err_report_string
        self.report_string += self.pass_report_string

        autopsy_logger.info(self.report_string)
        self.log_file.write(self.report_string)
        self.log_file.close()

        self.sendmail(self.report_string)

    def configure(self, options, config):
        """Configures the xunit plugin.
        :param config:
        :param options:
        """
        Plugin.configure(self, options, config)

        if self.enabled:
            self.stats = {
                'total': 0,
                'pass': 0,
                'fail': 0,
                'error': 0
            }

            self.pass_report_string = ''
            self.fail_report_string = ''
            self.err_report_string = ''

            self.report_string = '\n ' + '-' * 159
            self.report_string += "\n|{:^40}|{:^10}|{:^20}|{:^86}|".format('Test', 'Result', 'RunTime(sec)', 'Reason')
            self.report_string += '\n ' + '-' * 159
        self.config = config
        if self.enabled:
            self.archive_loc = os.path.realpath(options.autopsy_summary_file)
            self.log_file_name = self.archive_loc + "/summary.txt"
            self.mailto = options.mailto

        # self.sortTestCasesByName()
        autopsy_globals.dumpTestCaseJsonFile()

    def beforeTest(self, test):
        """Initializes a timer before starting a test.
        :param test:
        """
        self._timer = time()

    def startContext(self, context):
        if inspect.isclass(context):
            autopsy_logger.info("################################################################",
                                fg_color=autopsy_logger.GREEN)
            autopsy_logger.info('|            Starting Test: ' + context.__name__, fg_color=autopsy_logger.GREEN)
            if context.__doc__ is not None:
                self.currTestDescription = str.strip(str(context.__doc__))
                autopsy_logger.info('|            Description:', fg_color=autopsy_logger.GREEN)
                lines = context.__doc__.split('\n')
                for line in lines:
                    autopsy_logger.info("|                " + line, fg_color=autopsy_logger.GREEN)

            autopsy_logger.info("################################################################",
                                fg_color=autopsy_logger.GREEN)
            if TestCore.TestHookHandler.ON_START_TEST_CLASS in autopsy_globals.autopsy_test_hooks.keys():
                for testHook in autopsy_globals.autopsy_test_hooks[TestCore.TestHookHandler.ON_START_TEST_CLASS]:
                    testHook.exec_hook()
        elif inspect.ismodule(context):
            autopsy_logger.info("Starting Execution of test suite: " + context.__name__)
            if TestCore.TestHookHandler.ON_START_TEST_SUITE in autopsy_globals.autopsy_test_hooks.keys():
                for testHook in autopsy_globals.autopsy_test_hooks[TestCore.TestHookHandler.ON_START_TEST_SUITE]:
                    testHook.exec_hook()

    def dumpTestSteps(self):
        result = ''
        for step in autopsy_globals.test_steps:
            result += str(step) + "\n"

        return result

    def stopContext(self, context):
        if inspect.isclass(context):
            if TestCore.TestHookHandler.ON_END_TEST_CLASS in autopsy_globals.autopsy_test_hooks.keys():
                for testHook in autopsy_globals.autopsy_test_hooks[TestCore.TestHookHandler.ON_END_TEST_CLASS]:
                    testHook.exec_hook()
            autopsy_logger.info("################################################################",
                                fg_color=autopsy_logger.GREEN)
            autopsy_logger.info('|            Finished Test: ' + context.__name__, fg_color=autopsy_logger.GREEN)
            steps = self.dumpTestSteps()
            if str.lstrip(steps) != '':
                lines = steps.split('\n')
                for line in lines:
                    autopsy_logger.info("|                " + line, fg_color=autopsy_logger.GREEN)
            autopsy_logger.info("################################################################",
                                fg_color=autopsy_logger.GREEN)
        elif inspect.ismodule(context):
            if TestCore.TestHookHandler.ON_END_TEST_SUITE in autopsy_globals.autopsy_test_hooks.keys():
                for testHook in autopsy_globals.autopsy_test_hooks[TestCore.TestHookHandler.ON_END_TEST_SUITE]:
                    testHook.exec_hook()
            autopsy_logger.info("Finished Execution of test suite: " + context.__name__)

    def startTest(self, test):
        id = test.id()
        (modulename, classname, testname) = id.split('.')
        self.stats['total'] += 1

        if testname != "test":
            testcase = self.getTestByName(classname + "." + testname)
        else:
            testcase = self.getTestByName(classname)

        testcase.description = self.currTestDescription.replace('\n', '\\n')
        testcase.result = "InProgress"
        autopsy_globals.dumpTestCaseJsonFile()

        TestCore.startTest(testcase)
        # self.log_file.write("Test started: "+id_split(id)[0] + "\n")
        autopsy_logger.info("===========================================")
        autopsy_logger.info("|      Test Started : " + classname + "." + testname)
        autopsy_logger.info("===========================================")

        if TestCore.TestHookHandler.ON_START_TEST in autopsy_globals.autopsy_test_hooks.keys():
            for testHook in autopsy_globals.autopsy_test_hooks[TestCore.TestHookHandler.ON_START_TEST]:
                testHook.exec_hook()

        if is_pause_test_run():
            autopsy_logger.info("Pausing the test run as pause file found")
            pdb.set_trace()

    def stopTest(self, test):
        id = test.id()
        (modulename, classname, testname) = id.split('.')

        if testname != "test":
            testcase = self.getTestByName(classname + "." + testname)
        else:
            testcase = self.getTestByName(classname)

        if TestCore.TestHookHandler.ON_END_TEST in autopsy_globals.autopsy_test_hooks.keys():
            for testHook in autopsy_globals.autopsy_test_hooks[TestCore.TestHookHandler.ON_END_TEST]:
                testHook.exec_hook()

        testcase.description += "\\n" + self.dumpTestSteps().replace('\n', '\\n')
        autopsy_globals.dumpTestCaseJsonFile()

    def _getCapturedStdout(self):
        if self._currentStdout:
            value = self._currentStdout.getvalue()
            if value:
                return value
        return ''

    def _getCapturedStderr(self):
        if self._currentStderr:
            value = self._currentStderr.getvalue()
            if value:
                return value
        return ''

    def addSuccess(self, test, capt=None):
        id = test.id()
        self.stats['pass'] += 1
        (modulename, classname, testname) = id.split('.')
        autopsy_logger.info("===========================================")
        autopsy_logger.info("|      Test Passed : " + classname + "." + testname)
        autopsy_logger.info("===========================================")
        timetaken = self._timeTaken()
        self.total_run_time += timetaken

        if autopsy_globals.test_fail_reason.find("\n") != -1:
            autopsy_globals.test_fail_reason = autopsy_globals.test_fail_reason[0:autopsy_globals.test_fail_reason.find("\n")]\
                .strip()

        self.report_string += "\n|{:<40}|{:^10}|{:^20}|{:<86}|"\
            .format("    " + classname + ("" if testname.strip() == "test" else "." + testname), "PASS", self.nice_to_see_time(timetaken),
                    "   " + autopsy_globals.test_fail_reason.strip())

        self.pass_report_string += '\n' + "#" * 50 + '\n'
        self.pass_report_string += '\nTest Case    : ' + classname + "." + testname
        self.pass_report_string += '\nDescription  : \n' + self.reindent(self.currTestDescription, 5)
        self.pass_report_string += '\nSteps : \n' + self.reindent(self.dumpTestSteps(), 5)

        if "test" == testname:
            testcase = self.getTestByName(classname)
            testcase.result = "Passed"
            autopsy_globals.dumpTestCaseJsonFile()
        else:
            testcase = self.getTestByName(classname + "." + testname)
            testcase.result = "Passed"
            autopsy_globals.dumpTestCaseJsonFile()

    def addFailure(self, test, err, capt=None, tb_info=None):
        id = test.id()
        tb = format_exception(err, self.encoding)
        self.stats['fail'] += 1
        try:
            (modulename, classname, testname) = id.split('.')
        except Exception as e:
            autopsy_logger.error("ID: " + str(id))
            autopsy_logger.error(e.message)
            return

        #     autopsy_logger.error("REASON: " + format_exception(err, self.encoding))
        autopsy_logger.error("===========================================")
        autopsy_logger.error("|      Test Failed : " + classname + "." + testname)
        autopsy_logger.error("===========================================")
        timetaken = self._timeTaken()
        # autopsy_logger.info(timetaken)
        self.total_run_time += timetaken

        if autopsy_globals.test_fail_reason.find("\n") != -1:
            autopsy_globals.test_fail_reason = autopsy_globals.test_fail_reason[0:autopsy_globals.test_fail_reason.find("\n")]\
                .strip()

        self.report_string += "\n|{:<40}|{:^10}|{:^20}|{:<86}|"\
            .format("    " + classname + ("" if testname.strip() == "test" else "." + testname), "FAIL", self.nice_to_see_time(timetaken),
                    "   " + autopsy_globals.test_fail_reason.strip())

        self.fail_report_string += '\n' + "#" * 50 + '\n'
        self.fail_report_string += '\nTest Case    : ' + classname + "." + testname
        self.fail_report_string += '\nDescription  : \n' + self.reindent(self.currTestDescription, 5)
        self.fail_report_string += '\nSteps : \n' + self.reindent(self.dumpTestSteps(), 5)
        self.fail_report_string += '\nFail Reason  : \n' + self.reindent(format_exception(err, self.encoding), 5)

        if "test" == testname:
            testcase = self.getTestByName(classname)
            testcase.result = "Failed"
            autopsy_globals.dumpTestCaseJsonFile()

        else:
            testcase = self.getTestByName(classname + "." + testname)
            testcase.result = "Failed"
            autopsy_globals.dumpTestCaseJsonFile()

        if is_pause_on_fail():
            autopsy_logger.info("Pausing the test run as pause on fail file found")
            pdb.set_trace()

    def addError(self, test, err, capt=None):
        id = test.id()
        self.stats['error'] += 1
        try:
            (modulename, classname, testname) = id.split('.')
        except Exception as e:
            autopsy_logger.error("ID: " + str(id))
            autopsy_logger.error(e.message)
            return

        autopsy_logger.error("REASON: " + format_exception(err, self.encoding))
        autopsy_logger.error("===========================================")
        autopsy_logger.error("|      Test Errored : " + classname + "." + testname)
        autopsy_logger.error("===========================================")
        timetaken = self._timeTaken()
        self.total_run_time += timetaken

        if autopsy_globals.test_fail_reason.find("\n") != -1:
            autopsy_globals.test_fail_reason = autopsy_globals.test_fail_reason[0:autopsy_globals.test_fail_reason.find("\n")]\
                .strip()

        self.report_string += "\n|{:<40}|{:^10}|{:^20}|{:<86}|"\
            .format("    " + classname + ("" if testname.strip() == "test" else "." + testname), "ERROR", self.nice_to_see_time(timetaken),
                    "   " + autopsy_globals.test_fail_reason.strip())

        self.err_report_string += '\n' + "#" * 50 + '\n'
        self.err_report_string += '\nTest Case    : ' + classname + "." + testname
        self.err_report_string += '\nDescription  : \n' + self.reindent(self.currTestDescription, 5)
        self.err_report_string += '\nSteps : \n' + self.reindent(self.dumpTestSteps(), 5)
        self.err_report_string += '\nErr Reason   : \n' + self.reindent(format_exception(err, self.encoding), 5)

        if "test" == testname:
            testcase = self.getTestByName(classname)
            testcase.result = "Errored"
            autopsy_globals.dumpTestCaseJsonFile()
        else:
            testcase = self.getTestByName(classname + "." + testname)
            testcase.result = "Errored"
            autopsy_globals.dumpTestCaseJsonFile()