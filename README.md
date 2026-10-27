# EventFlow performance agent with Gemini 4 Argon

Code and recorded results for the DataCamp tutorial "Gemini 4 Argon API Tutorial: Build an Agent That Speeds Up Slow Python Code".

EventFlow is a small fictional Python app that turns activity, purchase, and refund events into per-customer reports. It is correct but slow on long customer histories. A Gemini 4 Argon agent, driven through the Interactions API with function calling, profiles it, patches it through a few guarded tools, and hands its final code to hidden tests it never sees.

## Requirements

- Python 3.10 or newer. The recorded results come from Python 3.13.17 on Linux x86_64.
- A Gemini API key on a project with billing turned on. Gemini 4 Argon has no Free tier.

## Setup

```bash
git clone https://github.com/KhalidAbdelaty/Gemini-4-Argon-API-Tutorial-.git eventflow-argon
cd eventflow-argon
python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS or Linux: source .venv/bin/activate
pip install -r requirements.txt
Copy-Item .env.example .env       # macOS or Linux: cp .env.example .env
```

Put `GEMINI_API_KEY=...` in `.env`. The code removes `GOOGLE_API_KEY` from its own environment, because the SDK would use it instead.

## Project layout

- `starter/`: the original EventFlow app (`eventflow/`), its fixture generator (`fixtures/`), and the 11 visible tests (`tests/`)
- `harness/`: the agent loop (`agent.py`), the 8 tools (`tools.py`), limits and pricing (`config.py`), and the first API request (`first_request.py`)
- `bench/runner.py`: the timing, memory, and profiling runner, outside the folder the agent edits
- `evaluator/`: the 13 hidden cases, the independent reference implementation, and the list of planted slowdowns. The agent's tools can't read this folder.
- `scripts/`: commands to run the agent, benchmark, evaluate, replay, and chart
- `results/`: everything the article's numbers come from: baseline, the 6 recorded attempts (traces, diffs, frozen code, hidden results), the final benchmark, verdicts, and charts

## Reproduce the results without API calls

These commands read the recorded results and cost nothing.

```bash
cd starter
python -m pytest -q tests                                 # 11 visible tests on the original app
cd ..
python scripts/show_first_request.py                      # the recorded first request and its usage
python scripts/replay.py --name medium_run1               # one attempt, turn by turn (--full adds thought summaries)
python scripts/check_evaluator.py                         # two wrong fixes pass the visible tests, the hidden cases reject both
python evaluator/evaluate.py --candidate results/runs/medium_run1/candidate --out hidden_check.json
python scripts/summarize_runs.py                          # per-attempt and per-level stats, total spend
pip install matplotlib==3.11.2
python scripts/make_charts.py                             # rebuild the 3 charts
```

`check_evaluator.py`, `summarize_runs.py`, and `make_charts.py` rewrite their files under `results/`.

## Run your own measurements and attempts

```bash
python scripts/baseline.py                                # no API calls; overwrites results/baseline/
python -m harness.first_request                           # one API call, under half a cent; overwrites results/first_request.json
python scripts/run_agent.py --level medium --name medium_run4    # one paid attempt from a clean copy of starter/
python scripts/finalize.py --run medium_run4              # visible tests, hidden cases once, benchmark, verdict
```

- `run_agent.py` needs a new `--name`, and `--level` takes `low`, `medium`, or `high`. Each recorded attempt cost $0.06 to $0.32 at the introductory price, which doubles after November 30, 2026.
- The agent stops on its own or at 40 turns, 10 patches, 45 minutes, or $5. The spend check runs between turns, so one turn can go over it.
- `finalize.py` runs the hidden cases only once per frozen candidate, then times the original and every candidate you pass in alternating fresh processes. It overwrites `results/final_bench.json` and `results/verdict.json`.
- Timings on your machine will differ from the recorded ones. Compare versions within one `finalize.py` session.

## Safety

The tools check paths, refuse writes outside `eventflow/`, reject patches that don't compile, and run tests and benchmarks in subprocesses with timeouts and no API key. That is not a sandbox: code the model writes runs as a normal local process. Run the agent inside a disposable container with networking off if you point it at code you care about.

Every file the agent reads is sent to Google. Paid-tier interactions are stored for 55 days by default, and you can shorten that in Google AI Studio.
