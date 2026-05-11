# claude-ffmpeg

An FFmpeg plugin for Claude Code. Describe what you want, get the command.

## Install (local dev)

```bash
claude --plugin-dir ./claude-ffmpeg
```

## Quick start

With the plugin loaded, describe what you want in plain English:

> *"trim input.mp4 from 10s to 25s, re-encode for web"*
> *"burn the subtitles from sample.srt using Poppins 24pt"*
> *"high-quality GIF from clip.mp4, max 640px wide"*
> *"package input.mp4 as HLS VOD for a CDN"*

Or use the slash command:

```
/ffmpeg scale to 1080x1920 with black bars, web-optimized
```

For uglier jobs (a filtergraph that won't compile, an encode that breaks on a real phone), Claude hands off to the `ffmpeg-expert` subagent.

## What it handles

Transcoding, remuxing, trimming, filter graphs, audio, subtitles, GIFs, HLS/DASH, GPU encoding (NVENC/QSV/VAAPI).

You don't have to pick between fast vs frame-accurate seek, or quality-first vs size-first GIF. Tell Claude what you actually care about ("smallest file", "plays on iPhone", "frame-accurate cut at 0:14") and it picks the approach and the flags for you.

## Remembers the flags that quietly ruin your day

`yuv420p` so QuickTime will play the file. `+faststart` for web MP4. `hvc1` for Apple HEVC. `setsar=1:1` after scale+pad. `palettegen` so the GIF isn't banded. `EXT-X-ENDLIST` so the HLS player doesn't think your finished file is a live stream. About twenty of these baked in. Mostly things you only learn by shipping a broken video first.

## License

MIT
