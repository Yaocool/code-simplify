import logging

from code_simplify.log.logger import traceback_error


def test_traceback_error_preserves_original_exception(caplog):
    logger = logging.getLogger("test.traceback_error")
    try:
        raise ValueError("original exception")
    except ValueError as error:
        traceback_error(logger, error, "operation failed")

    message = caplog.records[-1].getMessage()
    assert "message: operation failed ex: original exception traceback:" in message
    assert "test_traceback_error_preserves_original_exception" in message
