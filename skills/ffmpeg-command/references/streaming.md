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
