"""Run the agent once at one thinking level, from a clean copy of starter/.

Usage: python scripts/run_agent.py --level medium --name medium_run1
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness import agent, config  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", choices=["low", "medium", "high"], required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    baseline = json.loads((config.RESULTS / "baseline" / "tool_baseline.json").read_text())
    summary = agent.run(args.level, config.RESULTS / "runs" / args.name, baseline)
    print(json.dumps({k: v for k, v in summary.items() if k != "final_report"}, indent=2))
    print("\nFinal report from the model:\n")
    print(summary["final_report"])


if __name__ == "__main__":
    main()
