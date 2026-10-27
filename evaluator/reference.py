"""Independent reference implementation of the EventFlow contract.

Written separately from the application. It processes events in one pass per
customer, so it is fast enough to grade large hidden fixtures.
"""

GAP = 30 * 60


def reference_reports(batches):
    """batches: list of lists of raw event dicts, in ingest order."""
    seen, rows, seq = {}, {}, 0
    for batch in batches:
        for raw in batch:
            cid, eid = str(raw["customer_id"]), str(raw["event_id"])
            ids = seen.setdefault(cid, set())
            if eid not in ids:
                ids.add(eid)
                rows.setdefault(cid, []).append((raw["ts"], seq, raw))
            seq += 1
    return {cid: _report(cid, sorted(rows[cid], key=lambda r: (r[0], r[1]))) for cid in sorted(rows)}


def _report(cid, ordered):
    sessions = []                      # [start, end, count]
    purchases, refunded, pages = {}, {}, {}
    gross = refunded_total = rejected = 0
    for ts, _, raw in ordered:
        if sessions and ts - sessions[-1][1] <= GAP:
            sessions[-1][1] = ts
            sessions[-1][2] += 1
        else:
            sessions.append([ts, ts, 1])
        kind = raw["kind"]
        if kind == "activity":
            page = raw["page"].strip().lower()
            pages[page] = pages.get(page, 0) + 1
        elif kind == "purchase":
            purchases[str(raw["event_id"])] = raw["amount_cents"]
            gross += raw["amount_cents"]
        else:
            ref = raw["ref"]
            left = purchases.get(ref, 0) - refunded.get(ref, 0)
            if ref not in purchases or left <= 0:
                rejected += 1
                continue
            applied = min(raw["amount_cents"], left)
            refunded[ref] = refunded.get(ref, 0) + applied
            refunded_total += applied
    durations = [end - start for start, end, _ in sessions]
    top = min(pages.items(), key=lambda kv: (-kv[1], kv[0]))[0] if pages else None
    return {"customer_id": cid, "events": len(ordered), "sessions": len(sessions),
            "longest_session": max((n for _, _, n in sessions), default=0),
            "avg_session_seconds": sum(durations) // len(durations) if durations else 0,
            "purchases": len(purchases), "gross_cents": gross, "refunded_cents": refunded_total,
            "net_cents": gross - refunded_total, "rejected_refunds": rejected,
            "top_page": top, "first_seen": ordered[0][0] if ordered else None,
            "last_seen": ordered[-1][0] if ordered else None}
