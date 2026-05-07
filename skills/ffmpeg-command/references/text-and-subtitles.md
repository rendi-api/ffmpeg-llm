# Text and subtitles

`drawtext` for overlay text, `subtitles` for burned-in subtitles, mux/extract for soft subtitle tracks.

## `drawtext` — overlay text

Three text messages at specific times, each with fade-in alpha and a semi-transparent green background box:

```sh
ffmpeg -i input.mp4 -vf "drawtext=text='Get ready':x=50:y=100:fontsize=80:fontcolor=black:alpha='if(gte(t,1)*lte(t,3),(t-1)/2,1)':box=1:boxcolor=#6bb666@0.6:boxborderw=7:enable='gte(t,1)', drawtext=text='Set':x=50:y=200:fontsize=80:fontcolor=black:alpha='if(gte(t,6)*lte(t,10),(t-6)/4,1)':box=1:boxcolor=#6bb666@0.6:boxborderw=7:enable='gte(t,6)', drawtext=text='BOOM!':x=50:y=300:fontsize=80:fontcolor=black:alpha='if(gte(t,10)*lte(t,15),(t-10)/5,1)':box=1:boxcolor=#6bb666@0.6:boxborderw=7:enable='gte(t,10)'" -c:v libx264 output_text_overlay.mp4
```

### Key attributes (per `drawtext=`)

| Attribute | Meaning |
|---|---|
| `text='...'` | Literal text (single quotes; escape special chars or use `textfile=`) |
| `x=`, `y=` | Top-left position (px or expression like `(w-text_w)/2` for centered) |
| `fontsize=` | Pixel size |
| `fontcolor=` | Color name or `#RRGGBB`; can append alpha as `@0.6` (60% opaque) |
| `fontfile=` | Path to a `.ttf`/`.otf` file (FFmpeg uses this directly, no system lookup) |
| `enable=` | Expression controlling visibility (e.g., `'gte(t,1)*lte(t,7)'`) |
| `alpha=` | Opacity expression (0–1) for fades |
| `box=1` | Draw a background rectangle behind the text |
| `boxcolor=` | Box color; supports `@alpha` syntax (e.g., `#6bb666@0.6`) |
| `boxborderw=` | Padding (px) around the text inside the box |

### Reading the alpha expression

```
alpha='if(gte(t,1)*lte(t,3),(t-1)/2,1)'
```

"If 1 ≤ t ≤ 3, alpha is `(t-1)/2` (linearly increases from 0 at t=1 to 1 at t=3). Otherwise alpha is 1 (fully opaque)." Combined with `enable='gte(t,1)'`, this fades the text in from t=1 to t=3 and keeps it visible from t=3 onward.

### Local font file

Set `fontfile=` to the absolute or relative path:

```
drawtext=text='Get ready':x=50:y=100:fontsize=80:fontcolor=black:fontfile=arial.ttf
```

## `drawtext` from external files

When the text contains special characters (quotes, `:`, `\`) or you don't want long strings in the command:

```sh
ffmpeg -i input.mp4 -vf "drawtext=textfile=sample_text.txt:fontfile=Poppins-Regular.ttf:x=50:y=100:fontsize=40:fontcolor=black:alpha='if(gte(t,1)*lte(t,5),t-1,1)':box=1:boxcolor=#6bb666@0.6:boxborderw=7:enable='gte(t,1)'" -c:v libx264 output_text_font_file.mp4
```

`textfile=` — path to a UTF-8 text file containing the message.
`fontfile=` — path to the font file.

**FFmpeg does not download URLs for `textfile=` or `fontfile=`.** Both must be local files.

## Burn SRT subtitles with custom font and styling

```sh
ffmpeg -i input.mp4 -ss 00:00 -to 00:40 -vf "subtitles=sample_subtitles.srt:fontsdir=.:force_style='FontName=Poppins,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H4066B66B,Outline=1,BorderStyle=3'" -c:v libx264  -c:a copy output_subtitles.mp4
```

- `subtitles=path.srt` — file to burn.
- `fontsdir=.` — directory containing the font file(s).
- `force_style='...'` — comma-separated ASS-style attributes overriding the SRT's defaults.
- `FontName=Poppins` — font's *internal* name (open the font file in a viewer to see it). Not the filename.
- `FontSize=24` — pixel size.
- `PrimaryColour=&HFFFFFF` — text color in `&HBBGGRR` (or `&HAABBGGRR` with alpha). Note: this is **B-G-R**, the reverse of HTML's R-G-B.
- `OutlineColour=&H4066B66B,Outline=1,BorderStyle=3` — green outline/background. With `BorderStyle=3` and `Outline=1`, this produces an opaque colored box behind each line. The alpha byte `40` (`/FF` ≈ 25%) means 25% opaque background.

Subtitle styling is finicky. For heavy customization use the ASS subtitle format directly. For pixel-perfect effects, consider rendering subtitle frames as PNGs and burning them as image overlays instead.

## Mux SRT as a subtitle track (no re-encode)

Adds a default SRT track to an MKV without re-encoding video:

```sh
ffmpeg -i input.mp4 -i sample_subtitles.srt -c copy -c:s srt -disposition:s:0 default input.mkv
```

- `-c copy` — stream copy for video and audio.
- `-c:s srt` — store the subtitle stream in SRT format.
- `-disposition:s:0 default` — mark the first subtitle stream as the default track (auto-displayed by players).

MP4 supports muxed subtitles too, but MKV is more flexible.

## Extract subtitles from a container

```sh
ffmpeg -i input.mkv -map 0:s:0 subs.srt
```

`0:s:0` — input 0, first subtitle stream.

## Color encoding cheat (ASS / `force_style`)

| Form | Meaning |
|---|---|
| `&HBBGGRR` | Solid color — note the **reverse** of HTML's R-G-B |
| `&HAABBGGRR` | With alpha — `00` = fully opaque, `FF` = fully transparent |
| `&H000000` | Black, opaque |
| `&HFFFFFF` | White, opaque |
| `&H4066B66B` | Green `#6BB666` at 25% opaque (alpha `40` ≈ 25% in hex) |

## Choosing between drawtext and subtitles

- **drawtext** — for one-off overlays, headings, watermarks, dynamic text with frame-level control.
- **subtitles** (SRT/ASS) — for time-coded dialogue with many lines. Edit the subtitle file separately from the video.
- **Image overlays** — for pixel-perfect effects (custom shadows, fonts not in any subtitle library, animated text). Render frames externally and overlay PNGs with the `overlay` filter.
