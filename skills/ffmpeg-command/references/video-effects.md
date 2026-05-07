# Video effects

Scale, pad, crop, fps, speed, overlays, fades, stacks.

## Scale + pad (preserve aspect ratio, fill with black)

The canonical "fit input into a target frame and fill the rest" pattern. Always end with `setsar=1:1` to force square pixels.

```sh
ffmpeg -i input.mp4 -vf "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1" output_resized_pad.mp4
```

### Scale parameters

- `scale=w=1080:h=1920:force_original_aspect_ratio=decrease` — fits inside 1080×1920, downscales to keep the input's aspect ratio. With this input that produces 1080×810 before padding.
- `force_original_aspect_ratio` values:
  - `0` "disable" (default)
  - `1` "decrease" — auto-decrease output dimensions on need (output ≤ requested)
  - `2` "increase" — auto-increase output dimensions on need (output ≥ requested, will overflow without crop)
- `scale=w=1080:h=-1` — let FFmpeg pick the height to preserve aspect ratio. `-2` instead of `-1` forces dimensions divisible by 2 (required by many encoders).
- Don't use `scale=w=-1:1920` together with a pad target of 1080 wide — `-1` may pick a width larger than 1080, causing FFmpeg to error or overflow.

### Pad parameters

`pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black` — `width:height:x:y:color`. `(x, y)` is the top-left corner of the embedded video on the padded canvas. `(ow-iw)/2,(oh-ih)/2` centers it.

Negative coordinates also center, so `pad=1080:1920:-1:-1:color=black` is equivalent.

### `setsar=1:1`

Forces square pixels (Sample Aspect Ratio 1:1). Without it, FFmpeg may set a non-square SAR to compensate for the resize, distorting playback on some players. Equivalent forms: `setsar=1`, `setsar=1/1`.

## Multi-output: one input, two formats

Generate horizontal (1920×1080) and vertical (720×1280, with logo) videos in one pass:

```sh
ffmpeg -i input.mp4 -i logo.png -filter_complex "[0:v]split=2[s0][s1];[s0]scale=w=1920:h=1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[out1];[s1]scale=w=720:h=1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[s2];[s2][1]overlay=(main_w-overlay_w)/2:(main_w-overlay_w)/5[out2]" -map [out1] -map 0:a output_youtube.mp4 -map [out2] -map 0:a  output_shorts.mp4
```

The pattern: `split=2` fans out; one chain → `[out1]`, another → `[out2]`; multiple `-map [name] outputfile` pairs after the filter graph.

## Crop for vertical / social-media

Crop a 1080×720 source to 720×1080 by taking 480×720 chunks at different times (different x-offsets) and upscaling each chunk to 720×1080:

```sh
ffmpeg -i input.mp4 -vf "split=3[1][2][3];[1]trim=0.0:4.5,setpts=PTS-STARTPTS,crop=min(in_w-300\,480):min(in_h-0\,720):300:0,scale=720:1080,setsar=1:1[1];[2]trim=4.5:8.5,setpts=PTS-STARTPTS,crop=min(in_w-500\,480):min(in_h-0\,720):500:0,scale=720:1080,setsar=1:1[2];[3]trim=8.5,setpts=PTS-STARTPTS,crop=min(in_w-400\,480):min(in_h-0\,720):400:0,scale=720:1080,setsar=1:1[3];[1][2][3]concat=n=3:v=1" -c:v libx264 -c:a copy output_cropped.mp4
```

- `split=3[1][2][3]` — three copies of the input video.
- `trim=0.0:4.5` — trim each copy to a different time range. The third has no end time, so it runs to the input's end.
- `setpts=PTS-STARTPTS` — required after trim before concat (resets timestamps).
- `crop=W:H:X:Y` — crop to W×H starting at top-left (X, Y). The `min(in_w-N\,480)` form is a placeholder safety: it never crops outside the frame even if X exceeds bounds.
- `scale=720:1080` — upscale each cropped chunk by 1.5×.
- `concat=n=3:v=1` — join the three chunks back into one video stream.

If the crop x-offset would push the crop outside the frame, pad with black to fill the gap:

```sh
ffmpeg -i input.mp4 -vf "split=3[1][2][3];[1]trim=0.0:4.5,setpts=PTS-STARTPTS,crop=min(in_w-1200\,480):min(in_h-0\,720):1200:0,pad=480:720:(ow-iw)/2:(oh-ih)/2:color=black,scale=720:1080,setsar=1:1[1];[2]trim=4.5:8.5,setpts=PTS-STARTPTS,crop=min(in_w-500\,480):min(in_h-0\,720):500:0,pad=480:720:(ow-iw)/2:(oh-ih)/2:color=black,scale=720:1080,setsar=1:1[2];[3]trim=8.5,setpts=PTS-STARTPTS,crop=min(in_w-400\,480):min(in_h-0\,720):400:0,pad=480:720:(ow-iw)/2:(oh-ih)/2:color=black,scale=720:1080,setsar=1:1[3];[1][2][3]concat=n=3:v=1" -c:v libx264 -c:a copy output_cropped.mp4
```

## Speed change (no audio pitch shift)

```sh
ffmpeg -i input.mp4 -filter_complex "[0:v]setpts=PTS/1.5[v];[0:a]atempo=1.5[a]" -map "[v]" -map "[a]" output_sped_up.mp4
```

- `setpts=PTS/1.5` — speeds up video 1.5× (smaller PTS = earlier frames = faster).
- `atempo=1.5` — speeds up audio 1.5× while preserving pitch.
- `atempo` accepts 0.5–100.0; chain multiple if you need extreme rates: `atempo=2.0,atempo=2.0` = 4×.

## Frame rate change (without changing audio speed)

```sh
ffmpeg -i input.mp4 -filter:v fps=60 popeye_fps.mp4
```

`fps=60` resamples the video to 60 fps without affecting audio sync.

## Jump cuts (skip ranges, keep selected)

Used for shortening clips, removing silence, removing transitions:

```sh
ffmpeg -i input.mp4 -vf "select='between(t,0.0,5.7)+between(t,11.0,18.0)+between(t,19.0,20.0)',setpts=N/FRAME_RATE/TB" -af "aselect='between(t,0.0,5.7)+between(t,11.0,18.0)+between(t,19.0,20.0)',asetpts=N/SR/TB" popeye_jumpcuts.mp4
```

- `select='between(t,a,b)+between(t,c,d)'` — keep only frames in those time ranges (`+` is logical OR).
- `setpts=N/FRAME_RATE/TB` (video) and `asetpts=N/SR/TB` (audio) — recompute timestamps so the kept frames produce a continuous output:
  - `N` — count of consumed frames/audio samples (0-based)
  - `FRAME_RATE` / `SR` — video frame rate / audio sample rate
  - `TB` — input timebase

## Overlay logo (timed, simple)

```sh
ffmpeg -i input.mp4 -i logo.png -filter_complex "overlay=x=(main_w-overlay_w)/8:y=(main_h-overlay_h)/8:enable='gte(t,1)*lte(t,7)'" -c:v libx264 -c:a  output_logo.mp4
```

- `x=(main_w-overlay_w)/8:y=(main_h-overlay_h)/8` — top-left at 1/8 inset from top-left of frame.
- `enable='gte(t,1)*lte(t,7)'` — visible only between t=1 and t=7 (`*` is logical AND).

## Overlay logo with FFmpeg-controlled transparency

If the logo has no alpha channel, or you want to control opacity dynamically:

```sh
ffmpeg -i input.mp4 -i logo.png -filter_complex  "[1:v]format=argb,geq='p(X,Y)':a='0.5*alpha(X,Y)'[v1];[0:v][v1]overlay=x=(main_w-overlay_w)/8:y=(main_h-overlay_h)/8:enable='gte(t,1)*lte(t,7)'" -c:v libx264 -c:a copy output_faded_logo.mp4
```

- `format=argb` — ensures the logo has an alpha channel.
- `geq='p(X,Y)':a='0.5*alpha(X,Y)'` — keeps each pixel's color (`p(X,Y)`) and halves the alpha (`0.5*alpha(X,Y)`). This produces a 50% transparent logo.

## Video on top of a background image

Centers a video on a background image (creating a new aspect ratio):

```sh
ffmpeg -i input.mp4 -i bg.png -filter_complex "[1:v][0:v]overlay=(W-w)/2:(H-h)/2" -c:v libx264 -c:a copy output_bg.mp4
```

`[1:v][0:v]overlay=...` puts input 1 (the image) on the bottom and input 0 (the video) on top. `W/H` are the *first specified* stream's dimensions (the background image), `w/h` are the second (the video) — order in the filter, not in `-i`.

## Stack two videos vertically, keep one's audio

```sh
ffmpeg -i input.mp4 -i input2.mp4 -filter_complex "[0:v]scale=720:-2:force_original_aspect_ratio=decrease,pad=720:640:(ow-iw)/2:(oh-ih)/2:black[top];[1:v]scale=720:-2:force_original_aspect_ratio=decrease,pad=720:640:(ow-iw)/2:(oh-ih)/2:black[bottom];[top][bottom]vstack=inputs=2:shortest=1[v]" -map "[v]" -map 1:a -c:v libx264 -c:a aac -shortest output_stacked.mp4
```

- `[top][bottom]vstack=inputs=2:shortest=1` — vertical stack ending when the shorter input ends.
- `-map "[v]" -map 1:a` — uses the stacked video and only input 1's audio.
- `-shortest` — bounds the output to the shortest input/audio combination.
- `hstack` is the horizontal counterpart.

For unequal-sized inputs, scale and pad each to the same dimensions before stacking.

## Fades (video)

Inside a filter chain:

- `fade=t=in:st=0:d=1` — 1-second fade-in starting at t=0
- `fade=t=out:st=3.5:d=0.5` — 0.5-second fade-out starting at t=3.5

Pair with `afade` for audio (see `audio.md`).

## Filter chain quick reference

| Goal | Filter |
|---|---|
| Resize keeping AR | `scale=w=W:h=H:force_original_aspect_ratio=decrease` |
| Auto-pick dimension | `scale=W:-1` (any height) or `scale=W:-2` (height divisible by 2) |
| Pad to fixed canvas | `pad=W:H:(ow-iw)/2:(oh-ih)/2:color=black` |
| Force square pixels | `setsar=1:1` |
| Crop region | `crop=W:H:X:Y` (X,Y is top-left) |
| Speed up video | `setpts=PTS/RATIO` (video), `atempo=RATIO` (audio) |
| Change fps | `-filter:v fps=N` (or `fps=N` in a chain) |
| Pixel format compatibility | `format=yuv420p` |
