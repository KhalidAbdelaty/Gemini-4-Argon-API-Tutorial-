"""Event model and validation."""

from dataclasses import dataclass, field

KINDS = ("activity", "purchase", "refund")
_KNOWN_FIELDS = frozenset(("event_id", "customer_id", "ts", "kind", "page", "amount_cents", "ref"))


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


def validate(raw: dict, seq: int) -> Event:
    """Build an Event from a raw dict without modifying the dict."""
    for key in ("event_id", "customer_id", "ts", "kind"):
        if key not in raw:
            raise ValidationError(f"missing field: {key}")
    kind = raw["kind"]
    if kind not in KINDS:
        raise ValidationError(f"unknown kind: {kind!r}")
    ts = raw["ts"]
    if not isinstance(ts, int) or ts < 0:
        raise ValidationError("ts must be a non-negative integer")

    page = raw.get("page")
    amount = raw.get("amount_cents", 0)
    ref = raw.get("ref")
    if kind == "activity":
        if not isinstance(page, str) or not page.strip():
            raise ValidationError("activity events need a page")
    else:
        if not isinstance(amount, int) or amount <= 0:
            raise ValidationError(f"{kind} events need a positive amount_cents")
    if kind == "refund" and not ref:
        raise ValidationError("refund events need a ref to a purchase")

    metadata = {k: v for k, v in raw.items() if k not in _KNOWN_FIELDS}
    return Event(
        event_id=str(raw["event_id"]),
        customer_id=str(raw["customer_id"]),
        ts=ts,
        kind=kind,
        seq=seq,
        page=page,
        amount_cents=amount if kind != "activity" else 0,
        ref=ref,
        metadata=metadata,
    )
