"""Event model and validation."""

from dataclasses import dataclass, field

KINDS = ("activity", "purchase", "refund")


class ValidationError(ValueError):
    """Raised when a raw event does not match the EventFlow schema."""


@dataclass
class Event:
    """One validated event.

    ``seq`` is the arrival position assigned by the engine. It breaks ties
    between events that share a timestamp, so equal timestamps keep their
    arrival order.
    """

    event_id: str
    customer_id: str
    ts: int
    kind: str
    seq: int
    page: str | None = None
    amount_cents: int = 0
    ref: str | None = None
    metadata: dict = field(default_factory=dict)


_KNOWN_KEYS = frozenset(("event_id", "customer_id", "ts", "kind", "page", "amount_cents", "ref"))


def validate(raw: dict, seq: int) -> Event:
    """Build an Event from a raw dict without modifying the dict."""
    try:
        event_id = raw["event_id"]
        customer_id = raw["customer_id"]
        ts = raw["ts"]
        kind = raw["kind"]
    except KeyError as exc:
        raise ValidationError(f"missing field: {exc.args[0]}") from None

    if kind not in KINDS:
        raise ValidationError(f"unknown kind: {kind!r}")
    if not isinstance(ts, int) or ts < 0:
        raise ValidationError("ts must be a non-negative integer")

    page = raw.get("page")
    ref = raw.get("ref")
    if kind == "activity":
        if not isinstance(page, str) or not page.strip():
            raise ValidationError("activity events need a page")
        amount = 0
    else:
        amount = raw.get("amount_cents", 0)
        if not isinstance(amount, int) or amount <= 0:
            raise ValidationError(f"{kind} events need a positive amount_cents")
        if kind == "refund" and not ref:
            raise ValidationError("refund events need a ref to a purchase")

    metadata = {k: v for k, v in raw.items() if k not in _KNOWN_KEYS}
    return Event(
        event_id=str(event_id),
        customer_id=str(customer_id),
        ts=ts,
        kind=kind,
        seq=seq,
        page=page,
        amount_cents=amount,
        ref=ref,
        metadata=metadata,
    )
