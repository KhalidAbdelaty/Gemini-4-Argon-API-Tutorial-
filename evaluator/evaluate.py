"""Run the hidden acceptance cases once against a frozen candidate.

Usage: python evaluator/evaluate.py --candidate results/medium/candidate --out results/medium/hidden.json
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_cases(candidate: Path) -> dict:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(candidate.resolve()),
           "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):   # Windows needs these to start Python
        if key in os.environ:
            env[key] = os.environ[key]
    done = subprocess.run([sys.executable, str(HERE / "hidden_cases.py")], env=env,
                          capture_output=True, text=True, timeout=900)
    if done.returncode != 0:
        return {"_crash": {"passed": False, "detail": done.stderr[-2000:]}}
    return json.loads(done.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = run_cases(Path(args.candidate))
    passed = sum(r["passed"] for r in results.values())
    report = {"candidate": args.candidate, "passed": passed, "total": len(results), "cases": results}
    Path(args.out).write_text(json.dumps(report, indent=2))
    for name, r in results.items():
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {name}" + ("" if r["passed"] else f"  ({r['detail'][:120]})"))
    print(f"\nHidden acceptance: {passed}/{len(results)} passed")


if __name__ == "__main__":
    main()
