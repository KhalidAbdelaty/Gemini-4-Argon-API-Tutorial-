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
    summary = Summary()
    current = None
    for event in events:
        summary.events += 1
        if summary.first_seen is None:
            summary.first_seen = event.ts
        summary.last_seen = event.ts

        if current is not None and event.ts - current.end_ts <= SESSION_GAP_SECONDS:
            current.end_ts = event.ts
            current.events += 1
        else:
            current = Session(start_ts=event.ts, end_ts=event.ts, events=1)
            summary.sessions.append(current)

        if event.kind == "activity":
            page = event.page.strip().lower()
            summary.page_counts[page] = summary.page_counts.get(page, 0) + 1
        elif event.kind == "purchase":
            summary.purchases[event.event_id] = event.amount_cents
            summary.gross_cents += event.amount_cents
        elif event.kind == "refund":
            original = summary.purchases.get(event.ref)
            if original is None:
                summary.rejected_refunds += 1
                continue
            already = summary.refunded.get(event.ref, 0)
            applied = min(event.amount_cents, original - already)
            if applied <= 0:
                summary.rejected_refunds += 1
                continue
            summary.refunded[event.ref] = already + applied
            summary.refunded_cents += applied
    return summary
