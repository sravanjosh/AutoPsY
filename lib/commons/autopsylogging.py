from logging import Logger
import logging
import os
import sys

from coloredlogs import ColoredFormatter
from termcolor import colored

__author__ = 'joshisk'


# BECAREFUL ABOUT THIS CODE. Derived from logging.py --- START
if hasattr(sys, 'frozen'):
    _srcfile = "logging%s__init__%s" % (os.sep, __file__[-4:])
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


def currentframe():
    """Return the frame object for the caller's stack frame."""
    try:
        raise Exception
    except:
        return sys.exc_info()[2].tb_frame.f_back
# BECAREFUL ABOUT THIS CODE. Derived from logging.py --- END


class AutopsyLogger(logging.getLoggerClass()):

    RED     = "red"
    GREEN   = "green"
    MAGENTA = "magenta"
    # BLACK   = "black"
    WHITE   = "white"
    CYAN    = "cyan"
    YELLOW  = "yellow"
    BLUE    = "blue"
    GREY    = "grey"

    dateFmt = "%Y-%m-%d %H:%M:%S"
    # FORMATTER = logging.Formatter(fmt='%(asctime)s.%(msecs)03d: %(levelname)-8s : '
    #                                   '[%(threadName)s] - (%(funcName)-10s) - %(message)s', datefmt=dateFmt)
    FORMATTER = ColoredFormatter(fmt='%(asctime)s.%(msecs)03d: %(levelname)-8s : '
                                     '[%(threadName)-10s] - (%(funcName)-15s) - %(message)s',
                                 level_styles={
                                     "debug": {"color": "blue"},
                                     "info": {"color": "white"},
                                     "warning": {"color": "magenta"},
                                     "error": {"color": "red"},
                                     "critical": {"color": "red", "bold": True}
                                 },
                                 field_styles={
                                     "asctime": {"color": "yellow"},
                                     "msec": {"color": "yellow"},
                                     "levelname": {"color": "blue", "bold": True},
                                     "funcName": {"color": "cyan"}
                                 })

    def __init__(self, name="Main Logger", handlers=None, stderr=True):
        """
        :param name: Name of the logger, Default "Main Logger"
        :param handlers: List of handlers to attach
        :param stderr: If true, default StreamHandler to stderr is attached
        :return:
        """
        Logger.__init__(self, name)

        self.setLevel(logging.DEBUG)
        self.propagate = False

        if handlers and len(handlers) > 0:
            for handler in handlers:
                if isinstance(handler, logging.Handler):
                    handler.setFormatter(self.FORMATTER)
                    self.addHandler(handler)

        if stderr:
            self.stderrHandler = self.addStreamHandler()

    def setLogLevelStderrHandler(self, loggingLevel):
        self.stderrHandler.setLevel(loggingLevel)

    def addStreamHandler(self, loggingLevel=logging.DEBUG):
        logStreamHandler = logging.StreamHandler()
        # logStreamHandler = RainbowLoggingHandler(sys.stderr, datefmt=self.dateFmt,
        #                                          color_asctime=("yellow", None, False),
        #                                          color_msecs=("yellow", None, False),
        #                                          color_levelname=("blue", None, True))
        logStreamHandler.setFormatter(self.FORMATTER)
        logStreamHandler.setLevel(loggingLevel)

        self.addHandler(logStreamHandler)

        return logStreamHandler

    def addFileHandler(self, filePath, loggingLevel=logging.DEBUG):
        logFileHandler = logging.FileHandler(filePath, mode='w')
        logFileHandler.setLevel(loggingLevel)
        logFileHandler.setFormatter(self.FORMATTER)

        self.addHandler(logFileHandler)

    def logColor(self, level, msg,
                 fg_color=None, bg_color=None,
                 bold=False, blink=False, dark=False, underline=False,
                 reverse=False, concealed=False,
                 *args, **kwargs):
        attr = []
        if bold:
            attr.append("bold")
        if blink:
            attr.append("blink")
        if dark:
            attr.append("dark")
        if underline:
            attr.append("underline")
        if reverse:
            attr.append("reverse")
        if concealed:
            attr.append("concealed")

        if "%s" not in msg:
            msg = colored(msg, color=fg_color, on_color=("on_" + bg_color) if bg_color else None,
                          attrs=attr)
        super(AutopsyLogger, self).log(level, msg)

    def debug(self, msg, fg_color=GREEN, bg_color=None,
              bold=False, blink=False, dark=False, underline=False,
              reverse=False, concealed=False, *args, **kwargs):
        attr = []
        if bold:
            attr.append("bold")
        if blink:
            attr.append("blink")
        if dark:
            attr.append("dark")
        if underline:
            attr.append("underline")
        if reverse:
            attr.append("reverse")
        if concealed:
            attr.append("concealed")

        if "%s" not in msg:
            msg = colored(msg, color=fg_color, on_color=("on_" + bg_color) if bg_color else None,
                          attrs=attr)
        super(AutopsyLogger, self).debug(msg)

    def info(self, msg, fg_color=None, bg_color=None,
             bold=False, blink=False, dark=False, underline=False,
             reverse=False, concealed=False, *args, **kwargs):
        attr = []
        if bold:
            attr.append("bold")
        if blink:
            attr.append("blink")
        if dark:
            attr.append("dark")
        if underline:
            attr.append("underline")
        if reverse:
            attr.append("reverse")
        if concealed:
            attr.append("concealed")

        if "%s" not in msg:
            msg = colored(msg, color=fg_color, on_color=("on_" + bg_color) if bg_color else None,
                          attrs=attr)
        super(AutopsyLogger, self).info(msg)

    def warning(self, msg, fg_color=None, bg_color=None,
                bold=False, blink=False, dark=False, underline=False,
                reverse=False, concealed=False, *args, **kwargs):
        attr = []
        if bold:
            attr.append("bold")
        if blink:
            attr.append("blink")
        if dark:
            attr.append("dark")
        if underline:
            attr.append("underline")
        if reverse:
            attr.append("reverse")
        if concealed:
            attr.append("concealed")

        if "%s" not in msg:
            msg = colored(msg, color=fg_color, on_color=("on_" + bg_color) if bg_color else None,
                          attrs=attr)
        super(AutopsyLogger, self).warning(msg)

    def error(self, msg, fg_color=None, bg_color=None,
              bold=True, blink=False, dark=True, underline=False,
              reverse=False, concealed=False, *args, **kwargs):
        attr = []
        if bold:
            attr.append("bold")
        if blink:
            attr.append("blink")
        if dark:
            attr.append("dark")
        if underline:
            attr.append("underline")
        if reverse:
            attr.append("reverse")
        if concealed:
            attr.append("concealed")

        if "%s" not in msg:
            msg = colored(msg, color=fg_color, on_color=("on_" + bg_color) if bg_color else None,
                          attrs=attr)
        super(AutopsyLogger, self).error(msg)

    def critical(self, msg, fg_color=WHITE, bg_color=RED,
                 bold=True, blink=False, dark=True, underline=False,
                 reverse=False, concealed=False, *args, **kwargs):
        attr = []
        if bold:
            attr.append("bold")
        if blink:
            attr.append("blink")
        if dark:
            attr.append("dark")
        if underline:
            attr.append("underline")
        if reverse:
            attr.append("reverse")
        if concealed:
            attr.append("concealed")

        if "%s" not in msg:
            msg = colored(msg, color=fg_color, on_color=("on_" + bg_color) if bg_color else None,
                          attrs=attr)
        super(AutopsyLogger, self).critical(msg)

    # TODO: v_line_bold is not supported
    def header_box(self, msg="", level=logging.INFO,
                   width=70, left_margin=2, top_margin=2,
                   h_box_char='*', v_box_char="|",
                   h_line_bold=False, v_line_bold=False, un_ended=True):

        brokenLines = [msg[i:i+(width - (2*left_margin + 2))] for i in range(0, len(msg),
                                                                             (width - (2*left_margin + 2)))]

        # TODO: Handle "new-line" chars in the msg properly
        # finalLines = []
        # for line in brokenLines:
        #     map(finalLines.append, line.splitlines())
        # brokenLines = finalLines

        if h_box_char == '-' or h_box_char == '=':
            self.log(level, '+' + (h_box_char * (width-2)) + '+')
        else:
            self.log(level, (h_box_char * width))

        if h_line_bold:
            if h_box_char == '-' or h_box_char == '=':
                self.log(level, '+' + (h_box_char * (width-2)) + '+')
            else:
                self.log(level, (h_box_char * width))

        for i in range(top_margin):
            self.log(level, v_box_char + (" " * (width-2)) + (v_box_char if un_ended else ""))

        for line in brokenLines:
            temp_line = v_box_char + (" " * left_margin) + line.replace("\n", " ") + (" " * left_margin) + \
                        (v_box_char if un_ended else "")
            gap = width - len(temp_line)
            line = v_box_char + (" " * left_margin) + line.replace("\n", " ") + " " * gap + \
                   (" " * left_margin) + (v_box_char if un_ended else "")
            self.log(level, line)

        for i in range(top_margin):
            self.log(level, v_box_char + (" " * (width-2)) + (v_box_char if un_ended else ""))

        if h_line_bold:
            if h_box_char == '-' or h_box_char == '=':
                self.log(level, '+' + (h_box_char * (width-2)) + '+')
            else:
                self.log(level, (h_box_char * width))

        if h_box_char == '-' or h_box_char == '=':
            self.log(level, '+' + (h_box_char * (width-2)) + '+')
        else:
            self.log(level, (h_box_char * width))

    def header1_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=80, left_margin=3, top_margin=2,
                        h_box_char="#", v_box_char="#", h_line_bold=True, un_ended=False)

    def header2_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=80, left_margin=3, top_margin=2,
                        h_box_char="#", v_box_char="#", h_line_bold=True)

    def header3_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=74, left_margin=3, top_margin=2,
                        h_box_char="*", v_box_char="*",
                        h_line_bold=True)

    def header4_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=70, left_margin=2, top_margin=2, h_box_char="=")

    def header5_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=70, left_margin=2, top_margin=2, h_box_char="*", v_box_char="*")

    def header6_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=70, left_margin=1, top_margin=0, h_box_char="*", v_box_char="*")

    def header7_box(self, msg="", level=logging.INFO):
        self.header_box(msg, level, width=70, left_margin=1, top_margin=0, h_box_char="-")

    def horiz_line(self, size=72, level=logging.INFO):
        self.log(level, "-" * size)

    # THINK TWICE or MORE BEFORE CHANGING THIS FUNCTION. Derived from logging.py
    def findCaller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = currentframe()
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile or "logging/__init__.py" in filename:
                f = f.f_back
                continue

            if co.co_name.startswith("__") and co.co_name.endswith("__"):
                instance = f.f_locals.get("self", None)
                if instance:
                    rv = (co.co_filename, f.f_lineno, instance.__class__.__name__ + "." + co.co_name)
                else:
                    rv = (co.co_filename, f.f_lineno, co.co_name)
            else:
                rv = (co.co_filename, f.f_lineno, co.co_name)
            break
        return rv


def function():
    logger = AutopsyLogger()

    msg = "Hello"
    logger.debug("Hello {0}".format(msg))
    logger.info(msg)
    logger.warning(msg)
    logger.error(msg)
    logger.critical(msg)

    logger.header1_box("Hello how are you. Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. ")
    logger.info("")
    logger.info("")
    logger.header2_box("Hello how are you. Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. ")
    logger.info("")
    logger.info("")
    logger.header3_box("Hello how are you. Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. ")
    logger.info("")
    logger.info("")
    logger.header4_box("Hello how are you. Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. ")
    logger.info("")
    logger.info("")
    logger.header5_box("Hello how are you. Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. ")
    logger.info("")
    logger.info("")
    logger.header6_box("Hello how are you. Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. Hello how are you. "
                       "Hello how are you. Hello how are you. ")

if __name__ == "__main__":
    function()
