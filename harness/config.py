"""Shared settings for the EventFlow agent harness."""

import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "starter"
RESULTS = ROOT / "results"

MODEL = "gemini-4-argon"
MAX_OUTPUT_TOKENS = 65_536          # synchronous ceiling on Gemini 4 Argon
REQUEST_TIMEOUT_S = 900             # Google recommends at least 15 minutes

# Application limits, set before any run. The Gemini API has no task budget.
MAX_TURNS = 40                      # model interactions per run
MAX_PATCHES = 10                    # successful apply_patch calls per run
MAX_WALL_CLOCK_S = 45 * 60
MAX_SPEND_USD = 5.00

# Standard tier, per 1M tokens, through November 30, 2026 (official pricing page).
PRICE_INPUT = 2.00
PRICE_CACHED = 0.10
PRICE_OUTPUT = 10.00                # output and thinking tokens


def load_api_key() -> None:
    """Load only GEMINI_API_KEY from the project .env file.

    genai.Client() prefers GOOGLE_API_KEY when both are set, so remove it.
    """
    os.environ.pop("GOOGLE_API_KEY", None)
    for candidate in (ROOT / ".env", ROOT.parent / ".env"):
        if candidate.exists():
            key = dotenv_values(candidate).get("GEMINI_API_KEY")
            if key:
                os.environ["GEMINI_API_KEY"] = key
                return
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Set GEMINI_API_KEY in eventflow-argon/.env")


def cost_usd(usage: dict) -> float:
    """Price one interaction's usage at the Standard introductory rates."""
    cached = usage.get("total_cached_tokens") or 0
    uncached = (usage.get("total_input_tokens") or 0) - cached
    billed_output = (usage.get("total_output_tokens") or 0) + (usage.get("total_thought_tokens") or 0)
    return (uncached * PRICE_INPUT + cached * PRICE_CACHED + billed_output * PRICE_OUTPUT) / 1_000_000
