import asyncio
import threading
import time

from helpers.bounded_pool import BoundedPool
from helpers.i18n import current_locale
from helpers.security import hashing
from services.report_service import exporting
from services.upload_service import decoding


async def test_a_burst_of_work_waits_for_the_threads_of_its_pool_instead_of_running_all_at_once():
    pool = BoundedPool(2, "test")
    running, most = 0, 0
    guard = threading.Lock()

    def work():
        nonlocal running, most

        with guard:
            running += 1
            most = max(most, running)

        time.sleep(0.02)

        with guard:
            running -= 1

    await asyncio.gather(*(pool.run(work) for _ in range(8)))

    assert most == 2


async def test_the_work_reads_the_context_of_the_request_that_asked_for_it():
    token = current_locale.set("pt")

    try:
        assert await BoundedPool(1, "test").run(current_locale.get) == "pt"
    finally:
        current_locale.reset(token)


def test_decoding_hashing_and_exporting_each_run_on_a_pool_of_their_own_with_a_ceiling():
    pools = (decoding, hashing, exporting)

    assert len({id(pool.executor) for pool in pools}) == 3
    assert all(pool.executor._max_workers <= 4 for pool in pools)
