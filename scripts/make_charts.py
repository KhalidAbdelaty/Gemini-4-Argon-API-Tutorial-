"""Build the article charts from recorded results (no API calls).

Usage: python scripts/make_charts.py   -> writes results/charts/*.png
Requires matplotlib (pip install matplotlib); the experiment itself does not.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = RES / "charts"
NAVY, GREEN, BLUE, ORANGE, GREY = "#05192D", "#03EF62", "#06BDFC", "#FF931E", "#D9D9E2"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": NAVY, "axes.labelcolor": NAVY,
                     "xtick.color": NAVY, "ytick.color": NAVY, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 11})


def scaling():
    rows = json.loads((RES / "baseline" / "scaling.json").read_text())
    x = [r["history_length"] for r in rows]
    y = [r["median_s"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, y, marker="o", color=NAVY, linewidth=2.5, markersize=8, markerfacecolor=GREEN)
    for xi, yi in zip(x, y):
        ax.annotate(f"{yi:.2f}s", (xi, yi), textcoords="offset points", xytext=(0, 10),
                    ha="center", color=NAVY)
    ax.set_xticks(x)
    ax.set_xlabel("Events per customer (1,600 events in every run)")
    ax.set_ylabel("Median seconds")
    ax.set_title("Original EventFlow: same events, longer histories", color=NAVY, loc="left")
    ax.set_ylim(0, max(y) * 1.2)
    fig.tight_layout()
    fig.savefig(OUT / "baseline_scaling.png", dpi=200)


def before_after():
    bench = json.loads((RES / "final_bench.json").read_text())["results"]
    labels = ["baseline", "medium_run1", "high_run1"]
    names = {"baseline": "original", "medium_run1": "medium thinking", "high_run1": "high thinking"}
    workloads = ["short", "long", "mixed"]
    colors = [GREY, GREEN, BLUE, ORANGE]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    width = 0.8 / len(labels)
    for i, label in enumerate(labels):
        vals = [bench[label][w]["median_s"] for w in workloads]
        xs = [j + (i - (len(labels) - 1) / 2) * width for j in range(len(workloads))]
        bars = ax.bar(xs, vals, width * 0.95, color=colors[i % 4], edgecolor=NAVY, label=names[label])
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.3f}s" if v >= 0.01 else f"{v * 1000:.1f}ms", (b.get_x() + b.get_width() / 2, v), textcoords="offset points",
                        xytext=(0, 3), ha="center", fontsize=8, color=NAVY)
    ax.set_xticks(range(len(workloads)), [w + " history" if w != "mixed" else "mixed customers"
                                          for w in workloads])
    ax.set_yscale("log")
    ax.set_ylabel("Median seconds, log scale (9 timings each)")
    ax.set_title("EventFlow before and after the Gemini 4 Argon patches", color=NAVY, loc="left")
    ax.legend(frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout()
    fig.savefig(OUT / "before_after.png", dpi=200)


def thinking_per_turn():
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for level, color in (("medium", GREEN), ("high", BLUE)):
        for n in (1, 2, 3):
            trace = RES / "runs" / f"{level}_run{n}" / "trace.jsonl"
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            rows = [r for r in rows if "turn" in r]
            turns = [r["turn"] for r in rows]
            thought = [r["usage"].get("total_thought_tokens", 0) for r in rows]
            ax.plot(turns, thought, marker="o", color=color, linewidth=2, alpha=0.9,
                    label=f"{level} thinking" if n == 1 else None)
    ax.set_xlabel("Agent turn")
    ax.set_ylabel("Thinking tokens in that turn")
    ax.set_title("Thinking tokens per turn, 3 medium and 3 high attempts", color=NAVY, loc="left")
    ax.set_xticks(range(1, 9))
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "thinking_per_turn.png", dpi=200)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    scaling()
    if (RES / "final_bench.json").exists():
        before_after()
    if (RES / "runs").exists():
        thinking_per_turn()
    print("charts written to", OUT)
