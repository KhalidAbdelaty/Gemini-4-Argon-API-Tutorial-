"""Aggregation and reporting."""

from dataclasses import asdict, dataclass


@dataclass
class CustomerReport:
    customer_id: str
    events: int
    sessions: int
    longest_session: int
    avg_session_seconds: int
    purchases: int
    gross_cents: int
    refunded_cents: int
    net_cents: int
    rejected_refunds: int
    top_page: str | None
    first_seen: int | None
    last_seen: int | None


def build_report(state) -> CustomerReport:
    s = state.summary
    sessions = s.sessions
    num_sessions = len(sessions)
    if num_sessions:
        total_duration = 0
        longest_session = 0
        for x in sessions:
            total_duration += x.end_ts - x.start_ts
            if x.events > longest_session:
                longest_session = x.events
        avg_session_seconds = total_duration // num_sessions
    else:
        longest_session = 0
        avg_session_seconds = 0

    page_counts = s.page_counts
    if page_counts:
        top_page = None
        top_count = -1
        for page, count in page_counts.items():
            if count > top_count or (count == top_count and (top_page is None or page < top_page)):
                top_page = page
                top_count = count
    else:
        top_page = None

    return CustomerReport(
        customer_id=state.customer_id,
        events=s.events,
        sessions=num_sessions,
        longest_session=longest_session,
        avg_session_seconds=avg_session_seconds,
        purchases=len(s.purchases),
        gross_cents=s.gross_cents,
        refunded_cents=s.refunded_cents,
        net_cents=s.gross_cents - s.refunded_cents,
        rejected_refunds=s.rejected_refunds,
        top_page=top_page,
        first_seen=s.first_seen,
        last_seen=s.last_seen,
    )


def totals(reports: dict) -> dict:
    """Roll customer reports up into one dict of totals."""
    events = 0
    sessions = 0
    purchases = 0
    gross_cents = 0
    refunded_cents = 0
    net_cents = 0
    rejected_refunds = 0
    for report in reports.values():
        events += report.events
        sessions += report.sessions
        purchases += report.purchases
        gross_cents += report.gross_cents
        refunded_cents += report.refunded_cents
        net_cents += report.net_cents
        rejected_refunds += report.rejected_refunds
    return {
        "events": events,
        "sessions": sessions,
        "purchases": purchases,
        "gross_cents": gross_cents,
        "refunded_cents": refunded_cents,
        "net_cents": net_cents,
        "rejected_refunds": rejected_refunds,
        "customers": len(reports),
    }
