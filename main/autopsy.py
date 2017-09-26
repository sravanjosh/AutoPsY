#!/usr/bin/python

""" Automation Framework to run tests

    usage: autopsy.py [-h] --test-bed TEST_BED --log-file LOG_FILE --test-suite
                        TEST_SUITE [--run-tests RUN_TEST[,RUN_TEST,RUN_TEST]]
                        [--skip-tests SKIP_TEST[,SKIP_TEST,SKIP_TEST]] [-d]
"""

import os
import parser
import pdb
import re
import signal
import sys

import datetime
# Make sure these two lines are always present before using any framework library
import pwd

os.chdir(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, '..')

from lib.commons.autopsylogging import AutopsyLogger
from lib.core import autopsy_globals
from lib.core.autopsy_globals import autopsy_logger, TestCase, add_GA, allJobsRunning
from lib.core.autopsy_plugin import AutopsyPlugin
from lib.core.AutopsyCollectOnlyPlugin import AutopsyCollectOnlyPlugin
from lib.Testbed import Testbed
from lib.core.TestCore import unpause_on_fail, unpause_test_run
from lib.core.TestCore import archive_file_dir
from lib.commons.Utilities import visual_sleep
import nose
from argparse import ArgumentParser
import logging
import getpass
from random import choice

__author__ = 'joshisk'

sys.excepthook = sys.__excepthook__


def normalize_tb_name(name):
    name = name.replace(" ", "_")
    if name.find(".") != -1:
        name = name[0:name.find(".")]

    return name


def unlockTestbed(name):

    name = normalize_tb_name(name)

    try:
        autopsy_globals.autopsy_logger.info("Unlocking the testbed: " + name)
        os.remove(autopsy_globals.autopsy_loc_file_loc + "/" + name + ".lock")
        unpause_on_fail()  # Deleting the pause files
        unpause_test_run()
        return True
    except Exception as e:
        autopsy_globals.autopsy_logger.error("Error unlocking the testbed: " + e.message)
        return False


def lockTestbed(name):

    name = normalize_tb_name(name)

    try:
        os.makedirs(autopsy_globals.autopsy_loc_file_loc)
    except:
        pass

    pid = os.getpid()
    fileName = autopsy_globals.autopsy_loc_file_loc + "/" + name + ".lock"
    if os.path.isfile(fileName):
        with open(fileName, mode='r') as fileHandle:
            old_pid = int(fileHandle.readline())

            try:
                os.kill(old_pid, 0)
                autopsy_globals.autopsy_logger.error("Testbed already locked: " + name)
                return False
            except OSError:
                autopsy_globals.autopsy_logger.info("Deleting stale testbed lock: " + name)
                unlockTestbed(name)

    autopsy_globals.autopsy_logger.info("Locking the testbed: " + name)
    with open(fileName, mode='w') as fileHandle:
        fileHandle.write(str(pid))

    return True


def createLogDir(logDir, mail_to):
    curtime = datetime.datetime.now()
    year = curtime.strftime("%Y")
    month = curtime.strftime("%b")
    date = curtime.strftime("%d")

    mail_to = mail_to[0]

    if '@' in mail_to:
        userid = str.split(mail_to, '@')[0]
        logfile = 'test_log_' + userid + '_' + curtime.strftime("%Y-%m-%d:%H:%M:%S")
    else:
        logfile = 'test_log_' + curtime.strftime("%Y-%m-%d:%H:%M:%S")
    os.makedirs(logDir + "/" + year + "/" + month + "/" + date + "/" + logfile)

    return logDir + "/" + year + "/" + month + "/" + date + "/" + logfile


def stripExtension(arg):
    argList = re.split(r'[;,\s]\s*', arg)
    resultArgs = []

    for arg in argList:
        if arg.endswith(".py"):
            resultArgs.append(arg[:-3])
        else:
            resultArgs.append(arg)

    return ",".join(resultArgs)

def exit(status, archive=False):

    if autopsy_globals.autopsy_being_exited:
        # autopsy_logger.critical("Force stopping as per user request")
        if autopsy_globals.autopsy_testbed:
            autopsy_globals.autopsy_testbed.close_connections(True)
            unlockTestbed(autopsy_globals.autopsy_testbed.tbFileName)
        sys.exit(1)

    autopsy_globals.autopsy_being_exited = True

    for testcase in autopsy_globals.test_list:
        if testcase.result == 'InProgress':
            testcase.result = 'Stopped'
        autopsy_globals.dumpTestCaseJsonFile()

    for jobHandler in allJobsRunning:
        while jobHandler.isAlive():
            jobHandler.join(timeout=2)

    if archive:
        if autopsy_globals.autopsy_testbed:
            autopsy_globals.autopsy_testbed.close_connections(quick=args.quick)
        archive_file_dir(archive_location)

    if autopsy_globals.autopsy_testbed:
        unlockTestbed(autopsy_globals.autopsy_testbed.tbFileName)

    sys.exit(status)


def signalHandler(signum, frame):
    if signum == signal.SIGTERM or signum == signal.SIGINT:
        autopsy_logger.info("*************** Terminating as per user request ***************")
        exit(2, archive=True)
    elif signum == signal.SIGUSR1:
        pdb.set_trace()
        return

    exit(1)

if __name__ == '__main__':
    script_loc = os.path.dirname(os.path.realpath(__file__))
    print(' '.join(sys.argv))
    parser = ArgumentParser(description="Start Autopsy Automation run")

    req_group = parser.add_argument_group('Required Arguments')
    req_group.add_argument('--testbed', '--test-bed', help='Testbed to run', type=str, required=True, dest='testbed')
    req_group.add_argument('--testsuite','--test-suite', help='Test suite(s)', type=str, required=True,
                           dest='test_suite')

    opt_group = parser.add_argument_group('Optional Argumets')
    opt_group.add_argument('--mail', '--mailto', '--mail-to', nargs="+", help='Mail Id to send the report to',
                           dest='mail_to', required=False)
    opt_group.add_argument('-d', '--debugger', help='Start in debugger mode',
                           dest='debug', action='store_true', required=False)
    opt_group.add_argument('--run-tests', '--run', nargs="+", help='Tests to be run', type=str,
                           required=False)
    opt_group.add_argument('--run-tags', nargs="+", help='Tests to be run based on tag provided', type=str,
                           required=False)
    opt_group.add_argument('--skip-tests', '--skip', nargs="+", help='Tests to be skipped', type=str,
                           required=False)
    opt_group.add_argument('--repeat', help='Repeat the same test given number of times', type=int,
                           required=False)

    opt_group.add_argument('--rerun-failed', help='Re-run the failed cases again', dest='rerun_failed',
                           required=False, action='store_true')
    opt_group.add_argument('--random', nargs="?", help='Randomize the test cases order', dest='random',
                           required=False, const=1)
    opt_group.add_argument('-v', '--verbose', help='Verbose log', dest='verbose',
                           required=False, action='store_true')
    opt_group.add_argument('-q', '--quick', help='Quick Start', dest='quick',
                           required=False, action='store_true')
    opt_group.add_argument('--reboot', '-r', help='Reboot all DP nodes before test', dest='reboot',
                           required=False, action='store_true')

    # Users can pass in script specific parameters using this argument. This let's the scripts not to hardcode
    #   certain values with some assumption; instead let the users input them with this argument.
    # Scripts can use get_GA and it's flavours to get these values
    opt_group.add_argument('--user-vars', nargs="+", help='User specific variables, in X1 Y1 [X2 Y2 ..] format',
                           dest='user_vars',
                           required=False, type=str)

    parser.set_defaults(debug=False)
    parser.set_defaults(verbose=False)
    parser.set_defaults(quick=False)
    parser.set_defaults(reboot=False)
    parser.set_defaults(queue=False)
    parser.set_defaults(skip_pc=False)
    parser.set_defaults(rerun_failed=False)
    parser.set_defaults(log_file='test_log')
    # parser.set_defaults(exp_node='dataplane')

    args = parser.parse_args()

    try:

        if args.user_vars is not None and len(args.user_vars) > 0:
            if len(args.user_vars) % 2 != 0:
                autopsy_logger.critical("User vars should be of even number of values. It is X1 Y1 [X2 Y2]. "
                                      "Which means X1=Y1, X2=Y2 where X's are variables and Y's are values")
                sys.exit(0)

            i = 0
            while i < len(args.user_vars):
                add_GA(args.user_vars[i], args.user_vars[i+1])
                i += 2

        autopsy_globals.autopsy_quick_run = args.quick

        HOME_DIR = os.getenv('TEST_AUTO_HOME', script_loc + "/../../")
        LOG_DIR = os.getenv('TEST_AUTO_LOG_DIR', HOME_DIR) + "/autologs/"

        if args.mail_to is None or len(args.mail_to) == 0:
            args.mail_to = pwd.getpwuid(os.getuid())[0]

            if args.mail_to is None:
                args.mail_to = ["unknown-user"]
            else:
                args.mail_to = [args.mail_to]

        if len(args.mail_to) == 1:
            args.mail_to = re.split(r'[;,\s]\s*', args.mail_to[0])

        for i in range(len(args.mail_to)):
            if '@' not in args.mail_to[i]:
                args.mail_to[i] += '@gmail.com'

        archive_location = createLogDir(LOG_DIR, args.mail_to)
        autopsy_globals.autopsy_logloc = LOG_DIR
        autopsy_globals.autopsy_logfile = archive_location

        args.test_bed = args.testbed
        args.log_file = 'test_log.log'
        xml_summary_file = 'summary.xml'

        autopsy_globals.autopsy_logger.addFileHandler(filePath=archive_location + "/" + args.log_file)

        if not args.verbose:
            autopsy_globals.autopsy_logger.setLogLevelStderrHandler(loggingLevel=logging.INFO)

        autopsy_globals.autopsy_testbed = Testbed(args.test_bed)

        # Lock the testbed, so that only one run can be run on the testbed
        #   at a time

        autopsy_globals.autopsy_testbed.tbname = normalize_tb_name(autopsy_globals.autopsy_testbed.tbname)

        if not lockTestbed(autopsy_globals.autopsy_testbed.tbFileName):
            autopsy_globals.autopsy_logger.critical("Couldn't lock testbed, exiting...")
            sys.exit(1)

        # TODO: For AUTO UI to show log. But this logic should be replaced
        # if not args.verbose:
        #     autopsy_globals.autopsy_logger.addFileHandler("/tmp/QA-Testbed.log", loggingLevel=logging.INFO)
        # else:
        #     autopsy_globals.autopsy_logger.addFileHandler("/tmp/QA-Testbed.log")

        args.test_suite = stripExtension(args.test_suite)
        list1 = ['src'] + re.split(r'[;,\s]\s*', args.test_suite)

        autopsy_globals.autopsy_test_suites = re.split(r'[;,\s]\s*', args.test_suite)

        if args.skip_tests is not None and len(args.skip_tests) > 0:
            if len(args.skip_tests) == 1:
                args.skip_tests = re.split(r'[;,\s]\s*', args.skip_tests[0])

            for skip_test in args.skip_tests:
                list1 += ['-e', skip_test]

        if args.run_tests is not None and len(args.run_tests) > 0:
            if len(args.run_tests) == 1:
                args.run_tests = re.split(r'[;,\s]\s*', args.run_tests[0])
            for run_test in args.run_tests \
                    + ["TestCrashes", "TestIcaParams"]:
                list1 += ['-a', run_test]

        if args.run_tags is not None and len(args.run_tags) > 0:
            if len(args.run_tags) == 1:
                args.run_tags = re.split(r'[;,\s]\s*', args.run_tags[0])

            autopsy_globals.autopsy_run_tags.extend(args.run_tags)

        list1 += ['--debug-log', archive_location + "/" + args.log_file]
        list2 = list(list1)

        list2.append("--autopsy-collect-only")
        list2.append("--verbose")

        rebootTestCase = None
        testbedInitTestCase = None

        if args.reboot:
            rebootTestCase = TestCase("RebootAllNodes", "NotStarted", "Rebooting all nodes")
            autopsy_globals.test_list.append(rebootTestCase)

        if not args.quick:
            testbedInitTestCase = TestCase("TestbedInit",
                                           "NotStarted", "Initializing/Cleaning the nodes in testbed")
            autopsy_globals.test_list.append(testbedInitTestCase)

        nose.run(addplugins=[AutopsyCollectOnlyPlugin()], argv=list2)

        if args.debug:
            pdb.set_trace()

        signal.signal(signal.SIGUSR1, signalHandler)

        if args.reboot:
            autopsy_logger.info("*** REBOOTING all DP Nodes ***")
            rebootTestCase.result = "InProgress"
            autopsy_globals.dumpTestCaseJsonFile()
            autopsy_globals.autopsy_testbed.reboot_dp_nodes()

            # Waiting for all the processes to start and get settled with CP communication
            visual_sleep(120, "Waiting for all the processes to be up and settled")

            rebootTestCase.result = "Passed"
            autopsy_globals.dumpTestCaseJsonFile()

        if not args.quick:
            testbedInitTestCase.result = "InProgress"
            autopsy_globals.dumpTestCaseJsonFile()
            if not autopsy_globals.autopsy_testbed.openConnections():
                autopsy_logger.critical("Error connecting/logging-in to all necessary nodes..Exiting")
                exit(1)

            testbedInitTestCase.result = "Passed"
            autopsy_globals.dumpTestCaseJsonFile()

        list1 += ['--debug', 'nose.inspector,nose.result,nose.plugins',
                  '--nologcapture', '--nocapture',
                  '--autopsy-summary-log', archive_location,
                  '--autopsy-mailto', ', '.join(args.mail_to),
                  '--with-xunit', '--with-autopsy-auto', '--xunit-file',
                  archive_location + "/" + xml_summary_file]

        if args.random:
            list1.append('--with-randomly')
            list1.append('--randomly-dont-reset-seed')

            random_seed = 0
            if args.random != 1:
                random_seed = args.random
            else:
                random_seed = ''.join([choice('0123456789') for i in range(10)])

            autopsy_logger.info("Randomizing the tests with random seed of {0}".format(random_seed),
                                fg_color=AutopsyLogger.BLUE, bold=True)

            list1.append('--randomly-seed')
            list1.append(random_seed)

        if args.rerun_failed:
            list1.append('--failed')
    except KeyboardInterrupt:
        signalHandler(signal.SIGINT, None)

    # Testrun kick-off
    try:
        repeat = 1
        if args.repeat is not None:
            repeat = args.repeat

        while repeat > 0:
            nose.run(addplugins=[AutopsyPlugin()], argv=list1)

            repeat -= 1
            if repeat > 0:
                autopsy_logger.info("-" * 50)
                autopsy_logger.info("REPEATING THE RUN AS REQUESTED BY THE USER")
                autopsy_logger.info("-" * 50)

    finally:
        signal.signal(signal.SIGINT, signalHandler)
        signal.signal(signal.SIGTERM, signalHandler)

        exit(0, True)
