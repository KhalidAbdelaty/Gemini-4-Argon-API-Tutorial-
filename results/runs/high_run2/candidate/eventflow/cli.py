"""Command-line workload runner: python -m eventflow.cli --workload long"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures"))

from generate import WORKLOADS, build_workload  # noqa: E402

from eventflow.engine import EventFlow  # noqa: E402
from eventflow.reports import totals  # noqa: E402


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run one EventFlow workload.")
    parser.add_argument("--workload", choices=sorted(WORKLOADS), default="short")
    args = parser.parse_args(argv)

    events = build_workload(args.workload)
    start = time.perf_counter()
    engine = EventFlow()
    engine.ingest(events)
    reports = engine.report()
    elapsed = time.perf_counter() - start
    print(json.dumps({"workload": args.workload, "raw_events": len(events),
                      "seconds": round(elapsed, 3), **totals(reports)}, indent=2))


if __name__ == "__main__":
    main()
