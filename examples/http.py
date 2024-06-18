from models.errors import Error
from http_utils.http_request import sse_handler


# custom errors
class TestSyncEventFuncError(Error):
    def __init__(self):
        super().__init__(500, "TestSyncEventFuncError")


class TestSyncDataFuncError(Error):
    def __init__(self):
        super().__init__(500, "TestSyncDataFuncError")


class TestAsyncEventFuncError(Error):
    def __init__(self):
        super().__init__(500, "TestAsyncEventFuncError")


class TestAsyncDataFuncError(Error):
    def __init__(self):
        super().__init__(500, "TestAsyncDataFuncError")


def event_func(data: dict, *args, **kwargs):
    """

    :param data: data from sse, must be the first argument and cannot be None
    :return:
    """
    print(data)
    raise TestSyncEventFuncError()


def data_func(data: dict, *args, **kwargs):
    """

    :param data: data from sse, must be the first argument and cannot be None
    :return:
    """
    print(data)
    raise TestSyncDataFuncError()


async def async_event_func(data: dict, *args, **kwargs):
    """

    :param data: data from sse, must be the first argument and cannot be None
    :return:
    """
    print(data)
    raise TestAsyncEventFuncError()


async def async_data_func(data: dict, *args, **kwargs):
    """

    :param data: data from sse, must be the first argument and cannot be None
    :return:
    """
    print(data)
    raise TestAsyncEventFuncError()


if __name__ == '__main__':
    import asyncio

    # normal processing func
    asyncio.run(sse_handler(
        'POST',
        '<YOUR STREAM URL>',
        # event_process_func=event_func,
        event_process_func=async_event_func,
        data_process_func=data_func,
        # data_process_func=async_data_func,
        custom_errors=[TestSyncEventFuncError, TestSyncDataFuncError]  # custom errors can be None
    ))
