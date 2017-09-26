import inspect
import itertools
import random
import re
import smtplib
import socket
import subprocess
import sys
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from termcolor import colored

from lib.core.autopsy_globals import autopsy_logger

__author__ = 'joshisk'


class Ascii:
    NULL = '\x00'
    LINE_FEED = '\x0A'
    CARRIAGE_RETURN = '\x0D'
    CHARACTER_FILL = '\xDB'
    CTRL_LEFT_SQAURE_BRACKET = '\x1C'
    CTRL_RIGHT_SQAURE_BRACKET = '\x1D'


def archive_file_dir(file_dir):
    process = subprocess.Popen(["gzip", "-r", file_dir])
    process.communicate()


def probability(probs, eventlist=None):
    if not probs:
        autopsy_logger.error("List of probabilities cannot be empty")
        return -1
    if eventlist and len(eventlist) != len(probs):
        autopsy_logger.error("No if items in eventlist and probabilities must match")
        return -1

    sample_distribution = 100
    sample_space = sum(probs) * sample_distribution

    randNo = random.randint(1, sample_space)

    sumI = 0
    for i in range(len(probs)):
        sumI += probs[i]
        if randNo <= sumI * sample_distribution:
            if eventlist:
                return eventlist[i]
            return i


def convertBytesToReadable(bytes, suffix="B"):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(bytes) < 1024.0:
            return "%3.1f%s%s" % (bytes, unit, suffix)
        bytes /= 1024.0

    return "%.1f%s%s" % (bytes, 'Yi', suffix)


def convertToBytes(size):
    """
    :param size: Size in contracted format, e.g., 1M, 1G...etc.
    Doesn't support multiple units like 1M 10K
    :return: 1M = 1048576 (1024 * 1024)
    """
    match = re.match("([0-9]+)[ ]*([kmgtKMGT])?", str(size))
    magnitude = match.group(1)
    unit = match.group(2) if len(match.groups()) >= 2 else "b"

    if unit:
        value = 0
        for u in ["b", "k", "m", "g", "t", "p"]:
            if u == unit.lower():
                return int(magnitude) * (pow(1024, value))
            value += 1

    return int(magnitude)


def progressBar(currentValue, totalValue, percentWise=True,
                countDown=False, details=False, prefix="", indefinite=False):
    """
    :param details: Whether to show current Value out of total Value (e.g., 10 out of 20). Valid only
    with percentWise
    :param currentValue: Current Value of the complete progress w.r.to Total Value
    :param totalValue: Total Value of the progress bar
    :param percentWise: Whether to show the progress interms of percent of total completion.
    If False, will just show the current value
    :param countDown: Whether to show current progress in count down (Remaining of current value from total value)
    Works if percentWise is False
    :param prefix: To show any prefix next to the current value. Works if percentWise is False
    :return:
    """
    percentComplete = int((currentValue * 100) // totalValue)

    sys.stdout.write(" " * 150 + "\r")

    if percentComplete >= 100:
        sys.stdout.flush()
        return

    if not indefinite:

        sys.stdout.write(colored("  [ ", "blue"))

        sys.stdout.write(colored("=" * (percentComplete - 2), "green"))
        sys.stdout.write(colored("=>", "green", attrs=["bold"]))
        sys.stdout.write(" " * (100 - abs(percentComplete)))

        sys.stdout.write(colored(" ]", "blue"))
        if percentWise:
            if not details:
                sys.stdout.write(colored(" {0}%\r".format(percentComplete), "magenta", attrs=["bold"]))
            else:
                sys.stdout.write(colored(" {0}% ({1}/{2})\r".format(percentComplete, currentValue, totalValue),
                                         "magenta", attrs=["bold"]))
        else:
            if countDown:
                sys.stdout.write(colored(" {0}{1}\r".format(totalValue - currentValue, prefix + "     "),
                                         "magenta", attrs=["bold"]))
            else:
                sys.stdout.write(colored(" {0}{1}\r".format(currentValue, prefix + "        "),
                                         "magenta", attrs=["bold"]))
    else:
        pass

    sys.stdout.flush()


def visual_sleep(period, descr=""):
    if not time:
        return

    _timeout = time.time() + period

    if descr:
        autopsy_logger.info(descr),

    autopsy_logger.info("Sleeping for {0} seconds:".format(period))
    _slept_time = 0
    progressBar(_slept_time, period, percentWise=False, countDown=True, prefix="s")

    while time.time() < _timeout:
        time.sleep(1)
        _slept_time += 1
        progressBar(_slept_time, period, percentWise=False, countDown=True, prefix="s")


def repeatMultipleTimes(procs=None, count=1, gap=30, repeatDelay=5, args=None):
    """
    :param procs: List of procs to be executed with a gap of "gap" between each proc
    :param count: Number of times to execute the procs
    :param gap: Gap between each proc, incase it has more than one
    :param repeatDelay:
    :param args: List of tuples of arguments to each proc, argument tuple values should match
    the arguments take by respective proc otherwise it results in exception
    :return: Returns a tuple of return values of all the function calls in the order they executed
    """

    if not procs:
        return

    if type(procs) is not list:
        procs = [procs]

    returnValues = []
    for _ in range(count):
        for j, proc in enumerate(procs):
            if j > 0:
                time.sleep(gap)

            if args and args[j]:
                returnValues.append(proc(*args[j]))
            else:
                returnValues.append(proc())

        time.sleep(repeatDelay)

    return tuple(returnValues)


def waitUntil(condition, globals=None, locals=None, timeout=10, retryInterval=2):
    """
    Example:
        1. waitUntil("test.pass() or job.isFinished()", timeout=60)
        2. waitUntil("x >= 10 and x < 100, timeout=20, retryInterval=5)

    :param condition: Python condition in string format e.g., "x > 10 and y <=5"
    :param globals: use globals(), if None, will be taken from the calling scopes globals
    :param locals: use locals(), if None, will be taken from the calling scopes locals
    :param timeout: total number of seconds you want to give for the "condition" to be true
    :param retryInterval: How frequently you want to check the "condition" for it to be true
    :return: Returns True if condition results to True with in timeout, else False

    """

    if not condition:
        return False

    if not locals:
        locals = inspect.currentframe().f_back.f_locals

    if not globals:
        globals = inspect.currentframe().f_back.f_globals

    waittime = time.time() + timeout

    while waittime >= time.time():
        if eval(condition, globals, locals):
            return True

        time.sleep(retryInterval)

    return False


def waitOnProcCondition(proc, lambda_func=lambda output: output, timeout=30, interval=2, args=None):
    """
    Example:
     waitOnProcCondition(grep_log, lambda output: "Joe" in output, args=["/tmp/hi.txt", "emp_name"])

    :param interval:
    :param proc: proc to call
    :param lambda_func: lambda function to use to check. This should return True to pass the condition and exit
    the loop. Argument to lambda function is the return value of the proc with arguments in "args"
    :param timeout: timeout to wait till it sees the lambda function True
    :param args: Arguments to be passed to the proc
    :return:
    """
    if not args:
        args = []

    if type(args) is not list:
        args = list(args)

    waittime = time.time() + timeout

    while waittime >= time.time():
        result = proc(*args)

        if lambda_func(result):
            return True

        time.sleep(interval)

    return False


def waitOnProcOutput(proc, out_expected, timeout=30, interval=2, args=None,
                     match_exact=False, case_sensitive=False):
    """
    Example:
     1. waitOnProcOutput(area_of_rectangle, 6, args=[2, 3], match_exact=True)
     2. waitOnProcOutput(file_contains, "Job started successfully" , args=["/tmp/sylog"])
    :param case_sensitive:
    :param interval:
    :param proc: proc to call
    :param out_expected: Output you are expecting to match exactly
    :param timeout:
    :param args:
    :param match_exact: If True, output of proc should match exactly with the output param, else output of proc
    should contain the string passed by output param
    :return:
    """

    if match_exact:
        return waitOnProcCondition(proc, lambda_func=lambda x: x == out_expected,
                                   timeout=timeout, interval=interval, args=args)
    else:
        return waitOnProcCondition(proc, lambda_func=lambda x: out_expected in x,
                                   timeout=timeout, interval=interval, args=args)


def get_ordinal_indicator(number):
    remainder = number % 10
    if remainder == 1:
        return "st"
    if remainder == 2:
        return "nd"
    if remainder == 3:
        return "rd"
    return "th"


def intListToString(l):
    """
    To shorten and convert the integer list to string
    e.g., 1,2,3,5,6,8,9,10 ----> 1-3, 5, 6, 8-10
    :param l:
    :return:
    """

    def local():
        for a, b in itertools.groupby(enumerate(l), lambda (x, y): y - x):
            b = list(b)
            yield b[0][1], b[-1][1]

    result = list(local())

    resultString = ""
    for _i, tup in enumerate(result):
        if _i != 0:
            resultString += ", "
        if tup[0] == tup[1]:
            resultString += str(tup[0])
        elif tup[0] == tup[1] - 1:
            resultString += str(tup[0]) + ", " + str(tup[1])
        else:
            resultString += str(tup[0]) + "-" + str(tup[1])

    return resultString


def quotify(some_string, quote_char="\'"):
    """
    :param quote_char:
    :param some_string: Add quotes around a string
    :return:
    Hello =============> "Hello"

    """
    return quote_char + some_string + quote_char


def linesToPoints(lines, maxLineWidth=80):
    """
    To Convert list of sentences to String of points
    e.g., ["Hi! There", "U r sick"] -->
    1. Hi! There
    2. U r sick

    :param maxLineWidth:
    :param lines:
    :return:
    """
    if not isinstance(lines, list):
        autopsy_logger.critical("Argument lines should be list")
        return

    result = ""
    lines = [line for line in lines if line.strip() != ""]

    numSpaces = len(str(len(lines)))

    for _i, sentence in enumerate(lines):
        lenSentence = len(sentence)
        if _i != 0:
            result += "\n"
        result += str(_i + 1) + "."

        subStringRange = 0
        for subStringRange in range(0, lenSentence, maxLineWidth):
            if subStringRange > 0:
                result += "\n"
                result += " " * (len(str(_i + 1) + "."))

            result += " " * min(4, (numSpaces - len(str(_i + 1)) + 1))
            toValue = min(subStringRange + maxLineWidth, lenSentence)

            result += sentence[subStringRange:toValue].strip()

    return result


def align_side_by_side(lines1, lines2, gap=10, lines1_label="", lines2_label=""):
    """
    Align two different multiline content side by side.
    Works best for small length lines and want to save screen space.
    e.g.,

    # ###########
    #    BEFORE
    # ##########

    Lines 1:
    ******************************
    Email-ID: autopsyautotest9904@autopsynetworks.com
    Name: Joshi Sravan Kumar
    Is Active: True
    autopsy User Role: autopsy_user
    Street: Koramangala
    City: Bangalore
    State: Karnataka
    Country: INDIA
    Zip: None
    Mobile: None
    Timezone: None
    ******************************
    Lines 2:
    ******************************
    Email-ID: autopsyautotest9904@autopsynetworks.com
    Name: None None
    Is Active: None
    autopsy User Role: None
    Street: None
    City: None
    State: None
    Country: None
    Zip: None
    Mobile: None
    Timezone: None
    ******************************

    # ######################################################################
    # ##########
    #    After
    # ##########

    Lines 1:                                                Lines 2:
    ******************************                         ******************************
    Email-ID: autopsyautotest9904@autopsynetworks.com          Email-ID: autopsyautotest9904@autopsynetworks.com
    Name: Joshi Sravan Kumar                               Name: None None
    Is Active: True                                        Is Active: None
    autopsy User Role: autopsy_user                            autopsy User Role: None
    Street: Koramangala                                    Street: None
    City: Bangalore                                        City: None
    State: Karnataka                                       State: None
    Country: INDIA                                         Country: None
    Zip: None                                              Zip: None
    Mobile: None                                           Mobile: None
    Timezone: None                                         Timezone: None
    ******************************                         ******************************

    :param lines1:
    :param lines2:
    :param gap:
    :return:
    """
    if not isinstance(lines1, list):
        lines1 = str.splitlines(lines1)

    if not isinstance(lines2, list):
        lines2 = str.splitlines(lines2)

    if lines1_label:
        lines1 = [lines1_label + ":"] + lines1

    if lines2_label:
        lines2 = [lines2_label + ":"] + lines2

    max_line_width = 0

    for line in lines1:
        if len(line) > max_line_width:
            max_line_width = len(line)

    result_string = ""

    for line1, line2 in itertools.izip_longest(lines1, lines2):
        result_string += (line1 if line1 else "") + " " * (max_line_width - (len(line1) if line1 else 0) + gap) + \
                         (line2 if line2 else "")
        result_string += "\n"
    return result_string


def synchronized_block(arg, lock=None):
    if lock:
        return lock
    else:
        if not hasattr(arg, "syncLock"):
            setattr(arg, "syncLock", threading.RLock())

        return getattr(arg, "syncLock")


def sendmail(subject, from_mail, to_mail, msg, html_msg=None):
    me = from_mail
    you = re.split(r'[;,\s]\s*', to_mail)

    # Create message container - the correct MIME type is multipart/alternative.
    mime = MIMEMultipart('alternative')
    mime['Subject'] = subject
    mime['From'] = me
    mime['To'] = to_mail

    if not html_msg:
        html_msg = "<html> <pre> " + msg + "</pre> </html>"

    part1 = MIMEText(msg, 'plain')
    part2 = MIMEText(html_msg, 'html')
    mime.attach(part1)
    mime.attach(part2)

    try:
        autopsy_logger.info("Sending mail to: " + to_mail)
        server = smtplib.SMTP('localhost')
        server.set_debuglevel(0)

        server.sendmail(me, you, mime.as_string())
        server.quit()
    except socket.error as e:
        autopsy_logger.error("Couldn't send mail, check your local SMTP client: " + str(e))


######################################
#              DECORATORS
######################################

def repeat(count=2, repeatDelay=10):
    """
    Decorator to repeat a function.
    :param count:
    :param repeatDelay:
    :return:
    """
    def wrapper(func_name):
        def new_func(*args, **kwargs):
            result = None
            for i in range(count):
                result = func_name(*args, **kwargs)
                autopsy_logger.info(
                    "Repeating the function '{0}' {1}{2} time".format(func_name, i + 1, get_ordinal_indicator(i + 1)))
                time.sleep(repeatDelay)

            return result
        return new_func

    return wrapper


def repeat_on_return_value(return_value, count=2, repeatDelay=2):
    """
    Decorator to repeat a function if it returns the given return_value
    :param return_value:
    :param count:
    :param repeatDelay:
    :return:
    """
    def wrapper(func_name):
        def new_func(*args, **kwargs):
            result = None
            for i in range(count):
                result = func_name(*args, **kwargs)
                if result != return_value:
                    break
                autopsy_logger.info(
                    "Repeating the function '{0}' {1}{2} time".format(func_name, i + 1, get_ordinal_indicator(i + 1)))
                time.sleep(repeatDelay)

            return result
        return new_func

    return wrapper


def repeat_on_fail(count=2, repeatDelay=2):
    """
    Decorator to repeat a function if it returns False
    :param count:
    :param repeatDelay:
    :return:
    """
    return repeat_on_return_value(False, count, repeatDelay)


def synchronized(func):
    """
    Decorator once applied make the function (only for non-static member functions)
    thread safe by allowing only one thread at a time to execute the given function.
    :param func:
    :return:
    """
    def new_func(self, *args, **kwargs):
        func_args = inspect.getargspec(func).args

        # Quick, probably dirty way of identifying whether the decorated function is a
        #   member method and not a regular function. As only member methods can be synchronized
        #   this way with an object level Re-entrant Lock.
        # Probably there might be a better way to differentiate between member and non-member methods
        if func_args and func_args[0] != 'self':
            return func(self, *args, **kwargs)

        if not hasattr(self, "syncLock"):
            self.syncLock = threading.RLock()

        with self.syncLock:
            return func(self, *args, **kwargs)

    return new_func

if __name__ == "__main__":
    # def grep_log(file, pattern):
    #
    #     p = subprocess.Popen(['grep', pattern, file], stdout=subprocess.PIPE,
    #                                      stderr=subprocess.PIPE)
    #     out, err = p.communicate()
    #     print(out.strip())
    #     return out.strip()
    #
    # print("Waiting")
    #
    # waitOnProcOutput(grep_log, "Joe", timeout=120,
    #                  match_exact=False, args=["/tmp/hi.txt", "emp_name"])
    #
    # print("Done")

    # x = 0
    #
    # def someProc():
    #     global x
    #     for _ in range(15):
    #         x += 3
    #         print("X:"+str(x))
    #         time.sleep(1)
    #
    # threaD = threading.Thread(target=someProc)
    # threaD.start()
    #
    # print("Started Thread:")
    # print(waitUntil("x>30", timeout=2))
    # print("Waiting for thread to finish:")
    # threaD.join()

    # print(convertToBytes("100M"))
    # print(convertToBytes("1g"))
    # print(convertToBytes("19001299"))
    # repeatMultipleTimes(someProc)
    # for i in range(10):
    #     progressBar(i, 10)
    #     time.sleep(1)

    print intListToString([1, 2, 3, 4, 6, 7, 9, 10, 12])
    lines = ["A Quick brown fox jumps on a lazy dog. A Quick brown fox jumps on a lazy dog. ", "    \n"
                                                                                               "Quick brown fox jumps on a lazy dog",
             "A", "Quick", "Brown", "Fox", "Jump", "on",
             "lazy", "dog"]
    print(linesToPoints(lines, 100))

    #     lines1 = '''We added:
    # ******************************
    # Email-ID: autopsyautotest9904@autopsynetworks.com
    # Name: Joshi Sravan Kumar
    # Is Active: True
    # autopsy User Role: autopsy_user
    # Street: Koramangala
    # City: Bangalore
    # State: Karnataka
    # Country: INDIA
    # Zip: None
    # Mobile: None
    # Timezone: None
    # Mobile: None
    # Mobile: None
    # Mobile: None
    # ******************************'''
    #     lines2 = '''Get returned:
    # ******************************
    # Email-ID: autopsyautotest9904@autopsynetworks.com
    # Name: None None
    # Is Active: None
    # autopsy User Role: None
    # Street: None
    # City: None
    # State: None
    # Country: None
    # Zip: None
    # Mobile: None
    # Timezone: None
    # ******************************'''
    #
    #     print(align_side_by_side(lines1, lines2))
