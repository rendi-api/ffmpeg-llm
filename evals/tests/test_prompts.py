from pathlib import Path

import pytest
from pydantic import ValidationError

from runner.prompts import Prompt, load_prompts


def test_load_minimal_prompt(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: minimal-1\n"
        "  source: https://example.com/q\n"
        "  prompt: extract audio\n"
        "  category: [audio]\n"
        "  difficulty: easy\n"
    )
    prompts = load_prompts(yaml)
    assert len(prompts) == 1
    p = prompts[0]
    assert p.id == "minimal-1"
    assert p.category == ["audio"]
    assert p.difficulty == "easy"
    assert p.spot_check is None


def test_load_prompt_with_spot_check(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: spot-1\n"
        "  source: rendi-internal\n"
        "  prompt: trim 10s to 25s\n"
        "  category: [seeking-and-trimming]\n"
        "  difficulty: medium\n"
        "  spot_check:\n"
        "    fixture: sample_1080p.mp4\n"
        "    assertions:\n"
        "      - {type: duration, op: approx, value: 15.0, tolerance: 0.5}\n"
        "      - {type: ffprobe_field, stream: 0, key: codec_name, equals: h264}\n"
    )
    prompts = load_prompts(yaml)
    assert prompts[0].spot_check is not None
    assert prompts[0].spot_check.fixture == "sample_1080p.mp4"
    assert len(prompts[0].spot_check.assertions) == 2


def test_duplicate_ids_rejected(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: dup\n"
        "  source: x\n"
        "  prompt: a\n"
        "  category: [audio]\n"
        "  difficulty: easy\n"
        "- id: dup\n"
        "  source: x\n"
        "  prompt: b\n"
        "  category: [audio]\n"
        "  difficulty: easy\n"
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_prompts(yaml)


def test_invalid_difficulty_rejected(tmp_path: Path):
    yaml = tmp_path / "p.yaml"
    yaml.write_text(
        "- id: bad\n"
        "  source: x\n"
        "  prompt: a\n"
        "  category: [audio]\n"
        "  difficulty: extreme\n"
    )
    with pytest.raises(ValidationError):
        load_prompts(yaml)
