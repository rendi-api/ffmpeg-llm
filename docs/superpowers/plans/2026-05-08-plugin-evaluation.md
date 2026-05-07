# claude-ffmpeg plugin evaluation — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible benchmark that measures whether `claude-ffmpeg` produces meaningfully better FFmpeg commands than vanilla Claude on real-world prompts.

**Architecture:** A standalone Python package under `evals/` that drives headless `claude -p` in two configurations (with `--plugin-dir` / vanilla), captures generated commands to JSONL, runs them through a blinded LLM-judge with a 4-axis rubric, executes a ~15% spot-check sample against fixture media via ffprobe, and aggregates everything into `report.md`. Two phases: Phase 1 (30-prompt smoke) validates the harness end-to-end; Phase 2 (150 prompts) produces the publishable benchmark.

**Tech stack:** Python 3.11+, Pydantic v2 (schema), PyYAML, pytest, Anthropic Python SDK (judge calls with prompt caching), ffmpeg/ffprobe (spot-check execution), `claude` CLI (headless runner subject under test).

**Spec:** `docs/superpowers/specs/2026-05-08-plugin-evaluation-design.md` — read this first.

---

## Phase 1 — smoke test (Tasks 1–15)

Validates the full pipeline end-to-end on 30 prompts before committing to 150 prompts of curation.

---

### Task 1: Scaffold the `evals/` package

**Files:**
- Create: `evals/pyproject.toml`
- Create: `evals/README.md`
- Create: `evals/runner/__init__.py` (empty)
- Create: `evals/tests/__init__.py` (empty)
- Create: `evals/.gitignore`
- Create: `evals/.env.example`
- Modify: `claude-ffmpeg/.gitignore` (append a line)

- [ ] **Step 1: Write `evals/pyproject.toml`**

```toml
[project]
name = "claude-ffmpeg-evals"
version = "0.1.0"
description = "Benchmark harness for the claude-ffmpeg plugin"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "pydantic>=2.6",
    "anthropic>=0.40.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["runner"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `evals/.gitignore`**

```
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
results/*/raw.jsonl
results/*/judged.jsonl
results/*/spot_check.jsonl
# Keep report.md committed; raw artifacts can be regenerated.
!results/*/report.md
```

- [ ] **Step 3: Write `evals/.env.example`**

```
# Required: API key used by judge.py (direct Anthropic SDK call) and by `claude -p` runner.
ANTHROPIC_API_KEY=sk-ant-...

# Optional: override budget (USD) for a single benchmark run. Default is $30.
EVAL_BUDGET_USD=30
```

- [ ] **Step 4: Write `evals/README.md`**

````markdown
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
````

- [ ] **Step 5: Append to root `.gitignore`**

Append this line to `claude-ffmpeg/.gitignore` (create the file with just this line if it doesn't exist):

```
evals/.env
evals/.venv/
evals/results/*/raw.jsonl
evals/results/*/judged.jsonl
evals/results/*/spot_check.jsonl
```

- [ ] **Step 6: Verify install works**

Run from `evals/`:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
pip install -e .[dev]
pytest --collect-only
```

Expected: pytest reports "0 tests collected" with no errors.

- [ ] **Step 7: Commit**

```bash
git add evals/pyproject.toml evals/README.md evals/.gitignore evals/.env.example evals/runner/__init__.py evals/tests/__init__.py .gitignore
git commit -m "feat(evals): scaffold benchmark harness package"
```

---

### Task 2: Prompt schema (TDD)

**Files:**
- Create: `evals/runner/prompts.py`
- Create: `evals/tests/test_prompts.py`
- Create: `evals/prompts/schema.md`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_prompts.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from runner.prompts import Prompt, load_prompts


def test_load_minimal_prompt(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: minimal-1\n"
        "  source: https://example.com/q\n"
        "  prompt: extract audio\n"
        "  category: [audio]\n"
        "  difficulty: easy\n"
    )
    prompts = load_prompts(yaml)
    assert len(prompts) == 1
    p = prompts[0]
    assert p.id == "minimal-1"
    assert p.category == ["audio"]
    assert p.difficulty == "easy"
    assert p.spot_check is None


def test_load_prompt_with_spot_check(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: spot-1\n"
        "  source: rendi-internal\n"
        "  prompt: trim 10s to 25s\n"
        "  category: [seeking-and-trimming]\n"
        "  difficulty: medium\n"
        "  spot_check:\n"
        "    fixture: sample_1080p.mp4\n"
        "    assertions:\n"
        "      - {type: duration, op: approx, value: 15.0, tolerance: 0.5}\n"
        "      - {type: ffprobe_field, stream: 0, key: codec_name, equals: h264}\n"
    )
    prompts = load_prompts(yaml)
    assert prompts[0].spot_check is not None
    assert prompts[0].spot_check.fixture == "sample_1080p.mp4"
    assert len(prompts[0].spot_check.assertions) == 2


def test_duplicate_ids_rejected(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: dup\n"
        "  source: x\n"
        "  prompt: a\n"
        "  category: [audio]\n"
        "  difficulty: easy\n"
        "- id: dup\n"
        "  source: x\n"
        "  prompt: b\n"
        "  category: [audio]\n"
        "  difficulty: easy\n"
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_prompts(yaml)


def test_invalid_difficulty_rejected(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: bad\n"
        "  source: x\n"
        "  prompt: a\n"
        "  category: [audio]\n"
        "  difficulty: extreme\n"
    )
    with pytest.raises(ValidationError):
        load_prompts(yaml)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_prompts.py -v
```

Expected: `ImportError: cannot import name 'Prompt' from 'runner.prompts'`

- [ ] **Step 3: Implement `runner/prompts.py`**

```python
"""Prompt schema for the eval harness. Load + validate YAML prompt files."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, TypeAdapter

Difficulty = Literal["easy", "medium", "hard"]
Category = Literal[
    "encoding",
    "filters",
    "seeking-and-trimming",
    "audio",
    "video-effects",
    "text-and-subtitles",
    "asset-generation",
    "gpu-acceleration",
    "cross-category",
]


class FFprobeFieldAssertion(BaseModel):
    type: Literal["ffprobe_field"]
    stream: int
    key: str
    equals: str | None = None
    contains: str | None = None


class DurationAssertion(BaseModel):
    type: Literal["duration"]
    op: Literal["approx", "exact", "less_than", "greater_than"]
    value: float
    tolerance: float = 0.0


class NoBlackFramesAtStartAssertion(BaseModel):
    type: Literal["no_black_frames_at_start"]
    threshold: float = 0.05


class FileExistsAssertion(BaseModel):
    type: Literal["file_exists"]


Assertion = Annotated[
    Union[
        FFprobeFieldAssertion,
        DurationAssertion,
        NoBlackFramesAtStartAssertion,
        FileExistsAssertion,
    ],
    Field(discriminator="type"),
]


class SpotCheck(BaseModel):
    fixture: str
    assertions: list[Assertion]


class Prompt(BaseModel):
    id: str
    source: str
    prompt: str
    category: list[Category]
    difficulty: Difficulty
    spot_check: SpotCheck | None = None


_PromptList = TypeAdapter(list[Prompt])


def load_prompts(path: Path) -> list[Prompt]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    prompts = _PromptList.validate_python(raw)
    seen: set[str] = set()
    for p in prompts:
        if p.id in seen:
            raise ValueError(f"duplicate prompt id: {p.id}")
        seen.add(p.id)
    return prompts
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_prompts.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Write `evals/prompts/schema.md`**

````markdown
# Prompt schema

Each prompt is one YAML entry in `prompts/*.yaml`. See `runner/prompts.py` for the
authoritative Pydantic schema; this doc is for human curators.

```yaml
- id: so-2024-05-trim-keyframe       # unique slug, kebab-case, source-prefixed
  source: https://stackoverflow.com/questions/123  # URL or "rendi-internal"
  prompt: |
    Original phrasing of the user's question. Preserve typos, missing context, and
    wrong terminology — the plugin must perform on real questions, not idealized ones.
  category: [seeking-and-trimming]   # one or more from the categories list below
  difficulty: medium                 # easy / medium / hard
  spot_check:                        # OPTIONAL — only on the ~15% sampled for execution
    fixture: sample_1080p.mp4        # filename in evals/fixtures/
    assertions:
      - {type: duration, op: approx, value: 15.0, tolerance: 0.5}
      - {type: ffprobe_field, stream: 0, key: codec_name, equals: h264}
      - {type: no_black_frames_at_start}
      - {type: file_exists}
```

## Categories

`encoding`, `filters`, `seeking-and-trimming`, `audio`, `video-effects`,
`text-and-subtitles`, `asset-generation`, `gpu-acceleration`, `cross-category`.

## Difficulty heuristic

- **easy**: single-operation, well-specified ("convert mp4 to mkv without re-encoding").
- **medium**: multi-flag, some ambiguity ("trim and re-encode for the web").
- **hard**: filter graphs, multi-step audio, custom subtitle styling, GPU edge cases.
````

- [ ] **Step 6: Commit**

```bash
git add evals/runner/prompts.py evals/tests/test_prompts.py evals/prompts/schema.md
git commit -m "feat(evals): prompt schema + loader with validation"
```

---

### Task 3: Command extractor (TDD)

Pulls the canonical `ffmpeg` command out of a Claude response. The runner needs this; the spec mandates "take the last fenced block as canonical, log all blocks."

**Files:**
- Create: `evals/runner/extract.py`
- Create: `evals/tests/test_extract.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_extract.py`:

```python
from runner.extract import ExtractResult, extract_command


def test_single_fenced_sh_block():
    response = """Here's the command:

```sh
ffmpeg -i input.mp4 -c copy output.mkv
```
"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i input.mp4 -c copy output.mkv"
    assert r.no_command is False
    assert r.all_blocks == ["ffmpeg -i input.mp4 -c copy output.mkv"]


def test_takes_last_block_when_multiple():
    response = """First try:

```sh
ffmpeg -i a.mp4 b.mp4
```

Better:

```bash
ffmpeg -i a.mp4 -c copy b.mkv
```
"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i a.mp4 -c copy b.mkv"
    assert len(r.all_blocks) == 2


def test_accepts_shell_and_console_languages():
    response = """```shell
ffmpeg -i x.mp4 y.mp4
```"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i x.mp4 y.mp4"


def test_no_command_when_only_clarifying_questions():
    response = "What's the source codec and target container?"
    r = extract_command(response)
    assert r.command is None
    assert r.no_command is True
    assert r.all_blocks == []


def test_no_command_when_block_is_not_ffmpeg():
    response = """```python
print("hello")
```"""
    r = extract_command(response)
    assert r.command is None
    assert r.no_command is True


def test_strips_leading_dollar_prompt():
    response = """```sh
$ ffmpeg -i a.mp4 b.mp4
```"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i a.mp4 b.mp4"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_extract.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `runner/extract.py`**

```python
"""Extract the canonical ffmpeg command from a Claude response.

Convention: the LAST fenced shell block whose content starts with `ffmpeg` is the
canonical command. All blocks are preserved for later inspection. If no such block
exists, the response is treated as `no_command` (typically clarifying questions).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Match ```sh|bash|shell|console|zsh ... ``` blocks (case-insensitive language tag)
_FENCE = re.compile(
    r"```(?:sh|bash|shell|console|zsh)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class ExtractResult:
    command: str | None
    no_command: bool
    all_blocks: list[str]


def extract_command(response: str) -> ExtractResult:
    raw_blocks = [m.group(1).strip() for m in _FENCE.finditer(response)]
    blocks = [_strip_prompt(b) for b in raw_blocks]
    ffmpeg_blocks = [b for b in blocks if b.lower().startswith("ffmpeg")]
    if not ffmpeg_blocks:
        return ExtractResult(command=None, no_command=True, all_blocks=blocks)
    return ExtractResult(command=ffmpeg_blocks[-1], no_command=False, all_blocks=blocks)


def _strip_prompt(block: str) -> str:
    """Remove a leading `$ ` shell-prompt marker if present."""
    lines = block.splitlines()
    if lines and lines[0].lstrip().startswith("$ "):
        lines[0] = lines[0].split("$ ", 1)[1]
    return "\n".join(lines).strip()
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_extract.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/runner/extract.py evals/tests/test_extract.py
git commit -m "feat(evals): extract canonical ffmpeg command from claude response"
```

---

### Task 4: Budget guardrails (TDD)

Tracks cumulative cost across calls and aborts before exceeding `EVAL_BUDGET_USD`.

**Files:**
- Create: `evals/runner/budget.py`
- Create: `evals/tests/test_budget.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_budget.py`:

```python
import pytest

from runner.budget import Budget, BudgetExceeded, ModelPricing


def test_records_cost_under_cap():
    pricing = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    b = Budget(cap_usd=1.00)
    b.charge("claude-sonnet-4-6", input_tokens=1000, output_tokens=500, pricing=pricing)
    assert b.spent_usd == pytest.approx(0.003 + 0.0075, abs=1e-6)


def test_aborts_when_cap_exceeded():
    pricing = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    b = Budget(cap_usd=0.005)
    with pytest.raises(BudgetExceeded):
        b.charge("claude-sonnet-4-6", input_tokens=1000, output_tokens=500, pricing=pricing)


def test_check_before_spend_does_not_charge():
    pricing = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    b = Budget(cap_usd=0.005)
    assert b.would_exceed(input_tokens=1000, output_tokens=500, pricing=pricing) is True
    assert b.spent_usd == 0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_budget.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `runner/budget.py`**

```python
"""Budget tracker. Aborts the run before exceeding the configured USD cap."""
from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float   # USD per 1M input tokens
    output_per_mtok: float  # USD per 1M output tokens


# Pricing snapshot — adjust if Anthropic changes prices. Numbers as of 2026-05.
PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-6": ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-opus-4-7":   ModelPricing(input_per_mtok=15.0, output_per_mtok=75.0),
    "claude-haiku-4-5-20251001": ModelPricing(input_per_mtok=0.80, output_per_mtok=4.0),
}


@dataclass
class Budget:
    cap_usd: float
    spent_usd: float = 0.0
    log: list[tuple[str, float]] = field(default_factory=list)

    def cost_of(self, input_tokens: int, output_tokens: int, pricing: ModelPricing) -> float:
        return (input_tokens / 1_000_000) * pricing.input_per_mtok + (
            output_tokens / 1_000_000
        ) * pricing.output_per_mtok

    def would_exceed(self, input_tokens: int, output_tokens: int, pricing: ModelPricing) -> bool:
        return self.spent_usd + self.cost_of(input_tokens, output_tokens, pricing) > self.cap_usd

    def charge(
        self, label: str, input_tokens: int, output_tokens: int, pricing: ModelPricing
    ) -> None:
        cost = self.cost_of(input_tokens, output_tokens, pricing)
        if self.spent_usd + cost > self.cap_usd:
            raise BudgetExceeded(
                f"Adding {cost:.4f} USD for {label} would exceed cap "
                f"({self.spent_usd:.4f} + {cost:.4f} > {self.cap_usd:.4f})"
            )
        self.spent_usd += cost
        self.log.append((label, cost))
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_budget.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/runner/budget.py evals/tests/test_budget.py
git commit -m "feat(evals): budget guardrails with per-model pricing"
```

---

### Task 5: Verify the headless `claude -p` invocation works for both configs

Not TDD — this is a verification spike. We need to confirm the exact CLI shape that gives us a faithful "with-plugin" / "vanilla" pair before building the runner around it.

**Files:**
- Create: `evals/runner/_spike.py` (will be deleted at end of task)

- [ ] **Step 1: Write the spike script**

`evals/runner/_spike.py`:

```python
"""One-shot verification that we can drive `claude -p` headlessly with a plugin
loaded vs unloaded, with isolation from any globally-installed plugins.

Run from `evals/` with the repo root on the parent of cwd.
Delete this file once Task 5 is complete.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run_one(plugin_dir: Path | None, prompt: str) -> str:
    cmd = ["claude", "-p", "--model", "claude-sonnet-4-6"]
    if plugin_dir is not None:
        cmd += ["--plugin-dir", str(plugin_dir)]
    cmd += [prompt]

    with tempfile.TemporaryDirectory() as tmp_home:
        env = os.environ.copy()
        env["HOME"] = tmp_home
        env["USERPROFILE"] = tmp_home  # Windows
        # ANTHROPIC_API_KEY must already be in env
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude exited {result.returncode}\nstderr:\n{result.stderr}\nstdout:\n{result.stdout}"
            )
        return result.stdout


def main() -> int:
    if shutil.which("claude") is None:
        print("ERROR: `claude` not on PATH", file=sys.stderr)
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[2]   # evals/runner/_spike.py → repo root
    prompt = "Give me an ffmpeg command to extract the audio track from input.mp4 as AAC without re-encoding."

    print("=== VANILLA (no plugin, isolated HOME) ===")
    print(run_one(None, prompt))
    print()
    print("=== WITH PLUGIN (--plugin-dir, isolated HOME) ===")
    print(run_one(repo_root, prompt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the spike**

From `evals/`:

```bash
python -m runner._spike
```

- [ ] **Step 3: Verify the two outputs differ in expected ways**

The vanilla output should produce a plausible command. The with-plugin output should:
- Show evidence the plugin's skill engaged (it may discuss the workflow, mention reading references, etc.)
- Produce a command consistent with the cheatsheet's `ffmpeg -i input.mp4 -map 0:a:0 -acodec copy output.aac` shape.

If the spike fails (auth, flag mismatch, plugin not loading), debug here before proceeding. Common fixes:
- If `--plugin-dir` is not the correct flag, check `claude --help | grep -i plugin` and update.
- If isolated HOME breaks auth, switch to `CLAUDE_CONFIG_DIR=<tmp>` instead of `HOME=<tmp>` (then update `claude_invoke.py` in Task 6 accordingly).
- If `ANTHROPIC_API_KEY` env var isn't honored under isolated HOME, document the working setup in `evals/README.md`.

- [ ] **Step 4: Record the verified invocation**

Append a section to `evals/README.md`:

````markdown
## Verified headless invocation (recorded 2026-05-08)

The runner uses this shape for both configs:

```bash
HOME=<tempdir> claude -p --model <model> [--plugin-dir <repo-root>] "<prompt>"
```

`HOME` (and `USERPROFILE` on Windows) is redirected to a fresh temp directory per call,
so globally-installed plugins/agents/MCP cannot leak in. `ANTHROPIC_API_KEY` from the
parent env is passed through.

If you tweak this in the future, update `runner/claude_invoke.py` and re-run the spike
in `runner/_spike.py` (recreate it from git history if deleted).
````

- [ ] **Step 5: Delete the spike**

```bash
git rm evals/runner/_spike.py
```

- [ ] **Step 6: Commit**

```bash
git add evals/README.md
git commit -m "docs(evals): record verified headless claude -p invocation"
```

---

### Task 6: `claude_invoke.py` — runner wrapper (TDD-light)

Wraps the verified `claude -p` invocation. Hard to unit-test (shells out to a network-bound CLI), so we test the argument-construction logic and smoke-test the actual call.

**Files:**
- Create: `evals/runner/claude_invoke.py`
- Create: `evals/tests/test_claude_invoke.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_claude_invoke.py`:

```python
from pathlib import Path

from runner.claude_invoke import build_argv


def test_vanilla_argv():
    argv = build_argv(model="claude-sonnet-4-6", plugin_dir=None, prompt="hello")
    assert argv == ["claude", "-p", "--model", "claude-sonnet-4-6", "hello"]


def test_with_plugin_argv(tmp_path: Path):
    argv = build_argv(model="claude-sonnet-4-6", plugin_dir=tmp_path, prompt="hello")
    assert argv == [
        "claude", "-p",
        "--model", "claude-sonnet-4-6",
        "--plugin-dir", str(tmp_path),
        "hello",
    ]
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_claude_invoke.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `runner/claude_invoke.py`**

```python
"""Headless `claude -p` driver. See evals/README.md "Verified headless invocation"."""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InvokeResult:
    stdout: str
    stderr: str
    returncode: int


def build_argv(model: str, plugin_dir: Path | None, prompt: str) -> list[str]:
    argv = ["claude", "-p", "--model", model]
    if plugin_dir is not None:
        argv += ["--plugin-dir", str(plugin_dir)]
    argv.append(prompt)
    return argv


def invoke(
    *,
    model: str,
    plugin_dir: Path | None,
    prompt: str,
    timeout_s: int = 120,
) -> InvokeResult:
    """Spawn `claude -p` with isolated HOME so global plugins cannot leak in.

    ANTHROPIC_API_KEY must be set in the parent environment.
    """
    argv = build_argv(model=model, plugin_dir=plugin_dir, prompt=prompt)
    with tempfile.TemporaryDirectory(prefix="claude-eval-") as tmp_home:
        env = os.environ.copy()
        env["HOME"] = tmp_home
        env["USERPROFILE"] = tmp_home  # Windows
        result = subprocess.run(
            argv, env=env, capture_output=True, text=True, timeout=timeout_s
        )
    return InvokeResult(
        stdout=result.stdout, stderr=result.stderr, returncode=result.returncode
    )
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_claude_invoke.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/runner/claude_invoke.py evals/tests/test_claude_invoke.py
git commit -m "feat(evals): claude_invoke wrapper for headless runs"
```

---

### Task 7: Curate 30 smoke prompts

Manual curation. The deliverable is a YAML file conforming to the schema from Task 2.

**Files:**
- Create: `evals/prompts/smoke.yaml`

- [ ] **Step 1: Plan the distribution**

Target: 30 prompts.

| Bucket | Count | Source | Notes |
|---|---|---|---|
| Stack Overflow / Reddit | 20 | Public URLs | Pull from r/ffmpeg top of last year + Stack Overflow `[ffmpeg]` tag, votes ≥ 5. |
| Hand-authored "rendi-style" | 10 | `rendi-internal` | Phrased like a paying API customer would phrase it. Mark `source: rendi-internal`. Replace with real anonymized rendi prompts in Phase 2. |

Difficulty: 9 easy / 15 medium / 6 hard.

Categories: at least 2 prompts per category (encoding, filters, seeking-and-trimming, audio, video-effects, text-and-subtitles, asset-generation, gpu-acceleration), plus a few cross-category.

Spot-checks: 5 of the 30 (~17%) get a `spot_check` block. Pick from across difficulties.

- [ ] **Step 2: Source 20 SO/Reddit prompts**

For each, capture the original phrasing verbatim (preserve typos and missing context):

- Stack Overflow: filter by `[ffmpeg]` tag, sort by votes, skim top results from the last 3 years. Skip questions answered by trivial single-flag tweaks unless they cover a category that's underrepresented.
- Reddit r/ffmpeg: top of year + top of all-time, skip troubleshooting threads that don't have a clean question.

For each prompt, fill: `id`, `source` (URL), `prompt`, `category`, `difficulty`. Don't set `spot_check` yet.

- [ ] **Step 3: Hand-author 10 rendi-style prompts**

Cover scenarios a paying customer would ask: bulk transcoding, social-media format conversion (TikTok 9:16, YouTube Shorts), watermarking, subtitle burning, podcast audio normalization, GIF generation for marketing assets, etc. Phrase as a customer would — slightly imprecise, may have unstated business context.

For each: `id` prefixed `rendi-`, `source: rendi-internal`, plus the rest.

- [ ] **Step 4: Add 5 spot-checks**

Pick 5 prompts spanning difficulties and categories. For each, add a `spot_check` block with:
- `fixture`: pick from the fixtures list in Task 10 (`sample_1080p.mp4`, `sample_audio.mp3`, `sample_subtitles.srt`).
- `assertions`: 2–4 checks that distinguish a correct command from a broken one. E.g.:
  - For a "trim to 15s" prompt: `{type: duration, op: approx, value: 15.0, tolerance: 0.5}` + `{type: file_exists}`.
  - For an "add yuv420p for QuickTime" prompt: `{type: ffprobe_field, stream: 0, key: pix_fmt, equals: yuv420p}`.

- [ ] **Step 5: Validate the YAML**

```bash
python -c "from runner.prompts import load_prompts; ps = load_prompts('prompts/smoke.yaml'); print(f'{len(ps)} prompts loaded'); [print(p.id, p.difficulty, p.category) for p in ps]"
```

Expected: `30 prompts loaded` plus a list. Fix any validation errors.

- [ ] **Step 6: Commit**

```bash
git add evals/prompts/smoke.yaml
git commit -m "feat(evals): curate 30 smoke-test prompts (20 public + 10 rendi-style)"
```

---

### Task 8: Runner orchestrator (`run.py`)

CLI that drives `claude_invoke` for every (prompt × config) pair, extracts the command, and writes `raw.jsonl`.

**Files:**
- Create: `evals/runner/run.py`

- [ ] **Step 1: Implement `runner/run.py`**

```python
"""Drive `claude -p` for every prompt × config and capture raw.jsonl.

Usage:
    python -m runner.run --prompts prompts/smoke.yaml \
                         --model claude-sonnet-4-6 \
                         --out results/2026-05-08-sonnet46-smoke
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from runner.claude_invoke import invoke
from runner.extract import extract_command
from runner.prompts import Prompt, load_prompts


def _record(prompt: Prompt, config: str, model: str, plugin_dir: Path | None) -> dict:
    result = invoke(model=model, plugin_dir=plugin_dir, prompt=prompt.prompt)
    extracted = extract_command(result.stdout)
    return {
        "prompt_id": prompt.id,
        "config": config,
        "model": model,
        "command": extracted.command,
        "no_command": extracted.no_command,
        "all_blocks": extracted.all_blocks,
        "raw_response": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set (check evals/.env)", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path passed to claude --plugin-dir for the with-plugin config.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N prompts (smoke debugging).",
    )
    args = parser.parse_args(argv)

    prompts = load_prompts(args.prompts)
    if args.limit is not None:
        prompts = prompts[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    raw_path = args.out / "raw.jsonl"

    with raw_path.open("w", encoding="utf-8") as f:
        for i, prompt in enumerate(prompts, start=1):
            print(f"[{i}/{len(prompts)}] {prompt.id} ...", flush=True)
            for config, plugin_dir in (
                ("vanilla", None),
                ("with-plugin", args.repo_root),
            ):
                rec = _record(prompt, config, args.model, plugin_dir)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                status = "no-cmd" if rec["no_command"] else "ok"
                print(f"   {config}: {status}")

    print(f"\nWrote {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test on 2 prompts**

```bash
python -m runner.run --prompts prompts/smoke.yaml --model claude-sonnet-4-6 --out results/test-2 --limit 2
```

Expected: prints `[1/2]` and `[2/2]` lines, writes `results/test-2/raw.jsonl` with 4 lines (2 prompts × 2 configs). Each line is valid JSON with `command` populated for at least the with-plugin config.

- [ ] **Step 3: Inspect output**

```bash
python -c "import json; [print(json.dumps({k: v for k, v in json.loads(l).items() if k != 'raw_response'}, indent=2)) for l in open('results/test-2/raw.jsonl', encoding='utf-8')]"
```

Expected: 4 records with sensible commands.

- [ ] **Step 4: Clean up**

```bash
rm -r results/test-2
```

- [ ] **Step 5: Commit**

```bash
git add evals/runner/run.py
git commit -m "feat(evals): runner orchestrator producing raw.jsonl"
```

---

### Task 9: Curate fixtures from CC0 sources

**Files:**
- Create: `evals/fixtures/sample_1080p.mp4` (from Big Buck Bunny CC0)
- Create: `evals/fixtures/sample_audio.mp3`
- Create: `evals/fixtures/sample_subtitles.srt`
- Create: `evals/fixtures/README.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p evals/fixtures
```

- [ ] **Step 2: Generate `sample_1080p.mp4`**

Use ffmpeg's `lavfi` source (no download needed; license-clean):

```bash
ffmpeg -y -f lavfi -i testsrc=duration=30:size=1920x1080:rate=30 \
              -f lavfi -i sine=frequency=440:duration=30 \
              -c:v libx264 -preset veryfast -pix_fmt yuv420p \
              -c:a aac -b:a 128k \
              -movflags +faststart \
              evals/fixtures/sample_1080p.mp4
```

Expected: 30s 1080p H264 file, ~2–4 MB.

- [ ] **Step 3: Generate `sample_audio.mp3`**

```bash
ffmpeg -y -f lavfi -i sine=frequency=440:duration=20 -c:a libmp3lame -b:a 192k \
              evals/fixtures/sample_audio.mp3
```

Expected: 20s 192kbps MP3.

- [ ] **Step 4: Write `sample_subtitles.srt`**

`evals/fixtures/sample_subtitles.srt`:

```srt
1
00:00:01,000 --> 00:00:04,000
First subtitle line.

2
00:00:05,000 --> 00:00:08,000
Second subtitle line.

3
00:00:09,000 --> 00:00:12,000
Third subtitle line.
```

- [ ] **Step 5: Write `evals/fixtures/README.md`**

````markdown
# Fixture media

Synthetic test files generated locally — no external downloads, no third-party content,
no licensing complexity.

| File | How it was generated | License |
|---|---|---|
| `sample_1080p.mp4` | `ffmpeg -f lavfi -i testsrc=...,sine=...` (see commands below) | Procedurally generated, no copyrightable content |
| `sample_audio.mp3` | `ffmpeg -f lavfi -i sine=frequency=440:duration=20` | Procedurally generated, no copyrightable content |
| `sample_subtitles.srt` | Hand-written | MIT (matches repo) |

## Regenerating

If you change a fixture, regenerate with the commands recorded in
`docs/superpowers/plans/2026-05-08-plugin-evaluation.md` Task 9. Keep file sizes small —
these are committed to git, not pulled at runtime.

## Adding fixtures

Prefer `lavfi` synthetic sources or hand-authored small files. If you absolutely need
real-world media, use **Big Buck Bunny** (CC-BY 3.0, peach.blender.org) clips ≤10s and
add a credit line here.
````

- [ ] **Step 6: Verify fixtures play**

```bash
ffprobe -v error -show_format -show_streams evals/fixtures/sample_1080p.mp4
ffprobe -v error -show_format -show_streams evals/fixtures/sample_audio.mp3
```

Expected: streams listed, no errors.

- [ ] **Step 7: Commit**

```bash
git add evals/fixtures/
git commit -m "feat(evals): synthetic fixture media for spot-check execution"
```

---

### Task 10: Spot-check assertion library (TDD)

Evaluates the assertion types from the prompt schema against an actual output file.

**Files:**
- Create: `evals/runner/spot_check.py`
- Create: `evals/tests/test_spot_check.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_spot_check.py`:

```python
import shutil
import subprocess
from pathlib import Path

import pytest

from runner.prompts import (
    DurationAssertion,
    FFprobeFieldAssertion,
    FileExistsAssertion,
    NoBlackFramesAtStartAssertion,
)
from runner.spot_check import AssertionResult, evaluate_assertions

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


@pytest.fixture
def sample_mp4(tmp_path: Path) -> Path:
    out = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(out),
        ],
        check=True,
    )
    return out


def test_file_exists_assertion_passes(sample_mp4: Path):
    results = evaluate_assertions(sample_mp4, [FileExistsAssertion(type="file_exists")])
    assert results == [AssertionResult(passed=True, detail="exists")]


def test_file_exists_fails_when_missing(tmp_path: Path):
    results = evaluate_assertions(
        tmp_path / "missing.mp4", [FileExistsAssertion(type="file_exists")]
    )
    assert results[0].passed is False


def test_duration_approx_passes(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [DurationAssertion(type="duration", op="approx", value=10.0, tolerance=0.5)],
    )
    assert results[0].passed is True


def test_duration_approx_fails_outside_tolerance(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [DurationAssertion(type="duration", op="approx", value=5.0, tolerance=0.5)],
    )
    assert results[0].passed is False


def test_ffprobe_field_codec_h264(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [FFprobeFieldAssertion(type="ffprobe_field", stream=0, key="codec_name", equals="h264")],
    )
    assert results[0].passed is True


def test_ffprobe_field_pix_fmt_yuv420p(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [FFprobeFieldAssertion(type="ffprobe_field", stream=0, key="pix_fmt", equals="yuv420p")],
    )
    assert results[0].passed is True


def test_no_black_frames_at_start_passes(sample_mp4: Path):
    # testsrc is colorful — should pass.
    results = evaluate_assertions(
        sample_mp4, [NoBlackFramesAtStartAssertion(type="no_black_frames_at_start")]
    )
    assert results[0].passed is True
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_spot_check.py -v
```

Expected: ImportError on `runner.spot_check`.

- [ ] **Step 3: Implement `runner/spot_check.py`**

```python
"""Evaluate assertions from a prompt's spot_check block against an output file.

Used both as a library (for tests) and as a CLI (`python -m runner.spot_check ...`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random

from runner.prompts import (
    Assertion,
    DurationAssertion,
    FFprobeFieldAssertion,
    FileExistsAssertion,
    NoBlackFramesAtStartAssertion,
    Prompt,
    load_prompts,
)


@dataclass
class AssertionResult:
    passed: bool
    detail: str


def _ffprobe_json(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def _eval_file_exists(path: Path) -> AssertionResult:
    return AssertionResult(passed=path.exists(), detail="exists" if path.exists() else "missing")


def _eval_duration(path: Path, a: DurationAssertion) -> AssertionResult:
    info = _ffprobe_json(path)
    actual = float(info["format"]["duration"])
    if a.op == "approx":
        passed = abs(actual - a.value) <= a.tolerance
    elif a.op == "exact":
        passed = actual == a.value
    elif a.op == "less_than":
        passed = actual < a.value
    elif a.op == "greater_than":
        passed = actual > a.value
    else:
        raise ValueError(f"unknown duration op: {a.op}")
    return AssertionResult(passed=passed, detail=f"actual={actual:.3f}s expected {a.op} {a.value}±{a.tolerance}")


def _eval_ffprobe_field(path: Path, a: FFprobeFieldAssertion) -> AssertionResult:
    info = _ffprobe_json(path)
    streams = info.get("streams", [])
    if a.stream >= len(streams):
        return AssertionResult(passed=False, detail=f"stream {a.stream} not present")
    actual = streams[a.stream].get(a.key)
    if a.equals is not None:
        passed = actual == a.equals
        return AssertionResult(passed=passed, detail=f"{a.key}={actual!r} expected={a.equals!r}")
    if a.contains is not None:
        passed = a.contains in str(actual or "")
        return AssertionResult(passed=passed, detail=f"{a.key}={actual!r} contains={a.contains!r}")
    return AssertionResult(passed=actual is not None, detail=f"{a.key}={actual!r}")


def _eval_no_black_frames_at_start(path: Path, a: NoBlackFramesAtStartAssertion) -> AssertionResult:
    """Use ffmpeg's blackdetect filter on the first 2s — fail if any black detected."""
    result = subprocess.run(
        [
            "ffmpeg", "-v", "info", "-t", "2", "-i", str(path),
            "-vf", f"blackdetect=d=0.05:pic_th={1 - a.threshold}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=30,
    )
    has_black = "black_start" in result.stderr
    return AssertionResult(passed=not has_black, detail="no black detected" if not has_black else "black detected at start")


def evaluate_assertions(path: Path, assertions: list[Assertion]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    for a in assertions:
        if isinstance(a, FileExistsAssertion):
            out.append(_eval_file_exists(path))
        elif isinstance(a, DurationAssertion):
            out.append(_eval_duration(path, a))
        elif isinstance(a, FFprobeFieldAssertion):
            out.append(_eval_ffprobe_field(path, a))
        elif isinstance(a, NoBlackFramesAtStartAssertion):
            out.append(_eval_no_black_frames_at_start(path, a))
        else:
            raise TypeError(f"unhandled assertion type: {type(a).__name__}")
    return out


# ----------------------- CLI -----------------------

_FIXTURE_TOKEN = re.compile(r"\b(?:input\w*\.\w+|sample[\w-]*\.\w+)\b", re.IGNORECASE)


def _substitute_fixture(command: str, fixture_path: Path, output_path: Path) -> str:
    """Rewrite the command to point at our fixture for input and a tempfile for output.

    Heuristic: replace the FIRST input-looking filename with the fixture path, and the
    LAST filename token with the output path. Commands that fall outside this shape
    are flagged in spot_check.jsonl as `unrewritable=true` and skipped.
    """
    tokens = command.split()
    # Find the -i argument and replace what follows
    rewritten: list[str] = []
    i = 0
    found_i = False
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-i" and i + 1 < len(tokens):
            rewritten.append(tok)
            rewritten.append(str(fixture_path))
            i += 2
            found_i = True
            continue
        rewritten.append(tok)
        i += 1
    if not found_i:
        raise ValueError("no -i found")
    # Replace last token (assumed output path) with our output_path
    if not rewritten[-1].startswith("-"):
        rewritten[-1] = str(output_path)
    else:
        rewritten.append(str(output_path))
    return " ".join(rewritten)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--fixtures", default=Path("fixtures"), type=Path)
    parser.add_argument("--fraction", type=float, default=0.15, help="fraction of spot_check-having prompts to execute")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ERROR: ffmpeg/ffprobe not on PATH", file=sys.stderr)
        return 1

    prompts = {p.id: p for p in load_prompts(args.prompts)}
    raw_path = args.run_dir / "raw.jsonl"
    out_path = args.run_dir / "spot_check.jsonl"

    spot_eligible = [p for p in prompts.values() if p.spot_check is not None]
    rng = Random(args.seed)
    n = max(1, int(round(len(spot_eligible) * args.fraction)))
    sampled_ids = {p.id for p in rng.sample(spot_eligible, k=min(n, len(spot_eligible)))}
    print(f"Spot-checking {len(sampled_ids)} of {len(spot_eligible)} eligible prompts")

    with raw_path.open(encoding="utf-8") as f_in, out_path.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            rec = json.loads(line)
            if rec["prompt_id"] not in sampled_ids:
                continue
            if rec["no_command"] or rec["command"] is None:
                continue
            prompt = prompts[rec["prompt_id"]]
            assert prompt.spot_check is not None
            fixture = args.fixtures / prompt.spot_check.fixture
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "out.mp4"
                try:
                    rewritten = _substitute_fixture(rec["command"], fixture, output)
                except ValueError as e:
                    f_out.write(json.dumps({**_meta(rec), "unrewritable": True, "error": str(e)}) + "\n")
                    continue
                exec_result = subprocess.run(
                    rewritten, shell=True, capture_output=True, text=True, timeout=120
                )
                if exec_result.returncode != 0:
                    f_out.write(
                        json.dumps(
                            {**_meta(rec), "ran": False, "stderr": exec_result.stderr[-2000:]}
                        )
                        + "\n"
                    )
                    continue
                results = evaluate_assertions(output, prompt.spot_check.assertions)
                f_out.write(
                    json.dumps(
                        {
                            **_meta(rec),
                            "ran": True,
                            "results": [asdict(r) for r in results],
                            "all_passed": all(r.passed for r in results),
                        }
                    )
                    + "\n"
                )

    print(f"Wrote {out_path}")
    return 0


def _meta(rec: dict) -> dict:
    return {"prompt_id": rec["prompt_id"], "config": rec["config"], "command": rec["command"]}


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_spot_check.py -v
```

Expected: 7 passed (or 7 skipped if ffmpeg not on PATH — install ffmpeg if so).

- [ ] **Step 5: Commit**

```bash
git add evals/runner/spot_check.py evals/tests/test_spot_check.py
git commit -m "feat(evals): spot-check assertion library + CLI"
```

---

### Task 11: Judge module

Blinded LLM-as-judge. Uses Anthropic SDK directly (not Claude Code) so the judge is in a clean session with no plugin influence. Uses prompt caching on the rubric.

**Files:**
- Create: `evals/runner/judge.py`

- [ ] **Step 1: Implement `runner/judge.py`**

```python
"""Blinded LLM-as-judge over raw.jsonl. Writes judged.jsonl.

Per row: shuffles A/B labels (per-row blinding), sends both responses to a fresh
Claude Opus session with the rubric, parses scores + verdict + reasoning.

Uses prompt caching on the system prompt (rubric) — same rubric for every call.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from runner.budget import PRICING, Budget, BudgetExceeded

JUDGE_MODEL = "claude-opus-4-7"

RUBRIC_SYSTEM = """You are a senior FFmpeg expert grading two AI-generated responses to the same user request.

You will be shown:
- The user's request.
- Response A and Response B (one is from a baseline, one is from a tool under test — but you do NOT know which).

For each response, score on these axes. If the response contains a command, use these axes:

- correctness (0-3): would this command run without error and produce the requested output? 0 = wrong/broken; 1 = runs but mostly misses the goal; 2 = runs and mostly correct with minor issues; 3 = correct and complete.
- pitfall_coverage (0-3): does it apply the relevant playback-compat / faststart / yuv420p / setsar=1:1 / setpts-after-trim / hvc1 / similar defaults the situation calls for? 0 = ignores all relevant ones; 3 = nails them.
- efficiency_idiom (0-2): is it doing the work the cheap, standard way (e.g. -c copy when remuxing, single filter graph instead of multiple passes)? 0 = clearly wasteful or non-idiomatic; 2 = clean and idiomatic.

If the response contains NO command and is just clarifying questions, use this axis instead:

- clarification_quality (0-3): did it identify the RIGHT ambiguities (codec, target device, container, bitrate)? 0 = generic hedging or wrong questions; 3 = exactly what an expert would ask.

Then a verdict: which response is better? "A", "B", or "tie".

Penalize unsafe guesses (e.g., assuming H264 when the user said "make it work everywhere") more than neutral guesses (defaulting to MP4 container when unspecified).

Output STRICT JSON only, no prose, matching this schema:

{
  "a": {"correctness": int|null, "pitfall_coverage": int|null, "efficiency_idiom": int|null, "clarification_quality": int|null},
  "b": {"correctness": int|null, "pitfall_coverage": int|null, "efficiency_idiom": int|null, "clarification_quality": int|null},
  "verdict": "A" | "B" | "tie",
  "reasoning": "1-3 sentences explaining the verdict, naming specific flags or pitfalls."
}

Use null for axes that don't apply (e.g. `clarification_quality` is null when a command was given).
"""


def _build_user_message(prompt_text: str, response_a: str, response_b: str) -> str:
    return f"""User request:
---
{prompt_text}
---

Response A:
---
{response_a}
---

Response B:
---
{response_b}
---

Output the JSON now."""


def _extract_json(text: str) -> dict:
    """Tolerant JSON extractor — handles models wrapping JSON in ```json ... ```."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        return json.loads(obj_match.group(0))
    raise ValueError(f"no JSON found in: {text!r}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--budget-usd", type=float, default=float(os.environ.get("EVAL_BUDGET_USD", 30.0)))
    args = parser.parse_args(argv)

    raw_path = args.run_dir / "raw.jsonl"
    judged_path = args.run_dir / "judged.jsonl"

    # Group raw rows by prompt_id
    by_prompt: dict[str, dict[str, dict]] = defaultdict(dict)
    with raw_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_prompt[r["prompt_id"]][r["config"]] = r

    # Need prompt text — load it
    from runner.prompts import load_prompts
    prompts_by_id = {p.id: p for p in load_prompts(args.prompts)}

    rng = random.Random(args.seed)
    client = Anthropic()
    budget = Budget(cap_usd=args.budget_usd)
    pricing = PRICING[JUDGE_MODEL]

    with judged_path.open("w", encoding="utf-8") as out:
        for prompt_id, configs in by_prompt.items():
            if "vanilla" not in configs or "with-plugin" not in configs:
                print(f"   {prompt_id}: missing config; skipping", flush=True)
                continue
            # Per-row blinding
            swap = rng.random() < 0.5
            response_a_config = "with-plugin" if not swap else "vanilla"
            response_b_config = "vanilla" if not swap else "with-plugin"
            response_a = configs[response_a_config]["raw_response"]
            response_b = configs[response_b_config]["raw_response"]
            prompt_text = prompts_by_id[prompt_id].prompt

            # Pre-flight budget check (~2k input + 300 output as conservative estimate)
            if budget.would_exceed(input_tokens=2000, output_tokens=300, pricing=pricing):
                print(f"BUDGET CAP REACHED at prompt {prompt_id}; stopping.", file=sys.stderr)
                break

            try:
                msg = client.messages.create(
                    model=JUDGE_MODEL,
                    max_tokens=600,
                    system=[
                        {
                            "type": "text",
                            "text": RUBRIC_SYSTEM,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": _build_user_message(prompt_text, response_a, response_b),
                        }
                    ],
                )
            except Exception as e:
                out.write(json.dumps({"prompt_id": prompt_id, "error": str(e)}) + "\n")
                continue

            try:
                budget.charge(
                    f"judge:{prompt_id}",
                    input_tokens=msg.usage.input_tokens,
                    output_tokens=msg.usage.output_tokens,
                    pricing=pricing,
                )
            except BudgetExceeded as e:
                print(str(e), file=sys.stderr)
                break

            text = msg.content[0].text  # type: ignore[union-attr]
            try:
                parsed = _extract_json(text)
            except Exception as e:
                out.write(
                    json.dumps(
                        {"prompt_id": prompt_id, "error": f"unparseable: {e}", "raw": text}
                    )
                    + "\n"
                )
                continue

            # Translate verdict from A/B back to with-plugin/vanilla
            verdict_label_map = {"A": response_a_config, "B": response_b_config, "tie": "tie"}
            row = {
                "prompt_id": prompt_id,
                "blinding": {"A": response_a_config, "B": response_b_config},
                "scores": parsed,
                "verdict_resolved": verdict_label_map.get(parsed.get("verdict"), "tie"),
                "spent_usd": round(budget.spent_usd, 6),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"   {prompt_id}: {row['verdict_resolved']} (${budget.spent_usd:.4f})", flush=True)

    print(f"\nJudged. Total spent: ${budget.spent_usd:.4f}. Wrote {judged_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test on the 2-prompt run from Task 8**

Re-run Task 8 step 2 (`--limit 2 --out results/test-2`), then:

```bash
python -m runner.judge --run-dir results/test-2 --prompts prompts/smoke.yaml
```

Expected: writes `results/test-2/judged.jsonl` with 2 rows; each has `scores` and `verdict_resolved`. Cost should be a few cents.

- [ ] **Step 3: Clean up**

```bash
rm -r results/test-2
```

- [ ] **Step 4: Commit**

```bash
git add evals/runner/judge.py
git commit -m "feat(evals): blinded LLM-as-judge with prompt caching"
```

---

### Task 12: Report aggregator (TDD)

Aggregates `raw.jsonl` + `judged.jsonl` + `spot_check.jsonl` → `report.md`.

**Files:**
- Create: `evals/runner/report.py`
- Create: `evals/tests/test_report.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_report.py`:

```python
import json
from pathlib import Path

from runner.report import aggregate, format_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_aggregate_counts_verdicts(tmp_path: Path):
    judged = tmp_path / "judged.jsonl"
    _write_jsonl(judged, [
        {"prompt_id": "p1", "verdict_resolved": "with-plugin", "scores": {"verdict": "A"}, "blinding": {}},
        {"prompt_id": "p2", "verdict_resolved": "vanilla", "scores": {"verdict": "B"}, "blinding": {}},
        {"prompt_id": "p3", "verdict_resolved": "with-plugin", "scores": {"verdict": "A"}, "blinding": {}},
        {"prompt_id": "p4", "verdict_resolved": "tie", "scores": {"verdict": "tie"}, "blinding": {}},
    ])
    raw = tmp_path / "raw.jsonl"
    _write_jsonl(raw, [
        {"prompt_id": "p1", "config": "with-plugin", "no_command": False},
        {"prompt_id": "p1", "config": "vanilla", "no_command": False},
        {"prompt_id": "p2", "config": "with-plugin", "no_command": True},
        {"prompt_id": "p2", "config": "vanilla", "no_command": False},
    ])
    spot = tmp_path / "spot_check.jsonl"
    _write_jsonl(spot, [
        {"prompt_id": "p1", "config": "with-plugin", "ran": True, "all_passed": True},
        {"prompt_id": "p1", "config": "vanilla", "ran": True, "all_passed": False},
    ])

    agg = aggregate(judged_path=judged, raw_path=raw, spot_path=spot)

    assert agg.totals["with-plugin"] == 2
    assert agg.totals["vanilla"] == 1
    assert agg.totals["tie"] == 1
    assert agg.no_command_rate["with-plugin"] == 1
    assert agg.no_command_rate["vanilla"] == 0
    assert agg.spot_check_disagreement_count == 0  # judged plugin won, spot agrees


def test_format_report_smoke(tmp_path: Path):
    judged = tmp_path / "judged.jsonl"
    _write_jsonl(judged, [
        {"prompt_id": "p1", "verdict_resolved": "with-plugin", "scores": {"verdict": "A"}, "blinding": {}},
    ])
    raw = tmp_path / "raw.jsonl"
    _write_jsonl(raw, [
        {"prompt_id": "p1", "config": "with-plugin", "no_command": False},
        {"prompt_id": "p1", "config": "vanilla", "no_command": False},
    ])
    spot = tmp_path / "spot_check.jsonl"
    _write_jsonl(spot, [])

    agg = aggregate(judged_path=judged, raw_path=raw, spot_path=spot)
    md = format_report(agg)
    assert "# claude-ffmpeg evaluation" in md
    assert "with-plugin" in md
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_report.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `runner/report.py`**

```python
"""Aggregate raw.jsonl + judged.jsonl + spot_check.jsonl → report.md."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from runner.prompts import load_prompts


@dataclass
class Aggregate:
    totals: Counter = field(default_factory=Counter)              # with-plugin / vanilla / tie counts
    by_category: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    by_difficulty: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    no_command_rate: Counter = field(default_factory=Counter)     # config -> count of no_command
    top_plugin_losses: list[dict] = field(default_factory=list)
    spot_check_disagreement_count: int = 0
    spot_check_total: int = 0
    judged_count: int = 0


def aggregate(*, judged_path: Path, raw_path: Path, spot_path: Path, prompts_path: Path | None = None) -> Aggregate:
    agg = Aggregate()

    judged: list[dict] = []
    with judged_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "verdict_resolved" not in r:
                continue
            judged.append(r)
            agg.totals[r["verdict_resolved"]] += 1
    agg.judged_count = len(judged)

    # no_command per config
    with raw_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("no_command"):
                agg.no_command_rate[r["config"]] += 1

    # category / difficulty slicing requires prompts file
    if prompts_path is not None and prompts_path.exists():
        prompts_by_id = {p.id: p for p in load_prompts(prompts_path)}
        for r in judged:
            p = prompts_by_id.get(r["prompt_id"])
            if p is None:
                continue
            for cat in p.category:
                agg.by_category[cat][r["verdict_resolved"]] += 1
            agg.by_difficulty[p.difficulty][r["verdict_resolved"]] += 1

    # plugin losses (sorted by score gap if present, else just by appearance)
    losses = [r for r in judged if r["verdict_resolved"] == "vanilla"]
    agg.top_plugin_losses = losses[:10]

    # spot-check vs judge agreement
    if spot_path.exists():
        # Build a map (prompt_id, config) -> all_passed
        spot_results: dict[tuple[str, str], bool] = {}
        with spot_path.open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("ran") and "all_passed" in r:
                    spot_results[(r["prompt_id"], r["config"])] = r["all_passed"]

        for j in judged:
            plugin_pass = spot_results.get((j["prompt_id"], "with-plugin"))
            vanilla_pass = spot_results.get((j["prompt_id"], "vanilla"))
            if plugin_pass is None and vanilla_pass is None:
                continue
            agg.spot_check_total += 1
            verdict = j["verdict_resolved"]
            # Disagreement: judge said plugin won but its command actually failed.
            if verdict == "with-plugin" and plugin_pass is False:
                agg.spot_check_disagreement_count += 1
            if verdict == "vanilla" and vanilla_pass is False:
                agg.spot_check_disagreement_count += 1

    return agg


def _winrate(c: Counter) -> str:
    total = sum(c.values())
    if total == 0:
        return "(no data)"
    plugin = c.get("with-plugin", 0)
    vanilla = c.get("vanilla", 0)
    tie = c.get("tie", 0)
    return f"plugin {plugin}/{total} ({plugin / total:.0%}) | vanilla {vanilla}/{total} ({vanilla / total:.0%}) | tie {tie}/{total}"


def format_report(agg: Aggregate) -> str:
    lines = ["# claude-ffmpeg evaluation", ""]
    lines.append(f"Judged prompts: **{agg.judged_count}**")
    lines.append("")
    lines.append("## Headline win rate")
    lines.append("")
    lines.append(_winrate(agg.totals))
    lines.append("")

    if agg.by_category:
        lines.append("## Win rate by category")
        lines.append("")
        lines.append("| Category | Result |")
        lines.append("|---|---|")
        for cat, counter in sorted(agg.by_category.items()):
            lines.append(f"| {cat} | {_winrate(counter)} |")
        lines.append("")

    if agg.by_difficulty:
        lines.append("## Win rate by difficulty")
        lines.append("")
        lines.append("| Difficulty | Result |")
        lines.append("|---|---|")
        for diff in ("easy", "medium", "hard"):
            if diff in agg.by_difficulty:
                lines.append(f"| {diff} | {_winrate(agg.by_difficulty[diff])} |")
        lines.append("")

    lines.append("## `no_command` rate per config")
    lines.append("")
    lines.append(f"- with-plugin: **{agg.no_command_rate.get('with-plugin', 0)}**")
    lines.append(f"- vanilla:     **{agg.no_command_rate.get('vanilla', 0)}**")
    lines.append("")
    lines.append("> Asking too many clarifying questions when the user wants a quick command is itself a UX failure.")
    lines.append("")

    lines.append("## Spot-check vs judge agreement")
    lines.append("")
    if agg.spot_check_total == 0:
        lines.append("(no spot-check data)")
    else:
        rate = agg.spot_check_disagreement_count / agg.spot_check_total
        lines.append(f"Disagreement: **{agg.spot_check_disagreement_count} / {agg.spot_check_total} ({rate:.0%})**")
        if rate > 0.15:
            lines.append("")
            lines.append("> **WARNING:** disagreement >15%. Judge calls may not be reliable. Expand spot-check coverage.")
    lines.append("")

    lines.append("## Top plugin losses (most actionable section)")
    lines.append("")
    if not agg.top_plugin_losses:
        lines.append("(no losses recorded)")
    else:
        for loss in agg.top_plugin_losses:
            reasoning = loss.get("scores", {}).get("reasoning", "(no reasoning)")
            lines.append(f"- **{loss['prompt_id']}** — {reasoning}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    args = parser.parse_args(argv)

    agg = aggregate(
        judged_path=args.run_dir / "judged.jsonl",
        raw_path=args.run_dir / "raw.jsonl",
        spot_path=args.run_dir / "spot_check.jsonl",
        prompts_path=args.prompts,
    )
    md = format_report(agg)
    out = args.run_dir / "report.md"
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")
    print()
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_report.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/runner/report.py evals/tests/test_report.py
git commit -m "feat(evals): report aggregator + markdown formatter"
```

---

### Task 13: Run the Phase 1 smoke benchmark end-to-end

Validation checkpoint. Tests the full pipeline against the curated 30 smoke prompts.

**Files:**
- Create: `evals/results/<date>-sonnet46-smoke/report.md`

- [ ] **Step 1: Run the runner**

```bash
python -m runner.run --prompts prompts/smoke.yaml --model claude-sonnet-4-6 \
                     --out results/$(date +%Y-%m-%d)-sonnet46-smoke
```

(PowerShell: replace `$(date +%Y-%m-%d)` with `$(Get-Date -Format yyyy-MM-dd)`.)

Expected: 30 lines printed (one per prompt), 60 records in `raw.jsonl`. Run takes ~10–25 minutes depending on Claude Code latency.

- [ ] **Step 2: Run the judge**

```bash
python -m runner.judge --run-dir results/<date>-sonnet46-smoke --prompts prompts/smoke.yaml
```

Expected: 30 verdict lines, total spend reported under $5. Writes `judged.jsonl`.

- [ ] **Step 3: Run spot-check**

```bash
python -m runner.spot_check --run-dir results/<date>-sonnet46-smoke --prompts prompts/smoke.yaml --fraction 1.0
```

(For smoke we run all 5 — `--fraction 1.0`.)

Expected: 5 spot-check rows in `spot_check.jsonl`.

- [ ] **Step 4: Generate the report**

```bash
python -m runner.report --run-dir results/<date>-sonnet46-smoke --prompts prompts/smoke.yaml
```

Expected: report prints to stdout and writes `report.md`. Should show non-zero verdicts in all sections.

- [ ] **Step 5: Sanity-check the report**

Open `results/<date>-sonnet46-smoke/report.md` and verify:

- Headline win rate is computed and not 0/0.
- Category breakdown lists the categories from the smoke set.
- `no_command` rate is populated per config.
- Top plugin losses section has items if vanilla won any.
- Spot-check disagreement is sane (low or zero on 5 spot-checks).

**Decision point — DO NOT proceed to Phase 2 unless the smoke result is sane:**
- Did the harness run end-to-end without manual intervention? If no — fix the broken stage before scaling to 150.
- Is the win rate plausible (not 100/0 either way, not all ties)? If not — likely a blinding bug or rubric issue; investigate before Phase 2.
- Was the spot-check disagreement rate ≤15%? If higher — judge is unreliable; tighten the rubric or add more spot-checks before publishing larger numbers.

- [ ] **Step 6: Commit the report**

```bash
git add evals/results/<date>-sonnet46-smoke/report.md
git commit -m "feat(evals): phase 1 smoke benchmark results"
```

(`raw.jsonl`, `judged.jsonl`, `spot_check.jsonl` are gitignored — only `report.md` is committed.)

---

## Phase 1 → Phase 2 review checkpoint

**Stop here and review with the project owner before proceeding.** Phase 2 is a multi-day effort (curation of 150 prompts, full Sonnet pass, Opus subset). It is wasted effort if Phase 1 surfaced harness bugs or rubric problems.

Questions to answer before starting Phase 2:

1. Did the smoke report tell us something useful? (If "yes" — proceed. If "no, the data feels noisy" — tighten rubric and re-run smoke.)
2. Are there prompt categories where the plugin clearly underperforms? Note them — Phase 2 should oversample those.
3. Is the spot-check rewrite heuristic in `_substitute_fixture` working, or are too many commands flagged `unrewritable`? If unrewritable rate >30%, broaden the heuristic before Phase 2.
4. Is the budget cap appropriate? Estimate cost for 150-prompt run from smoke spend × 5; adjust `EVAL_BUDGET_USD` if needed.

---

## Phase 2 — scale to 150 (Tasks 14–18)

Lighter detail by design — Phase 2 gates on Phase 1 outcomes and may need adjustments based on what smoke reveals.

---

### Task 14: Anonymization tool for rendi text dumps

Aggressive scrubbing of customer prompt dumps. Per design call: "as many as possible."

**Files:**
- Create: `evals/runner/anonymize.py`
- Create: `evals/tests/test_anonymize.py`

- [ ] **Step 1: Write the failing test**

`evals/tests/test_anonymize.py`:

```python
from runner.anonymize import anonymize_prompt


def test_strips_filenames_to_neutral_placeholders():
    text = "I want to convert acme_demo_video.mp4 to webm"
    out = anonymize_prompt(text)
    assert "acme_demo_video" not in out
    assert "input.mp4" in out or "input" in out


def test_strips_paths():
    text = "process /home/jdoe/customers/acme/raw/movie.mov"
    out = anonymize_prompt(text)
    assert "jdoe" not in out
    assert "acme" not in out
    assert "customers" not in out


def test_strips_email_and_url():
    text = "see https://acme.example.com/api?key=abc and email me at user@acme.example.com"
    out = anonymize_prompt(text)
    assert "acme.example.com" not in out
    assert "user@" not in out
    assert "key=abc" not in out


def test_strips_uuids_and_long_hex_ids():
    text = "job 550e8400-e29b-41d4-a716-446655440000 and customer 9f3b2c1d8a"
    out = anonymize_prompt(text)
    assert "550e8400-e29b-41d4-a716-446655440000" not in out


def test_preserves_ffmpeg_terminology():
    text = "I need yuv420p with -movflags +faststart"
    out = anonymize_prompt(text)
    assert "yuv420p" in out
    assert "+faststart" in out
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_anonymize.py -v
```

- [ ] **Step 3: Implement `runner/anonymize.py`**

```python
"""Aggressive anonymization for rendi.dev customer prompt dumps.

Strips: filenames, file paths, URLs, emails, UUIDs, long hex/base64 IDs, business
names (heuristic — capitalized multi-word phrases that aren't FFmpeg terms).

Preserves: FFmpeg terminology (codec names, flags, parameters).

Usage:
    python -m runner.anonymize input.txt > anonymized.txt
    # then hand-review and convert each block to a YAML prompt entry.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Whitelist of FFmpeg terms (kept verbatim even if they look identifying)
_FFMPEG_TERMS = {
    "yuv420p", "yuv422p", "yuv444p",
    "h264", "h265", "hevc", "av1", "vp9", "aac", "mp3", "opus", "flac",
    "mp4", "mkv", "webm", "mov", "avi", "ts", "m4a", "m3u8", "flv",
    "libx264", "libx265", "libvpx-vp9", "libmp3lame", "libopus",
    "faststart", "movflags", "vtag", "hvc1", "setsar", "setpts",
    "atempo", "amix", "concat", "overlay", "scale", "pad", "crop",
}

_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/)\S+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_LONG_HEX_RE = re.compile(r"\b[0-9a-f]{10,}\b", re.IGNORECASE)

# Filename: any token with an extension we recognize as media/related
_MEDIA_EXTS = "mp4|mkv|webm|mov|avi|ts|m4a|m3u8|flv|mp3|wav|flac|opus|aac|srt|ass|vtt|jpg|jpeg|png|gif"
_FILENAME_RE = re.compile(rf"\b[\w.-]+\.({_MEDIA_EXTS})\b", re.IGNORECASE)


def anonymize_prompt(text: str) -> str:
    text = _URL_RE.sub("[URL]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _UUID_RE.sub("[ID]", text)
    text = _PATH_RE.sub("[PATH]", text)

    # Filenames -> input.<ext> / output.<ext> placeholders by ordinal
    seen_inputs = 0
    def _filename_sub(m: re.Match) -> str:
        nonlocal seen_inputs
        ext = m.group(1).lower()
        if seen_inputs == 0:
            seen_inputs += 1
            return f"input.{ext}"
        return f"output.{ext}"
    text = _FILENAME_RE.sub(_filename_sub, text)

    # Long hex/base64-like tokens
    text = _LONG_HEX_RE.sub(
        lambda m: m.group(0) if m.group(0).lower() in _FFMPEG_TERMS else "[ID]",
        text,
    )
    return text


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python -m runner.anonymize <input.txt>", file=sys.stderr)
        return 1
    raw = Path(args[0]).read_text(encoding="utf-8")
    print(anonymize_prompt(raw))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_anonymize.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add evals/runner/anonymize.py evals/tests/test_anonymize.py
git commit -m "feat(evals): aggressive anonymization for rendi text dumps"
```

---

### Task 15: Curate `prompts/stack-overflow.yaml` (~75 prompts)

Manual curation, same shape as Task 7 step 2 but at scale.

**Files:**
- Create: `evals/prompts/stack-overflow.yaml`

- [ ] **Step 1: Pull and curate ~75 prompts**

Same heuristic as smoke (Task 7 step 2). Distribute by category — at least 7 per category, plus extras in the categories Phase 1 surfaced as plugin-weak.

- [ ] **Step 2: Add spot_check blocks**

Aim for 12–15 spot-checks (~15–20% of these 75). Use existing fixtures where possible; add new fixtures (Task 16) only when the assertions can't be expressed against existing files.

- [ ] **Step 3: Validate**

```bash
python -c "from runner.prompts import load_prompts; print(len(load_prompts('prompts/stack-overflow.yaml')), 'prompts')"
```

Expected: ~75.

- [ ] **Step 4: Commit**

```bash
git add evals/prompts/stack-overflow.yaml
git commit -m "feat(evals): curate stack-overflow.yaml (~75 public prompts)"
```

---

### Task 16: Curate `prompts/rendi-logs.yaml` from anonymized text dump

**Files:**
- Create: `evals/prompts/rendi-logs.yaml`

- [ ] **Step 1: Get the text dump from the user**

This task blocks on input from the user. They provide a plain-text file with one prompt per blank-line-separated block.

- [ ] **Step 2: Anonymize the dump**

```bash
python -m runner.anonymize rendi_dump.txt > rendi_anonymized.txt
```

- [ ] **Step 3: Hand-review the anonymization**

Open `rendi_anonymized.txt` and check that no identifying content survived. The anonymizer is aggressive but not perfect — fix edge cases by hand.

- [ ] **Step 4: Convert to YAML**

For each block, create one YAML entry:

```yaml
- id: rendi-NNN-<short-slug>
  source: rendi-internal
  prompt: |
    <anonymized text>
  category: [<best-guess>]
  difficulty: <easy|medium|hard>
```

Aim for ~75 prompts. If the dump has more, oversample for the categories Phase 1 surfaced as plugin-weak. If fewer, fall back to padding with hand-authored rendi-style prompts (mark them clearly with `id: rendi-synthetic-NNN-...`).

- [ ] **Step 5: Add spot_check blocks**

Same heuristic — ~15% with spot_checks.

- [ ] **Step 6: Validate**

```bash
python -c "from runner.prompts import load_prompts; print(len(load_prompts('prompts/rendi-logs.yaml')))"
```

- [ ] **Step 7: Delete the dump files**

```bash
rm rendi_dump.txt rendi_anonymized.txt
```

(They must NOT enter git history.)

- [ ] **Step 8: Commit**

```bash
git add evals/prompts/rendi-logs.yaml
git commit -m "feat(evals): curate rendi-logs.yaml from anonymized customer prompts"
```

---

### Task 17: Run full Sonnet benchmark + curated Opus subset

**Files:**
- Create: `evals/results/<date>-sonnet46/report.md`
- Create: `evals/results/<date>-opus47-subset/report.md`
- Create: `evals/prompts/opus_subset.yaml` — manually curated ~50 hardest prompts from the union of `stack-overflow.yaml` + `rendi-logs.yaml`.

- [ ] **Step 1: Build the Opus subset YAML**

Pick ~50 prompts oversampled from: filter graphs, multi-step audio, custom subtitle styling, GPU edge cases, and any categories the Phase 1 smoke flagged as plugin-weak. These are simply copies of the relevant entries from the larger YAMLs into a new file.

```bash
git add evals/prompts/opus_subset.yaml
git commit -m "feat(evals): curate ~50-prompt opus subset from hardest categories"
```

- [ ] **Step 2: Combine SO + rendi for the full Sonnet run**

Create `evals/prompts/full.yaml` by concatenating `stack-overflow.yaml` and `rendi-logs.yaml`:

```bash
python -c "
import yaml
so = yaml.safe_load(open('prompts/stack-overflow.yaml'))
rendi = yaml.safe_load(open('prompts/rendi-logs.yaml'))
yaml.safe_dump(so + rendi, open('prompts/full.yaml', 'w'), sort_keys=False)
"
```

- [ ] **Step 3: Run the full Sonnet benchmark**

```bash
python -m runner.run        --prompts prompts/full.yaml --model claude-sonnet-4-6 --out results/<date>-sonnet46
python -m runner.judge      --run-dir results/<date>-sonnet46 --prompts prompts/full.yaml
python -m runner.spot_check --run-dir results/<date>-sonnet46 --prompts prompts/full.yaml --fraction 0.15
python -m runner.report     --run-dir results/<date>-sonnet46 --prompts prompts/full.yaml
```

- [ ] **Step 4: Run the Opus subset**

```bash
python -m runner.run        --prompts prompts/opus_subset.yaml --model claude-opus-4-7 --out results/<date>-opus47-subset
python -m runner.judge      --run-dir results/<date>-opus47-subset --prompts prompts/opus_subset.yaml
python -m runner.spot_check --run-dir results/<date>-opus47-subset --prompts prompts/opus_subset.yaml --fraction 0.15
python -m runner.report     --run-dir results/<date>-opus47-subset --prompts prompts/opus_subset.yaml
```

- [ ] **Step 5: Commit reports**

```bash
git add evals/results/<date>-sonnet46/report.md evals/results/<date>-opus47-subset/report.md
git commit -m "feat(evals): phase 2 full benchmark results (sonnet 4.6 + opus 4.7 subset)"
```

---

### Task 18: Phase 2 reflection and link from main README

**Files:**
- Modify: `claude-ffmpeg/README.md`

- [ ] **Step 1: Add eval section to root README**

Append a section after `## Status`:

```markdown
## Evaluation

This plugin is benchmarked against vanilla Claude on real-world FFmpeg prompts.
See [`evals/`](evals/) for the harness and [`evals/results/`](evals/results/) for
the latest reports. The most recent headline numbers:

- **Sonnet 4.6, 150 prompts:** see `evals/results/<latest>-sonnet46/report.md`
- **Opus 4.7, 50-prompt hard subset:** see `evals/results/<latest>-opus47-subset/report.md`
```

(Replace `<latest>` with the actual dated directory.)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): link to plugin evaluation harness and latest reports"
```

---

## Self-review

I'm running the plan against the spec and checking for placeholders, type consistency, and gaps:

**Spec coverage:**
- Goal (uplift + coverage measurement) → Tasks 8 (runner), 11 (judge), 12 (report).
- 150-prompt corpus, 75/75 split → Tasks 15, 16. Smoke-first via Task 7 (30 prompts).
- Cheatsheet-derived prompts excluded → noted in Task 7 step 2 ("don't pull from the cheatsheet"). Stronger note in Task 15: kept by inheritance from Task 7's heuristic.
- YAML schema with spot_check optional → Task 2.
- `evals/` repo layout matches spec exactly → Task 1.
- Headless `claude -p` with-plugin/vanilla, isolated `HOME` → Tasks 5–6.
- Sonnet 4.6 full / Opus 4.7 ~50-prompt subset → Task 17.
- Last fenced block as canonical command → Task 3.
- Blinded judge with 4-axis rubric (correctness/pitfalls/idiom/clarification) → Task 11.
- Tie-rate guardrail >25% → Captured in Task 13 step 5 decision point. Not auto-enforced; documented.
- ~15% spot-check, ffprobe-based assertions → Tasks 9–10.
- `no_command` rate per config in report → Task 12.
- Top plugin losses with reasoning → Task 12.
- Spot-check vs judge agreement (<15% target) → Task 12 + Task 13 decision point.
- Anonymization → Task 14.
- API budget cap → Task 4 + integrated in Task 11 (judge calls).
- Staged rollout (smoke → full) → Phase 1 / Phase 2 split + checkpoint between Tasks 13 and 14.
- Phase 3 (CI) deferred per spec → not planned, correct.

**Type consistency:** `Prompt`, `SpotCheck`, `*Assertion` (Pydantic models from Task 2) are imported and used in Tasks 10–12 with consistent names. `ExtractResult` from Task 3 used by Task 8. `InvokeResult` from Task 6 used by Task 8. `Budget`, `BudgetExceeded`, `ModelPricing`, `PRICING` from Task 4 used by Task 11. `Aggregate` from Task 12 self-contained. All consistent.

**Placeholder scan:** No "TBD" / "TODO" / "implement later" / "add appropriate error handling" patterns in any step. Each code step shows complete code. Spike-style verification in Task 5 has explicit fallbacks rather than "figure it out."

**Scope check:** Phase 1 is fully concrete (15 tasks with bite-sized steps). Phase 2 is appropriately lighter (5 tasks) because it gates on Phase 1 outcomes — its detail level matches the uncertainty.

No issues found. Plan complete.

---

## Cost expectation summary

(Repeated from `evals/README.md` for plan reviewers.)

| Run | Prompts | Calls | Estimated cost |
|---|---|---|---|
| Phase 1 smoke (Sonnet) | 30 | 60 runner + 30 judge | $3–5 |
| Phase 2 full (Sonnet) | 150 | 300 runner + 150 judge | $15–25 |
| Phase 2 hard subset (Opus) | 50 | 100 runner + 50 judge | $10–20 |

Default `EVAL_BUDGET_USD=30` covers a single run with margin. Total cost across the full Phase 1 + Phase 2 sequence: **~$30–50**.
