"""Write the complete diff of each frozen candidate (show_diff output is clipped for the model)."""

import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for name in sys.argv[1:]:
    cand = ROOT / "results" / "runs" / name / "candidate" / "eventflow"
    chunks = []
    for path in sorted(cand.glob("*.py")):
        rel = f"eventflow/{path.name}"
        before = (ROOT / "starter" / rel).read_text().splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(before, path.read_text().splitlines(keepends=True),
                                           f"a/{rel}", f"b/{rel}"))
    (ROOT / "results" / "runs" / name / "candidate.diff").write_text("".join(chunks))
    changed = sum(1 for c in chunks if c[:1] in "+-" and c[:3] not in ("+++", "---"))
    files = sorted({c[6:].strip() for c in chunks if c.startswith("+++ b/")})
    print(f"{name}: {changed} changed lines in {files}")
