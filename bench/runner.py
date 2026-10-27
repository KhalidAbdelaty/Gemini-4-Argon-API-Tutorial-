"""Protected measurement runner. Lives outside the repository the agent edits.

Usage: python bench/runner.py --repo PATH --mode time|memory|profile --workload NAME

Timing, profiling, and memory tracing run in separate processes, so neither
cProfile nor tracemalloc ever slows down a timed run.
"""

import argparse
import cProfile
import hashlib
import io
import json
import os
import pstats
import statistics
import sys
import sysconfig
import time
import tracemalloc
from dataclasses import asdict
from pathlib import Path

PRISTINE_FIXTURES = Path(__file__).resolve().parents[1] / "starter" / "fixtures"


def load(repo):
    sys.path.insert(0, str(PRISTINE_FIXTURES))
    sys.path.insert(0, str(Path(repo).resolve()))
    from generate import build_workload  # noqa: PLC0415
    from eventflow import EventFlow  # noqa: PLC0415
    return build_workload, EventFlow


def run_once(EventFlow, events):
    engine = EventFlow()
    engine.ingest(events)
    return engine.report()


def digest(reports):
    rows = [asdict(r) for r in reports.values()]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def mode_time(EventFlow, events, warmups, repeats):
    for _ in range(warmups):
        run_once(EventFlow, events)
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        reports = run_once(EventFlow, events)
        samples.append(time.perf_counter() - start)
    return {"samples_s": [round(s, 4) for s in samples],
            "median_s": round(statistics.median(samples), 4),
            "digest": digest(reports)}


def mode_memory(EventFlow, events):
    tracemalloc.start()
    before, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    run_once(EventFlow, events)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"peak_tracked_kib": round((peak - before) / 1024, 1)}


def mode_profile(EventFlow, events, repo, top):
    profiler = cProfile.Profile()
    profiler.enable()
    run_once(EventFlow, events)
    profiler.disable()
    out = {}
    for key in ("cumulative", "tottime"):
        buf = io.StringIO()
        stats = pstats.Stats(profiler, stream=buf)
        stats.sort_stats(key).print_stats(top)
        text = buf.getvalue()
        text = _strip(text, str(Path(repo).resolve()), "")
        text = _strip(text, str(Path(__file__).resolve().parent), "<bench>/")
        text = _strip(text, sysconfig.get_paths()["stdlib"], "<stdlib>/")
        out[f"top_by_{key}"] = text[text.find("   ncalls"):].rstrip()
    return out


def _strip(text, prefix, label):
    """Shorten absolute paths in profiler output; Windows paths use backslashes."""
    for sep in {os.sep, "/"}:
        text = text.replace(prefix + sep, label)
    return text.replace("eventflow\\", "eventflow/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--mode", choices=["time", "memory", "profile"], required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    build_workload, EventFlow = load(args.repo)
    events = build_workload(args.workload)
    result = {"workload": args.workload, "raw_events": len(events)}
    if args.mode == "time":
        result.update(mode_time(EventFlow, events, args.warmups, args.repeats))
    elif args.mode == "memory":
        result.update(mode_memory(EventFlow, events))
    else:
        result.update(mode_profile(EventFlow, events, args.repo, args.top))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
