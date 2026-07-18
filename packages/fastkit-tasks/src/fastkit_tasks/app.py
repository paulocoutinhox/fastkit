import asyncio

from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_tasks.models import ScheduledTask, TaskAttempt, TaskExecution
from fastkit_tasks.queue import TaskQueue
from fastkit_tasks.registry import TaskRegistry
from fastkit_tasks.scheduler import Scheduler
from fastkit_tasks.worker import Worker


class TasksApp(FastKitApp):
    name = "fastkit.tasks"
    label = "tasks"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(ScheduledTask, source=self.name)
        context.models.register(TaskExecution, source=self.name)
        context.models.register(TaskAttempt, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")

        registry = TaskRegistry()
        queue = TaskQueue(database, registry=registry)
        scheduler = Scheduler(database, queue)

        context.set_component("task_registry", registry)
        context.set_component("task_queue", queue)
        context.set_component("task_scheduler", scheduler)

    async def startup(self, context: BootstrapContext) -> None:
        config = context.settings.tasks

        if not config.run_worker:
            return

        registry = context.component("task_registry")
        worker = Worker(
            context.component("task_queue"),
            registry,
            context.component("database"),
            worker_id=config.worker_id,
            queues=config.worker_queues or registry.queues(),
            lease_seconds=config.worker_lease_seconds,
        )
        self._worker_task = asyncio.create_task(worker.run(config.poll_interval_seconds, context.component("task_scheduler")))

    async def shutdown(self, context: BootstrapContext) -> None:
        task = getattr(self, "_worker_task", None)

        if task is None:
            return

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
