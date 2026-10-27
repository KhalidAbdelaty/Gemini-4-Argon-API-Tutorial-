"""Event-history processing: sessions, revenue, and page activity."""

from dataclasses import dataclass, field

SESSION_GAP_SECONDS = 30 * 60


@dataclass
class Session:
    start_ts: int
    end_ts: int
    events: int


@dataclass
class Summary:
    sessions: list = field(default_factory=list)
    purchases: dict = field(default_factory=dict)   # purchase id -> amount
    refunded: dict = field(default_factory=dict)    # purchase id -> refunded so far
    gross_cents: int = 0
    refunded_cents: int = 0
    rejected_refunds: int = 0
    page_counts: dict = field(default_factory=dict)
    first_seen: int | None = None
    last_seen: int | None = None
    events: int = 0


def summarize(events) -> Summary:
    """Summarize one customer's events, which must be in processing order.

    Sessions split when two consecutive events are more than 30 minutes
    apart. A refund applies only to a purchase processed before it, and is
    capped at the amount still unrefunded on that purchase. A refund with
    nothing left to apply counts as rejected. This function does not modify
    the events it receives.
    """
    sessions = []
    purchases = {}
    refunded = {}
    gross_cents = 0
    refunded_cents = 0
    rejected_refunds = 0
    page_counts = {}
    num_events = 0
    current = None

    for event in events:
        num_events += 1
        ts = event.ts
        if current is not None and ts - current.end_ts <= SESSION_GAP_SECONDS:
            current.end_ts = ts
            current.events += 1
        else:
            current = Session(start_ts=ts, end_ts=ts, events=1)
            sessions.append(current)

        kind = event.kind
        if kind == "activity":
            page = event.page.strip().lower()
            page_counts[page] = page_counts.get(page, 0) + 1
        elif kind == "purchase":
            amount = event.amount_cents
            purchases[event.event_id] = amount
            gross_cents += amount
        elif kind == "refund":
            ref = event.ref
            original = purchases.get(ref)
            if original is None:
                rejected_refunds += 1
                continue
            already = refunded.get(ref, 0)
            applied = min(event.amount_cents, original - already)
            if applied <= 0:
                rejected_refunds += 1
                continue
            refunded[ref] = already + applied
            refunded_cents += applied

    if current is not None:
        first_seen = sessions[0].start_ts
        last_seen = current.end_ts
    else:
        first_seen = None
        last_seen = None

    return Summary(
        sessions=sessions,
        purchases=purchases,
        refunded=refunded,
        gross_cents=gross_cents,
        refunded_cents=refunded_cents,
        rejected_refunds=rejected_refunds,
        page_counts=page_counts,
        first_seen=first_seen,
        last_seen=last_seen,
        events=num_events,
    )
