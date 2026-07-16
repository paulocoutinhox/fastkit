import logging

logger = logging.getLogger("demo.tasks")


async def send_welcome_email(context, payload):
    logger.info("welcome email queued for delivery (%s)", payload)

    return {"sent": True, "template": payload.get("template"), "locale": payload.get("locale")}


async def cleanup(context, payload):
    return {"removed": 0}


async def sync(context, payload):
    return {"synced": True}


def setup_tasks(registry) -> None:
    registry.task("demo.send_welcome_email", queue="emails")(send_welcome_email)
    registry.task("demo.cleanup")(cleanup)
    registry.task("demo.sync")(sync)
