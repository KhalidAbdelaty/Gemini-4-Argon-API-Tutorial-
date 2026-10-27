"""Aggregate the recorded runs into results/run_stats.json (no API calls)."""

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"
verdict = json.loads((ROOT / "results" / "verdict.json").read_text())
bench = json.loads((ROOT / "results" / "final_bench.json").read_text())["results"]

rows = {}
for run in sorted(RUNS.iterdir()):
    s = json.loads((run / "summary.json").read_text())
    u = s["usage_totals"]
    diff = (run / "candidate.diff").read_text().splitlines()
    rows[run.name] = {
        "level": s["thinking_level"], "turns": s["turns"], "tool_calls": s["tool_calls"],
        "patches": s["patches_applied"], "wall_clock_s": s["wall_clock_s"],
        "input": u["total_input_tokens"], "cached": u["total_cached_tokens"],
        "output": u["total_output_tokens"], "thought": u["total_thought_tokens"],
        "cost_intro": s["cost_usd_intro"], "cost_dec1": s["cost_usd_from_dec_1"],
        "changed_lines": sum(1 for d in diff if d[:1] in "+-" and d[:3] not in ("+++", "---")),
        "accepted": verdict[run.name]["accepted"], "hidden": verdict[run.name]["hidden_passed"],
        "speedup": verdict[run.name]["speedup"],
        "median_s": {w: bench[run.name][w]["median_s"] for w in ("short", "long", "mixed")},
    }

levels = {}
for level in ("medium", "high"):
    sel = [r for r in rows.values() if r["level"] == level]
    mean = lambda k: round(statistics.mean(r[k] for r in sel), 4)  # noqa: E731
    levels[level] = {"runs": len(sel), "accepted": sum(r["accepted"] for r in sel),
                     **{k: mean(k) for k in ("turns", "tool_calls", "patches", "wall_clock_s", "input",
                                             "cached", "output", "thought", "cost_intro", "cost_dec1",
                                             "changed_lines")},
                     "long_speedup_range": [min(r["speedup"]["long"] for r in sel),
                                            max(r["speedup"]["long"] for r in sel)],
                     "short_speedup_range": [min(r["speedup"]["short"] for r in sel),
                                             max(r["speedup"]["short"] for r in sel)],
                     "mixed_speedup_range": [min(r["speedup"]["mixed"] for r in sel),
                                             max(r["speedup"]["mixed"] for r in sel)]}
total = round(sum(r["cost_intro"] for r in rows.values()), 4)
out = {"runs": rows, "by_level": levels, "total_cost_intro_all_runs": total}
(ROOT / "results" / "run_stats.json").write_text(json.dumps(out, indent=2))
print(json.dumps(levels, indent=2), "\ntotal agent spend:", total)
