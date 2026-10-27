"""Print the recorded first request (results/first_request.json) without calling the API."""

import json
from pathlib import Path

r = json.loads((Path(__file__).resolve().parents[1] / "results" / "first_request.json").read_text())
u = r["usage"]
print(r["output_text"])
print(f"\nstatus={r['status']}  seconds={r['seconds']}")
print(f"input={u['total_input_tokens']}  output={u['total_output_tokens']}  "
      f"thinking={u.get('total_thought_tokens', 0)}  cached={u.get('total_cached_tokens', 0)}  "
      f"total={u['total_tokens']}")
print(f"cost=${r['cost_usd']:.4f} at introductory Standard rates")
