"""Published benchmark: fresh process per run, perf_counter only, no profiler.

Usage:
  python scripts/benchmark.py --repo starter --label baseline --out results/baseline_bench.json
  python scripts/benchmark.py --repo starter --repo results/medium/candidate --label baseline --label medium ...

With two or more repos, runs alternate between them so slow drift on the
machine hits every revision equally.
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "bench" / "runner.py"
WORKLOADS = ("short", "long", "mixed")


def child(repo, mode, workload, extra=()):
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PATH": ""}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):   # Windows needs these to start Python
        if key in os.environ:
            env[key] = os.environ[key]
    cmd = [sys.executable, str(RUNNER), "--repo", str(repo), "--mode", mode, "--workload", workload, *extra]
    done = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600, check=True)
    return json.loads(done.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--label", action="append", required=True)
    parser.add_argument("--runs", type=int, default=9)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    results = {label: {} for label in args.label}
    for workload in WORKLOADS:
        samples = {label: [] for label in args.label}
        digests = {}
        for i in range(args.runs):
            order = list(zip(args.label, args.repo))
            if i % 2:
                order.reverse()
            for label, repo in order:
                data = child(repo, "time", workload, ["--warmups", "1", "--repeats", "1"])
                samples[label].append(data["samples_s"][0])
                digests[label] = data["digest"]
        for label, repo in zip(args.label, args.repo):
            mem = child(repo, "memory", workload)
            s = sorted(samples[label])
            results[label][workload] = {
                "median_s": round(statistics.median(s), 4), "min_s": s[0], "max_s": s[-1],
                "runs": len(s), "samples_s": samples[label],
                "peak_tracked_kib": mem["peak_tracked_kib"], "digest": digests[label]}
        line = "  ".join(f"{lab}={results[lab][workload]['median_s']:.3f}s" for lab in args.label)
        print(f"{workload:6s} {line}", flush=True)

    meta = {"python": platform.python_version(), "machine": platform.machine(),
            "system": platform.system(), "runs_per_workload": args.runs,
            "method": "fresh process per run; 1 in-process warm-up; time.perf_counter(); "
                      "tracemalloc in a separate process"}
    Path(args.out).write_text(json.dumps({"meta": meta, "results": results}, indent=2))


if __name__ == "__main__":
    main()
