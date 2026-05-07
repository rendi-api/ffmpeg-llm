# Pitfalls — the 🛠️ list

Concentrated tribal knowledge: things FFmpeg does that surprise LLMs and humans alike, and the patterns that work around them. Each item is a rule, the *why*, and the fix.

## 1. Pixel format compatibility — `format=yuv420p` / `-pix_fmt yuv420p`

**Rule:** When re-encoding H264/H265 for general playback, force pixel format to `yuv420p`.

**Why:** QuickTime and most players only support 4:2:0 chroma subsampling for H.264. Without this flag, FFmpeg may pick a pixel format the target player can't decode, producing files that won't play or render with wrong colors.

**How to apply:** Either as a filter (`-vf format=yuv420p`) or output flag (`-pix_fmt yuv420p`). When already using `-vf`, append `,format=yuv420p` to the chain.

```sh
ffmpeg -i input.mp4 -vf "scale=1280:720,format=yuv420p" -c:v libx264 output.mp4
```

## 2. Web playback — `-movflags +faststart`

**Rule:** Add `-movflags +faststart` to MP4/MOV/M4A outputs intended for web playback.

**Why:** Moves the `moov` atom (metadata) to the front of the file. Without it, the player must download the whole file before it can start playing. Works with both libx264 and libx265.

**How to apply:** Output flag, after `-i`. Even pure remuxes can add it:

```sh
ffmpeg  -i input.mp4 -c copy -movflags +faststart input_faststart.mp4
```

Verify with:

```sh
ffprobe -v trace -i your_video.mp4
```

Look for `type:'moov'` near the start of the trace output.

## 3. Apple H265 — `-vtag hvc1`

**Rule:** When encoding H265 for Apple devices (AirDrop, QuickTime, iOS Photos), add `-vtag hvc1`.

**Why:** Apple's HEVC decoders accept the `hvc1` tag but reject the default `hev1` parameter sets that FFmpeg writes.

```sh
ffmpeg -i input.mp4 -c:v libx265 -vtag hvc1 -c:a copy output_265.mp4
```

## 4. Square pixels after scale+pad — `setsar=1:1`

**Rule:** After scaling and padding, append `,setsar=1:1` to the filter chain.

**Why:** FFmpeg may set a non-square Sample Aspect Ratio to compensate for ratio change, which distorts playback on some players. Stating SAR 1:1 explicitly forces square pixels.

**How to apply:** Always end a `scale+pad` chain with `setsar=1:1`. `setsar=1` and `setsar=1/1` are equivalent.

```sh
ffmpeg -i input.mp4 -vf "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1" output_resized_pad.mp4
```

## 5. `-c copy` is incompatible with filters and frame-accurate trimming

**Rule:** Don't combine `-c copy` with `-vf`/`-af`/`-filter_complex`, and don't use it for tight trims.

**Why (filters):** Filters operate on decoded frames. Stream copy skips decoding entirely — there's nothing for the filter to read.

**Why (trims):** Stream copy can only cut at keyframes. With H.264 at 25fps, keyframes are typically every 10 seconds. Cutting at a non-keyframe with `-c copy` produces:
- Black frames at the start of the output (frames that depend on a missing keyframe), or
- A trim point silently shifted to the nearest preceding keyframe.

**When to use `-c copy`:** Container change (remux), muxing/extracting tracks, joining keyframe-aligned segments, moving metadata (faststart). See `seeking-and-trimming.md` for the full story.

## 6. Flag position — input flags before `-i`, output flags after

**Rule:** `-ss`, `-loop`, `-t`, `-r`, `-skip_frame`, `-pattern_type` go *before* the `-i` they apply to. `-c:v`, `-c:a`, `-vf`, `-crf`, `-movflags`, `-map`, `-shortest`, `-frames:v`, the output filename go *after*.

**Why:** Flags are positional — placement determines whether they apply to the input or the output. `-ss 00:00:10 -i in.mp4` is fast keyframe seek of the input. `-i in.mp4 -ss 00:00:10` is slow but frame-accurate seek of the output.

## 7. Reset timestamps before concatenating trimmed streams

**Rule:** After `trim` (video) or `atrim` (audio) inside a filter graph, add `setpts=PTS-STARTPTS` (video) or `asetpts=PTS-STARTPTS` (audio) before `concat`.

**Why:** `trim` keeps the original timestamps. If those are non-zero (which they always are after a trim that doesn't start at 0), `concat` produces wrong durations or gaps. Resetting PTS to start at 0 makes each segment behave as if it were a fresh input.

```sh
[0:v]trim=start=11:end=15,setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5,fade=t=out:st=3.5:d=0.5[v1];[0:a]atrim=start=11:end=15,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.5,afade=t=out:st=3.5:d=0.5[a1]
```

## 8. `force_original_aspect_ratio` direction matters

**Rule:** Pick `decrease` to shrink-to-fit (then pad fills), or `increase` to grow-to-cover (then crop). They are not interchangeable.

**Why:** From FFmpeg's docs:
- `0` "disable" (default)
- `1` "decrease" — auto-decrease output dimensions on need (output ≤ requested, with letterbox if needed)
- `2` "increase" — auto-increase output dimensions on need (output ≥ requested, will overflow without crop)

**Tip:** `scale=w=1080:h=-1` lets FFmpeg pick the height for you while keeping aspect ratio. `-2` instead of `-1` forces dimensions divisible by 2 (required by many encoders).

## 9. Subtitle font handling — `FontName` is the *internal* name

**Rule:** When burning subtitles with a custom font, `FontName=...` in `force_style` is the font's internal/PostScript name, not the filename. Also set `fontsdir=...` to the directory holding the font file.

**Why:** Subtitle renderers look up fonts by their internal name (open the font file in any OS font viewer to see it). The filename is irrelevant to lookup.

```sh
ffmpeg -i input.mp4 -ss 00:00 -to 00:40 -vf "subtitles=sample_subtitles.srt:fontsdir=.:force_style='FontName=Poppins,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H4066B66B,Outline=1,BorderStyle=3'" -c:v libx264  -c:a copy output_subtitles.mp4
```

ASS subtitle colors are `&HBBGGRR` (blue-green-red, reverse of HTML), or `&HAABBGGRR` with alpha (`FF` = 100% transparent, `00` = no transparency).

## 10. `-vsync 0` is deprecated — use `-fps_mode`

**Rule:** Replace `-vsync 0` with `-fps_mode passthrough`. Other modes: `cfr` (constant frame rate), `vfr` (variable frame rate), `drop`.

**Why:** Newer FFmpeg builds deprecated `-vsync` in favor of `-fps_mode`. The cheatsheet still uses `-vsync 0` because it predates the change; both work today, but `-fps_mode` is the future.

## 11. `zoompan` jitters — upscale first

**Rule:** When using `zoompan` (Ken Burns effect), prepend `scale=8000:-1` (or another large upscale) before `zoompan`.

**Why:** A long-standing zoompan bug ([trac #4298](https://trac.ffmpeg.org/ticket/4298)) produces jittery zoom at native resolution. Upscaling first gives the filter more pixels to interpolate, smoothing the effect at the cost of compute time.

```sh
[0:v]scale=8000:-1,zoompan=z='zoom+0.005':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=100:s=1920x1080:fps=25,trim=duration=4,format=yuv420p,setpts=PTS-STARTPTS[v0]
```

Note: `-t=4` before the input doesn't work correctly with `zoompan` — use `trim=duration=4` after the zoompan filter instead.

## 12. Input vs output seeking — accuracy vs speed

**Rule:** For trimming, prefer **output seeking** (`-ss` after `-i`) **without** `-c:v copy`.

**Why:**
- **Input seeking** (`-ss` before `-i`): fast (jumps by keyframe) but less accurate. With H.264 at 25fps a keyframe is every ~10s. Resets the timestamps on the output, so subsequent filters see times relative to the trimmed start.
- **Output seeking** (`-ss` after `-i`): "decodes but discards input until the timestamps reach position" — frame accurate, slower (must decode the discarded part).
- **Output seeking + `-c:v copy`**: produces black frames because copy keeps frames that started after a keyframe but not the keyframe itself.
- **Input seeking + `-c:v copy`**: there's an open bug ([trac #8189](https://trac.ffmpeg.org/ticket/8189)) where it fails to trim correctly.

So: trim with output seeking and re-encode. Adjust output bitrate as needed.

## 13. Image looping over network is slow

**Rule:** When using `-loop 1` with an image input, download the image locally first.

**Why:** FFmpeg downloads the image *for every video frame* over a remote URL. Local files don't have this problem.

## 14. `duration=shortest` vs `-shortest` — they're not the same flag

**Rule:** For audio mixing in `-filter_complex`, use both `amix=...:duration=shortest` *and* the output flag `-shortest`.

**Why:** `duration=shortest` inside the `amix` filter controls only the audio output duration. `-shortest` (output flag) controls the whole output file's duration. Without both, the output video can run past the end of the audio (or vice versa).

```sh
ffmpeg -i input.mp4 -i input.mp3 -filter_complex "[1:a]volume=0.2[a1];[0:a][a1]amix=inputs=2:duration=shortest" -shortest -map 0:v -c:v copy -c:a aac output_mix_audio.mp4
```

## 15. `concat` with mismatched stream parameters fails silently

**Rule:** Before concatenating multiple inputs with the `concat` filter, normalize their video format/SAR/fps/audio format. The cheatsheet's intro+main+outro recipe normalizes with:

- `fps=30,format=yuv420p,setsar=1` on every video stream
- `aformat=sample_fmts=fltp:channel_layouts=stereo` on every audio stream

**Why:** `concat` requires matching parameters across inputs. Without normalization, FFmpeg either errors or produces garbled output. The `aformat=sample_fmts=fltp` form converts to 32-bit float planar, a commonly used internal format.

## 16. `-c copy` with non-keyframe trim sometimes works but isn't documented

**Rule:** Don't rely on `-c copy` for trimming non-keyframe boundaries even when it appears to work.

**Why:** The cheatsheet author found one case (`-shortest -c:v copy -c:a aac` with audio shorter than video) that produced a clean output despite trimming at a non-keyframe — and another case where forcing `-c:v libx264` produced a 7-second output for a 5-second audio. Behavior is inconsistent. Use re-encoding for predictable trims.

## 17. Storyboards with `-vsync 0` (now `-fps_mode passthrough`)

**Rule:** When extracting frames where multiple consecutive source frames belong to the same scene, drop duplicates with `-fps_mode passthrough` (or the legacy `-vsync 0`).

**Why:** Without it, you get duplicate frames in the output sequence — each input frame becomes one output. The pass-through mode preserves only frames the filter selected.

## 18. CRF value: lower is better, range is exponential

**Rule:** For `libx264`/`libx265`: CRF 0 = lossless (8-bit only — for 10-bit use `-qp 0`), 23 = default, 51 = worst. Sane range is 17–28. **+6 CRF ≈ half the bitrate; -6 CRF ≈ double.**

**Note:** The cheatsheet author reports `-crf 10` looks better than `-crf 18` for very high quality H264, despite 18 being the common "visually lossless" recommendation.

For `libvpx-vp9`, CRF range is 0–63, recommended 15–35, with 31 for 1080p HD. Constant Quality VP9 requires `-crf <n> -b:v 0` (omitting `-b:v 0` switches to Constrained Quality).

## 19. `select` filter vs `-frames:v` — they don't always combine

**Rule:** When extracting *one* frame at a specific time, prefer `-ss` + `-frames:v 1` over a `select` filter expression.

**Why:** `select` evaluates per-frame; combining with `-frames:v 1` may emit before the desired frame. `-ss` seeks first, then `-frames:v 1` outputs exactly one frame from that position.

```sh
ffmpeg -i input.mp4 -ss 00:00:07 -frames:v 1 -q:v 2 output_thumbnail.jpg
```

For *multiple* thumbnails from one input, use `-filter_complex` with `split` and named outputs.

## 20. Always include `-y`

**Rule:** Add `-y` at the start of every command in scripts/automation.

**Why:** Without it, FFmpeg prompts for confirmation when the output file exists. That hangs non-interactive runs.
