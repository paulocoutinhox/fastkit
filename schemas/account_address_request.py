from schemas.address_fields import AddressFields


class AccountAddressRequest(AddressFields):
    """The account writes its own address, so the owner is the session and never a field of the payload."""
