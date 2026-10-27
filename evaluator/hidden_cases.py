"""Hidden acceptance cases. Run in a separate process against a frozen candidate.

Usage: python evaluator/hidden_cases.py  (with PYTHONPATH pointing at the candidate)
Prints one JSON object with a pass/fail entry per case.
"""

import copy
import json
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "starter" / "fixtures"))

from generate import generate_events  # noqa: E402
from reference import reference_reports  # noqa: E402

from eventflow import EventFlow, ValidationError  # noqa: E402


def as_rows(reports):
    return {cid: asdict(r) for cid, r in reports.items()}


def ev(eid, cid, ts, kind="activity", **extra):
    base = {"event_id": eid, "customer_id": cid, "ts": ts, "kind": kind}
    if kind == "activity":
        base["page"] = extra.pop("page", "home")
    base.update(extra)
    return base


def check_batches(batches, report_between=True):
    engine = EventFlow()
    for i, batch in enumerate(batches, 1):
        engine.ingest(batch)
        if report_between or i == len(batches):
            got, want = as_rows(engine.report()), reference_reports(batches[:i])
            if got != want:
                bad = sorted(c for c in set(got) | set(want) if got.get(c) != want.get(c))
                return False, f"after batch {i}: {len(bad)} customers differ, e.g. {bad[:3]}"
    return True, "matches reference"


def case_differential(seed):
    events = generate_events(customers=60, per_customer=(1, 80), seed=seed, dup_rate=0.05,
                             shuffle_window=12, refund_rate=0.15)
    return check_batches([events])


def case_long_history():
    events = generate_events(customers=3, per_customer=(300, 300), seed=9201, refund_rate=0.12,
                             dup_rate=0.02, shuffle_window=6)
    return check_batches([events])


def case_incremental_batches():
    events = generate_events(customers=25, per_customer=(5, 60), seed=9301, dup_rate=0.04,
                             shuffle_window=5, refund_rate=0.15)
    size = len(events) // 5 + 1
    return check_batches([events[i:i + size] for i in range(0, len(events), size)])


def case_late_batch_with_earlier_timestamps():
    first = [ev("r1", "a", 500, "refund", ref="p1", amount_cents=300), ev("v1", "a", 600)]
    second = [ev("p1", "a", 100, "purchase", amount_cents=1000), ev("v0", "a", 50, page="Cart")]
    return check_batches([first, second])


def case_duplicates_first_copy_wins():
    first = [ev("p1", "a", 100, "purchase", amount_cents=900), ev("v1", "a", 110, page="help")]
    second = [ev("p1", "a", 20, "purchase", amount_cents=5), ev("v1", "a", 115, page="cart"),
              ev("v1", "b", 115, page="cart")]
    return check_batches([first, second])


def case_equal_timestamps_keep_arrival_order():
    batch = [ev("r1", "a", 100, "refund", ref="p1", amount_cents=100),
             ev("p1", "a", 100, "purchase", amount_cents=400),
             ev("r2", "a", 100, "refund", ref="p1", amount_cents=100)]
    return check_batches([batch])


def case_history_is_owned_by_caller():
    engine = EventFlow()
    engine.ingest([ev("v1", "a", 1, device="web"), ev("p1", "a", 2, "purchase", amount_cents=700)])
    before_report, before_hist = as_rows(engine.report()), [asdict(e) for e in engine.history("a")]
    snapshot = engine.history("a")
    snapshot[0].page = "MUTATED"
    snapshot[0].metadata["device"] = "MUTATED"
    snapshot[1].amount_cents = 1
    snapshot.clear()
    engine.ingest([ev("v2", "a", 3)])
    want = reference_reports([[ev("v1", "a", 1, device="web"),
                               ev("p1", "a", 2, "purchase", amount_cents=700), ev("v2", "a", 3)]])
    hist_ok = [asdict(e) for e in engine.history("a")][:2] == before_hist
    ok = hist_ok and as_rows(engine.report()) == want and before_report["a"]["gross_cents"] == 700
    return ok, "history snapshot isolated" if ok else "mutating a history snapshot changed engine state"


def case_reports_are_owned_by_caller():
    engine = EventFlow()
    engine.ingest([ev("p1", "a", 1, "purchase", amount_cents=500)])
    first = engine.report()
    first["a"].gross_cents = 0
    first["a"].top_page = "MUTATED"
    first.clear()
    again = as_rows(engine.report())
    ok = again == reference_reports([[ev("p1", "a", 1, "purchase", amount_cents=500)]])
    return ok, "report objects isolated" if ok else "mutating a report changed later reports"


def case_raw_events_not_modified():
    events = generate_events(customers=10, per_customer=(5, 20), seed=9401, dup_rate=0.05)
    frozen = copy.deepcopy(events)
    EventFlow().ingest(events)
    ok = events == frozen
    return ok, "inputs untouched" if ok else "ingest() modified the raw event dicts"


def case_engines_are_isolated():
    one, two = EventFlow(), EventFlow()
    one.ingest([ev("v1", "a", 1), ev("p1", "b", 2, "purchase", amount_cents=50)])
    two.ingest([ev("v1", "a", 5)])
    ok = (two.customers() == ["a"] and two.report_for("a").events == 1
          and one.report_for("a").events == 1 and one.customers() == ["a", "b"])
    return ok, "engines independent" if ok else "state leaked between engine instances"


def case_validation_still_raises():
    try:
        EventFlow().ingest([ev("r1", "a", 1, "refund", amount_cents=10)])
    except ValidationError:
        return True, "refund without ref rejected"
    return False, "invalid refund was accepted"


CASES = {
    "differential_seed_9101": lambda: case_differential(9101),
    "differential_seed_9102": lambda: case_differential(9102),
    "differential_seed_9103": lambda: case_differential(9103),
    "long_history_differential": case_long_history,
    "incremental_batches_with_reports": case_incremental_batches,
    "late_batch_with_earlier_timestamps": case_late_batch_with_earlier_timestamps,
    "duplicates_first_copy_wins": case_duplicates_first_copy_wins,
    "equal_timestamps_keep_arrival_order": case_equal_timestamps_keep_arrival_order,
    "history_snapshot_owned_by_caller": case_history_is_owned_by_caller,
    "reports_owned_by_caller": case_reports_are_owned_by_caller,
    "raw_events_not_modified": case_raw_events_not_modified,
    "engines_are_isolated": case_engines_are_isolated,
    "validation_still_raises": case_validation_still_raises,
}


def main():
    results = {}
    for name, fn in CASES.items():
        try:
            ok, detail = fn()
        except Exception:  # noqa: BLE001
            ok, detail = False, traceback.format_exc(limit=3)[-600:]
        results[name] = {"passed": bool(ok), "detail": detail}
    print(json.dumps(results))


if __name__ == "__main__":
    main()
