"""Visible functional tests for EventFlow."""

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures"))

from generate import generate_events  # noqa: E402

from eventflow import EventFlow, ValidationError  # noqa: E402


def act(eid, cid, ts, page="home"):
    return {"event_id": eid, "customer_id": cid, "ts": ts, "kind": "activity", "page": page}


def buy(eid, cid, ts, amount):
    return {"event_id": eid, "customer_id": cid, "ts": ts, "kind": "purchase", "amount_cents": amount}


def refund(eid, cid, ts, ref, amount):
    return {"event_id": eid, "customer_id": cid, "ts": ts, "kind": "refund",
            "ref": ref, "amount_cents": amount}


def run(events):
    engine = EventFlow()
    engine.ingest(events)
    return engine


def test_unknown_kind_is_rejected():
    with pytest.raises(ValidationError):
        run([{"event_id": "x", "customer_id": "a", "ts": 1, "kind": "click"}])


def test_purchase_needs_positive_amount():
    with pytest.raises(ValidationError):
        run([buy("p1", "a", 10, 0)])


def test_ingest_returns_accepted_count():
    engine = EventFlow()
    assert engine.ingest([act("e1", "a", 1), act("e1", "a", 2), act("e2", "a", 3)]) == 2


def test_duplicate_event_is_ignored():
    report = run([buy("p1", "a", 10, 500), buy("p1", "a", 20, 500)]).report_for("a")
    assert report.events == 1 and report.gross_cents == 500


def test_sessions_split_after_thirty_minutes():
    report = run([act("e1", "a", 0), act("e2", "a", 1800), act("e3", "a", 3601)]).report_for("a")
    assert report.sessions == 2 and report.longest_session == 2


def test_refund_is_capped_at_purchase_amount():
    report = run([buy("p1", "a", 10, 1000), refund("r1", "a", 20, "p1", 1500)]).report_for("a")
    assert report.refunded_cents == 1000 and report.net_cents == 0


def test_refund_for_unknown_purchase_is_rejected():
    report = run([refund("r1", "a", 5, "nope", 100)]).report_for("a")
    assert report.rejected_refunds == 1 and report.refunded_cents == 0


def test_top_page_breaks_ties_alphabetically():
    report = run([act("e1", "a", 1, "search"), act("e2", "a", 2, "Cart")]).report_for("a")
    assert report.top_page == "cart"


def test_customers_are_reported_separately():
    reports = run([buy("p1", "a", 1, 700), buy("p2", "b", 2, 300)]).report()
    assert reports["a"].gross_cents == 700 and reports["b"].gross_cents == 300


def test_events_in_one_batch_are_processed_by_timestamp():
    report = run([refund("r1", "a", 50, "p1", 200), buy("p1", "a", 10, 1000)]).report_for("a")
    assert report.refunded_cents == 200 and report.rejected_refunds == 0


def test_small_fixture_matches_known_digest():
    events = generate_events(customers=40, per_customer=(1, 30), seed=7,
                             dup_rate=0.03, shuffle_window=4)
    rows = [asdict(r) for r in run(events).report().values()]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    assert digest == "befa182a55521056a3b07594f811f3bd05e05a20be21de0d6cf8976a042a99e0"
