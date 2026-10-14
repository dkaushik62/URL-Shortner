"""PostgreSQL checkpoints without changing Windows' subprocess-capable loop.

psycopg async connections require SelectorEventLoop on Windows, while subprocess
support requires ProactorEventLoop. Threading synchronous database I/O preserves
both durable checkpoints and asynchronous model subprocesses on every platform.
"""
import asyncio

from langgraph.checkpoint.postgres import PostgresSaver


class ThreadedPostgresSaver(PostgresSaver):
    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        items = await asyncio.to_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for item in items:
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id):
        return await asyncio.to_thread(self.delete_thread, thread_id)
