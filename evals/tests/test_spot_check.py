import shutil
import subprocess
from pathlib import Path

import pytest

from runner.prompts import (
    DurationAssertion,
    FFprobeFieldAssertion,
    FileExistsAssertion,
    NoBlackFramesAtStartAssertion,
)
from runner.spot_check import AssertionResult, evaluate_assertions

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


@pytest.fixture
def sample_mp4(tmp_path: Path) -> Path:
    out = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(out),
        ],
        check=True,
    )
    return out


def test_file_exists_assertion_passes(sample_mp4: Path):
    results = evaluate_assertions(sample_mp4, [FileExistsAssertion(type="file_exists")])
    assert results == [AssertionResult(passed=True, detail="exists")]


def test_file_exists_fails_when_missing(tmp_path: Path):
    results = evaluate_assertions(
        tmp_path / "missing.mp4", [FileExistsAssertion(type="file_exists")]
    )
    assert results[0].passed is False


def test_duration_approx_passes(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [DurationAssertion(type="duration", op="approx", value=10.0, tolerance=0.5)],
    )
    assert results[0].passed is True


def test_duration_approx_fails_outside_tolerance(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [DurationAssertion(type="duration", op="approx", value=5.0, tolerance=0.5)],
    )
    assert results[0].passed is False


def test_ffprobe_field_codec_h264(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [FFprobeFieldAssertion(type="ffprobe_field", stream=0, key="codec_name", equals="h264")],
    )
    assert results[0].passed is True


def test_ffprobe_field_pix_fmt_yuv420p(sample_mp4: Path):
    results = evaluate_assertions(
        sample_mp4,
        [FFprobeFieldAssertion(type="ffprobe_field", stream=0, key="pix_fmt", equals="yuv420p")],
    )
    assert results[0].passed is True


def test_no_black_frames_at_start_passes(sample_mp4: Path):
    # testsrc is colorful — should pass.
    results = evaluate_assertions(
        sample_mp4, [NoBlackFramesAtStartAssertion(type="no_black_frames_at_start")]
    )
    assert results[0].passed is True
