# Asset generation

Image → video, slideshows, Ken Burns, GIFs, video compilations, thumbnails, storyboards.

## Image to video (looping)

10-second video from a looping image with audio and fade-in:

```sh
ffmpeg -loop 1 -t 10 -i image.png -i input.mp3 -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1:color=black,setsar=1,fade=t=in:st=0:d=1,format=yuv420p" -c:v libx264 -c:a aac -shortest output_loop.mp4
```

- `-loop 1` — infinitely loop the input image.
- `-t 10` — cap the loop duration at 10 seconds.
- `fade=t=in:st=0:d=1` — 1-second fade-in at start.
- `format=yuv420p` — required for player compatibility.
- `-shortest` — bound output to the shortest input.

**Performance note:** if the image is at a remote URL, FFmpeg downloads it for *every* video frame — extremely slow. Download the image locally first.

## Slideshow with crossfade

5 seconds per image, 0.5-second crossfade between them, with background audio:

```sh
ffmpeg -loop 1 -t 5 -i image1.png -loop 1 -t 5 -i image2.png -i input.mp3 -filter_complex "[0:v]format=yuv420p,fade=t=in:st=0:d=0.5,setpts=PTS-STARTPTS[v0];[1:v]format=yuv420p,fade=t=out:st=4.5:d=0.5,setpts=PTS-STARTPTS[v1];[v0][v1]xfade=transition=fade:duration=0.5:offset=4.5,format=yuv420p[v]" -map "[v]" -map 2:a -c:v libx264 -c:a aac -shortest slideshow_with_fade.mp4
```

- Result is 9.5 seconds (5 + 5 - 0.5 overlap).
- `xfade=transition=fade:duration=0.5:offset=4.5` — the second image enters at offset 4.5 s and the transition lasts 0.5 s.
- Other transitions: `wipeleft`, `wiperight`, `wipeup`, `wipedown`, `slideleft`, `slideright`, `slideup`, `slidedown`, `circleopen`, `circleclose`, `pixelize`, `dissolve`, `radial`, etc.

## Ken Burns (zoom + pan over still images)

Two images, zoom in on the first then zoom out from the second, with a fade transition:

```sh
ffmpeg -loop 1 -i image1.png -loop 1 -i image2.png -i input.mp3 -filter_complex "[0:v]scale=8000:-1,zoompan=z='zoom+0.005':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=100:s=1920x1080:fps=25,trim=duration=4,format=yuv420p,setpts=PTS-STARTPTS[v0];[1:v]scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.5,max(zoom-0.005,1.005))':x=0:y='ih/2-(ih/zoom/2)':d=100:s=1920x1080:fps=25,trim=duration=4,format=yuv420p,setpts=PTS-STARTPTS[v1];[v0][v1]xfade=transition=fade:duration=1:offset=3,format=yuv420p[v]" -map "[v]" -map 2:a -c:v libx264 -c:a aac -shortest output_kenburns.mp4
```

### Decoding the recipe

- **`scale=8000:-1` first** — required to dodge a [zoompan jitter bug](https://trac.ffmpeg.org/ticket/4298). Pre-upscaling gives the filter more pixels to interpolate. `-1` keeps the aspect ratio.
- **`z='zoom+0.005'`** — adds 0.005 zoom per frame (zooms in 1.005× per frame).
- **`x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'`** — pans toward the center.
- **`d=100:s=1920x1080:fps=25`** — generates 100 frames at 1920×1080, 25 fps = 4 seconds of effect.
- **Zoom-out variant:** `z='if(lte(zoom,1.0),1.5,max(zoom-0.005,1.005))'` starts zoomed (1.5×) and zooms out toward 1.005×, then plateaus to avoid resetting.
- **`trim=duration=4`** — required to cap the chunk's length. `-t=4` before the input does *not* work with `zoompan` (it gets overridden by the `d`/`fps` interaction).

The output is 7 seconds long (4 + 4 - 1 fade overlap).

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

## Video compilation from one source

Take two segments (11–15 s and 21–25 s), apply fade in/out to each, concatenate:

```sh
ffmpeg -i input.mp4 -filter_complex "[0:v]trim=start=11:end=15,setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5,fade=t=out:st=3.5:d=0.5[v1];[0:a]atrim=start=11:end=15,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.5,afade=t=out:st=3.5:d=0.5[a1];[0:v]trim=start=21:end=25,setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5,fade=t=out:st=3.5:d=0.5[v2];[0:a]atrim=start=21:end=25,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.5,afade=t=out:st=3.5:d=0.5[a2];[v1][a1][v2][a2]concat=n=2:v=1:a=1[outv][outa]" -map "[outv]" -map "[outa]" -c:v libx264 -c:a aac output_fade_in_out.mp4
```

- `trim=start=X:end=Y` (video) and `atrim` (audio) — cut to time range.
- `setpts=PTS-STARTPTS` / `asetpts=PTS-STARTPTS` — reset timestamps (required before concat).
- Fades apply to each segment's local 0–4 s window.
- `concat=n=2:v=1:a=1` — joins 2 segments, each with 1 video + 1 audio stream, into named outputs `outv` and `outa`.

## Thumbnails

### Single thumbnail at a specific time

```sh
ffmpeg -i input.mp4 -ss 00:00:07 -frames:v 1 output_thumbnail.png
```

Control JPEG quality (1 best, 31 worst — sane is 2):

```sh
ffmpeg -i input.mp4 -ss 00:00:07 -frames:v 1 -q:v 2 output_thumbnail.jpg
```

### Two thumbnails in one pass

```sh
ffmpeg -i input.mp4 -filter_complex "[0:v]split=2[first][second];[first]select='gte(t,5)'[thumb1];[second]select='gte(t,15)'[thumb2]" -map [thumb1] -frames:v 1 output_thumbnail_1.png -map [thumb2] -frames:v 1 output_thumbnail_2.png
```

The `-frames:v 1` after each `-map` outputs exactly one frame per file.

### Thumbnail from a scene change

```sh
ffmpeg -i input.mp4 -vf "select='gt(scene,0.4)'" -frames:v 1  -q:v 2 thumbnail_scene.jpg
```

`scene` is FFmpeg's per-frame scene-change detection score (0–1). Lower threshold = more sensitive = more scenes detected. Recommended range 0.3–0.5.

## Composite thumbnail from multiple images

A background image with two overlay images padded with a black border, placed bottom-left and bottom-right:

```sh
ffmpeg -i bg.png -i image1.png -i image2.png -filter_complex "[1]scale=640:360,pad=648:368:4:4:black[overlay1];[2]scale=640:360,pad=648:368:4:4:black[overlay2];[0][overlay1]overlay=0:main_h-overlay_h[tmp1];[tmp1][overlay2]overlay=main_w-overlay_w:main_h-overlay_h" -frames:v 1 thumbnail_overlayed.png
```

The `pad=648:368:4:4:black` adds a 4 px black border around each scaled overlay (640+8, 360+8).

## Storyboards

### Tiled storyboard from scene changes

```sh
ffmpeg -i input.mp4 -vf "select='gt(scene,0.4)',scale=640:480,tile=2X2" -frames:v 1 scene_storyboard.jpg
```

`tile=2X2` — arrange the selected frames into a 2×2 grid in one image.

### One file per scene

```sh
ffmpeg -i input.mp4 -vf "select='gt(scene,0.4)'" -vsync 0 scene_storyboard_%03d.jpg
```

`-vsync 0` (deprecated — prefer `-fps_mode passthrough`) drops duplicate frames so each file represents a unique scene.

### Tiled storyboard from keyframes

```sh
ffmpeg -skip_frame nokey -i input.mp4 -vf 'scale=640:480,tile=4x4' -an -vsync 0 keyframes%03d.png
```

- `-skip_frame nokey` (input flag) — only decode keyframes.
- `tile=4x4` — 16 frames per output file. Multi-file output (`%03d`) handles cases where there are more than 16 keyframes.
- `-an` — no audio stream in output (PNGs can't have audio).

### Tile from every Nth frame

```sh
ffmpeg -i input.mp4  -vf "select=not(mod(n\,10)),scale=640:480,tile=4x2"  -vsync 0 tile_4_2_frames_10_%03d.png
```

`select=not(mod(n,10))` — keeps frames where the frame number is divisible by 10. Drop the `,tile=4x2` to get one image per selected frame instead of a tile.

## fps mode reminder

`-vsync 0` is deprecated. New form:

```
-fps_mode passthrough
```

The cheatsheet uses `-vsync 0` because it predates the change; both still work.

## Loop and image gotcha

When using `-loop 1` with an image, **download the image locally first**. FFmpeg downloads the file for every video frame over a remote URL, which is dramatically slower than reading from disk.
