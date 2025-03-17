import asyncio
import json
import logging
from typing import Any, List, Type
from inspect import iscoroutinefunction

from aiohttp import ClientSession, ClientTimeout, ContentTypeError
from aiohttp.hdrs import METH_HEAD, METH_GET, METH_OPTIONS, METH_POST, METH_PUT, METH_PATCH, METH_DELETE

from code_simplify.models.base import BaseResponse
from code_simplify.models.errors import RequestTimeoutError, InternalError, Error

logger = logging.getLogger(__name__)


async def http_head(path: str, headers: dict = None) -> BaseResponse:
    return await _request(METH_HEAD, path, headers=headers)


async def http_get(path: str, headers: dict = None) -> BaseResponse:
    return await _request(METH_GET, path, headers=headers)


async def http_options(path: str, headers: dict = None, allow_redirects: bool = True) -> BaseResponse:
    return await _request(METH_OPTIONS, path, headers=headers, allow_redirects=allow_redirects)


async def http_post(path: str, data: Any = None, json_data: Any = None, headers: dict = None) -> BaseResponse:
    return await _request(METH_POST, path, data, json_data, headers)


async def http_put(path: str, data: Any, json_data: Any, headers: dict = None) -> BaseResponse:
    return await _request(METH_PUT, path, data=data, json_data=json_data, headers=headers)


async def http_patch(path: str, data: Any, headers: dict = None) -> BaseResponse:
    return await _request(METH_PATCH, path, data=data, headers=headers)


async def http_delete(path: str, data: Any, headers: dict = None) -> BaseResponse:
    return await _request(METH_DELETE, path, data, headers)


async def sse_handler(
        method: str,
        url: str,
        data: Any = None,
        json_data: Any = None,
        headers: dict = None,
        timeout: int = 300,
        event_process_func=None,
        event_func_args: List = None,
        data_process_func=None,
        data_func_args: List = None,
        custom_errors: List[Type[Error]] = None
):
    """
    sse proto handler, both sync and async processing func are supported. Processing func for event and data type
     doesn't have to be async or sync at the same time. Raise custom errors if provided.
    :param method: http_utils method
    :param url: url
    :param data: data
    :param json_data: json
    :param headers: headers
    :param timeout: total timeout in seconds(include connecting)
    :param event_process_func: processing func for event type in sse proto, both async and sync func are supported
    :param event_func_args: processing func args for event type in sse proto
    :param data_process_func: processing func for data type in sse proto, both async and sync func are supported
    :param data_func_args: processing func args for data type in sse proto
    :param custom_errors: custom errors for event_process_func or data_process_func will be raised
    :return:
    """
    try:
        async with ClientSession() as session:
            async with session.request(
                    method,
                    url,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=ClientTimeout(total=timeout)  # timeout: total timeout in seconds(include connecting)
            ) as response:
                while True:
                    line = await response.content.readline()
                    if not line:
                        break
                    line = line.decode().strip()
                    if not line:
                        # ignore empty line
                        continue
                    if line.startswith("data:"):
                        data = line.replace("data: ", "")
                        if data == '[DONE]':
                            break
                        data = json.loads(data)
                        if data_process_func:
                            if not data_func_args:
                                data_func_args = []
                            if iscoroutinefunction(data_process_func):
                                await data_process_func(data, *data_func_args)
                                continue
                            data_process_func(data, *data_func_args)
                    elif line.startswith("event:"):
                        if event_process_func:
                            if not event_func_args:
                                event_func_args = []
                            if iscoroutinefunction(event_process_func):
                                await event_process_func(
                                    json.loads(line.replace("event: ", "")),
                                    *event_func_args
                                )
                                continue
                            event_process_func(json.loads(
                                line.replace("event: ", "")), *event_func_args)
                await response.release()
    except asyncio.TimeoutError as e:
        logger.error("request to %s timeout after %s seconds, error: %s", url, timeout, e)
        raise RequestTimeoutError(f"request timeout: {e}")
    except Exception as e:
        logger.error("request to %s failed, error: %s", url, e)
        if not custom_errors:
            raise InternalError(f"request to {url} failed, error: {e}")

        for custom_error_type in custom_errors:
            if isinstance(e, custom_error_type):
                raise e
        raise InternalError(
            f"request to {url} failed and no matching custom error found, got error type: {type(e)},"
            f" custom error types: [{','.join([str(custom_error) for custom_error in custom_errors])}],"
            f" error: {e}")


async def _request(
        method: str,
        url: str,
        data: Any = None,
        json_data: Any = None,
        headers: dict = None,
        timeout: int = 300,
        **kwargs
) -> BaseResponse:
    try:
        async with ClientSession() as session:
            async with session.request(
                    method,
                    url,
                    data=data,
                    json=json_data,
                    headers=headers,
                    # timeout: total timeout in seconds(include connecting)
                    timeout=ClientTimeout(total=timeout),
                    **kwargs
            ) as response:
                try:
                    data = await response.json()
                except ContentTypeError:
                    data = await response.read()
                return BaseResponse(code=response.status, data=data)
    except asyncio.TimeoutError as e:
        logger.error(f"request to {url} failed cause timeout after {timeout} seconds, error: {e}")
        raise RequestTimeoutError(f"request timeout: {e}")
    except Exception as e:
        logger.error(f"request to {url} failed, error: {e}")
        raise InternalError(f"request to {url} error: {e}")
