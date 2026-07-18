from fastkit_tasks.queue import TaskQueue


class TaskContext:
    """Handed to a task handler so it can report progress and extend its lease."""

    def __init__(self, queue: TaskQueue, execution, worker_id: str, lease_seconds: int):
        self.queue = queue
        self.execution = execution
        self.worker_id = worker_id
        self._lease_seconds = lease_seconds

    async def heartbeat(
        self, progress: int | None = None, message: str | None = None
    ) -> None:
        await self.queue.heartbeat(
            self.execution.id, self.worker_id, self._lease_seconds, progress, message
        )
