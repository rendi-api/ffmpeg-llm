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
