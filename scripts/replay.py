"""Print a recorded agent run without calling the API (used for screenshots).

Usage: python scripts/replay.py --name medium_run1 [--full]
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def short(call):
    try:
        r = json.loads(call["result"])
    except json.JSONDecodeError:      # long results are clipped in the trace
        r = {}
    n, a = call["name"], call["arguments"] or {}
    if call["is_error"]:
        return f"ERROR {r.get('error', '')[:90]}"
    if n == "run_benchmark":
        return (f"{a['workload']}: median {r['median_s']}s, {r['speedup_vs_original']}x vs original, "
                f"output matches={r['output_matches_original']}")
    if n == "run_tests":
        return (r.get("output", "").splitlines() or [""])[-1]
    if n == "run_profiler":
        return f"{a.get('workload', '')} profile"
    if n in ("read_file", "apply_patch", "revert_file"):
        return a.get("path", "")
    if n == "show_diff":
        return f"{len(r['diff'].splitlines())} diff lines" if r else "diff (clipped in trace)"
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--full", action="store_true", help="also print thought summaries")
    args = parser.parse_args()
    run = ROOT / "results" / "runs" / args.name
    for line in (run / "trace.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if "retry" in rec:
            print(f"  retry {rec['retry']}: {rec['error'][:80]}")
            continue
        u = rec["usage"]
        print(f"turn {rec['turn']:>2}  {rec['elapsed_s']:>6}s  in={u.get('total_input_tokens', 0):>6} "
              f"cached={u.get('total_cached_tokens', 0):>6} out={u.get('total_output_tokens', 0):>5} "
              f"think={u.get('total_thought_tokens', 0):>5}")
        if args.full:
            for t in rec.get("thought_summaries", []):
                print("        thought:", t.replace("\n", " ")[:160])
        for c in rec["calls"]:
            print(f"        -> {c['name']:<13} {short(c)}")
    s = json.loads((run / "summary.json").read_text())
    print(f"\nstop: {s['stop_reason']} | turns {s['turns']} | tool calls {s['tool_calls']} | "
          f"patches {s['patches_applied']} | {s['wall_clock_s']}s | ${s['cost_usd_intro']}")


if __name__ == "__main__":
    main()
