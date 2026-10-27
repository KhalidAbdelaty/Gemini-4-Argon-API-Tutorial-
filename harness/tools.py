"""Application-defined tools for the EventFlow agent.

Gemini only requests these calls. This module validates every request,
runs it locally, and returns a bounded result. Nothing here is executed by
the Gemini API.
"""

import difflib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from harness.config import MAX_PATCHES, ROOT, STARTER

READABLE_DIRS = ("eventflow", "tests", "fixtures")
WRITABLE_DIR = "eventflow"
WORKLOADS = ("short", "long", "mixed")
MAX_READ_CHARS = 20_000
MAX_OUTPUT_CHARS = 6_000
MAX_PATCH_CHARS = 12_000


class ToolError(Exception):
    """A rejected or failed tool call. Returned to the model, never raised to the loop."""


def _clip(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


def _child_env(repo: Path) -> dict:
    """Minimal environment for model-modified code: no API key, no user secrets."""
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(repo),
           "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(repo), "LANG": "C.UTF-8"}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):   # Windows needs these to start Python
        if key in os.environ:
            env[key] = os.environ[key]
    return env


DECLARATIONS = [
    {"type": "function", "name": "list_files",
     "description": "List the repository files you can read, with line counts and whether each is writable.",
     "parameters": {"type": "object", "properties": {}}},
    {"type": "function", "name": "read_file",
     "description": "Read one repository file, with line numbers.",
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Repository-relative path, e.g. eventflow/engine.py"}},
         "required": ["path"]}},
    {"type": "function", "name": "run_profiler",
     "description": "Run one workload once under cProfile and return the top functions by cumulative and internal time.",
     "parameters": {"type": "object", "properties": {
         "workload": {"type": "string", "enum": list(WORKLOADS)}}, "required": ["workload"]}},
    {"type": "function", "name": "run_benchmark",
     "description": ("Time one workload without profiling (1 warm-up, 3 timed runs, median). "
                     "Also reports whether the output still matches the original application's output."),
     "parameters": {"type": "object", "properties": {
         "workload": {"type": "string", "enum": list(WORKLOADS)}}, "required": ["workload"]}},
    {"type": "function", "name": "apply_patch",
     "description": ("Replace exactly one occurrence of old_text with new_text in a file under eventflow/. "
                     "The file must still compile afterwards."),
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"},
         "old_text": {"type": "string", "description": "Exact text to replace; must occur once."},
         "new_text": {"type": "string"}},
         "required": ["path", "old_text", "new_text"]}},
    {"type": "function", "name": "revert_file",
     "description": "Restore one file under eventflow/ to its original content.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"type": "function", "name": "run_tests",
     "description": "Run the visible pytest suite in tests/ and return the summary.",
     "parameters": {"type": "object", "properties": {}}},
    {"type": "function", "name": "show_diff",
     "description": "Show a unified diff of every change made so far under eventflow/.",
     "parameters": {"type": "object", "properties": {}}},
]


class Toolbox:
    def __init__(self, workdir: Path, baseline: dict):
        self.repo = Path(workdir).resolve()
        self.baseline = baseline          # tool-method baseline medians and digests
        self.patches_used = 0

    # ---------- path checks ----------
    def _resolve(self, rel: str, write: bool = False) -> Path:
        if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or ":" in rel:
            raise ToolError("use a repository-relative path such as eventflow/engine.py")
        candidate = (self.repo / rel).resolve()
        if self.repo not in candidate.parents:
            raise ToolError("path escapes the repository")
        parts = candidate.relative_to(self.repo).parts
        if parts[0] not in READABLE_DIRS or candidate.suffix != ".py":
            raise ToolError(f"readable files are .py files under {', '.join(READABLE_DIRS)}/")
        if write and (parts[0] != WRITABLE_DIR or len(parts) != 2):
            raise ToolError("only existing files directly under eventflow/ are writable")
        if not candidate.is_file():
            raise ToolError(f"no such file: {rel}")
        return candidate

    # ---------- tools ----------
    def list_files(self):
        rows = []
        for top in READABLE_DIRS:
            for path in sorted((self.repo / top).rglob("*.py")):
                rel = path.relative_to(self.repo).as_posix()
                rows.append({"path": rel, "lines": len(path.read_text().splitlines()),
                             "writable": rel.startswith(WRITABLE_DIR + "/") and rel.count("/") == 1})
        return {"files": rows}

    def read_file(self, path):
        text = self._resolve(path).read_text()
        numbered = "\n".join(f"{i:4d}  {line}" for i, line in enumerate(text.splitlines(), 1))
        return {"path": path, "content": _clip(numbered, MAX_READ_CHARS)}

    def _bench(self, mode, workload, extra=()):
        if workload not in WORKLOADS:
            raise ToolError(f"workload must be one of {WORKLOADS}")
        cmd = [sys.executable, str(ROOT / "bench" / "runner.py"), "--repo", str(self.repo),
               "--mode", mode, "--workload", workload, *extra]
        try:
            done = subprocess.run(cmd, cwd=self.repo, env=_child_env(self.repo),
                                  capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            raise ToolError("workload timed out after 240 seconds") from None
        if done.returncode != 0:
            raise ToolError("workload crashed:\n" + _clip(done.stderr[-4000:]))
        return json.loads(done.stdout)

    def run_profiler(self, workload):
        data = self._bench("profile", workload, ["--top", "12"])
        return {"workload": workload, "note": "cProfile adds overhead; use run_benchmark for timings.",
                "top_by_cumulative": data["top_by_cumulative"], "top_by_tottime": data["top_by_tottime"]}

    def run_benchmark(self, workload):
        data = self._bench("time", workload, ["--warmups", "1", "--repeats", "3"])
        base = self.baseline[workload]
        return {"workload": workload, "median_s": data["median_s"], "samples_s": data["samples_s"],
                "original_median_s": base["median_s"],
                "speedup_vs_original": round(base["median_s"] / data["median_s"], 2),
                "output_matches_original": data["digest"] == base["digest"]}

    def apply_patch(self, path, old_text, new_text):
        if self.patches_used >= MAX_PATCHES:
            raise ToolError(f"patch budget used up ({MAX_PATCHES} patches)")
        target = self._resolve(path, write=True)
        if len(old_text) + len(new_text) > MAX_PATCH_CHARS:
            raise ToolError("patch too large; split it into smaller patches")
        source = target.read_text()
        count = source.count(old_text) if old_text else 0
        if count != 1:
            raise ToolError(f"old_text must occur exactly once in {path}; found {count}")
        updated = source.replace(old_text, new_text, 1)
        try:
            compile(updated, path, "exec")
        except SyntaxError as err:
            raise ToolError(f"patch rejected, file would not compile: {err}") from None
        target.write_text(updated)
        self.patches_used += 1
        return {"ok": True, "path": path, "patches_left": MAX_PATCHES - self.patches_used}

    def revert_file(self, path):
        target = self._resolve(path, write=True)
        target.write_text((STARTER / target.relative_to(self.repo)).read_text())
        return {"ok": True, "path": path, "reverted": True}

    def run_tests(self):
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short", "tests"]
        try:
            done = subprocess.run(cmd, cwd=self.repo, env=_child_env(self.repo),
                                  capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            raise ToolError("tests timed out after 180 seconds") from None
        return {"exit_code": done.returncode, "output": _clip((done.stdout + done.stderr).strip(), 4000)}

    def show_diff(self):
        chunks = []
        for path in sorted((self.repo / WRITABLE_DIR).glob("*.py")):
            rel = path.relative_to(self.repo).as_posix()
            before = (STARTER / rel).read_text().splitlines(keepends=True)
            after = path.read_text().splitlines(keepends=True)
            chunks.extend(difflib.unified_diff(before, after, f"a/{rel}", f"b/{rel}"))
        return {"diff": _clip("".join(chunks), 8000) or "(no changes)"}

    # ---------- dispatch ----------
    def call(self, name, arguments):
        """Run one requested tool. Returns (result_dict, is_error, seconds)."""
        start = time.perf_counter()
        handler = getattr(self, name, None) if name in {d["name"] for d in DECLARATIONS} else None
        try:
            if handler is None:
                raise ToolError(f"unknown tool: {name}")
            result, is_error = handler(**(arguments or {})), False
        except ToolError as err:
            result, is_error = {"error": str(err)}, True
        except TypeError as err:
            result, is_error = {"error": f"bad arguments: {err}"}, True
        return result, is_error, round(time.perf_counter() - start, 2)
