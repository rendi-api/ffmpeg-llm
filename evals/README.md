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

## Authentication & plugin isolation

The runner and judge both call `claude -p` and use your **Max-plan OAuth** credentials
from `~/.claude/.credentials.json`. No `ANTHROPIC_API_KEY` needed.

To prevent globally-installed Claude Code plugins (`superpowers`, `claude-hud`, etc.)
from polluting the "vanilla" baseline, the runner and judge automatically wrap their
main loop in `runner.plugin_isolation.isolated_user_plugins()`. Behavior:

1. Snapshot currently-enabled user-scope plugins.
2. Run `claude plugin disable -a -s user` (disables them all globally).
3. Run the benchmark.
4. Re-enable each plugin in the snapshot via `claude plugin enable <id> -s user`.

The disable/restore is wrapped in `try/finally` so plugins come back even on Ctrl-C
or exception. **Side effect:** while the benchmark runs (~25 min smoke / ~2 hr full),
any other Claude Code session you have open also sees no user plugins. Project-scope
plugins (pinned to specific project paths) are untouched.

If a benchmark crashes and leaves plugins disabled, restore manually:

```bash
claude plugin enable claude-hud -s user
claude plugin enable superpowers -s user
# (or whatever was in your snapshot — check `claude plugin list`)
```

### Verified headless invocations (recorded 2026-05-08)

```bash
# Runner — vanilla baseline (no plugin loaded)
claude -p --model <model> "<prompt>"

# Runner — with the claude-ffmpeg plugin loaded
claude -p --model <model> --plugin-dir <repo-root> "<prompt>"

# Judge — Opus on the rubric
claude -p --disable-slash-commands --output-format json \
       --model claude-opus-4-7 \
       --system-prompt "<rubric>" "<user message>"
```

`--disable-slash-commands` on the judge prevents skill resolution mid-session, keeping
the judge's response clean. Plugin isolation handles the rest.
