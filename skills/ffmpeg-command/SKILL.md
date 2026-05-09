---
name: ffmpeg-command
description: Use when the user describes a video or audio operation in natural language and needs the corresponding FFmpeg command — transcoding, trimming, concatenating, extracting audio, changing resolution/bitrate/codec, applying filters, overlaying text or images, generating thumbnails or GIFs, burning subtitles, or muxing streams.
---

# FFmpeg Command Builder

Translate a described media operation into a correct, efficient FFmpeg command.

## Read the matching reference — every time

**Before writing any command, identify the matching reference file(s) and read them with the Read tool.** The recipes and gotchas in this file are summaries for quick recall. The references hold the parameter ranges, alternatives, edge cases, and tribal knowledge that separate a working command from a plausible-looking broken one.

This is non-negotiable — even when a recipe below seems to fit. Recipes show shape; references show *why* and *what breaks*. Skipping the read step is how broken commands get shipped.

| If the operation involves... | Read |
|---|---|
| Any non-trivial command (read every time) | `references/pitfalls.md` |
| Codec choice, CRF, preset, tune, faststart, yuv420p, hvc1, 1-/2-pass | `references/encoding.md` |
| Filter graphs, `-vf`/`-af`/`-filter_complex`, stream selectors, `split`/`concat`/`overlay`, expressions | `references/filters.md` |
| Trimming, seeking, accuracy vs speed, `-c copy` interactions | `references/seeking-and-trimming.md` |
| Audio (extract, replace, mix, fades, format, normalize, channels) | `references/audio.md` |
| Scale, pad, crop, fps, speed, overlay, fades, vstack/hstack, jump cuts | `references/video-effects.md` |
| Drawtext or subtitles (burn or mux), ASS, font handling | `references/text-and-subtitles.md` |
| Image→video, slideshow, Ken Burns/zoompan, GIFs, thumbnails, storyboards | `references/asset-generation.md` |
| GPU encoding (NVENC, QSV, VAAPI) | `references/gpu-acceleration.md` |
| HLS packaging, VOD/live segments, ABR multi-bitrate | `references/streaming.md` |

If the operation spans categories (e.g., "burn subtitles with custom styling and re-encode for web"), read every relevant reference. **Always** include `pitfalls.md` for non-trivial commands.

## Workflow

1. **Identify the operation type.** Transcode? Remux? Trim? Filter? Generate from images? Mix audio?
2. **Read the matching reference(s).** Use the table above. Always include `pitfalls.md` for non-trivial commands. Use the Read tool — do not generate the command from memory.
3. **Probe inputs only when codec, duration, or stream layout matters.** Run `ffprobe -show_streams -i <input>` first if the request depends on input properties (e.g., "match the source frame rate", "keep the original audio codec", "trim the last 5 seconds"). Skip for plain remux/transcode.
4. **Decide stream copy vs re-encode.**
   - `-c copy` (remux only): changing container, muxing tracks, joining keyframe-aligned segments, moving metadata (faststart).
   - Re-encode: applying any filter, changing codec, frame-accurate trimming, compressing.
   - Details and edge cases: `references/seeking-and-trimming.md`, `references/encoding.md`.
5. **Choose codec parameters for the target use case.** Defaults below; verify against `references/encoding.md` for CRF ranges, preset trade-offs, and rate-control modes.
   - Web/VOD/archival: `libx264 -crf 18 -preset veryslow -tune fastdecode -movflags +faststart`
   - Apple H265: add `-vtag hvc1`
   - WebM: `libvpx-vp9 -crf 31 -b:v 0 -c:a libopus`
   - Live streaming: `-preset ultrafast -tune zerolatency`
6. **Place flags in the correct position.** Input flags (`-ss`, `-loop`, `-t`, `-r`, `-skip_frame`) come before `-i`; output flags (`-c:v`, `-vf`, `-crf`, `-movflags`, output path) come after.
7. **Apply playback-compatibility defaults** unless the user has a reason not to: `format=yuv420p` (or `-pix_fmt yuv420p`), `setsar=1:1` after scale+pad, `+faststart` for web MP4. Full list in `references/pitfalls.md`.

## Axis declaration

Many operations have a meaningful trade-off axis where the right default depends on user intent: GIF quality vs size, encoder preset speed vs compression, single-pass vs two-pass, CBR vs VBR, fast seek vs frame-accurate. Recipes for operations on a trade-off axis MUST:

1. **Name the axis** in the section heading or first sentence (e.g., "GIF — quality-first" vs "GIF — size-first").
2. **Show both branches inline.** Do not bury the alternative under "advanced".
3. **List the user signals that flip the default.** Words like "quality matters more than size", "for archival", "for fast turnaround", "bandwidth-constrained", "size budget under N MB", "live", "VOD" each push the choice.

Before writing a command for a trade-off-axis operation, re-read the user's request and pick the branch their wording supports. Do not lock in a single default just because the recipe shows one.

If you find yourself writing one set of defaults but the user's request mentions the opposite axis, you've taken the wrong branch — switch.

## Quick recipes

Canonical shapes for common operations — for quick recall after you've already read the reference. **The reference is authoritative; the recipe is a stub.** Adapt input/output paths and parameter values; do **not** reorder flags. The linked reference covers variants, parameter ranges, and gotchas the recipe omits.

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

### Archive transcode (legacy AVI/WMV/MPEG-2 — likely interlaced)

```sh
ffmpeg -i input.avi -vf "yadif=mode=1:parity=auto,format=yuv420p" -c:v libx264 -crf 20 -preset slow -c:a aac -b:a 128k -movflags +faststart output.mp4
```

→ `references/encoding.md` (Archive transcode section)

### Trim by time (frame-accurate)

```sh
ffmpeg -i input.mp4 -ss 00:00:10 -to 00:00:25 output_trimmed.mp4
```

→ `references/seeking-and-trimming.md`

### Audio

Extract AAC without re-encoding:

```sh
ffmpeg -i  input.mp4 -map 0:a:0 -acodec copy output.aac
```

Replace audio in video (trim video to audio length):

```sh
ffmpeg -i input.mp4 -i input.mp3 -map 0:v -map 1:a  -shortest -c:v copy -c:a aac output_replace_audio.mp4
```

Mix new audio over original at lower volume:

```sh
ffmpeg -i input.mp4 -i input.mp3 -filter_complex "[1:a]volume=0.2[a1];[0:a][a1]amix=inputs=2:duration=shortest" -shortest -map 0:v -c:v copy -c:a aac output_mix_audio.mp4
```

→ `references/audio.md`

### Resize / pad

Scale to 1080×1920 keeping aspect ratio with black padding:

```sh
ffmpeg -i input.mp4 -vf "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1" output_resized_pad.mp4
```

→ `references/video-effects.md`

### Overlay logo (timed)

```sh
ffmpeg -i input.mp4 -i logo.png -filter_complex "overlay=x=(main_w-overlay_w)/8:y=(main_h-overlay_h)/8:enable='gte(t,1)*lte(t,7)'" -c:v libx264 -c:a  output_logo.mp4
```

→ `references/video-effects.md`

### Burn subtitles (custom font)

```sh
ffmpeg -i input.mp4 -ss 00:00 -to 00:40 -vf "subtitles=sample_subtitles.srt:fontsdir=.:force_style='FontName=Poppins,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H4066B66B,Outline=1,BorderStyle=3'" -c:v libx264  -c:a copy output_subtitles.mp4
```

→ `references/text-and-subtitles.md`

### Speed change (1.5×, no audio pitch shift)

```sh
ffmpeg -i input.mp4 -filter_complex "[0:v]setpts=PTS/1.5[v];[0:a]atempo=1.5[a]" -map "[v]" -map "[a]" output_sped_up.mp4
```

→ `references/video-effects.md`

### Thumbnail at second 7

```sh
ffmpeg -i input.mp4 -ss 00:00:07 -frames:v 1 output_thumbnail.png
```

### GIF (quality-first canonical — pick the branch matching user intent)

```sh
ffmpeg -i input.mp4 -vf "fps=20,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=full[p];[s1][p]paletteuse=dither=sierra2_4a" -loop 0 -an output.gif
```

This is the quality-first default. For size-first (smaller file, lower fps/resolution, `stats_mode=diff` + bayer dither) or the stylized fast-cut variant, see the GIF section in the reference — it has both branches and a chooser table.

→ `references/asset-generation.md`

### GPU transcode (NVIDIA)

```sh
ffmpeg -i input.avi -c:v h264_nvenc output_gpu_264.mp4
```

→ `references/gpu-acceleration.md`

### HLS VOD (single rendition — rendi.dev house style)

```sh
ffmpeg -i input.mp4 -c:v h264 -c:a aac -b:v 2000k -b:a 128k -hls_time 5 -hls_list_size 0 -f hls playlist.m3u8
```

This is the minimalist form. For hardened-VOD playback (older players, ABR-ready, explicit GOP alignment) or multi-bitrate ABR, see the reference. The reference also has a parallel DASH recipe.

→ `references/streaming.md`

## Top gotchas (summary — `pitfalls.md` is the source of truth)

The most common LLM failure modes when generating FFmpeg commands. **Read `references/pitfalls.md` for the full 20-item list with explanations.** The summary below is for quick recall; trust the reference over the summary if they ever diverge.

1. **`format=yuv420p` (or `-pix_fmt yuv420p`)** when re-encoding video for general playback — without it QuickTime and many devices refuse the file or render wrong colors.
2. **`-movflags +faststart`** for web MP4/MOV/M4A — moves the moov atom to the front so playback starts before download finishes.
3. **`-vtag hvc1` for H265 + Apple devices** — without it AirDrop/QuickTime reject the file.
4. **`setsar=1:1` after `scale + pad`** — otherwise FFmpeg may set a non-square SAR to compensate, distorting output on some players.
5. **`-c copy` is incompatible with filters and frame-accurate trimming.** Filters require re-encoding; copy can only cut at keyframes (often produces black frames at the start).
6. **Input flags before `-i`, output flags after `-i`.** `-ss`/`-loop`/`-t` before apply to the input; after, they apply to the output.
7. **After `trim`/`atrim`, reset timestamps with `setpts=PTS-STARTPTS` / `asetpts=PTS-STARTPTS` before `concat`** — otherwise concat produces wrong durations or gaps.
8. **`force_original_aspect_ratio=decrease` shrinks-to-fit** (then pad fills); `=increase` grows-to-cover (then crop). Pick deliberately.
9. **Subtitles `FontName=` is the font's *internal* name** (open the font file to see it), not the filename. Set `fontsdir` to the directory holding the font.
10. **`-vsync 0` is deprecated** — use `-fps_mode passthrough` (or `cfr`/`vfr`).
11. **`zoompan` jitters** without first upscaling: `scale=8000:-1,zoompan=...`.
12. **Don't re-encode when remuxing.** If only the container changes, use `-c copy`.

## Glossary

Common flags and selectors:

- `-vf` / `-filter:v` — video filter chain
- `-af` / `-filter:a` — audio filter chain
- `-filter_complex` — multi-input/multi-output filter graph
- `[0:v]` — video stream of first input; `[1:a]` — audio stream of second input
- `0:v:0` — first input, first video stream (0-based)
- `[name]` — named filter output, used inside `-filter_complex`
- `-map` — select streams for output
- `-y` — overwrite output without prompting (add to every command)
- `-c copy` — stream copy (remux without re-encoding)
- `-c:v` / `-c:a` — video / audio codec (`libx264`, `libx265`, `libvpx-vp9`, `aac`, `libmp3lame`, `libopus`, `pcm_s32le`)
- `-an` — disable audio in output
- `-ss` — seek (placement matters: input vs output)
- `-shortest` — finish output when shortest input ends
