from enums.email import OutboundEmailStatus
from jobs.email import send_pending_emails
from services.email import email_service


async def test_the_job_sends_what_the_queue_holds(db, tenant):
    record = await email_service.queue(db, tenant.id, "reader@acme.com", "Olá", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")

    await send_pending_emails()

    await db.refresh(record)

    assert record.status == OutboundEmailStatus.SENT


async def test_the_job_sweeps_what_a_dead_node_left_before_it_sends(db, tenant):
    """One write over the whole table belongs where a single node runs it, and that is the job and not the pass."""
    from datetime import timedelta

    from helpers.dates import now
    from services import email as email_module

    record = await email_service.queue(db, tenant.id, "reader@acme.com", "Olá", "password_reset", token="abc", hours=1, link="https://acme.com/account/password-reset/abc")
    await email_service.claim(db, record.id)

    record.updated_at = now() - email_module.ABANDONED_AFTER - timedelta(minutes=1)
    await db.commit()

    await send_pending_emails()
    await db.refresh(record)

    assert record.status == OutboundEmailStatus.SENT
