"""What the checkout hands the gateway as the address the buyer comes back to."""

import pytest

from services.checkout import checkout_service


@pytest.mark.parametrize(
    ("written", "sent"),
    [
        ("https://app.acme.com/ok", "https://app.acme.com/ok?purchase=P-1"),
        ("https://app.acme.com/ok?session={CHECKOUT_SESSION_ID}", "https://app.acme.com/ok?session={CHECKOUT_SESSION_ID}&purchase=P-1"),
        ("https://app.acme.com/ok?tag=a&tag=b&empty=", "https://app.acme.com/ok?tag=a&tag=b&empty=&purchase=P-1"),
        ("https://app.acme.com/ok?next=%2Fplans#top", "https://app.acme.com/ok?next=%2Fplans&purchase=P-1#top"),
    ],
)
def test_the_return_address_keeps_what_the_caller_wrote_and_adds_the_purchase(written, sent):
    """Stripe fills a literal placeholder, so an encoded brace is an address it never completes and a buyer who lands nowhere."""
    assert checkout_service.naming(written, "P-1") == sent
