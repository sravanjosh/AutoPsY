import inspect

from lib.core import autopsy_globals
from lib.core.autopsy_globals import autopsy_logger, TestCase

__author__ = 'joshisk'

"""
This plugin bypasses the actual execution of tests, and instead just collects
test names. Fixtures are also bypassed, so running nosetests with the
collection plugin enabled should be very quick.

This plugin is useful in combination with the testid plugin (``--with-id``).
Run both together to get an indexed list of all tests, which will enable you to
run individual tests by index number.

This plugin is also useful for counting tests in a test suite, and making
people watching your demo think all of your tests pass.
"""
from nose.plugins.base import Plugin
from nose.case import Test
import logging
import unittest

log = logging.getLogger(__name__)


class AutopsyCollectOnlyPlugin(Plugin):
    """
    Collect and output test names only, don't run any tests.
    """
    name = "autopsy-collect-only"
    enableOpt = 'autopsy-collect_only'

    def options(self, parser, env):
        """Register commandline options.
        :param env:
        :param parser:
        """
        parser.add_option('--autopsy-collect-only',
                          action='store_true',
                          dest=self.enableOpt,
                          default=env.get('NOSE_COLLECT_ONLY'),
                          help="Enable collect-only: {0} [COLLECT_ONLY]".format
                          (self.help()))

    def prepareTestLoader(self, loader):
        """Install collect-only suite class in TestLoader.
        :param loader:
        """
        # Disable context awareness
        loader.suiteClass = TestSuiteFactory(self.conf)

    def sortTestCasesByName(self):
        autopsy_globals.test_list.sort(key=lambda x: x.name)

    def startContext(self, context):
        if inspect.isclass(context):
            if context.__doc__ is not None:
                _currTestDescription = str.strip(str(context.__doc__))
                lines = context.__doc__.split('\n')
                testcase = autopsy_globals.getTestByName(context.__name__)
                testcase.description = _currTestDescription.replace('\n', '\\n')
                autopsy_globals.dumpTestCaseJsonFile()

    def prepareTestCase(self, test):
        """Replace actual test with dummy that always passes.
        :param test:
        """
        # Return something that always passes
        autopsy_logger.debug("Preparing test case {0}".format(test))
        id = test.id()
        (modulename, classname, testname) = id.split('.')
        autopsy_logger.debug(testname)
        if "test" == testname:
            autopsy_globals.test_list.append(TestCase(classname, "NotStarted", "Yet to get"))
        else:
            autopsy_globals.test_list.append(TestCase(classname+'.'+testname, "NotStarted", "Yet to get"))
        # self.sortTestCasesByName()
        autopsy_globals.dumpTestCaseJsonFile()
        if not isinstance(test, Test):
            return

        def run(result):
            # We need to make these plugin calls because there won't be
            # a result proxy, due to using a stripped-down test suite
            # self.conf.plugins.startTest(test)
            # result.startTest(test)
            # self.conf.plugins.addSuccess(test)
            # result.addSuccess(test)
            # self.conf.plugins.stopTest(test)
            # result.stopTest(test)
            pass
        return run


class TestSuiteFactory:
    """
    Factory for producing configured test suites.
    """
    def __init__(self, conf):
        self.conf = conf

    def __call__(self, tests=(), **kw):
        return TestSuite(tests, conf=self.conf)


class TestSuite(unittest.TestSuite):
    """
    Basic test suite that bypasses most proxy and plugin calls, but does
    wrap tests in a nose.case.Test so prepareTestCase will be called.
    """
    def __init__(self, tests=(), conf=None):
        self.conf = conf
        # Exec lazy suites: makes discovery depth-first
        if callable(tests):
            tests = tests()
        unittest.TestSuite.__init__(self, tests)

    def addTest(self, test):
        if isinstance(test, unittest.TestSuite):
            self._tests.append(test)
        else:
            self._tests.append(Test(test, config=self.conf))

