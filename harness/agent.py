"""EventFlow performance agent: a manual Interactions API tool loop."""

import json
import shutil
import time
from pathlib import Path

from google import genai

from harness import config
from harness.tools import DECLARATIONS, Toolbox

SYSTEM_INSTRUCTION = """\
You are a performance engineer working on EventFlow, a Python application that
you can reach only through the tools provided. You cannot run arbitrary commands.

Objective: make EventFlow faster on the supplied workloads without changing its
observable outputs or its public interfaces.

Rules:
- Measure before you edit. Use run_benchmark and run_profiler to find where the
  time goes, then read the code the evidence points to.
- Base each change on profiler or benchmark evidence. Prefer small, reviewable patches.
- Behavior must follow the public contract documented in the docstrings, not
  only the visible tests.
- After every change, run run_tests and run_benchmark. If a test fails or
  output_matches_original is false, repair or revert the change.
- You can write only to existing files directly under eventflow/. Tests and
  fixtures are read-only.
- Acceptance target: at least 1.5x faster on the long workload, no more than 5%
  slower on short and mixed, all visible tests passing, and
  output_matches_original true on all three workloads.
- When you are done, check show_diff, then reply without calling a tool. Give a
  short report: what you changed and why, before and after medians for each
  workload, and the risks or limitations that remain.
"""

TASK = ("Start the EventFlow performance task. Budget: {turns} model turns and "
        "{patches} successful patches.")

TERMINAL = {"failed", "cancelled", "incomplete", "budget_exceeded"}


def _usage(interaction) -> dict:
    return interaction.usage.model_dump(exclude_none=True) if interaction.usage else {}


def _create(client, trace, **request):
    """One interactions.create() call with a small retry for transient errors.

    Tool calls have already run when a retry happens, so a retry only resends
    the same function results. Nothing is executed twice.
    """
    for attempt in range(4):
        try:
            return client.interactions.create(**request, timeout=config.REQUEST_TIMEOUT_S)
        except Exception as err:  # noqa: BLE001
            code = getattr(err, "status_code", None) or getattr(err, "code", None)
            if code in (400, 401, 403, 404) or attempt == 3:
                raise
            trace.write(json.dumps({"retry": attempt + 1, "error": repr(err)[:300]}) + "\n")
            time.sleep(5 * 3 ** attempt)


def run(thinking_level: str, run_dir: Path, baseline: dict) -> dict:
    config.load_api_key()
    client = genai.Client()

    run_dir.mkdir(parents=True, exist_ok=False)
    workdir = run_dir / "repo"
    shutil.copytree(config.STARTER, workdir)   # clean copy of the original app
    tools = Toolbox(workdir, baseline)

    # Interaction-scoped settings: sent again on every turn.
    request = dict(
        model=config.MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
        tools=DECLARATIONS,
        generation_config={"thinking_level": thinking_level,
                           "max_output_tokens": config.MAX_OUTPUT_TOKENS,
                           "thinking_summaries": "auto"},
    )

    trace = open(run_dir / "trace.jsonl", "w")
    started = time.perf_counter()
    totals, spend, turns, stop = {}, 0.0, 0, "model finished"
    calls_made = []

    interaction = _create(client, trace, input=TASK.format(turns=config.MAX_TURNS,
                                                            patches=config.MAX_PATCHES), **request)
    while True:
        turns += 1
        usage = _usage(interaction)
        for key, value in usage.items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
        spend += config.cost_usd(usage)

        calls = [s for s in interaction.steps if s.type == "function_call"]
        thoughts = [c.text for s in interaction.steps if s.type == "thought"
                    for c in (s.summary or []) if getattr(c, "type", "") == "text"]
        record = {"turn": turns, "elapsed_s": round(time.perf_counter() - started, 1),
                  "status": interaction.status, "usage": usage, "thought_summaries": thoughts,
                  "calls": [], "text": interaction.output_text if not calls else None}

        if interaction.status in TERMINAL:
            stop = f"interaction status {interaction.status}"
        elif not calls:
            stop = "model finished"
        if stop != "model finished" or not calls:
            trace.write(json.dumps(record) + "\n")
            break

        results = []
        for call in calls:
            result, is_error, seconds = tools.call(call.name, call.arguments)
            calls_made.append(call.name)
            record["calls"].append({"name": call.name, "arguments": call.arguments,
                                    "is_error": is_error, "seconds": seconds,
                                    "result": json.dumps(result)[:3000]})
            results.append({"type": "function_result", "name": call.name, "call_id": call.id,
                            "is_error": is_error,
                            "result": [{"type": "text", "text": json.dumps(result)}]})
        trace.write(json.dumps(record) + "\n")
        trace.flush()

        elapsed = time.perf_counter() - started
        if turns >= config.MAX_TURNS:
            stop = "turn budget reached"
        elif elapsed >= config.MAX_WALL_CLOCK_S:
            stop = "wall-clock budget reached"
        elif spend >= config.MAX_SPEND_USD:
            stop = "spend budget reached"
        if stop != "model finished":
            break

        note = (f"\n\n[harness] turns used {turns}/{config.MAX_TURNS}, "
                f"patches used {tools.patches_used}/{config.MAX_PATCHES}")
        results[-1]["result"][0]["text"] += note
        interaction = _create(client, trace, input=results,
                              previous_interaction_id=interaction.id, **request)

    trace.close()
    final_text = interaction.output_text if stop == "model finished" else None

    # Freeze the candidate before any independent evaluation.
    shutil.copytree(workdir / "eventflow", run_dir / "candidate" / "eventflow")
    (run_dir / "candidate.diff").write_text(tools.show_diff()["diff"])

    summary = {
        "thinking_level": thinking_level, "model": config.MODEL, "stop_reason": stop,
        "turns": turns, "tool_calls": len(calls_made),
        "tool_counts": {n: calls_made.count(n) for n in sorted(set(calls_made))},
        "patches_applied": tools.patches_used,
        "wall_clock_s": round(time.perf_counter() - started, 1),
        "usage_totals": totals, "cost_usd_intro": round(spend, 4),
        "cost_usd_from_dec_1": round(spend * 2, 4), "final_report": final_text,
        "limits": {"max_turns": config.MAX_TURNS, "max_patches": config.MAX_PATCHES,
                   "max_wall_clock_s": config.MAX_WALL_CLOCK_S, "max_spend_usd": config.MAX_SPEND_USD},
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
