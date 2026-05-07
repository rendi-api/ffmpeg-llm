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
