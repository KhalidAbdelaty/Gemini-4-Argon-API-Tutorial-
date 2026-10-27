"""Measure the original EventFlow before any model touches it.

Writes results/baseline/: tests.txt, bench.json, profile_long.txt,
tool_baseline.json (what run_benchmark compares against), scaling.json.
"""

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "baseline"
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
ENV.pop("GEMINI_API_KEY", None)


def sh(*cmd, cwd=ROOT):
    return subprocess.run([sys.executable, *cmd], cwd=cwd, env=ENV, capture_output=True,
                          text=True, timeout=1800)


def scaling():
    """Same 1,600 events, split into longer and longer customer histories."""
    sys.path.insert(0, str(ROOT / "starter" / "fixtures"))
    sys.path.insert(0, str(ROOT / "starter"))
    from generate import generate_events  # noqa: PLC0415
    from eventflow import EventFlow  # noqa: PLC0415
    rows = []
    for length in (20, 40, 80, 160):
        events = generate_events(customers=1600 // length, per_customer=(length, length), seed=505)
        samples = []
        for _ in range(3):
            start = time.perf_counter()
            engine = EventFlow()
            engine.ingest(events)
            engine.report()
            samples.append(time.perf_counter() - start)
        rows.append({"history_length": length, "customers": 1600 // length,
                     "events": len(events), "median_s": round(statistics.median(samples), 4)})
        print(rows[-1], flush=True)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tests = sh("-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", cwd=ROOT / "starter")
    (OUT / "tests.txt").write_text(tests.stdout + tests.stderr)
    print(tests.stdout.strip().splitlines()[-1])

    tool = {}
    for w in ("short", "long", "mixed"):
        data = json.loads(sh("bench/runner.py", "--repo", "starter", "--mode", "time",
                             "--workload", w, "--warmups", "1", "--repeats", "3").stdout)
        tool[w] = {"median_s": data["median_s"], "digest": data["digest"]}
    (OUT / "tool_baseline.json").write_text(json.dumps(tool, indent=2))

    prof = json.loads(sh("bench/runner.py", "--repo", "starter", "--mode", "profile",
                         "--workload", "long", "--top", "12").stdout)
    (OUT / "profile_long.txt").write_text(prof["top_by_cumulative"] + "\n\n" + prof["top_by_tottime"] + "\n")

    bench = sh("scripts/benchmark.py", "--repo", "starter", "--label", "baseline",
               "--out", str(OUT / "bench.json"))
    print(bench.stdout.strip())
    (OUT / "scaling.json").write_text(json.dumps(scaling(), indent=2))


if __name__ == "__main__":
    main()
