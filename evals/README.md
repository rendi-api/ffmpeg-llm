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

The runner spawns `claude --bare -p`. The `--bare` flag is documented as: "skip hooks,
LSP, plugin sync, attribution, auto-memory, background prefetches, keychain reads, and
CLAUDE.md auto-discovery. Anthropic auth is strictly `ANTHROPIC_API_KEY` or `apiKeyHelper`
via `--settings` (OAuth and keychain are never read)." This gives us a clean baseline
that doesn't leak globally-installed plugins/agents/MCP servers, and forces explicit auth.

You must set `ANTHROPIC_API_KEY` in `evals/.env` — subscription OAuth (the default for
Claude Code Max users) is intentionally bypassed by `--bare`. The judge calls the
Anthropic API directly via the same key.

## Verified headless invocation (recorded 2026-05-08)

Investigated against `claude --version 2.1.132` (Claude Code). The runner uses:

```bash
# vanilla baseline (no plugin)
claude --bare -p --model <model> "<prompt>"

# with the claude-ffmpeg plugin loaded
claude --bare -p --model <model> --plugin-dir <repo-root> "<prompt>"
```

Why `--bare` over the originally-planned `HOME=<tempdir>` isolation:

- `--bare` is the documented, supported way to disable plugin auto-discovery and CLAUDE.md
  auto-load. HOME-isolation is a hack that also breaks OAuth.
- `--bare` still loads plugins via explicit `--plugin-dir`, so the with-plugin path works.
- Skills still resolve, so the plugin's skill machinery functions normally.

If you change the invocation in `runner/claude_invoke.py`, re-validate by running a
single (vanilla, with-plugin) pair against a prompt where you can eyeball the difference
— e.g., "extract audio without re-encoding" should produce a `-acodec copy` form for
both, but the with-plugin run typically shows evidence of reading the audio reference.
