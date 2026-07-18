import logging

logger = logging.getLogger("demo.tasks")


async def send_welcome_email(context, payload):
    logger.info("welcome email queued for delivery (%s)", payload)

    return {
        "sent": True,
        "template": payload.get("template"),
        "locale": payload.get("locale"),
    }


async def sync(context, payload):
    return {"synced": True}


def setup_tasks(registry, file_service) -> None:
    async def cleanup_orphan_files(context, payload):
        removed = await file_service.cleanup_orphans()

        return {"removed": removed}

    registry.task("demo.send_welcome_email", queue="emails")(send_welcome_email)
    registry.task("demo.cleanup")(cleanup_orphan_files)
    registry.task("demo.sync")(sync)
