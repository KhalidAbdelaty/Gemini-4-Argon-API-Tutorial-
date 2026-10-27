"""Check that the hidden evaluator catches two plausible wrong fixes (no API calls).

Usage: python scripts/check_evaluator.py   -> writes results/evaluator_check.json

Each mutant is the original app with one hand-written change to session.py.
Both pass the visible tests; the hidden cases should reject both.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluator"))

from evaluate import run_cases  # noqa: E402

SESSION = ROOT / "starter" / "eventflow" / "session.py"

# Drop the deep copy: fast to write, breaks "history() returns an object the caller owns".
DROP_DEEP_COPY = SESSION.read_text().replace(
    "return copy.deepcopy(self._events)", "return self._events")

# Lazy cached summary that is never invalidated: right for one ingest(), stale after that.
STALE_SUMMARY = '''"""Per-customer session state."""

import bisect
import copy

from eventflow.history import summarize


def _order_key(event):
    return (event.ts, event.seq)


class CustomerState:
    """Holds one customer's events in processing order (timestamp, then arrival)."""

    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self._events = []
        self._event_ids = set()
        self._summary = None

    @property
    def summary(self):
        if self._summary is None:
            self._summary = summarize(self._events)
        return self._summary

    def get_history(self):
        return copy.deepcopy(self._events)

    def has_event(self, event_id: str) -> bool:
        return event_id in self._event_ids

    def add(self, event) -> None:
        self._event_ids.add(event.event_id)
        bisect.insort(self._events, event, key=_order_key)
'''

MUTANTS = {"drop_deep_copy": DROP_DEEP_COPY, "stale_summary": STALE_SUMMARY}


def visible_tests(repo: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    env.update(PYTHONPATH=str(repo), PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                          cwd=repo, env=env, capture_output=True, text=True, timeout=300)
    last = (done.stdout.strip().splitlines() or ["no output"])[-1]
    return {"exit_code": done.returncode, "summary": last}


def main():
    report = {}
    for name, source in MUTANTS.items():
        assert source != SESSION.read_text(), f"{name} did not change session.py"
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for part in ("eventflow", "tests", "fixtures"):
                shutil.copytree(ROOT / "starter" / part, repo / part)
            (repo / "eventflow" / "session.py").write_text(source)
            vis = visible_tests(repo)
            cases = run_cases(repo)
        failed = [k for k, v in cases.items() if not v["passed"]]
        report[name] = {"visible_tests": vis, "hidden_passed": len(cases) - len(failed),
                        "hidden_total": len(cases), "hidden_failures": failed}
        print(f"{name}: visible {vis['summary']} | hidden {len(cases) - len(failed)}/{len(cases)} "
              f"| failed: {', '.join(failed) or 'none'}")
    (ROOT / "results" / "evaluator_check.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
