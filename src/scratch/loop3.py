import concurrent
import asyncio


DRIVES = [
    'C:/',
    'D:/',

]

def sync_to_async_main(*a, **kw):
    asyncio.run(main(*a, **kw))


async def main(*a, **kw):
    loop = asyncio.get_event_loop()
    await run_loop(loop, *a, **kw)
    print('End of main')
    loop.close()

from monitor import win as monitor

async def run_loop(loop, *a, **kw):
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [loop.run_in_executor(executor, monitor.start, i)
                   for i in DRIVES]
        result = await asyncio.gather(*futures)


if __name__ == "__main__":
    sync_to_async_main(DRIVES)
    #main(DRIVES)
