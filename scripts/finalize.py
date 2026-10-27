"""Freeze-time evaluation: visible tests, hidden cases (once), published benchmark, verdict.

Usage: python scripts/finalize.py --run medium_run1 --run high_run1
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"
PY = sys.executable
ENV = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
ENV.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")


def visible_tests(candidate: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        shutil.copytree(ROOT / "starter" / "tests", repo / "tests")
        shutil.copytree(ROOT / "starter" / "fixtures", repo / "fixtures")
        shutil.copytree(candidate / "eventflow", repo / "eventflow")
        done = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                              cwd=repo, env={**ENV, "PYTHONPATH": str(repo)},
                              capture_output=True, text=True, timeout=300)
    last = (done.stdout.strip().splitlines() or ["no output"])[-1]
    return {"exit_code": done.returncode, "summary": last}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--runs-per-workload", type=int, default=9)
    args = parser.parse_args()

    verdicts = {}
    for name in args.run:
        cand = RUNS / name / "candidate"
        vis = visible_tests(cand)
        hidden_path = RUNS / name / "hidden.json"
        if not hidden_path.exists():   # the hidden evaluator runs once per frozen candidate
            subprocess.run([PY, str(ROOT / "evaluator" / "evaluate.py"), "--candidate", str(cand),
                            "--out", str(hidden_path)], env=ENV, check=True)
        hidden = json.loads(hidden_path.read_text())
        verdicts[name] = {"visible_tests": vis, "hidden_passed": hidden["passed"],
                          "hidden_total": hidden["total"],
                          "hidden_failures": [k for k, v in hidden["cases"].items() if not v["passed"]]}
        print(name, vis["summary"], f"hidden {hidden['passed']}/{hidden['total']}", flush=True)

    labels = ["baseline", *args.run]
    repos = [str(ROOT / "starter"), *[str(RUNS / n / "candidate") for n in args.run]]
    cmd = [PY, str(ROOT / "scripts" / "benchmark.py"), "--runs", str(args.runs_per_workload),
           "--out", str(ROOT / "results" / "final_bench.json")]
    for label, repo in zip(labels, repos):
        cmd += ["--repo", repo, "--label", label]
    subprocess.run(cmd, env=ENV, check=True)
    bench = json.loads((ROOT / "results" / "final_bench.json").read_text())["results"]

    base = bench["baseline"]
    for name in args.run:
        cand = bench[name]
        speed = {w: round(base[w]["median_s"] / cand[w]["median_s"], 2) for w in base}
        same_output = all(cand[w]["digest"] == base[w]["digest"] for w in base)
        v = verdicts[name]
        checks = {
            "long_speedup_at_least_1.5x": speed["long"] >= 1.5,
            "short_within_5pct": cand["short"]["median_s"] <= 1.05 * base["short"]["median_s"],
            "mixed_within_5pct": cand["mixed"]["median_s"] <= 1.05 * base["mixed"]["median_s"],
            "visible_tests_pass": v["visible_tests"]["exit_code"] == 0,
            "hidden_cases_pass": v["hidden_passed"] == v["hidden_total"],
            "benchmark_outputs_match": same_output,
        }
        v.update(speedup=speed, checks=checks, accepted=all(checks.values()),
                 memory_kib={w: [base[w]["peak_tracked_kib"], cand[w]["peak_tracked_kib"]] for w in base})
    (ROOT / "results" / "verdict.json").write_text(json.dumps(verdicts, indent=2))
    print(json.dumps(verdicts, indent=2))


if __name__ == "__main__":
    main()
