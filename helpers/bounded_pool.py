"""A few threads of its own for work that holds a lot of memory while it runs, so a burst of requests waits for them instead of each holding its share at once."""

import asyncio
import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


class BoundedPool:
    """Work run away from the loop on at most a fixed number of threads, with the context of the request that asked for it, the way `asyncio.to_thread` runs it."""

    def __init__(self, workers: int, name: str):
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)

    async def run(self, function: Callable, *arguments):
        context = contextvars.copy_context()

        return await asyncio.get_running_loop().run_in_executor(self.executor, context.run, function, *arguments)
