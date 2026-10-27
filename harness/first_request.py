"""First Gemini 4 Argon request: interpret a slice of EventFlow profiler output."""

import json
import time

from google import genai

from harness import config

config.load_api_key()
client = genai.Client()  # reads GEMINI_API_KEY from the environment

profile = (config.RESULTS / "baseline" / "profile_long.txt").read_text()
excerpt = "\n".join(profile.splitlines()[:9])

prompt = (
    "This cProfile excerpt comes from a Python app that turns customer events into "
    "reports. It is correct but slow on long customer histories.\n\n"
    f"{excerpt}\n\n"
    "In three short bullets: what the profile shows, what you would read next in the "
    "code, and what this evidence alone does not prove."
)

start = time.perf_counter()
interaction = client.interactions.create(
    model=config.MODEL,
    input=prompt,
    generation_config={"thinking_level": "medium"},
    timeout=config.REQUEST_TIMEOUT_S,
)
elapsed = time.perf_counter() - start

print(interaction.output_text)
usage = interaction.usage
print(f"\nstatus={interaction.status}  seconds={elapsed:.1f}")
print(f"input={usage.total_input_tokens}  output={usage.total_output_tokens}  "
      f"thinking={usage.total_thought_tokens}  cached={usage.total_cached_tokens}  "
      f"total={usage.total_tokens}")
print(f"cost=${config.cost_usd(usage.model_dump()):.4f} at introductory Standard rates")

(config.RESULTS / "first_request.json").write_text(json.dumps({
    "prompt": prompt, "output_text": interaction.output_text, "status": interaction.status,
    "seconds": round(elapsed, 1), "usage": usage.model_dump(exclude_none=True),
    "cost_usd": round(config.cost_usd(usage.model_dump()), 6)}, indent=2))
