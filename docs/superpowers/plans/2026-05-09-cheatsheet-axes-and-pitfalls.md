# Cheatsheet axis declarations and pitfall coverage — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two systemic skill-content gaps surfaced by the 2026-05-08 sonnet-4.6 smoke eval — (1) recipes hard-code a single set of defaults instead of branching on user intent (e.g. quality vs size for GIF), and (2) the cheatsheet is missing pitfalls and recipes that show up routinely in the StackOverflow corpus (HLS VOD packaging, archive deinterlacing).

**Architecture:** Pure markdown edits to `skills/ffmpeg-command/`. Add an "axis declaration" structural pattern to `SKILL.md` so future recipes can't repeat the GIF mistake; rewrite the GIF reference with explicit quality-first / size-first branches plus the missing `palettegen`/`paletteuse` pipeline; create a new `references/streaming.md` axis-declared on two axes (VOD vs live, minimalist vs hardened) with HLS recipes anchored on the rendi.dev published commands plus a DASH parallel; add an archive-transcode recipe with `yadif` to `references/encoding.md`; add three new pitfalls (HLS VOD, GIF palette, interlaced sources) to `references/pitfalls.md`. Verbatim recipes from external authoritative sources (rendi.dev) are cited inline.

**Tech Stack:** Markdown only. Verification by `grep` for required tokens — no test framework, since the skill content has none and adding one is out of scope.

**Source losses being fixed (from `evals/results/2026-05-08-sonnet46-smoke/`):**
- `synthetic-so-convert-mp4-to-gif` — plugin defaulted to `stats_mode=diff` + `bayer` when user explicitly said "quality matters more than size"
- `synthetic-so-hls-packaging` — plugin missing `-hls_playlist_type vod` and `scenecut=0`
- `rendi-bulk-archive-transcode` — plugin missing `-vf yadif` for interlaced 2005-era AVI/WMV

---

## File Structure

**Create:**
- `skills/ffmpeg-command/references/streaming.md` — HLS VOD packaging (single rendition + ABR variant), keyframe alignment, `playlist_type vod`, `independent_segments`, fMP4 vs TS

**Modify:**
- `skills/ffmpeg-command/SKILL.md` — add `## Axis declaration` section after `## Workflow`; add `streaming.md` row to references table; replace GIF quick recipe with quality-first canonical; add HLS quick recipe; add archive-transcode quick recipe
- `skills/ffmpeg-command/references/asset-generation.md` — replace the single GIF section with quality-first + size-first branches plus a "How to choose" table; introduce `palettegen`/`paletteuse`
- `skills/ffmpeg-command/references/encoding.md` — add an `## Archive transcode (legacy AVI/WMV/MPEG-2)` section with `yadif` deinterlace note
- `skills/ffmpeg-command/references/pitfalls.md` — append three pitfalls: HLS VOD (`playlist_type vod` + GOP alignment), GIF requires palettegen, interlaced sources need yadif

No tests, no code, no harness changes.

---

## Task 1: Add the axis-declaration pattern to SKILL.md

This is the structural fix that prevents future "wrong default" losses. Without it, fixing GIF only patches one instance of a recurring problem.

**Files:**
- Modify: `skills/ffmpeg-command/SKILL.md` — insert new `## Axis declaration` section between `## Workflow` (ends at line 45) and `## Quick recipes` (starts at line 47)

- [ ] **Step 1: Insert the new section**

Insert this block immediately after line 45 (the end of step 7 in `## Workflow`) and before line 47 (the start of `## Quick recipes`):

```markdown

## Axis declaration

Many operations have a meaningful trade-off axis where the right default depends on user intent: GIF quality vs size, encoder preset speed vs compression, single-pass vs two-pass, CBR vs VBR, fast seek vs frame-accurate. Recipes for operations on a trade-off axis MUST:

1. **Name the axis** in the section heading or first sentence (e.g., "GIF — quality-first" vs "GIF — size-first").
2. **Show both branches inline.** Do not bury the alternative under "advanced".
3. **List the user signals that flip the default.** Words like "quality matters more than size", "for archival", "for fast turnaround", "bandwidth-constrained", "size budget under N MB", "live", "VOD" each push the choice.

Before writing a command for a trade-off-axis operation, re-read the user's request and pick the branch their wording supports. Do not lock in a single default just because the recipe shows one.

If you find yourself writing one set of defaults but the user's request mentions the opposite axis, you've taken the wrong branch — switch.

```

- [ ] **Step 2: Verify the insertion**

Run:
```bash
grep -n "## Axis declaration" skills/ffmpeg-command/SKILL.md
grep -n "## Workflow" skills/ffmpeg-command/SKILL.md
grep -n "## Quick recipes" skills/ffmpeg-command/SKILL.md
```

Expected: `## Axis declaration` line number is between `## Workflow` and `## Quick recipes`.

---

## Task 2: Rewrite the GIF section in asset-generation.md with quality-first / size-first branches

**Files:**
- Modify: `skills/ffmpeg-command/references/asset-generation.md` — replace the existing `## GIF` section (lines 52–64) with a structured quality-first / size-first pair plus a chooser table and the missing `palettegen` pipeline.

- [ ] **Step 1: Replace the entire GIF section**

Find the existing block:

```markdown
## GIF

Looping GIF, every 2nd frame, 10× sped up, scaled to 320 px wide:

```sh
ffmpeg -i input.mp4 -vf "select='gt(trunc(t/2),trunc(prev_t/2))',setpts='PTS*0.1',scale=trunc(oh*a/2)*2:320:force_original_aspect_ratio=decrease,pad=trunc(oh*a/2)*2:320:-1:-1" -loop 0 -an output.gif
```

- `select='gt(trunc(t/2),trunc(prev_t/2))'` — keeps one frame every 2 seconds of source time.
- `setpts='PTS*0.1'` — multiplies timestamps by 0.1 (10× faster playback).
- `scale=trunc(oh*a/2)*2:320:...` — scales to 320 px tall with width auto, ensuring even dimensions.
- `-loop 0` — infinite loop (default; `-loop 1` plays once).
- `-an` — no audio (GIFs don't carry audio).
```

Replace it with:

```markdown
## GIF

GIF is on a quality-vs-size axis (see SKILL.md → Axis declaration). The 256-color palette ceiling makes palette generation disproportionately impactful — single-pass GIFs without a custom palette always look banded. Pick one of the two branches based on user wording.

### How to choose

| User signal | Branch |
|---|---|
| "quality matters more than size", "looks crisp", "for marketing/portfolio", "smooth gradients" | quality-first |
| "size budget under N MB", "Slack/Discord upload", "fast turnaround", "thumbnail" | size-first |
| (no signal) | size-first (cheaper, fast enough for most users) |

### Quality-first (preserve gradients and detail)

```sh
ffmpeg -i input.mp4 -vf "fps=20,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=full[p];[s1][p]paletteuse=dither=sierra2_4a" -loop 0 -an output.gif
```

- `fps=20` — smooth motion. Drop to `15` if you need to save size with minimal visible loss.
- `scale=640:-1:flags=lanczos` — Lanczos is the sharpest downscaler.
- `palettegen=stats_mode=full` — analyzes **every frame** for the optimal global palette (vs `diff`, which is biased toward inter-frame motion).
- `paletteuse=dither=sierra2_4a` — Sierra 2-4A produces film-like noise on gradients and skin tones; avoids the visible crosshatch pattern of bayer dithering.

### Size-first (smallest acceptable file)

```sh
ffmpeg -i input.mp4 -vf "fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -loop 0 -an output.gif
```

- `fps=15`, `scale=480:-1` — cuts roughly half the bytes vs the quality-first defaults at the cost of detail.
- `palettegen=stats_mode=diff` — palette favors moving regions; static backgrounds compress better.
- `dither=bayer:bayer_scale=5` — ordered dithering compresses more efficiently than error-diffusion.
- `diff_mode=rectangle` — only re-dithers the changed bounding box per frame, shrinking the file further.

### Stylistic GIF (looping, every 2nd frame, 10× speed, 320 px)

The original cheatsheet recipe — useful when the goal is a stylized fast-cut effect rather than a faithful clip:

```sh
ffmpeg -i input.mp4 -vf "select='gt(trunc(t/2),trunc(prev_t/2))',setpts='PTS*0.1',scale=trunc(oh*a/2)*2:320:force_original_aspect_ratio=decrease,pad=trunc(oh*a/2)*2:320:-1:-1" -loop 0 -an output.gif
```

- `select='gt(trunc(t/2),trunc(prev_t/2))'` — keeps one frame every 2 seconds of source time.
- `setpts='PTS*0.1'` — multiplies timestamps by 0.1 (10× faster playback).
- `scale=trunc(oh*a/2)*2:320:...` — scales to 320 px tall with width auto, ensuring even dimensions.
- `-loop 0` — infinite loop (default; `-loop 1` plays once).
- `-an` — no audio (GIFs don't carry audio).

This branch does not use a custom palette; it relies on the stylized effect masking banding. Pair it with `palettegen`+`paletteuse` if banding is visible on the source.
```

- [ ] **Step 2: Verify the section landed correctly**

Run:
```bash
grep -c "palettegen=stats_mode=full" skills/ffmpeg-command/references/asset-generation.md
grep -c "palettegen=stats_mode=diff" skills/ffmpeg-command/references/asset-generation.md
grep -c "dither=sierra2_4a" skills/ffmpeg-command/references/asset-generation.md
grep -c "dither=bayer" skills/ffmpeg-command/references/asset-generation.md
grep -n "### Quality-first" skills/ffmpeg-command/references/asset-generation.md
grep -n "### Size-first" skills/ffmpeg-command/references/asset-generation.md
```

Expected: each grep returns at least 1 match; the `### Quality-first` and `### Size-first` headings appear in the file with `### Quality-first` before `### Size-first`.

---

## Task 3: Update the GIF quick recipe in SKILL.md

The quick-recipe block on line 137–141 currently shows only the stylistic fast-cut GIF. Replace it with the quality-first canonical so the most common case is the most visible default, and link to the new branched section.

**Files:**
- Modify: `skills/ffmpeg-command/SKILL.md` — replace the GIF quick recipe block (lines 137–143)

- [ ] **Step 1: Replace the block**

Find:

```markdown
### GIF (looping, every 2nd frame, 10× speed, 320px wide)

```sh
ffmpeg -i input.mp4 -vf "select='gt(trunc(t/2),trunc(prev_t/2))',setpts='PTS*0.1',scale=trunc(oh*a/2)*2:320:force_original_aspect_ratio=decrease,pad=trunc(oh*a/2)*2:320:-1:-1" -loop 0 -an output.gif
```

→ `references/asset-generation.md`
```

Replace with:

```markdown
### GIF (quality-first canonical — pick the branch matching user intent)

```sh
ffmpeg -i input.mp4 -vf "fps=20,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=full[p];[s1][p]paletteuse=dither=sierra2_4a" -loop 0 -an output.gif
```

This is the quality-first default. For size-first (smaller file, lower fps/resolution, `stats_mode=diff` + bayer dither) or the stylized fast-cut variant, see the GIF section in the reference — it has both branches and a chooser table.

→ `references/asset-generation.md`
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "GIF (quality-first canonical" skills/ffmpeg-command/SKILL.md
grep -c "stats_mode=full" skills/ffmpeg-command/SKILL.md
```

Expected: heading line is present, at least 1 match for `stats_mode=full`.

---

## Task 4: Create `references/streaming.md` with HLS (axis-declared) and DASH

This file is the missing reference for HLS and DASH packaging. Per the user's design call, it presents two HLS forms — **minimalist** (anchored on the rendi.dev verbatim command, relies on muxer defaults) and **hardened VOD** (adds explicit player-compat flags the eval surfaced) — with no preferred default. A DASH stub mirrors the rendi.dev verbatim command.

**Sources for verbatim recipes:**
- HLS canonical → `https://www.rendi.dev/docs/playlist-outputs#ffmpeg-command-to-generate-hls-playlist`
- DASH canonical → `https://www.rendi.dev/docs/playlist-outputs#ffmpeg-command-to-generate-dash-playlist`

The hardened-VOD additions (`-hls_playlist_type vod`, `-hls_flags independent_segments`, `-pix_fmt yuv420p`, GOP alignment) come from the FFmpeg HLS muxer source (`libavformat/hlsenc.c`), Apple's HLS authoring spec (`#EXT-X-ENDLIST`, `#EXT-X-INDEPENDENT-SEGMENTS`), and the eval responses (raw.jsonl:23, 40, 55). Each addition is annotated with what player-compat issue it fixes so the user can opt in or out per recipe.

**Files:**
- Create: `skills/ffmpeg-command/references/streaming.md`

- [ ] **Step 1: Create the file**

Write to `skills/ffmpeg-command/references/streaming.md`:

```markdown
# Streaming — HLS and DASH packaging

Streaming packaging is on **two** axes (see SKILL.md → Axis declaration):

1. **VOD vs live** — finished file vs ongoing ingest. Different muxer flags.
2. **Minimalist vs hardened** — rely on muxer defaults and a known-modern player, or pin every flag for unknown-player robustness. Both forms are correct; pick based on context.

The HLS section below shows both axes; the DASH section is a single recipe (the format is younger and the rendi.dev house form is the practical default).

## HLS — VOD vs live

| User signal | Branch |
|---|---|
| "package this video", "for the website", "complete file", "playable from a CDN" | VOD |
| "live stream", "rolling window", "broadcast", "ingest" | live |
| (no signal, but input is a finished file) | VOD |

## HLS VOD — minimalist canonical (rendi.dev house style)

```sh
ffmpeg -i input.mp4 -c:v h264 -c:a aac -b:v 2000k -b:a 128k -hls_time 5 -hls_list_size 0 -f hls playlist.m3u8
```

Verbatim from `rendi.dev/docs/playlist-outputs` (with the rendi sample input/output paths substituted; the original includes `-t 20` to trim the demo to 20 seconds — drop that for a full-length transcode).

### Why each flag

- `-c:v h264 -c:a aac` — codec aliases. Equivalent to `-c:v libx264 -c:a aac` on builds where libx264 is the registered h264 encoder.
- `-b:v 2000k` — target video bitrate (CBR-style; the muxer averages over the file). House style favors explicit bitrate over CRF for streaming output because the playlist consumer wants predictable per-segment download size.
- `-b:a 128k` — audio bitrate.
- `-hls_time 5` — target segment length in seconds. The muxer cuts only on keyframes, so actual segments may run slightly longer if your encoder doesn't emit keyframes every 5 s.
- `-hls_list_size 0` — keep every segment in the playlist (default 5 is a sliding window for live).
- `-f hls` — explicit muxer selection. Without it, FFmpeg infers from the `.m3u8` extension; explicit is safer.

This form relies on the muxer's defaults for keyframe alignment, segment naming, and player-mode hints. It works on modern players (HLS.js, Safari, Android ≥ 7) where `#EXT-X-ENDLIST` isn't strictly required to seek a finished playlist. If your consumer is unknown or older, use the hardened form below.

## HLS VOD — hardened (explicit player-compat)

```sh
ffmpeg -i input.mp4 \
  -c:v libx264 -b:v 2000k -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -hls_time 6 \
  -hls_playlist_type vod \
  -hls_list_size 0 \
  -hls_flags independent_segments \
  -hls_segment_filename "seg_%03d.ts" \
  -f hls playlist.m3u8
```

### What each addition fixes (vs minimalist)

- `-pix_fmt yuv420p` — without it libx264 may emit yuv444p, which QuickTime / iOS / many smart TVs reject. (See pitfalls.md #1.)
- `-g 60 -keyint_min 60 -sc_threshold 0` — forces one keyframe every 60 frames so segments end exactly on `-hls_time` boundaries. Without this, segments end at whatever keyframe the encoder happens to emit, producing uneven segments and "missing keyframe" errors when ABR players switch mid-stream. Choose `<fps × hls_time>` (30 fps × 2 s = 60; 24 fps × 6 s = 144; 30 fps × 6 s = 180). Equivalent `-x264-params` form: `keyint=N:min-keyint=N:scenecut=0`.
- `-hls_playlist_type vod` — writes `#EXT-X-PLAYLIST-TYPE:VOD` and `#EXT-X-ENDLIST`. Older / unknown players treat a playlist without `#EXT-X-ENDLIST` as live and refuse to seek beyond the current segment or display total duration. (See pitfalls.md #21.)
- `-hls_flags independent_segments` — writes `#EXT-X-INDEPENDENT-SEGMENTS`, declaring each segment decodable without prior context. Required for clean ABR rendition switches.
- `-hls_segment_filename "seg_%03d.ts"` — explicit naming pattern. Without it the muxer uses the playlist filename as the prefix, which can collide if you re-run.

The codec switch from `-c:v h264` to `-c:v libx264` here is just to make the encoder choice explicit (the alias is sometimes resolved differently across builds when extra encoder-specific flags like `-x264-params` are in play).

## HLS — multi-bitrate ABR (3 renditions)

Three video qualities + three audio qualities behind one master playlist:

```sh
ffmpeg -i input.mp4 \
  -filter_complex \
    "[0:v]split=3[v1][v2][v3]; \
     [v1]scale=-2:1080,setsar=1:1,format=yuv420p[v1out]; \
     [v2]scale=-2:720,setsar=1:1,format=yuv420p[v2out]; \
     [v3]scale=-2:480,setsar=1:1,format=yuv420p[v3out]" \
  -map "[v1out]" -map "[v2out]" -map "[v3out]" \
  -map 0:a -map 0:a -map 0:a \
  -c:v libx264 -preset slow \
  -force_key_frames "expr:gte(t,n_forced*6)" \
  -b:v:0 4000k -b:v:1 2000k -b:v:2 1000k \
  -c:a aac -ar 48000 -ac 2 \
  -b:a:0 192k -b:a:1 128k -b:a:2 96k \
  -f hls \
  -hls_time 6 \
  -hls_playlist_type vod \
  -hls_flags independent_segments \
  -hls_segment_filename "stream_%v/seg_%03d.ts" \
  -var_stream_map "v:0,a:0 v:1,a:1 v:2,a:2" \
  -master_pl_name "master.m3u8" \
  "stream_%v/playlist.m3u8"
```

Output structure:

```
master.m3u8        ← player loads this
stream_0/playlist.m3u8 + seg_*.ts   (1080p, 4 Mbps)
stream_1/playlist.m3u8 + seg_*.ts   (720p,  2 Mbps)
stream_2/playlist.m3u8 + seg_*.ts   (480p,  1 Mbps)
```

### Why each flag (additions vs single-rendition)

- `split=3` — decode the input once and fan out three scale chains. Three `-i input.mp4` would decode three times.
- `scale=-2:H` — `-2` auto-computes width preserving aspect ratio AND rounds to an even number (libx264 with yuv420p requires even dimensions). `-1` may produce odd widths.
- `-force_key_frames "expr:gte(t,n_forced*6)"` — forces a keyframe at every 6-second boundary regardless of fps. Use this OR the `-g`/`-keyint_min`/`-sc_threshold` combo from the single-rendition hardened recipe; not both.
- `-b:v:N` (per-stream bitrate) — house-style CBR-ish target for ABR. ABR players estimate bandwidth from segment download time and need predictable per-segment size. Pair with `-maxrate:v:N` and `-bufsize:v:N` (≈ 2× maxrate) if you need stricter VBV constraints.
- `-var_stream_map` — pairs each video output with an audio output. `v:0,a:0 v:1,a:1 v:2,a:2` ⇒ three variants, each with its own audio.
- `-master_pl_name "master.m3u8"` — auto-generates the top-level master playlist with `BANDWIDTH` and `RESOLUTION` for each variant.
- `%v` in filenames — expands to the variant index (0, 1, 2).

## HLS — fMP4 (CMAF) segments instead of MPEG-TS

Modern players (HLS.js, Safari ≥ 10, Android ≥ 7) support fragmented MP4 segments. They share segment format with DASH (CMAF), so a single set of segments can serve both manifests. Add to either single-rendition or ABR recipe:

```sh
  -hls_segment_type fmp4 \
  -hls_fmp4_init_filename "init.mp4" \
```

Per variant in the ABR case:

```sh
  -hls_segment_type fmp4 \
  -hls_fmp4_init_filename "stream_%v/init.mp4" \
```

## HLS — live (sliding window)

For live ingest output (rolling window of 6 most-recent 5-second segments):

```sh
ffmpeg -re -i input \
  -c:v libx264 -preset veryfast -tune zerolatency -b:v 2500k -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -g 50 -keyint_min 50 -sc_threshold 0 \
  -hls_time 5 \
  -hls_list_size 6 \
  -hls_flags delete_segments+append_list+independent_segments \
  -hls_segment_filename "seg_%03d.ts" \
  live.m3u8
```

Differences from VOD:

- `-re` — read input at native frame rate (only for file inputs simulating live; omit for true live ingest).
- `-tune zerolatency`, `-preset veryfast` — minimize latency at the cost of compression.
- `-hls_list_size 6` — keep the last 6 segments in the playlist.
- `-hls_flags delete_segments+append_list` — auto-delete segments that fall off the window; append to the playlist rather than rewriting it on each update.
- No `-hls_playlist_type` — leaving it unset is what marks the playlist as live.

## DASH (MPEG-DASH manifest)

Verbatim from `rendi.dev/docs/playlist-outputs` (input/output substituted; original includes `-t 20` for the demo trim):

```sh
ffmpeg -i input.mp4 -map 0:v -map 0:a -c:v libx264 -b:v 2000k -c:a aac -b:a 128k -use_timeline 1 -use_template 1 -seg_duration 5 -init_seg_name init-$RepresentationID$.mp4 -media_seg_name chunk-stream$RepresentationID$-$Number%05d$.m4s -adaptation_sets "id=0,streams=v id=1,streams=a" -f dash manifest.mpd
```

### Why each flag

- `-map 0:v -map 0:a` — explicit selection of one video and one audio stream from the input.
- `-c:v libx264 -b:v 2000k` — video codec + bitrate. House style favors explicit bitrate.
- `-use_timeline 1 -use_template 1` — emit a SegmentTemplate with a SegmentTimeline. Compact manifest; preferred by modern DASH players.
- `-seg_duration 5` — target segment length (DASH analog of `-hls_time`).
- `-init_seg_name init-$RepresentationID$.mp4` — fMP4 init segment naming pattern. `$RepresentationID$` substitutes the representation index.
- `-media_seg_name chunk-stream$RepresentationID$-$Number%05d$.m4s` — media segment pattern. `$Number%05d$` is the segment counter zero-padded to 5 digits.
- `-adaptation_sets "id=0,streams=v id=1,streams=a"` — declares two adaptation sets, one for video and one for audio. Required so the manifest groups streams correctly for adaptive switching.
- `-f dash` — explicit muxer.

For multi-bitrate DASH, extend with additional `-map`/`-c:v:N`/`-b:v:N` pairs and add a representation per quality, similar to the HLS ABR shape above.

## `-movflags +faststart` does NOT apply to HLS or DASH

`+faststart` rewrites the `moov` atom of a single MP4 file so progressive-download players can start before the file finishes loading. HLS `.ts` segments are MPEG-TS (no moov atom). HLS fMP4 segments and all DASH segments are already fragmented — the init segment carries the moov, each media segment carries `moof+mdat`. The flag is a no-op in streaming pipelines; don't add it.
```

- [ ] **Step 2: Verify file content**

Run:
```bash
ls skills/ffmpeg-command/references/streaming.md
grep -c "hls_playlist_type vod" skills/ffmpeg-command/references/streaming.md
grep -c "sc_threshold 0" skills/ffmpeg-command/references/streaming.md
grep -c "independent_segments" skills/ffmpeg-command/references/streaming.md
grep -c "force_key_frames" skills/ffmpeg-command/references/streaming.md
grep -c "use_timeline" skills/ffmpeg-command/references/streaming.md
grep -c "adaptation_sets" skills/ffmpeg-command/references/streaming.md
grep -c "minimalist canonical" skills/ffmpeg-command/references/streaming.md
grep -c "hardened" skills/ffmpeg-command/references/streaming.md
```

Expected: file exists; `hls_playlist_type vod`, `sc_threshold 0`, `independent_segments`, `force_key_frames`, `use_timeline`, `adaptation_sets` each match at least once; `minimalist canonical` and `hardened` each appear (proving both axis branches are present).

---

## Task 5: Wire `streaming.md` into SKILL.md

**Files:**
- Modify: `skills/ffmpeg-command/SKILL.md` — add a row to the references table; add an HLS quick recipe block.

- [ ] **Step 1: Add the streaming row to the references table**

Find this line (currently around line 26):

```markdown
| GPU encoding (NVENC, QSV, VAAPI) | `references/gpu-acceleration.md` |
```

Insert this row immediately after it (so streaming sits next to GPU encoding, both being delivery-pipeline concerns):

```markdown
| HLS packaging, VOD/live segments, ABR multi-bitrate | `references/streaming.md` |
```

- [ ] **Step 2: Add an HLS quick recipe**

Insert this new section between the existing `### GPU transcode (NVIDIA)` block (which ends around line 151) and the `## Top gotchas` heading (around line 153):

```markdown
### HLS VOD (single rendition — rendi.dev house style)

```sh
ffmpeg -i input.mp4 -c:v h264 -c:a aac -b:v 2000k -b:a 128k -hls_time 5 -hls_list_size 0 -f hls playlist.m3u8
```

This is the minimalist form. For hardened-VOD playback (older players, ABR-ready, explicit GOP alignment) or multi-bitrate ABR, see the reference. The reference also has a parallel DASH recipe.

→ `references/streaming.md`

```

- [ ] **Step 3: Verify the wiring**

Run:
```bash
grep -n "references/streaming.md" skills/ffmpeg-command/SKILL.md
grep -n "### HLS VOD" skills/ffmpeg-command/SKILL.md
```

Expected: at least 2 matches for `references/streaming.md` (one in the table, one in the link), and 1 for `### HLS VOD`.

---

## Task 6: Add an archive-transcode recipe with `yadif` to encoding.md

**Files:**
- Modify: `skills/ffmpeg-command/references/encoding.md` — append a new `## Archive transcode (legacy AVI/WMV/MPEG-2)` section before the `## Container vs codec` section (currently around line 174).

- [ ] **Step 1: Insert the new section**

Find the line `## Container vs codec` (around line 174). Insert this block immediately before it:

```markdown

## Archive transcode (legacy AVI/WMV/MPEG-2)

Old captures (VHS digitizations, 2000s-era broadcast rips, capture-card AVI/WMV files) are usually interlaced even when ffprobe doesn't say so. Without a deinterlace, the H.264 output retains combing artifacts on motion that look exactly like a broken encoder.

### Recommended archive recipe

```sh
ffmpeg -i input.avi -vf "yadif=mode=1:parity=auto,format=yuv420p" -c:v libx264 -crf 20 -preset slow -c:a aac -b:a 128k -movflags +faststart output.mp4
```

- `yadif=mode=1:parity=auto` — deinterlace, output one frame per *field* (60i → 60p, preserves motion smoothness). Use `mode=0` for one frame per *pair of fields* (60i → 30p, half the output frame rate, smaller file). `parity=auto` lets FFmpeg detect field order; specify `tff` (top-field-first, MPEG-2/DV) or `bff` (bottom-field-first, DV PAL/HDV) if auto-detect is wrong.
- `format=yuv420p` — required for libx264 broad-compatibility output (see pitfalls.md #1).
- `-crf 20 -preset slow` — archival quality; if storage is tight, raise to `-crf 23`. Don't go above `-crf 26` for archive material.
- `-movflags +faststart` — moves the moov atom to the front for progressive playback / S3 streaming.

### When to skip yadif

If you've confirmed the source is progressive (e.g., a digital screen recording, modern phone capture), `yadif` slightly softens the output and adds compute. Drop it.

Confirm interlacing with:

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=field_order -of default=noprint_wrappers=1 input.avi
```

Output `field_order=tt` or `bb` ⇒ interlaced. `progressive` ⇒ no yadif needed. Many old captures report `unknown` — when in doubt with archive content, deinterlace anyway; the cost is small.

### Conditional deinterlace (only flagged frames)

For mixed sources where some content is correctly flagged and some isn't:

```sh
ffmpeg -i input.avi -vf "yadif=mode=1:deint=interlaced,format=yuv420p" -c:v libx264 -crf 20 -preset slow -c:a aac -b:a 128k -movflags +faststart output.mp4
```

`deint=interlaced` deinterlaces only frames the demuxer marks as interlaced. Safe for mixed content but skips unflagged-but-actually-interlaced frames; less aggressive than always-on.

### Batch archive transcode (PowerShell)

```powershell
Get-ChildItem -Recurse -Include *.avi,*.wmv,*.mpg | ForEach-Object {
    $out = $_.FullName -replace '\.(avi|wmv|mpg)$', '.mp4'
    ffmpeg -i $_.FullName -vf "yadif=mode=1:parity=auto,format=yuv420p" -c:v libx264 -crf 20 -preset slow -c:a aac -b:a 128k -movflags +faststart $out
}
```

```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "## Archive transcode" skills/ffmpeg-command/references/encoding.md
grep -c "yadif" skills/ffmpeg-command/references/encoding.md
grep -n "## Container vs codec" skills/ffmpeg-command/references/encoding.md
```

Expected: `## Archive transcode` appears before `## Container vs codec`; `yadif` matches at least 3 times.

---

## Task 7: Add the archive-transcode quick recipe to SKILL.md

**Files:**
- Modify: `skills/ffmpeg-command/SKILL.md` — add an `### Archive transcode` block under `## Quick recipes`, near the existing `### Remux / transcode` section.

- [ ] **Step 1: Insert the new quick recipe**

Find this block in `SKILL.md` (currently lines 51–65):

```markdown
### Remux / transcode

Remux MP4 to MKV (no re-encode):

```sh
ffmpeg -i input.mp4 -c copy output.mkv
```

Generic web-optimized re-encode (good default for archiving, streaming, edge devices):

```sh
ffmpeg -i input.mp4 -vf "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1" -crf 18 -preset veryslow  -threads 0 -tune fastdecode  -movflags +faststart  output_scaled_optimized.mp4
```

→ `references/encoding.md`
```

Insert this block immediately after `→ `references/encoding.md`` and before the next `### Trim by time` section:

```markdown

### Archive transcode (legacy AVI/WMV/MPEG-2 — likely interlaced)

```sh
ffmpeg -i input.avi -vf "yadif=mode=1:parity=auto,format=yuv420p" -c:v libx264 -crf 20 -preset slow -c:a aac -b:a 128k -movflags +faststart output.mp4
```

→ `references/encoding.md` (Archive transcode section)

```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "Archive transcode" skills/ffmpeg-command/SKILL.md
grep -c "yadif" skills/ffmpeg-command/SKILL.md
```

Expected: `Archive transcode` appears once; `yadif` matches at least once.

---

## Task 8: Add three new pitfalls to pitfalls.md

**Files:**
- Modify: `skills/ffmpeg-command/references/pitfalls.md` — append three new items (#21, #22, #23) after the existing #20 (line 197–202).

- [ ] **Step 1: Append the three pitfalls**

After the last existing pitfall (#20 ends around line 202), append:

```markdown

## 21. HLS VOD requires `-hls_playlist_type vod` and aligned keyframes

**Rule:** When packaging a finished file as HLS VOD, set `-hls_playlist_type vod` AND force keyframes to the segment boundary with `-g <fps × hls_time> -keyint_min <same> -sc_threshold 0`.

**Why (`playlist_type vod`):** Without it, the playlist omits `#EXT-X-ENDLIST`, players treat it as live, refuse to seek beyond the current segment, and don't display total duration. This is the single most common HLS-packaging mistake.

**Why (keyframe alignment):** `-hls_time N` is a *target*. The muxer can only cut at keyframes. Without forcing GOPs to align, segments end up uneven (e.g., 3 s + 9 s + 4 s instead of 6 + 6 + 4) and ABR players that switch renditions land mid-GOP, producing visible glitches.

**How to apply:**

```sh
ffmpeg -i input.mp4 \
  -c:v libx264 -pix_fmt yuv420p \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -hls_time 6 -hls_playlist_type vod -hls_list_size 0 \
  -hls_flags independent_segments \
  -hls_segment_filename "seg_%03d.ts" \
  output.m3u8
```

For variable frame rates or non-libx264 encoders, use `-force_key_frames "expr:gte(t,n_forced*6)"` instead of the `-g`/`-keyint_min`/`-sc_threshold` combo. See `streaming.md`.

## 22. GIF without `palettegen` looks banded

**Rule:** Always use the `palettegen` → `paletteuse` two-pass pipeline when converting video to GIF (single-command via `split` is preferred; no intermediate file needed).

**Why:** GIF is limited to 256 colors. The default global palette is generic — assigned to arbitrary footage it produces severe banding on gradients, color shift on skin tones, and dithering crosshatch. A custom palette generated from the actual footage uses the available 256 slots for colors that matter to *this* clip.

**How to apply:**

```sh
ffmpeg -i input.mp4 -vf "fps=20,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=full[p];[s1][p]paletteuse=dither=sierra2_4a" -loop 0 -an output.gif
```

For size-first vs quality-first parameter choices, see `asset-generation.md` → GIF.

## 23. Old archive footage is often interlaced — apply `yadif`

**Rule:** When transcoding pre-2010 AVI/WMV/MPEG-2 (VHS digitizations, capture-card files, broadcast rips), apply `yadif` deinterlacing unless you've verified the source is progressive.

**Why:** Interlaced content stored as progressive metadata is common. Re-encoding without deinterlacing produces visible combing on motion that looks like a broken encoder. The H.264 spec allows interlaced encoding (`-flags +ilme+ildct`) but most playback paths assume progressive — combing artifacts persist.

**How to apply:**

```sh
ffmpeg -i input.avi -vf "yadif=mode=1:parity=auto,format=yuv420p" -c:v libx264 -crf 20 -preset slow -c:a aac -b:a 128k output.mp4
```

- `mode=1` — output one frame per field (60i → 60p, preserves motion).
- `mode=0` — output one frame per *pair* of fields (60i → 30p, half output rate, smaller file).
- `parity=auto` — auto-detect field order; specify `tff` (MPEG-2/DV NTSC) or `bff` (DV PAL) if detection is wrong.
- `deint=interlaced` (optional) — only deinterlace frames marked as interlaced; safer for mixed content but skips unflagged-but-interlaced frames.

Check field order before deciding:

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=field_order -of default=noprint_wrappers=1 input.avi
```

`tt`/`bb` ⇒ interlaced; `progressive` ⇒ skip yadif; `unknown` ⇒ apply yadif anyway when in doubt.
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "^## 21" skills/ffmpeg-command/references/pitfalls.md
grep -n "^## 22" skills/ffmpeg-command/references/pitfalls.md
grep -n "^## 23" skills/ffmpeg-command/references/pitfalls.md
grep -c "hls_playlist_type vod" skills/ffmpeg-command/references/pitfalls.md
grep -c "palettegen" skills/ffmpeg-command/references/pitfalls.md
grep -c "yadif" skills/ffmpeg-command/references/pitfalls.md
```

Expected: pitfalls #21, #22, #23 all present, in order; each new keyword matches at least once.

---

## Task 9: Cross-cutting verification

A single check that all the failing-prompt fixes are now expressible from the cheatsheet content alone.

**Files:** none (read-only)

- [ ] **Step 1: Confirm GIF quality-first content is reachable**

Run:
```bash
grep -l "stats_mode=full" skills/ffmpeg-command/
grep -l "stats_mode=full" skills/ffmpeg-command/references/asset-generation.md
grep -l "dither=sierra2_4a" skills/ffmpeg-command/references/asset-generation.md
```

Expected: matches in `SKILL.md` AND `asset-generation.md`. Rationale: this is the regression-fix for `synthetic-so-convert-mp4-to-gif`.

- [ ] **Step 2: Confirm HLS VOD content is reachable (both axis branches)**

Run:
```bash
# Minimalist canonical (rendi.dev house style) — should be in SKILL.md and streaming.md
grep -l "b:v 2000k" skills/ffmpeg-command/SKILL.md skills/ffmpeg-command/references/streaming.md
# Hardened form additions — should be in streaming.md and pitfalls.md (NOT SKILL.md, by design)
grep -l "hls_playlist_type vod" skills/ffmpeg-command/references/streaming.md skills/ffmpeg-command/references/pitfalls.md
grep -l "sc_threshold 0" skills/ffmpeg-command/references/streaming.md skills/ffmpeg-command/references/pitfalls.md
grep -l "independent_segments" skills/ffmpeg-command/references/streaming.md
# DASH parallel — should be in streaming.md
grep -l "use_timeline" skills/ffmpeg-command/references/streaming.md
grep -l "adaptation_sets" skills/ffmpeg-command/references/streaming.md
```

Expected: each grep returns the listed files. SKILL.md should NOT contain `hls_playlist_type vod` (the hardened form lives only in the reference). Rationale: regression-fix for `synthetic-so-hls-packaging` is reachable via the hardened branch in `streaming.md`; the minimalist branch is the SKILL.md quick recipe; DASH parallels the rendi.dev house-style HLS.

- [ ] **Step 3: Confirm archive-transcode content is reachable**

Run:
```bash
grep -l "yadif" skills/ffmpeg-command/SKILL.md skills/ffmpeg-command/references/encoding.md skills/ffmpeg-command/references/pitfalls.md
```

Expected: all three files match. Rationale: regression-fix for `rendi-bulk-archive-transcode`.

- [ ] **Step 4: Confirm axis-declaration pattern is in SKILL.md and applied in asset-generation.md**

Run:
```bash
grep -n "## Axis declaration" skills/ffmpeg-command/SKILL.md
grep -n "Axis declaration" skills/ffmpeg-command/references/asset-generation.md
```

Expected: heading in `SKILL.md`; back-reference in `asset-generation.md` (the GIF section's first paragraph).

---

## Task 10: Commit the changes

Use the `commits` skill for the commit messages. Group commits by logical concern so each one stands on its own.

**Files:** all the staged changes from Tasks 1–8.

- [ ] **Step 1: Stage and commit the axis-declaration + GIF rewrite**

```bash
git add skills/ffmpeg-command/SKILL.md skills/ffmpeg-command/references/asset-generation.md
git commit
```

Use commit message:
```
feat(ffmpeg-command): add axis-declaration pattern and GIF quality/size split

GIF defaults were baked-in (size-optimized) so the model couldn't
deviate when the user explicitly asked for quality. Add a SKILL.md
"Axis declaration" pattern that requires recipes on a trade-off axis
to name the axis, show both branches inline, and list signals that
flip the default. Apply it to the GIF section: split into quality-first
(stats_mode=full + sierra2_4a) and size-first (stats_mode=diff + bayer)
with a chooser table, and surface palettegen+paletteuse which were
missing from the cheatsheet.

Regression fix for: synthetic-so-convert-mp4-to-gif (eval 2026-05-08).
```

- [ ] **Step 2: Commit the streaming reference and SKILL.md wiring**

After Task 4 and Task 5 are both complete:

```bash
git add skills/ffmpeg-command/references/streaming.md skills/ffmpeg-command/SKILL.md
git commit
```

Note: SKILL.md will already be staged from the previous commit if Tasks 1–5 ran in order. Re-staging it here picks up the streaming-row addition.

Use commit message:
```
feat(ffmpeg-command): add HLS and DASH streaming reference

New references/streaming.md is axis-declared on two axes: VOD vs live,
and minimalist (rendi.dev house style, relies on muxer defaults) vs
hardened (explicit -hls_playlist_type vod, GOP alignment via -g and
-sc_threshold 0, -hls_flags independent_segments, -pix_fmt yuv420p).
Both forms are correct; users pick by player target. Also covers
multi-bitrate ABR, fMP4/CMAF segments, live sliding-window, and a
parallel DASH recipe (-use_timeline, -use_template, -seg_duration,
-adaptation_sets) anchored on the rendi.dev published example.

SKILL.md gets the minimalist HLS form as the quick recipe and a row
in the references table.

Regression fix for: synthetic-so-hls-packaging (eval 2026-05-08).
Sources: rendi.dev/docs/playlist-outputs (HLS + DASH verbatim);
FFmpeg libavformat/hlsenc.c options for hardened-form additions.
```

- [ ] **Step 3: Commit the archive-transcode recipe**

```bash
git add skills/ffmpeg-command/references/encoding.md skills/ffmpeg-command/SKILL.md
git commit
```

Use commit message:
```
feat(ffmpeg-command): add archive transcode recipe with yadif deinterlace

Pre-2010 AVI/WMV/MPEG-2 archives (VHS digitizations, capture-card files)
are usually interlaced even when ffprobe doesn't say so. Add a dedicated
"Archive transcode (legacy AVI/WMV/MPEG-2)" section to encoding.md with
yadif options (mode=0 vs mode=1, parity, deint=interlaced for mixed
content), an ffprobe field-order check, and a PowerShell batch loop.
Add a quick recipe to SKILL.md.

Regression fix for: rendi-bulk-archive-transcode (eval 2026-05-08).
```

- [ ] **Step 4: Commit the new pitfalls**

```bash
git add skills/ffmpeg-command/references/pitfalls.md
git commit
```

Use commit message:
```
docs(ffmpeg-command): document HLS VOD, GIF palette, and interlacing pitfalls

Add three pitfalls covering the regressions surfaced by the 2026-05-08
eval: #21 HLS VOD requires hls_playlist_type vod and aligned keyframes,
#22 GIF without palettegen looks banded, #23 old archive footage is
often interlaced and needs yadif. Each pitfall follows the existing
rule/why/how-to-apply structure.
```

- [ ] **Step 5: Verify the four commits landed**

Run:
```bash
git log --oneline -5
```

Expected: 4 new commits at the top, matching the order above, each with the conventional-commits format.

---

## Self-review checklist

**1. Spec coverage** — every requirement from the user's request is covered:
- "Cheatsheet defaults are baked-in single answers, not matches user intent branches" → Task 1 (axis-declaration pattern in SKILL.md)
- "GIF defaults to size/speed; user wanted quality" → Tasks 2, 3 (GIF reference rewrite + quick recipe update)
- "each recipe should specify the axis it's optimizing and offer an alternate" → Task 1 establishes the rule, Task 2 demonstrates it
- "Cheatsheet pitfall coverage gaps. Specific recipes (HLS VOD, archive transcode) are missing flags" → Tasks 4, 5, 6, 7 (HLS reference + archive recipe)
- "playlist_type vod, scenecut=0, yadif" — all three explicitly added: Task 4 (`-hls_playlist_type vod`, `-sc_threshold 0`/`scenecut=0`), Task 6 (`yadif`)
- "GIF quality defaults: quality-first → stats_mode=full + sierra2_4a; size-first → diff + bayer" → Task 2 verbatim
- "HLS packaging missing -hls_playlist_type vod and scenecut=0" → Task 4 + Task 8 pitfall #21

**2. Placeholder scan** — every code block contains real, runnable content; no "TBD", no "implement appropriate", no "see above". Verified.

**3. Type/identifier consistency** — flag names (`-hls_playlist_type`, `-sc_threshold`, `palettegen`, `paletteuse`, `yadif`, `stats_mode=full`, `stats_mode=diff`, `dither=sierra2_4a`, `dither=bayer`) match across SKILL.md, the reference files, and the pitfalls. The GIF "split" syntax in Task 2 matches the SKILL.md quick recipe in Task 3 byte-for-byte.

**4. Ordering** — Tasks 1, 2, 3 are SKILL.md + asset-generation.md (one logical commit). Tasks 4, 5 are streaming.md + SKILL.md wiring (one commit). Tasks 6, 7 are encoding.md + SKILL.md (one commit). Task 8 is pitfalls.md alone (one commit). Each commit is independently sensible.

**5. No regressions to passing prompts** — the existing GIF stylistic recipe (`select`/`setpts`/`scale=trunc`) is preserved in Task 2 as the third "Stylistic GIF" branch. The existing quick recipes for non-GIF, non-HLS, non-archive content are untouched. No deletions of correct content.
