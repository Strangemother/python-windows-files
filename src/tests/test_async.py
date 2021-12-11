import asyncio
import aiounittest


async def add(x, y):
    await asyncio.sleep(0.1)
    return x + y


class MyTest(aiounittest.AsyncTestCase):

    async def test_async_add(self):
        ret = await add(5, 6)
        self.assertEqual(ret, 11)

    # # or 3.4 way
    # @asyncio.coroutine
    # def test_sleep(self):
    #     ret = yield from add(5, 6)
    #     self.assertEqual(ret, 11)

    # some regular test code
    def test_something(self):
        self.assertTrue(True)
