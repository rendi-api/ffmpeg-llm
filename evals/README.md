# claude-ffmpeg evals

Benchmark harness comparing `claude-ffmpeg` vs vanilla Claude on real FFmpeg prompts.
See `docs/superpowers/specs/2026-05-08-plugin-evaluation-design.md` for design context.

## Setup

```bash
cd evals
python -m venv .venv && source .venv/bin/activate    # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
cp .env.example .env                                  # then add your ANTHROPIC_API_KEY
```

Verify the `claude` CLI is on PATH (`claude --version`) — the runner shells out to it.

Verify `ffmpeg` and `ffprobe` are on PATH for spot-check execution.

## Running a benchmark

```bash
python -m runner.run   --prompts prompts/smoke.yaml   --model claude-sonnet-4-6   --out results/$(date +%Y-%m-%d)-sonnet46-smoke
python -m runner.judge --run-dir results/<date>-sonnet46-smoke
python -m runner.spot_check --run-dir results/<date>-sonnet46-smoke --fraction 0.15
python -m runner.report --run-dir results/<date>-sonnet46-smoke
```

## Cost guardrails

Each full run is capped at `EVAL_BUDGET_USD` (default $30). The runner aborts before
exceeding the cap. Estimated cost for the 30-prompt smoke on Sonnet: ~$3–5; for the
150-prompt full Sonnet pass: ~$15–25; for the curated 50-prompt Opus subset: ~$10–20.
Adjust `EVAL_BUDGET_USD` in `.env` if needed.

## Authentication

The runner spawns `claude -p`. It must be authenticated via `ANTHROPIC_API_KEY` in the
environment (not subscription OAuth) so we can run with an isolated `HOME` and avoid
leakage from globally-installed plugins. The judge calls the Anthropic API directly via
the same key.
