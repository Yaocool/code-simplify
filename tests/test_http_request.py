import asyncio
from contextlib import asynccontextmanager

import pytest
from aiohttp import web

from code_simplify.http_utils.http_request import http_get, http_post, sse_handler
from code_simplify.models.errors import Error


@asynccontextmanager
async def local_http_server():
    async def echo(request):
        if request.method == 'POST':
            return web.json_response(await request.json())
        return web.json_response({'header': request.headers.get('X-Test')})

    async def stream(request):
        return web.Response(
            body=(b'event: {"kind":"start"}\n\ndata: {"value":1}\n\n'
                  b'data: [DONE]\n\ndata: {"value":2}\n\n'),
            content_type='text/event-stream',
        )

    async def binary(request):
        return web.Response(body=b'raw bytes', content_type='application/octet-stream')

    app = web.Application()
    app.router.add_get('/echo', echo)
    app.router.add_post('/echo', echo)
    app.router.add_get('/stream', stream)
    app.router.add_get('/binary', binary)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, '127.0.0.1', 0).start()
        address = runner.addresses[0]
        assert isinstance(address, tuple)
        yield f'http://127.0.0.1:{address[1]}'
    finally:
        await runner.cleanup()


def test_http_json_and_binary_responses():
    async def check():
        async with local_http_server() as url:
            response = await http_get(url + '/echo', headers={'X-Test': 'ok'})
            assert response.code == 200
            assert response.data == {'header': 'ok'}
            response = await http_post(url + '/echo', json_data={'value': 1})
            assert response.code == 200
            assert response.data == {'value': 1}
            response = await http_get(url + '/binary')
            assert response.code == 200
            assert response.data == b'raw bytes'

    asyncio.run(check())


@pytest.mark.parametrize('async_event', [False, True])
@pytest.mark.parametrize('async_data', [False, True])
def test_sse_sync_and_async_callbacks_stop_at_done(async_event, async_data):
    async def check():
        received = []

        def record(data, marker):
            received.append((marker, data))

        async def record_async(data, marker):
            record(data, marker)

        async with local_http_server() as url:
            await sse_handler(
                'GET', url + '/stream',
                event_process_func=record_async if async_event else record,
                event_func_args=['event'],
                data_process_func=record_async if async_data else record,
                data_func_args=['data'],
            )
        assert received == [('event', {'kind': 'start'}), ('data', {'value': 1})]

    asyncio.run(check())


def test_sse_preserves_custom_callback_error():
    expected = Error(400, 'callback failure')

    def fail(data):
        raise expected

    async def check():
        async with local_http_server() as url:
            with pytest.raises(Error) as caught:
                await sse_handler('GET', url + '/stream', data_process_func=fail, custom_errors=[Error])
            assert caught.value is expected

    asyncio.run(check())
