# claude-ffmpeg plugin evaluation — design

**Date:** 2026-05-08
**Author:** Yuval Yakubov
**Status:** Design — pending implementation plan

## Goal

Prove (or disprove) that installing `claude-ffmpeg` produces meaningfully better FFmpeg commands than vanilla Claude on real-world prompts. The output is a reproducible benchmark — re-runnable on every plugin change and every new Claude model release — that doubles as a credible artifact for `rendi.dev`.

The two success criteria the eval must measure:

1. **Uplift over vanilla Claude.** For the same natural-language request, the plugin's command is meaningfully better (correctness, pitfall coverage, idiom).
2. **Coverage of real-world requests.** Performance holds across what FFmpeg users actually ask for, not just what the cheatsheet covers.

## Non-goals

- Marketing copy or a public leaderboard. Internal-quality artifact first; publication is downstream.
- Comparing against non-Claude models (GPT, Gemini). Within scope to add later; out of scope here.
- Training data or fine-tuning the plugin. The eval informs the plugin; it doesn't auto-fix it.

## Corpus — 150 prompts

| Source | Count | Notes |
|---|---|---|
| Stack Overflow + Reddit (r/ffmpeg) | ~75 | Public, citable, captures "what people Google when stuck." Top-voted and recent within last ~3 years. |
| `rendi.dev` request logs | ~75 | Anonymized customer prompts. Strip filenames, customer IDs, internal paths to neutral placeholders before any file enters the repo. |

**Excluded:** prompts derived from the cheatsheet itself (biased — the plugin was built from the cheatsheet, would self-grade well, would prove nothing).

**Curation guidance for prompts:** phrased as the user originally phrased them (typos, missing context, wrong terminology preserved). The plugin must perform on real questions, not idealized ones.

**Difficulty distribution target:** ~30% easy (single-operation, well-specified), ~50% medium (multi-flag, some ambiguity), ~20% hard (filter graphs, multi-step audio, GPU edge cases, custom subtitle styling).

**Category distribution target** (mirrors the skill's reference structure): encoding, filters, seeking-and-trimming, audio, video-effects, text-and-subtitles, asset-generation, gpu-acceleration, plus a "cross-category" bucket for prompts that span multiple references.

## Prompt schema

YAML, one entry per prompt:

```yaml
- id: so-2024-05-trim-keyframe
  source: https://stackoverflow.com/questions/...   # url for SO/Reddit; "rendi-internal" for logs
  prompt: "I want to cut my mp4 from 10s to 25s without re-encoding, but the start is black for two seconds. How do I fix it?"
  category: [seeking-and-trimming]
  difficulty: medium                                # easy / medium / hard
  spot_check:                                       # optional; only on the ~15% sampled for execution
    fixture: sample_1080p.mp4
    assertions:
      - { type: duration, op: approx, value: 15.0, tolerance: 0.5 }
      - { type: ffprobe_field, stream: 0, key: codec_name, equals: h264 }
      - { type: no_black_frames_at_start }
```

Schema documented in `evals/prompts/schema.md`. Keep it minimal — every field must justify itself in the report or it gets cut.

## Repo layout

```
claude-ffmpeg/
├── evals/
│   ├── prompts/
│   │   ├── stack-overflow.yaml
│   │   ├── rendi-logs.yaml
│   │   └── schema.md
│   ├── fixtures/                    # input media for spot-check execution
│   │   ├── sample_1080p.mp4
│   │   ├── sample_audio.mp3
│   │   ├── sample_subtitles.srt
│   │   └── README.md                # provenance / licensing of each fixture
│   ├── runner/
│   │   ├── run.py                   # spawns claude -p (with/without plugin), captures commands
│   │   ├── judge.py                 # LLM-as-judge, blind, rubric-scored
│   │   ├── spot_check.py            # executes ~15% of pairs, validates ffprobe output
│   │   └── report.py                # aggregates → report.md
│   ├── results/
│   │   └── 2026-05-08-sonnet46/     # one dir per run
│   │       ├── raw.jsonl
│   │       ├── judged.jsonl
│   │       ├── spot_check.jsonl
│   │       └── report.md
│   └── README.md
```

## Components

### Runner (`run.py`)

Per prompt, spawns two `claude -p` invocations:

- **with-plugin:** `claude -p --plugin-dir <repo-root>` — the actual installation experience.
- **vanilla:** `claude -p` with no plugin loaded, fresh session.

Same model, same prompt, same temperature, fresh session for each call. Captures the final assistant message, extracts the **last** fenced ```sh / ```bash code block as the canonical command (matches "here's what to run" UX); logs all blocks in `raw.jsonl` so we can revisit.

If no command block is found, marks the row `no_command: true` and stores the full response for the judge to evaluate as a clarification-quality case.

`raw.jsonl` schema (one line per [prompt, config] pair):

```json
{"prompt_id": "...", "config": "with-plugin|vanilla", "model": "claude-sonnet-4-6", "command": "ffmpeg -i ...", "no_command": false, "all_blocks": [...], "raw_response": "..."}
```

**Cost guardrails:** runner has a hard cap on max tokens per call and max calls per run, surfaced in `evals/README.md`. Default budget for one full Sonnet run estimated up front.

### Judge (`judge.py`)

Reads `raw.jsonl`, groups rows by `prompt_id`, sends each (prompt, config-A-command, config-B-command) triple to a fresh Claude Opus session. **Per-row blinding:** A/B labels are randomized so the judge cannot tell which side is the plugin. No model identity in the judge prompt.

**Rubric — when both sides returned a command:**

- **Correctness** (0–3): would this command run without error and produce the requested output?
- **Pitfall coverage** (0–3): does it apply the relevant playback-compat / faststart / yuv420p / setsar / setpts-after-trim defaults the situation calls for?
- **Efficiency / idiom** (0–2): is it doing the work the cheap/standard way?
- **Verdict:** A wins / B wins / tie.

**Rubric — when one or both sides returned no command (clarifying questions instead):**

- **Clarification quality** (0–3): did the response identify the *right* ambiguities (codec, target device, bitrate, container)? Are these questions a real expert would ask, or generic hedging?
- **Verdict:** A wins / B wins / tie. Meaningfully better questions count as a win on the same headline metric.

Judge writes `judged.jsonl` with scores, verdict, and freeform reasoning per row. **Reasoning is the most valuable output** — it tells us *why* the plugin wins or loses, which drives future plugin improvements.

**Tie-rate guardrail:** if overall tie rate >25%, the rubric is treated as broken and tightened before numbers are published.

### Spot-checker (`spot_check.py`)

For prompts with `spot_check` defined (~15% of the 150, sampled to cover all categories): runs both commands against `fixtures/<file>`, runs `ffprobe -show_streams -show_format` on the output, evaluates the assertions list. Writes `spot_check.jsonl`.

Used to **calibrate the judge**: if the judge said "plugin wins" but the plugin's command segfaults, that's a calibration problem. Target: <15% spot-check-vs-judge disagreement. Above that, we don't trust the judge and add execution coverage until disagreement comes down.

### Report generator (`report.py`)

Aggregates from `judged.jsonl` + `spot_check.jsonl`:

- **Headline:** overall win rate (plugin wins / vanilla wins / tie).
- **By category:** win rate per FFmpeg topic — exposes where the plugin's references actually help vs where they don't.
- **By difficulty:** win rate at easy / medium / hard — does the plugin's value scale with prompt difficulty?
- **`no_command` rate per config:** over-asking clarifying questions is a UX failure; tracked separately even when judge calls those rows ties.
- **Top plugin losses:** the 10 prompts where vanilla beat the plugin most decisively, with judge reasoning. **Most actionable section** — drives future plugin work.
- **Spot-check vs judge agreement rate:** sanity check on judge reliability.

Output: `report.md` per run, committed alongside the `raw.jsonl` for full reproducibility.

## Models — what we run

| Model | Coverage | Rationale |
|---|---|---|
| Claude Sonnet 4.6 | Full 150-prompt benchmark | Most paying users run Sonnet. Headline numbers come from here. |
| Claude Opus 4.7 | Curated ~50-prompt subset | Oversampled from the hardest categories (filter graphs, multi-step audio, custom subtitle styling, GPU). Where model capability matters most. |

Haiku and prior model versions deferred — easy to add as additional `results/` directories once the harness is stable.

## Edge cases and how we handle them

- **Multiple candidate commands in one response.** Take the last fenced block as canonical; log all in `raw.jsonl`.
- **No command, just clarifying questions.** Mark `no_command: true`; judge scores on the clarification-quality sub-rubric. Rolls into headline win rate. `no_command` rate also reported separately per config.
- **Judge ties / refusal to call.** Allowed; tracked. >25% tie rate triggers rubric tightening before publication.
- **Spot-check disagrees with judge.** Calibration signal. >15% disagreement → expand spot-check coverage; don't trust judge numbers until agreement comes back in range.
- **Under-specified prompt.** Both sides guess. Judge instructed to penalize *unsafe* guesses (assuming H264 when user said "make it work everywhere") more than *neutral* guesses (defaulting to MP4 container when unspecified).
- **rendi.dev log anonymization.** Preprocessing step before any log enters the repo. Strip filenames, customer IDs, paths → neutral placeholders (`input.mp4`, `output.mp4`). Raw logs never committed.
- **API cost runaway.** Hard cap on tokens per call and calls per run in `run.py`. Default budgets surfaced in `evals/README.md`.

## Staged rollout

1. **Phase 1 — 30-prompt smoke test.** Mixed categories, mixed sources. Drive end-to-end through runner → judge → spot-check → report. Goal: catch harness bugs *before* curating 150 prompts that depend on it.
2. **Phase 2 — scale to 150.** Curate the remaining prompts. Run full Sonnet pass + curated Opus subset. Publish first report.
3. **Phase 3 — CI-runnable.** `make eval` or equivalent; runnable on every plugin change. Deferred until Phase 2 ships and the harness has settled.

## Out of scope

- Comparison against non-Claude models.
- Training-data extraction or auto-fixing the plugin from eval results.
- Public leaderboard infrastructure.
- Latency/cost measurement (could be added; not the primary question).

## Open implementation questions (resolve in writing-plans)

- Where do `rendi.dev` logs come from operationally? File dump, API export, manual extraction? Determines anonymization tooling.
- Fixture media: synthesize from Big Buck Bunny / similar CC0 sources, or use existing rendi.dev test assets? Affects licensing of the eval repo.
- Headless `claude -p` exact invocation for "with-plugin" vs "vanilla" — what's the cleanest way to load/unload the plugin per call? May need a small wrapper.
- Judge model: hardcoded Opus 4.7, or configurable? Trade-off: stability of numbers across runs vs ability to upgrade judge as models improve.
