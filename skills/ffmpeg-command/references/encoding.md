# Encoding — codecs, bitrate, presets, web optimization

How to choose codec parameters for a given target. Pick the codec first, then pick the rate-control mode, then the preset/tune.

## Codec selection

| Codec | Encoder | Container | Use case |
|---|---|---|---|
| H.264 / AVC | `libx264` | MP4, MKV, MOV | Most common; broad device support |
| H.265 / HEVC | `libx265` | MP4, MKV, MOV (with `-vtag hvc1` for Apple) | ~30–50% smaller than H264 at same quality; less universal |
| VP9 | `libvpx-vp9` | WebM | Open / royalty-free; 20–50% smaller than H264 same quality; YouTube re-encodes uploads to VP9 |
| AAC (audio) | `aac` (built-in) | most | Default audio codec for MP4; good practice to specify explicitly |
| MP3 (audio) | `libmp3lame` | MP3, MP4, MKV | Universal compatibility |
| Opus (audio) | `libopus` | WebM, MKV, OGG | Default for WebM; best quality at low bitrates |
| PCM (audio) | `pcm_s16le`, `pcm_s32le`, etc. | WAV, MOV | Uncompressed |

**Always specify the codec.** FFmpeg defaults to libx264 for MP4 *unless* the build doesn't include it. Explicit `-c:v libx264` is safer than relying on the default.

## H.264 (`libx264`)

Constant Rate Factor is the recommended rate-control mode for most uses:

```sh
ffmpeg -i input.mp4 -c:v libx264 -crf 18 -preset veryslow -movflags +faststart output.mp4
```

CRF semantics:

> The range of the CRF scale is 0–51, where 0 is lossless (for 8 bit only, for 10 bit use -qp 0), 23 is the default, and 51 is worst quality possible. A lower value generally leads to higher quality, and a subjectively sane range is 17–28. Consider 17 or 18 to be visually lossless or nearly so; it should look the same or nearly the same as the input but it isn't technically lossless.
> The range is exponential, so increasing the CRF value +6 results in roughly half the bitrate / file size, while -6 leads to roughly twice the bitrate.

The cheatsheet author finds `-crf 10` looks better than `-crf 18` for very high quality H264.

### Generic web-optimized command

Good default for archiving, streaming (non-live), and playback on many edge devices. Can be used unchanged for most jobs unless there's a specific reason not to:

```sh
ffmpeg -i input.mp4 -vf "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1" -crf 18 -preset veryslow  -threads 0 -tune fastdecode  -movflags +faststart  output_scaled_optimized.mp4
```

### `-preset`

Slower preset = better compression at the same quality (smaller file), at the cost of encode time. Available: `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`, `placebo`.

- Web/VOD/archive: `veryslow`
- Fast encoding with larger files: `ultrafast`
- Default: `medium`

### `-tune`

Optimizes encoding for a specific decoding scenario:

- `-tune fastdecode` — output requires less computational power to decode (good for many edge devices)
- `-tune zerolatency` — optimization for fast encoding and low-latency streaming
- `-tune film`, `animation`, `grain`, `stillimage` — content-aware tuning

### `-movflags +faststart`

Moves the `moov` atom to the front of the file so playback can begin before the file is fully downloaded. Works with H264 and H265, even on pure remux:

```sh
ffmpeg  -i input.mp4 -c copy -movflags +faststart input_faststart.mp4
```

YouTube recommends uploading MP4 files with `+faststart`. They re-encode to VP9 server-side anyway, but the metadata position helps their pipeline.

Verify with:

```sh
ffprobe -v trace -i your_video.mp4
```

Look for a `type:'moov'` line near the start of the trace output.

### `format=yuv420p`

H.264 YUV planar 4:2:0 chroma format. Required for QuickTime and most other players to play the output correctly. Apply when transforming images to video, and any time you have playback issues on a target device.

Use as a filter (`-vf format=yuv420p`) or output flag (`-pix_fmt yuv420p`).

## H.265 (`libx265`)

Same controls as libx264 (`-crf`, `-preset`, `-tune`).

For Apple compatibility (AirDrop, QuickTime, iOS Photos), add `-vtag hvc1`:

```sh
ffmpeg -i input.mp4 -c:v libx265 -vtag hvc1 -c:a copy output_265.mp4
```

`-movflags +faststart` works with libx265 too:

```sh
ffmpeg  -i input.mp4 -c:v libx265 -c:a copy -movflags +faststart input_h265_faststart.mp4
```

## VP9 (`libvpx-vp9`)

Constant Quality VP9 — use `-crf` *and* `-b:v 0` together:

```sh
ffmpeg -i input.mp4 -c:v libvpx-vp9 -crf 15 -b:v 0 -c:a libopus output.webm
```

> To trigger this mode, you must use a combination of `-crf` and `-b:v 0`. Note that `-b:v` MUST be 0. Setting it to anything higher or omitting it entirely will instead invoke the Constrained Quality mode.

> The CRF value can be from 0–63. Lower values mean better quality. Recommended values range from 15–35, with 31 being recommended for 1080p HD video.

The default audio encoder for WebM is `libopus`. The above command re-encodes AAC audio in MP4 to Opus in WebM.

## 1-pass vs 2-pass

VP9, libx264, and libx265 all support 1-pass and 2-pass encodings. Recommendations from slhck:

> - Archival — CRF that gives you the quality you want.
> - Streaming — Two-pass CRF or ABR with VBV-constrained bitrate.
> - Live Streaming — One-pass CRF or ABR with VBV-constrained bitrate, or CBR if you can waste bits.
> - Encoding for Devices — Two-pass ABR, typically.

For VP9 streaming, use [two-pass CRF](https://trac.ffmpeg.org/wiki/Encode/VP9#twopass): the first pass calculates statistics so the second can compress more efficiently while keeping quality.

## Audio encoding

```sh
# AAC (default for MP4, good practice to specify)
-c:a aac

# MP3
-c:a libmp3lame

# Opus (default for WebM)
-c:a libopus

# Disable audio in output
-an
```

### Audio bitrate / sample rate / channels

- `-ar 16000` — sample rate 16 kHz
- `-b:a 48k` (alias `-ab 48k`) — bitrate 48 kbit/s
- `-ac 1` — mono (1 channel); `-ac 2` — stereo
- `-q:a 2` for MP3 — high-quality VBR (~170–210 kbit/s stereo)

Example: extract MP4 audio to mono 16 kHz MP3 at 48 kbit/s, while also exporting the muted video:

```sh
ffmpeg -i  input.mp4 -ar 16000 -ab 48k -codec:a libmp3lame -ac 1 output_extracted_audio.mp3 -map 0:v -c:v copy -an out_video_only.mp4
```

## `-c copy` (stream copy / remux)

Re-wraps streams into a new container without altering them. Much cheaper than transcoding (especially video). Use whenever possible:

```sh
ffmpeg -i input.mp4 -c copy output.mkv
```

`-c:v copy` copies only video; `-c:a copy` (alias `-acodec copy`) copies only audio.

**Don't use `-c copy` when:**
- Applying any video filter (scale, overlay, subtitles, trim, fade) — these need re-encoding.
- Modifying audio (amix, atempo, volume) — these need re-encoding.
- Burning subtitles into the picture.
- Trimming with frame accuracy (it can only cut at keyframes — see `seeking-and-trimming.md`).
- Changing codec.
- Compressing.

## `-threads 0`

Default. Lets FFmpeg pick the optimal thread count for your system. Usually best to omit the flag entirely; tweak only if you have a specific bottleneck.

## Container vs codec

Both MP4 and MKV are containers that can hold H264 or H265 video and AAC or MP3 audio. The container format does not determine quality — the codec does. MKV can hold multiple video streams; MP4 is more widely supported on devices and platforms. MOV is similar to MP4 (both are MPEG-4 family).
