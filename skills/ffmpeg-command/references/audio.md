# Audio operations

Extract, replace, mix, format, channels, fades, normalize.

## Audio options

- `-ar 16000` — sample rate (Hz)
- `-b:a 48k` (alias `-ab`) — bitrate
- `-ac 1` — mono (1 channel); `-ac 2` — stereo
- `-q:a 2` — VBR quality for MP3 (range 0–9, 0 best); `-q:a 2` ≈ 170–210 kbit/s stereo
- `-an` — disable audio in output

## Extract audio from video

Encode MP4 → MP3 with FFmpeg's defaults:

```sh
ffmpeg -i input.mp4 output.mp3
```

Extract MP4 audio, downsample to 16 kHz mono MP3 at 48 kbit/s, *and* extract the muted video in the same command:

```sh
ffmpeg -i  input.mp4 -ar 16000 -ab 48k -codec:a libmp3lame -ac 1 output_extracted_audio.mp3 -map 0:v -c:v copy -an out_video_only.mp4
```

Extract AAC without re-encoding (fast, no quality loss):

```sh
ffmpeg -i  input.mp4 -map 0:a:0 -acodec copy output.aac
```

## Replace audio in video

Trim video to audio length with `-shortest`:

```sh
ffmpeg -i input.mp4 -i input.mp3 -map 0:v -map 1:a  -shortest -c:v copy -c:a aac output_replace_audio.mp4
```

`-shortest` trims the video's end to match the shorter (audio) input. Without it, the output keeps the video's length and is silent past the audio's end.

> Note from the cheatsheet author: this command uses `-c:v copy` and trims at non-keyframes without re-encoding, which would normally cause black frames. Output looks perfect anyway. Forcing `-c:v libx264` produced a 7-second output for 5-second audio. Behavior is inconsistent — see `pitfalls.md` item 16.

## Mix audio over video at lower volume

```sh
ffmpeg -i input.mp4 -i input.mp3 -filter_complex "[1:a]volume=0.2[a1];[0:a][a1]amix=inputs=2:duration=shortest" -shortest -map 0:v -c:v copy -c:a aac output_mix_audio.mp4
```

- `[1:a]volume=0.2[a1]` — drops input 1's audio to 20%, names the result `a1`
- `[0:a][a1]amix=inputs=2:duration=shortest` — mixes the video's audio with the volume-adjusted audio
- `:duration=shortest` (filter option) controls the *audio* output duration
- `-shortest` (output flag) controls the *file's* duration — both are needed

If volume change isn't required:

```sh
-filter_complex "[0:a][1:a]amix=inputs=2:duration=shortest"
```

There's [an open FFmpeg bug](https://trac.ffmpeg.org/ticket/9487) around `amix` durations. Using both `:duration=shortest` and `-shortest` together avoids it.

## Concatenate MP3 tracks with a fade overlap

```sh
ffmpeg -i input.mp3 -i input2.mp3 -filter_complex "[0:a]afade=t=out:st=2:d=3[a0];[1:a]afade=t=in:st=0:d=3[a1];[a0][a1]concat=n=2:v=0:a=1" -c:a libmp3lame -q:a 2 output_gapless_fade.mp3
```

- First input fades out for 3 s starting at its 2 s mark.
- Second input fades in for 3 s starting at its 0 s mark.
- `concat=n=2:v=0:a=1` joins them as a single audio stream (no video).
- `-q:a 2` outputs high-quality VBR MP3 (~170–210 kbit/s stereo).

## Crossfade two tracks

```sh
ffmpeg -i input.mp3 -i input2.mp3 -filter_complex "[0:0][1:0]acrossfade=d=3:c1=exp:c2=qsin" -c:a libmp3lame -q:a 2 output.mp3
```

- `acrossfade=d=3:c1=exp:c2=qsin` — 3-second crossfade where the first track fades out exponentially (`c1=exp`) and the second fades in with quarter-sine (`c2=qsin`). Available curves: `tri`, `qsin`, `hsin`, `esin`, `log`, `ipar`, `qua`, `cub`, `squ`, `cbr`, `par`, `exp`, `iqsin`, `ihsin`, `dese`, `desi`, `losi`.

## Format conversion

MP3 → WAV (32-bit little-endian PCM, mono, 48 kHz):

```sh
ffmpeg -i input.mp3 -acodec pcm_s32le -ac 1 -ar 48000 output.wav
```

Common PCM codec names: `pcm_s16le` (16-bit signed LE — most common for WAV), `pcm_s24le`, `pcm_s32le`, `pcm_f32le` (32-bit float).

## Merge audio from multiple videos with normalization

Mix the audio from two MP4s, blend stereo to mono equally, normalize loudness, downsample to 16 kHz, encode as MP3 at 64 kbit/s:

```sh
ffmpeg -i input.mp4 -i input2.mp4 -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest,pan=mono|c0=.5*c0+.5*c1,dynaudnorm" -ar 16000 -c:a libmp3lame -b:a 64k merged_audio.mp3
```

- `amix=inputs=2:duration=longest` — mix and follow the longer input
- `pan=mono|c0=.5*c0+.5*c1` — output one channel (`c0`) made of 50% left + 50% right (a balanced stereo→mono downmix instead of dropping a channel)
- `dynaudnorm` — dynamic audio normalization (smooths loud/quiet sections)

## Codec quick reference

| Codec | Encoder | Use case |
|---|---|---|
| AAC | `aac` | Default for MP4; good practice to specify |
| MP3 | `libmp3lame` | Universal compatibility |
| Opus | `libopus` | Default for WebM; best at low bitrates |
| PCM (uncompressed) | `pcm_s16le`, `pcm_s32le`, etc. | WAV/MOV |
| Vorbis | `libvorbis` | Older WebM/OGG content |

## Audio fades

Inside a filter chain:

- `afade=t=in:st=0:d=1.5` — 1.5-second fade-in starting at t=0
- `afade=t=out:st=20:d=2` — 2-second fade-out starting at t=20

Pair with `aformat=sample_fmts=fltp` (32-bit float planar) when the chain feeds into a normalization or mix step that expects a specific format.
