"""Prompt schema for the eval harness. Load + validate YAML prompt files."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, TypeAdapter

Difficulty = Literal["easy", "medium", "hard"]
Category = Literal[
    "encoding",
    "filters",
    "seeking-and-trimming",
    "audio",
    "video-effects",
    "text-and-subtitles",
    "asset-generation",
    "gpu-acceleration",
    "cross-category",
]


class FFprobeFieldAssertion(BaseModel):
    type: Literal["ffprobe_field"]
    stream: int
    key: str
    equals: str | None = None
    contains: str | None = None


class DurationAssertion(BaseModel):
    type: Literal["duration"]
    op: Literal["approx", "exact", "less_than", "greater_than"]
    value: float
    tolerance: float = 0.0


class NoBlackFramesAtStartAssertion(BaseModel):
    type: Literal["no_black_frames_at_start"]
    threshold: float = 0.05


class FileExistsAssertion(BaseModel):
    type: Literal["file_exists"]


Assertion = Annotated[
    Union[
        FFprobeFieldAssertion,
        DurationAssertion,
        NoBlackFramesAtStartAssertion,
        FileExistsAssertion,
    ],
    Field(discriminator="type"),
]


class SpotCheck(BaseModel):
    fixture: str
    assertions: list[Assertion]


class Prompt(BaseModel):
    id: str
    source: str
    prompt: str
    category: list[Category]
    difficulty: Difficulty
    spot_check: SpotCheck | None = None


_PromptList = TypeAdapter(list[Prompt])


def load_prompts(path: Path) -> list[Prompt]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    prompts = _PromptList.validate_python(raw)
    seen: set[str] = set()
    for p in prompts:
        if p.id in seen:
            raise ValueError(f"duplicate prompt id: {p.id}")
        seen.add(p.id)
    return prompts
