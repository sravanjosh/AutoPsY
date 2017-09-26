import time

from lib.commons.autopsylogging import AutopsyLogger
from lib.core.TestCore import check, autopsytest, TestHookHandler, TestHook
from lib.core.autopsy_globals import autopsy_logger, autopsy_testbed, autopsy_quick_run, get_GA

__author__ = 'joshisk'

host1 = autopsy_testbed.host[0]
host2 = autopsy_testbed.host[1]
host3 = autopsy_testbed.host[2]


# This "some_var" can be passed as '--user_vars some_var value' with ./autopsy.py. Which gives flexibility
#   to control the suite values during the run instead of hardcode.
# The 'value" of some_var can be of types boolean, string or int and you can use respective get_GA to get them
simulate_wan_type = get_GA("some_var")


# #################################################
#          TEST HANDLERS CAN BE CREATED -- START
# #################################################

def print_mem(node):
    autopsy_logger.warning("Free Memory of {0} is {1}MB".format(node.hostname, node.getRamDetails()["free"]))

# print_mem will be executed before each test of a test class
TestHookHandler.addTestHook(TestHookHandler.ON_START_TEST, TestHook(print_mem, [host1]))
# print_mem will be executed after each test of a test class
TestHookHandler.addTestHook(TestHookHandler.ON_END_TEST, TestHook(print_mem, [host1]))
# print_mem will be executed after test suite
TestHookHandler.addTestHook(TestHookHandler.ON_END_TEST_SUITE, TestHook(print_mem, [host1]))
# print_mem will be executed before each test class
TestHookHandler.addTestHook(TestHookHandler.ON_START_TEST_CLASS, TestHook(print_mem, [host1]))
# print_mem will be executed after each test class
TestHookHandler.addTestHook(TestHookHandler.ON_END_TEST_CLASS, TestHook(print_mem, [host1]))

# #############################################
#          TEST HANDLERS CAN BE CREATED -- END
# #############################################


def preConfig():
    if simulate_wan_type:
        autopsy_logger.info("Configuring wan type as : " + simulate_wan_type,
                            fg_color=AutopsyLogger.MAGENTA)

        host1.simulate_wan_characteristics("eth0", "add", wan_type=simulate_wan_type)
        host2.simulate_wan_characteristics("eth0", "add", wan_type=simulate_wan_type)


def postConfig():
    if simulate_wan_type:
        host1.simulate_wan_characteristics("eth0", "del", wan_type=simulate_wan_type)
        host2.simulate_wan_characteristics("eth0", "del", wan_type=simulate_wan_type)


def setUpModule(module):
    # autopsy_quick_run is True if "-q" option is passed while running ./autopsy.py
    if not autopsy_quick_run:
        host1.adjust_qos_param("eth0", "del")
        preConfig()


def tearDownModule(module):
    # autopsy_quick_run is True if "-q" option is passed while running ./autopsy.py
    if not autopsy_quick_run:
        postConfig()


############################################################################################
#                                                                                          #
#                                       TEST CASES                                         #
#                                                                                          #
############################################################################################


@autopsytest
class TestBasicMulticast:
    """ Simple Multicast Transfer
    """

    def test(self):
        check(host1.createFile(filePath="/tmp", fileName="testfilename"),
              descr="Creating a file in host: " + host1.hostname,
              fail_msg="Unable to create file")