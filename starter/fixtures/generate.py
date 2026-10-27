"""Deterministic synthetic workloads for EventFlow.

Every workload comes from a fixed seed, so the same name always produces the
same events in the same arrival order.
"""

import random

PAGES = ["home", "search", "product", "cart", "checkout", "account", "help",
         "Deals", " blog ", "Product"]
DEVICES = ["ios", "android", "web", "desktop"]

WORKLOADS = {
    # many customers, short histories
    "short": dict(customers=2000, per_customer=(5, 5), seed=101),
    # few customers, long histories
    "long": dict(customers=8, per_customer=(160, 160), seed=202),
    # mixed history lengths, interleaved arrivals, duplicates and refunds
    "mixed": dict(customers=300, per_customer=(1, 30), seed=303,
                  dup_rate=0.03, shuffle_window=8),
}


def _customer_events(rng, customer_id, n, start_ts, refund_rate):
    events, purchases = [], []
    ts = start_ts
    for i in range(n):
        ts += rng.randint(1801, 7200) if rng.random() < 0.08 else rng.randint(5, 600)
        event = {"event_id": f"{customer_id}-{i:05d}", "customer_id": customer_id,
                 "ts": ts, "device": rng.choice(DEVICES),
                 "attrs": {"ab": rng.randint(0, 3), "tags": [rng.randint(0, 9)]}}
        roll = rng.random()
        if roll < 0.12:
            event.update(kind="purchase", amount_cents=rng.randint(500, 20000))
            purchases.append(event)
        elif roll < 0.12 + refund_rate and purchases:
            target = rng.choice(purchases)
            share = rng.choice([1.0, 1.0, 0.5, 0.25, 1.4])
            event.update(kind="refund", ref=target["event_id"],
                         amount_cents=max(1, int(target["amount_cents"] * share)))
        elif roll < 0.13 + refund_rate:
            event.update(kind="refund", ref=f"{customer_id}-missing",
                         amount_cents=rng.randint(100, 900))
        else:
            event.update(kind="activity", page=rng.choice(PAGES))
        events.append(event)
    return events


def generate_events(customers, per_customer, seed, dup_rate=0.0,
                    shuffle_window=0, refund_rate=0.06):
    """Return raw event dicts in arrival order."""
    rng = random.Random(seed)
    stream = []
    for c in range(customers):
        cid = f"c{seed}-{c:05d}"
        n = rng.randint(*per_customer)
        stream.extend(_customer_events(rng, cid, n, rng.randint(0, 3600), refund_rate))
    stream.sort(key=lambda e: (e["ts"], e["customer_id"]))  # interleave customers
    if dup_rate:
        for _ in range(int(len(stream) * dup_rate)):
            i = rng.randrange(len(stream))
            j = rng.randrange(i, len(stream) + 1)
            stream.insert(j, dict(stream[i]))
    if shuffle_window:
        for start in range(0, len(stream), shuffle_window):
            chunk = stream[start:start + shuffle_window]
            rng.shuffle(chunk)
            stream[start:start + shuffle_window] = chunk
    return stream


def build_workload(name):
    return generate_events(**WORKLOADS[name])
