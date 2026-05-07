# GPU acceleration

Hardware-accelerated encoders for NVIDIA, Intel, and AMD GPUs.

## When to use GPU encoding

- **Helps:** large transcodes (long files, high resolutions), real-time streaming, throughput-bound batches.
- **Hurts:** small files (the GPU init overhead dominates), complex filter graphs (filters often run on CPU and force expensive GPU↔CPU copies), maximum-quality encoding (CPU encoders at slow presets achieve smaller files at the same visual quality).

Default to CPU encoders (`libx264`, `libx265`, `libvpx-vp9`) for quality work. Switch to GPU when encode time is the bottleneck.

## NVIDIA — NVENC

H.264:

```sh
ffmpeg -i input.avi -c:v h264_nvenc output_gpu_264.mp4
```

H.265:

```sh
ffmpeg -i input.avi -c:v hevc_nvenc output_gpu_265.mp4
```

Reference: [FFmpeg NVENC wiki](https://trac.ffmpeg.org/wiki/HWAccelIntro#NVENC).

## Intel — Quick Sync Video (QSV)

```sh
ffmpeg -init_hw_device qsv=hw -filter_hw_device hw -i input.avi -c:v h264_qsv output_gpu_qsv.mp4
```

QSV requires the `-init_hw_device` and `-filter_hw_device` setup before `-i` to wire up the hardware context.

Reference: [FFmpeg QuickSync wiki](https://trac.ffmpeg.org/wiki/Hardware/QuickSync).

## AMD — VAAPI

More complicated and less universally supported than NVENC/QSV. See the [VAAPI wiki](https://trac.ffmpeg.org/wiki/Hardware/VAAPI) for the full setup (involves `-vaapi_device`, `-vf 'format=nv12,hwupload'`, and a VAAPI-prefixed encoder like `h264_vaapi`).

## Encoder name reference

| Vendor | H.264 encoder | H.265 encoder |
|---|---|---|
| CPU (software) | `libx264` | `libx265` |
| NVIDIA | `h264_nvenc` | `hevc_nvenc` |
| Intel | `h264_qsv` | `hevc_qsv` |
| AMD | `h264_vaapi` / `h264_amf` | `hevc_vaapi` / `hevc_amf` |
| Apple | `h264_videotoolbox` | `hevc_videotoolbox` |

## Quality controls

GPU encoders have their own rate-control modes that don't map 1:1 to libx264's CRF:

- `-cq <n>` (NVENC, QSV) — constant quality, similar idea to CRF.
- `-b:v <bitrate>` — average bitrate (ABR).
- `-rc constqp -qp <n>` (NVENC) — constant quantization parameter.

Quality-per-bit is generally lower than `libx264 -preset slow/veryslow`, but the speedup can be 5–20×. Test on your content.

## Probing GPU support

List encoders the FFmpeg build supports:

```sh
ffmpeg -encoders
```

Look for entries like `V..... h264_nvenc` to confirm GPU encoder availability. Absence usually means the FFmpeg build wasn't compiled with that hardware support, not that the GPU is unavailable.
