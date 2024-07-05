import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from typing import Optional

FAILED_UP_PATH = "logs"
DEFAULT_FORMAT = (
    "%(asctime)s.%(msecs)03d [%(threadName)s] %(levelname)s %(pathname)s(%(funcName)s:%("
    "lineno)d) - %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
WARN_LOGGERS: list[str] = ["parso"]
ERROR_LOGGERS: list[str] = []

logging.setLogRecordFactory(logging.getLogRecordFactory())


def setup_logger(
        level: int = logging.INFO,
        debug: bool = False,
        filename: Optional[str] = None,
        log_path: str = ".",
        max_bytes: int = 100 * 1024 * 1024,
        backup_count: int = 5,
        log_name: Optional[str] = None,
        warn_level_logs: Optional[list[str]] = None,
        error_level_logs: Optional[list[str]] = None,
) -> logging.Logger:
    logger = logging.getLogger(log_name)
    logger.setLevel(level)

    handlers: list[logging.Handler] = []
    # file log handler
    filename = (
        filename if filename else "code_simplify.log"
    )
    if debug:
        log_path = f"{filename}.debug"
    if not os.path.isdir(log_path):
        os.makedirs(log_path)
    real_path = os.path.join(log_path, filename)
    handlers.append(
        RotatingFileHandler(real_path, maxBytes=max_bytes, backupCount=backup_count)
    )
    # console log handler
    handlers.append(logging.StreamHandler())

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DATE_FORMAT)
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    warn_logs = (
        warn_level_logs + WARN_LOGGERS if warn_level_logs is not None else WARN_LOGGERS
    )
    for warn_log in warn_logs:
        logger = logging.getLogger(warn_log)
        logger.setLevel(logging.WARN)

    error_logs = (
        error_level_logs + ERROR_LOGGERS
        if error_level_logs is not None
        else ERROR_LOGGERS
    )
    for error_log in error_logs:
        logger = logging.getLogger(error_log)
        logger.setLevel(logging.ERROR)
    return logger


def disable_logging(libs: list[str]):
    if not libs:
        return
    for lib in libs:
        logging.getLogger(lib).disabled = True


def traceback_error(logger, ex: Exception, msg: str = None):
    logger.error(ex)
    tb = traceback.extract_tb(ex.__traceback__)
    ignore_locations = [sys.prefix, "homebrew/Cellar/python", "site-packages"]
    callstack_in_user_code = []
    for ex in tb:
        if not any(location in ex.filename for location in ignore_locations):
            callstack_in_user_code.append(ex)
    sb = ""
    for frame in callstack_in_user_code:
        sb += frame.__str__() + "\n"
    logger.error(f"message: {msg} ex: {ex} traceback: {sb}")
