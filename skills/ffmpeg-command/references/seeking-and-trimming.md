# Seeking and trimming

`-ss` is the seek flag. Its position changes everything.

## Rule of thumb

For trimming, use **output seeking without `-c:v copy`** (re-encode the output):

```sh
ffmpeg -i input.mp4 -ss 00:00:10 -to 00:00:25 output_trimmed.mp4
```

Faster alternatives exist, but they're less accurate or can produce black frames.

## Input seeking — `-ss` before `-i`

```sh
ffmpeg -ss 00:00:03 -i input.mp4 -frames:v 1 input_seeking.jpg
```

- **Fast.** Parses the input by keyframe and jumps directly.
- **Less accurate.** With H.264 at 25fps, keyframes are typically every ~10 seconds. The seek lands on the nearest keyframe at or before the requested time.
- **Resets timestamps.** When trimming with input seeking, the output video's timestamps start from 0 — so subsequent filters see times relative to the trimmed start, not the original.

## Output seeking — `-ss` after `-i`

```sh
ffmpeg -i input.mp4 -ss 00:00:03 -frames:v 1 input_seeking.jpg
```

From the FFmpeg docs:

> When used as an input option, seeks in this input file to position. Note that in most formats it is not possible to seek exactly, so ffmpeg will seek to the closest seek point before position. When transcoding and -accurate_seek is enabled (the default), this extra segment between the seek point and position will be decoded and discarded. When doing stream copy or when -noaccurate_seek is used, it will be preserved.

- **Frame-accurate.** Decodes from the nearest preceding keyframe but discards frames until the requested time.
- **Slower.** That decode-and-discard is the cost of accuracy.
- **Preserves source timestamps.** Filters see the original video's times.

## Trimming + `-c:v copy` — avoid

When trimming, **don't combine output seeking with `-c:v copy`**:

- `-c:v copy` copies frames starting from your seek point — but if the keyframe before that seek point isn't included, the copied frames have no reference and decode as black/garbage at the start of the output.
- See FFmpeg's [trac documentation](https://trac.ffmpeg.org/wiki/Seeking#codec-copy) for the full explanation.

And **don't combine input seeking with `-c:v copy`** either:

- There's an open bug ([trac #8189](https://trac.ffmpeg.org/ticket/8189)) where it fails to trim correctly. See [Stackoverflow discussion](https://stackoverflow.com/questions/57450657/ffmpeg-fails-to-trim-beginning-of-clip).

So for clean trimming: output seeking, re-encode.

## Bitrate consideration

When re-encoding for a trim, the output video may be in a different bitrate than the source. Adjust output bitrate or use a CRF target (see `encoding.md`).

## Alternative: `trim` filter inside a graph

For trims that are part of a larger filter graph (e.g., concat or split), use the `trim` filter (video) and `atrim` filter (audio) instead of `-ss`:

```
[0:v]trim=start=11:end=15,setpts=PTS-STARTPTS[v1]
[0:a]atrim=start=11:end=15,asetpts=PTS-STARTPTS[a1]
```

`setpts=PTS-STARTPTS` resets timestamps to start at 0 — required before concat-ing trimmed segments. Without it, `concat` produces wrong durations.

## Quick reference table

| Goal | Approach |
|---|---|
| Frame-accurate trim, output is a clean clip | `-i input -ss start -to end output.mp4` (output seeking, re-encode) |
| Fast keyframe-based trim, accept ~10s slop | `-ss start -to end -i input -c copy output.mp4` (input seeking + stream copy) |
| Trim part of a complex filter graph | Use `trim`/`atrim` filter, then `setpts=PTS-STARTPTS`/`asetpts=PTS-STARTPTS` before further filters |
| Single thumbnail at a specific time | `-i input -ss time -frames:v 1 output.jpg` (output seeking; or input seeking for speed) |

## Always-on flag

Add `-y` to the start of every command in scripts so FFmpeg overwrites without prompting.
