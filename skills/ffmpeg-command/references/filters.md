# Filters — syntax, stream labels, complex graphs

How to read and write FFmpeg filter graphs. The filter graph is the most powerful and most error-prone part of FFmpeg.

## Three filter flag forms

| Flag | Use for |
|---|---|
| `-vf` (alias `-filter:v`) | Video-only filter chain on a single video stream |
| `-af` (alias `-filter:a`) | Audio-only filter chain on a single audio stream |
| `-filter_complex` | Anything with multiple inputs, multiple outputs, or both audio and video |

If the operation has only one input and one output and only touches video, `-vf` is simpler. If the operation has multiple inputs or splits/joins streams, use `-filter_complex`.

## Stream selectors

In `-map` and inside `-filter_complex`:

| Selector | Meaning |
|---|---|
| `[0]` | All streams from input 0 (0-based) |
| `[0:v]` | Video stream(s) of input 0 |
| `[1:a]` | Audio stream(s) of input 1 |
| `0:v:0` | Input 0, first video stream (0-based) |
| `0:a:1` | Input 0, second audio stream |
| `[name]` | A named output from inside the filter graph |

`-map` selects which streams end up in the output:

```sh
-map 0:v -map 1:a              # Video from input 0, audio from input 1
-map "[v]" -map "[a]"          # Named outputs from a filter_complex
-map 0:s:0                     # First subtitle stream of input 0
```

## Filter graph anatomy

Inside `-filter_complex`:
- Filters are separated by commas within a single chain: `scale=1280:720,format=yuv420p`
- Chains are separated by semicolons: `[0:v]scale=...[v0];[1:v]scale=...[v1]`
- Square brackets are stream labels: `[0:v]` (input), `[v0]` (named intermediate)
- A filter consumes the labels immediately before it and produces the labels immediately after.

Read this as a sentence:

```
[0:v] scale=1280:720 [v0] ;  [v0][1:v] overlay=10:10 [out]
```

"Take input 0's video, scale it, call the result `v0`. Then take `v0` and input 1's video, overlay them, call the result `out`."

## `split` — fan out one stream

`split=N` produces N copies of an input stream so you can apply different filter chains to each:

```sh
ffmpeg -i input.mp4 -vf "split=3[1][2][3];[1]trim=0.0:4.5,setpts=PTS-STARTPTS,crop=min(in_w-300\,480):min(in_h-0\,720):300:0,scale=720:1080,setsar=1:1[1];[2]trim=4.5:8.5,setpts=PTS-STARTPTS,crop=min(in_w-500\,480):min(in_h-0\,720):500:0,scale=720:1080,setsar=1:1[2];[3]trim=8.5,setpts=PTS-STARTPTS,crop=min(in_w-400\,480):min(in_h-0\,720):400:0,scale=720:1080,setsar=1:1[3];[1][2][3]concat=n=3:v=1" -c:v libx264 -c:a copy output_cropped.mp4
```

Audio counterpart: `asplit=N`.

## `concat` filter — stitch streams together

`concat=n=N:v=V:a=A` joins N segments end-to-end. `v=` and `a=` say how many video and audio streams each segment contributes.

```sh
[v1][a1][v2][a2]concat=n=2:v=1:a=1[outv][outa]
```

"Take 2 segments (`n=2`), each with 1 video and 1 audio stream, produce one combined video stream `outv` and one combined audio stream `outa`."

**Required:** before concat-ing trimmed streams, reset timestamps with `setpts=PTS-STARTPTS` (and `asetpts=PTS-STARTPTS` for audio). Otherwise concat produces wrong durations.

**Required:** all inputs to concat must have matching parameters (resolution, SAR, fps, sample format, channel layout). The intro/main/outro recipe normalizes with `fps=30,format=yuv420p,setsar=1` on each video stream and `aformat=sample_fmts=fltp:channel_layouts=stereo` on each audio stream:

```sh
ffmpeg -i intro.mp4 -i main.mp4 -i outro.mp4 -i bgm.mp3 -filter_complex "[0:v]fps=30,format=yuv420p,setsar=1[intro_v];[1:v]scale=-2:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p,setsar=1[main_v];[2:v]fps=30,format=yuv420p,setsar=1[outro_v];[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo[intro_a];[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo[main_a];[2:a]aformat=sample_fmts=fltp:channel_layouts=stereo[outro_a];[intro_v][intro_a][main_v][main_a][outro_v][outro_a]concat=n=3:v=1:a=1[combined_video][combined_audio];[3:a]volume=0.1,aformat=sample_fmts=fltp,afade=t=in:ss=0:d=1.5,afade=t=out:st=20:d=2[bgm_faded];[combined_audio][bgm_faded]amix=inputs=2:duration=first:dropout_transition=2[final_audio]" -map "[combined_video]" -map "[final_audio]" -c:v libx264 -c:a aac -shortest intro_main_outro.mp4
```

`duration=first` makes the mixed audio match the *first* (combined) input's duration. `dropout_transition=2` fades out the shorter audio so it doesn't cut abruptly.

`aformat=sample_fmts=fltp` converts audio to 32-bit float planar — a commonly used internal FFmpeg format that prevents format mismatches across the graph.

## `overlay` — composite streams

`overlay=x:y` places the second input on top of the first at position `(x, y)` (top-left corner of the overlay).

Position variables inside `overlay=`:
- `main_w`, `main_h` — width/height of the main (first) video
- `overlay_w`, `overlay_h` — width/height of the overlay (second) video
- `W`, `H` — main video dimensions (uppercase)
- `w`, `h` — overlay dimensions (lowercase)

Examples:

```
x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2     # center
x=(main_w-overlay_w)/8:y=(main_h-overlay_h)/8     # top-left at 1/8 inset
x=W-w-10:y=H-h-10                                  # bottom-right with 10px margin
```

When overlaying onto a *background image* with the video on top:

```sh
ffmpeg -i input.mp4 -i bg.png -filter_complex "[1:v][0:v]overlay=(W-w)/2:(H-h)/2" -c:v libx264 -c:a copy output_bg.mp4
```

Order matters: `[1:v][0:v]overlay=...` puts input 1 (the image) on the bottom and input 0 (the video) on top. `W/H` then refer to input 1's dimensions, `w/h` to input 0's — based on filter input order, *not* file input order.

## `vstack` / `hstack` — stack videos

```sh
[top][bottom]vstack=inputs=2:shortest=1[v]
```

`shortest=1` makes the stack's duration match the shorter input. `hstack` is the horizontal counterpart.

For unequal-sized inputs, scale and pad to the same dimensions first:

```sh
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v]scale=720:-2:force_original_aspect_ratio=decrease,pad=720:640:(ow-iw)/2:(oh-ih)/2:black[top];[1:v]scale=720:-2:force_original_aspect_ratio=decrease,pad=720:640:(ow-iw)/2:(oh-ih)/2:black[bottom];[top][bottom]vstack=inputs=2:shortest=1[v]" -map "[v]" -map 1:a -c:v libx264 -c:a aac -shortest output_stacked.mp4
```

## Multi-output: split + named outputs + `-map`

Generate two scaled videos from one input in a single FFmpeg command — horizontal and vertical with a logo overlay:

```sh
ffmpeg -i input.mp4 -i logo.png -filter_complex "[0:v]split=2[s0][s1];[s0]scale=w=1920:h=1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[out1];[s1]scale=w=720:h=1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[s2];[s2][1]overlay=(main_w-overlay_w)/2:(main_w-overlay_w)/5[out2]" -map [out1] -map 0:a output_youtube.mp4 -map [out2] -map 0:a  output_shorts.mp4
```

The pattern: list multiple `-map` + output filename pairs after the filter graph. Each `-map [name]` + filename pair is a separate output file.

## Expression syntax in filters

Many filters take expressions (`alpha=...`, `enable=...`, `x=...`). Common operators and functions:

| Form | Meaning |
|---|---|
| `t` | Current time in seconds |
| `n` | Current frame number (0-based) |
| `gte(t,5)` | t ≥ 5 (1 if true, 0 if false) |
| `lte(t,10)` | t ≤ 10 |
| `gt(t,5)` | t > 5 |
| `between(t,5,10)` | 5 ≤ t ≤ 10 |
| `if(cond, a, b)` | a if cond else b |
| `*` (between booleans) | logical AND (`gte(t,1)*lte(t,3)` = "1 ≤ t ≤ 3") |
| `+` (between booleans) | logical OR |

Example — visible only between t=1 and t=7:

```
enable='gte(t,1)*lte(t,7)'
```

Example — alpha fades in from 0 to 1 over t=1 to t=3, then stays at 1:

```
alpha='if(gte(t,1)*lte(t,3),(t-1)/2,1)'
```

## Always include `-y`

`-y` overwrites the output without prompting. Place it at the start of the command in scripts and automation. Without it, FFmpeg blocks on prompts when output files exist.
