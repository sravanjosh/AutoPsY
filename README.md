# AutoPsY
Python based Automation framework on top of Python Unittest and nose frameworks. It has wrappers for remotely connecting to nodes and write test cases easily.

This framework is to mainly to help the QA teams to write black box tests where as Python unittest and nose are mainly for unittesting.

Autopsy Executes the test, saves logs, sends mail to the user with summary of the run.

### Topology


                                              +---------------------------+
                                              |                  Testbed  |
                                              | +-----------------------+ |
                                              | |        HOST 1         | |
                                              | |                       | |
     +-----------------------+                | +-----------------------+ |
     |                       |        *       | +-----------------------+ |
     |                       |     SSH        | |        HOST 2         | |
     |        AUTOPSY        +------------------>                       | |
     |                       |                | +-----------------------+ |
     |Exec M/c               |                |                           |
     +-----------------------+                | +-----------------------+ |
                                              | |        HOST n         | |
                                              | |                       | |
                                              | +-----------------------+ |
                                              |                           |
                                              +---------------------------+
     *Right now only SSH

### Execution
 Sample test using different features of AutoPsY can be found in src/sample_suite.py
 
    cd main/
    ./autopsy.py --mail <userid>@<domain>.com --testbed ../testbeds/testbed.json --testsuite sample_suite
    
    ./autopsy.py
      usage: autopsy.py [-h] --testbed TESTBED --testsuite TEST_SUITE
                  [--mail MAIL_TO [MAIL_TO ...]] [-d]
                  [--run-tests RUN_TESTS [RUN_TESTS ...]]
                  [--run-tags RUN_TAGS [RUN_TAGS ...]]
                  [--skip-tests SKIP_TESTS [SKIP_TESTS ...]] [--repeat REPEAT]
                  [--rerun-failed] [--random [RANDOM]] [-v] [-q] [--reboot]
                  [--user-vars USER_VARS [USER_VARS ...]]
