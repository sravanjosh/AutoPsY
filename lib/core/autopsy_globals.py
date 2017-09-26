""" File to contain all global variable to be
accessible by every module started from autopsy.py
which is a main class
"""

import os
import time

from lib.commons.autopsylogging import AutopsyLogger

__author__ = 'joshisk'

autopsy_logger = AutopsyLogger("Main logger")

autopsy_quick_run = False
autopsy_testbed = None
autopsy_test_suites = []
autopsy_logloc = None
autopsy_logfile = None
autopsy_loc_file_loc = os.getenv('AUTOPSY_AUTO_LOCK_DIR', "/tmp/autolocks/")
autopsy_keys_location = os.getenv("AUTOPSY_KEY_LOCATION", "/home/ubuntu/keys")

# ######
#   INTERNAL USE: Fossa Zone. eNtEr At YoUr OwN rIsK !!!
#
#          Don't proceed further this point unless you are an eager adventurist risking your 'life' being ended
#        up in office OR you are sent to repair the shit caused by earlier so called prime movers.
# ######

autopsy_being_exited = False


def add_GA(var, value):
    if not value:
        raise ValueError("Value can't be empty/None")
    if not var:
        raise ValueError("var can't be empty/None")
    autopsy_user_vars[var] = value


def add_GA_Int(var, value):
    """ Be cautious about value error exception if the value is not integer
    :param value:
    :param var:
    """
    if not value:
        raise ValueError("Value can't be empty/None")
    if not var:
        raise ValueError("var can't be empty/None")
    autopsy_user_vars[var] = int(value)


def add_GA_Float(var, value):
    """ Be cautious about value error exception if the value is not integer
    :param value:
    :param var:
    """
    if not value:
        raise ValueError("Value can't be empty/None")
    if not var:
        raise ValueError("var can't be empty/None")
    autopsy_user_vars[var] = float(value)


def add_GA_Bool(var, value):
    """ Be cautious about value error exception if the value is not integer
    :param value:
    :param var:
    """
    if not value:
        raise ValueError("Value can't be empty/None")
    if not var:
        raise ValueError("var can't be empty/None")
    autopsy_user_vars[var] = value.lower() == "true"


def get_GA(var, default=None):
    if var in autopsy_user_vars.keys():
        return autopsy_user_vars[var]

    return default


def get_GA_Bool(var, default):
    val = get_GA(var)
    if not val:
        return default
    return val.lower() == "true"


def get_GA_Int(var, default):
    """ Be cautious about value error exception if the value is not integer
    :param var:
    :param default: default value to be returned if the variable is not found
    :return:
    """
    return int(get_GA(var, default))


def get_GA_Float(var, default):
    """ Be cautious about value error exception if the value is not float
    :param var:
    :param default: default value to be returned if the variable is not found
    :return:
    """
    return float(get_GA(var, default))


def dumpTestCaseJsonFile():
        # fh = open("/tmp/" + autopsy_testbed.tbname + "_tests.json", "w")
        fh = open("/tmp/" + autopsy_testbed.tbFileName, "w")

        str = "{\n" \
              "      \"TestCases\":\n" \
              "          [\n"
        isFirst = True
        for test in test_list:
            if not isFirst:
                str += ',\n'
            str += "                  " + test.toJson()
            isFirst = False

        str += "\n         ]\n" \
               "}"

        fh.write(str)


def getTestByName(self, name):
        for test in test_list:
            if test.name == name:
                return test

        return None


class TestCase:
    def __init__(self, name, result, description):
        self.name = name
        self.result = result
        self.description = description
        self.starttime = time.time()

    def toJson(self):
        str =  "{\n" \
               "                     \"name\": " + "\"" + self.name + "\",\n"
        str += "                     \"result\": " + "\"" + self.result + "\",\n"
        str += "                     \"description\": " + "\"" + self.description + "\"\n" \
                                                                                    "                  }"

        return str

current_test = None
test_list = []
test_steps = []
test_fail_reason = ''
autopsy_run_tags = []

autopsy_user_vars = {}

allJobsRunning = []
autopsy_test_hooks = {}
