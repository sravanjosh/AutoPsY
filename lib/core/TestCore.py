import inspect
import os
import subprocess
import time

import re
from numpy import random

from lib.core import autopsy_globals
from lib.core.autopsy_globals import autopsy_logger
from termcolor import colored

__author__ = 'joshisk'


def autopsytest(*tags):
    """
    Decorator function to add a ClassName=True in the test case
    so that it can be controlled with --run-tests variable in autopsyauto
    which is a requirement from NOSE

    :param tags: Pass one or more number of tags to control the test selection with run-tags
    :return:
    """
    # Following code is good to have. But commenting it out as, if we change the name of the class
    #   autopsyskip decorator may give problem if this function and autopsyskip are called in reverse order

    # classname = oldclass.__name__
    # if "test" not in classname.lower():
    #     oldclass.__name__ = "Test" + classname

    if tags and len(tags) == 1 and inspect.isclass(tags[0]):
        tags = tags[0]
        if autopsy_globals.autopsy_run_tags and "untagged" not in autopsy_globals.autopsy_run_tags:
            oldclass = autopsyskip(tags)
        else:
            oldclass = tags

        setattr(oldclass, oldclass.__name__, True)

        return oldclass
    else:
        if len(tags) == 1:
            tags = re.split(r'[;,\s]\s*', tags[0])

        def decorate(oldclass):

            setattr(oldclass, oldclass.__name__, True)

            if not autopsy_globals.autopsy_run_tags:
                return oldclass
            if not tags and "untagged" in autopsy_globals.autopsy_run_tags:
                return oldclass
            if tags and "always" in tags:
                return oldclass

            found = False
            for tag in autopsy_globals.autopsy_run_tags:
                if tag in tags:
                    found = True

            if not found:
                oldclass = autopsyskip(oldclass)

            return oldclass

        return decorate


def autopsySkipIf(*args):
    """
    Decorator function to skip if the condition is True
    Example:
            @autopsySkipIf(something < 4, "Some thing is < 4")
    :param args: condition, description
    :return:
    """
    if args and len(args) == 1 and inspect.isclass(args[0]):
        return autopsyskip(args[0])
    elif len(args) == 1:
        def decorate(oldclass):
            if args[0]:
                autopsy_logger.info("Skipping '{0}' as {1}".format(oldclass.__name__, args[1] if len(args) > 1 and args[
                    1] else "Skip Condition met"),
                                    fg_color=autopsy_logger.MAGENTA)
                return autopsyskip(oldclass)
            return oldclass

        return decorate


def autopsySkipUnless(*args):
    """
    Decorator function to skip if the condition is False
    Example:
            @autopsySkipUnless(something < 4, "Some thing is >= 4")
    :param args: condition, description
    :return:
    """
    if args and len(args) == 1 and inspect.isclass(args[0]):
        return autopsyskip(args[0])
    elif len(args) >= 1:
        def decorate(oldclass):
            if not args[0]:
                autopsy_logger.info("Skipping '{0}' as {1}".format(oldclass.__name__, args[1] if len(args) > 1 and args[
                    1] else "Skip Condition met"),
                                    fg_color=autopsy_logger.MAGENTA)
                return autopsyskip(oldclass)
            return oldclass

        return decorate


def autopsyskip(oldclass):
    """
    Decorator function to skip the testcase always.
    You can use this decorator if you are willing to skip
    the test cases as they are not yet finished or not to be
    tested because of some dev limitation
    :param oldclass: autopsy Test
    :return:
    """
    # Nose always look for the class name
    #   having "test" (case in sensitive) in it. So setting the
    #   class name to some dummy name, so that nose ignores it
    oldclass.__name__ = 'dummy'
    oldclass.__unittest_skip__ = True
    oldclass.__unittest_skip_why__ = "Skipped By User"
    return oldclass


class Step:
    """ Each test step can be recorded with this STEP object
    """

    def __init__(self):
        self.stepnum = len(autopsy_globals.test_steps) + 1
        self.stepdescr = ''
        self.stepstatus = 'PASSED'
        self.starttime = time.time()
        self.finishtime = None

    def __str__(self):
        if self.stepstatus is None or \
                        str.strip(str(self.stepstatus)) == '':
            return "{time:.3f} STEP {stepnum}: {stepdescr}" \
                .format(stepnum=self.stepnum, stepdescr=self.stepdescr,
                        time=self.finishtime - autopsy_globals.current_test.starttime)

        return "{time:.3f} STEP {stepnum}: {stepdescr} - {stepstatus}". \
            format(stepnum=self.stepnum, stepdescr=self.stepdescr, stepstatus=self.stepstatus,
                   time=self.finishtime - autopsy_globals.current_test.starttime)

    def setStatus(self, status):
        self.finishtime = time.time()
        self.stepstatus = status


def startTest(testcase):
    autopsy_globals.current_test = testcase
    autopsy_globals.test_steps = []
    autopsy_globals.test_fail_reason = ''


def step(descr):
    step = Step()
    # step.stepnum = len(autopsy_globals.test_steps) + 1
    step.stepdescr = descr
    step.stepstatus = ''


def fail(fail_msg=None, descr='', cont=False, run_before_fail=None):
    check(False, fail_msg=fail_msg, descr=descr, cont=cont, run_on_fail=run_before_fail)


def archive_file_dir(file_dir):
    process = subprocess.Popen(["gzip", "-r", file_dir])
    process.communicate()


def verify_checks(fail_msg="Some test steps failed"):
    steps = autopsy_globals.test_steps

    for step in steps:
        if step.stepstatus != "PASSED":
            fail(descr="Verify all steps passed",
                 fail_msg=fail_msg)


def check(condition, fail_msg=None, pass_msg=None,
          descr='', cont=False, run_on_fail=None):
    """

    :param run_on_fail:
    :param condition: Some condition to evaluate to TRUE or FALSE
    :param fail_msg:
    :param pass_msg:
    :param descr:
    :param cont: Not to assert and continue with remaining even on failure,
                run_on_fail will not be called
    :return:
    """
    step = Step()
    # step.stepnum = len(autopsy_globals.test_steps) + 1
    step.stepdescr = descr
    if condition:
        step.setStatus('PASSED')
        if pass_msg is not None:
            # autopsy_logger.info("PASSED: " + pass_msg)
            if str.strip(str(descr)) == '':
                step.stepdescr = pass_msg
            else:
                step.stepdescr += " ({0})".format(pass_msg)

        if str.strip(str(step.stepdescr)) != '':
            autopsy_globals.test_steps.append(step)
            autopsy_logger.info(colored("STEP {0}: {1} - "
                                        .format(step.stepnum, step.stepdescr),
                                        color="magenta", attrs=["bold"]) +
                                colored(step.stepstatus, color="green", on_color=None, attrs=["bold", "dark"]))
    else:
        step.setStatus('FAILED')

        if fail_msg is not None:
            autopsy_logger.error(colored("FAILED: " + fail_msg))
            if str.strip(str(descr)) == '':
                step.stepdescr = fail_msg
        else:
            if str.strip(str(descr)) != '':
                fail_msg = descr + " is FAILED"
            else:
                fail_msg = "Test Step Failed"

        if str.strip(str(step.stepdescr)) != '':
            autopsy_globals.test_steps.append(step)
            autopsy_logger.info(colored("STEP {0}: {1} - "
                                        .format(step.stepnum, step.stepdescr),
                                        color="magenta", attrs=["bold"]) +
                                colored(step.stepstatus, color="red", on_color=None, attrs=["bold", "dark"]))

        if len(autopsy_globals.test_fail_reason) > 0:
            autopsy_globals.test_fail_reason += '\n'

        autopsy_globals.test_fail_reason += fail_msg if len(fail_msg) < 80 else fail_msg[:70] + '...'
        if not cont:
            if run_on_fail is not None:
                if type(run_on_fail) is list:
                    for func in run_on_fail:
                        func()
                else:
                    run_on_fail()

            assert False, fail_msg
        else:
            # if run_on_fail is not None:
            #     autopsy_logger.warning("Run-On-Fail will not be called when cont is True")
            pass


def is_pause_on_fail():
    if os.path.isfile(autopsy_globals.autopsy_loc_file_loc + "/pause_on_fail." + autopsy_globals.autopsy_testbed.tbname):
        return True

    return False


def is_pause_test_run():
    if os.path.isfile(autopsy_globals.autopsy_loc_file_loc + "/pause." + autopsy_globals.autopsy_testbed.tbname):
        return True

    return False


def unpause_on_fail():
    try:
        os.remove(autopsy_globals.autopsy_loc_file_loc + "/pause_on_fail." + autopsy_globals.autopsy_testbed.tbname)
    except OSError as e:
        pass


def unpause_test_run():
    try:
        os.remove(autopsy_globals.autopsy_loc_file_loc + "/pause." + autopsy_globals.autopsy_testbed.tbname)
    except OSError as e:
        pass


def pause_on_fail():
    with open(autopsy_globals.autopsy_loc_file_loc + "/pause_on_fail." + autopsy_globals.autopsy_testbed.tbname, "w") as f:
        f.write("pause_on_fail - " + autopsy_globals.autopsy_testbed.tbname)


def pause_test_run():
    with open(autopsy_globals.autopsy_loc_file_loc + "/pause." + autopsy_globals.autopsy_testbed.tbname, "w") as f:
        f.write("pause before next test start - " + autopsy_globals.autopsy_testbed.tbname)


class TestHook:
    """ TestHook to be created that can be hooked to a handler
    e.g.,
    TestHookHandler.addTestHook(TestHookHandler.ON_START_TEST, TestHook(print, ["Hello"]))
    """
    def __init__(self, func, args=None, tag=None):
        self.func = func
        if type(args) is list:
            self.args = args
        else:
            self.args = [args]

        # Tag can be used to identify the testhook for later point of time.
        # Create a random name on None/Empty
        if tag:
            self.tag = tag
        else:
            self.tag = "TestHook-" + str(random.randint(1000, 9999))

    def exec_hook(self):
        if self.args:
            return self.func(*self.args)
        else:
            return self.func()


class TestHookHandler:
    ON_START_TEST_SUITE = 0
    ON_START_TEST_CLASS = 1
    ON_START_TEST = 2
    ON_END_TEST_SUITE = 3
    ON_END_TEST_CLASS = 4
    ON_END_TEST = 5

    def __init__(self):
        pass

    @staticmethod
    def addTestHook(testHookStage, testHook):
        if not isinstance(testHook, TestHook):
            raise ValueError("testHook should be of Instance TestHook")

        if testHookStage in autopsy_globals.autopsy_test_hooks.keys():
            autopsy_globals.autopsy_test_hooks[testHookStage].append(testHook)
        else:
            autopsy_globals.autopsy_test_hooks[testHookStage] = [testHook]

    @staticmethod
    def delTestHook(testHookStage, testHookTag):
        if testHookStage in autopsy_globals.autopsy_test_hooks.keys():
            for testHook in autopsy_globals.autopsy_test_hooks[testHookStage]:
                if testHook.tag == testHookTag:
                    autopsy_globals.autopsy_test_hooks[testHookStage].remove(testHook)
