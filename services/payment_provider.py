import inspect

import httpx2

from models.integration import Integration
from services.credential import Credential
from services.inbound_call import InboundCall
from services.provider_event import ProviderEvent
from services.provider_purchase import ProviderPurchase


class PaymentProvider:
    """A gateway authenticates its call and reads it, and says what an account holds by whichever of the two ways it has."""

    # The gateway answers what an account holds right now, which is the reliable source and the one a safety net can use.
    queryable = False

    # The gateway only tells, and its own notice carries enough to say what the account holds.
    event_stated = False

    # What an operator has to paste, named the way the gateway names it, because a generic label sends them looking for a field that is not there.
    credentials: tuple[Credential, ...] = ()

    def __init_subclass__(cls, **kwargs) -> None:
        """A gateway that declares a capability it cannot honour fails here, and not halfway through a pass over somebody's subscription."""
        super().__init_subclass__(**kwargs)

        if not (cls.queryable or cls.event_stated):
            raise TypeError(f"{cls.__name__} says nothing about how it answers what an account holds")

        if cls.authenticate is PaymentProvider.authenticate:
            raise TypeError(f"{cls.__name__} does not implement authenticate, and nothing else proves the caller is the gateway")

        if cls.read is PaymentProvider.read:
            raise TypeError(f"{cls.__name__} does not implement read, and nothing else can say what a call was about")

        if cls.queryable and cls.state_from_query is PaymentProvider.state_from_query:
            raise TypeError(f"{cls.__name__} says it can be queried and does not implement state_from_query")

        # The caller does not wait for authenticate, so one written as a coroutine hands back an object nobody looks at: it never runs, it never raises, and every call from the internet is treated as signed.
        if inspect.iscoroutinefunction(cls.authenticate):
            raise TypeError(f"{cls.__name__} writes authenticate as a coroutine, and the caller does not wait for one, so nothing would ever prove the call came from the gateway")

        # These two are waited for, and a plain method answers a value where a coroutine is expected.
        unwaitable = sorted(name for name in ("read", "state_from_query") if not inspect.iscoroutinefunction(getattr(cls, name)))

        if unwaitable:
            raise TypeError(f"{cls.__name__} writes {unwaitable} without async, and the caller waits for what they answer")

        if not cls.credentials:
            raise TypeError(f"{cls.__name__} does not say what an operator has to paste for it")

        unknown = [credential.field for credential in cls.credentials if not hasattr(Integration, f"{credential.field}_encrypted")]

        if unknown:
            raise TypeError(f"{cls.__name__} asks for {sorted(unknown)}, which the integration has nowhere to keep")

        # Two credentials for one part leave the reader of that part picking whichever came first.
        played = [credential.role for credential in cls.credentials if credential.role]

        if len(played) != len(set(played)):
            raise TypeError(f"{cls.__name__} names more than one credential for the same part")

    def authenticate(self, integration: Integration, call: InboundCall, secret: str) -> None:
        raise NotImplementedError

    async def read(self, integration: Integration, call: InboundCall, client: httpx2.AsyncClient) -> ProviderEvent | None:
        """What the call was about, and the gateway is reachable from here because a notice that carries only an id is answered by asking."""
        raise NotImplementedError

    async def state_from_query(self, secret: str, token: str, client: httpx2.AsyncClient) -> list[ProviderPurchase]:
        raise NotImplementedError
