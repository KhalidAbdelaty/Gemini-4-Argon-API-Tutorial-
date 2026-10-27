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
    durations = [x.end_ts - x.start_ts for x in sessions]
    if s.page_counts:
        top_page = sorted(s.page_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    else:
        top_page = None
    return CustomerReport(
        customer_id=state.customer_id,
        events=s.events,
        sessions=len(sessions),
        longest_session=max((x.events for x in sessions), default=0),
        avg_session_seconds=(sum(durations) // len(durations)) if durations else 0,
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
    keys = ("events", "sessions", "purchases", "gross_cents", "refunded_cents",
            "net_cents", "rejected_refunds")
    out = {k: 0 for k in keys}
    for report in reports.values():
        row = asdict(report)
        for k in keys:
            out[k] += row[k]
    out["customers"] = len(reports)
    return out
