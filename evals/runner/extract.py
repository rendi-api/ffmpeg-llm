"""Extract the canonical ffmpeg command from a Claude response.

Convention: the LAST fenced shell block whose content starts with `ffmpeg` is the
canonical command. All blocks are preserved for later inspection. If no such block
exists, the response is treated as `no_command` (typically clarifying questions).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Match ```sh|bash|shell|console|zsh ... ``` blocks (case-insensitive language tag)
_FENCE = re.compile(
    r"```(?:sh|bash|shell|console|zsh)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class ExtractResult:
    command: str | None
    no_command: bool
    all_blocks: list[str]


def extract_command(response: str) -> ExtractResult:
    raw_blocks = [m.group(1).strip() for m in _FENCE.finditer(response)]
    blocks = [_strip_prompt(b) for b in raw_blocks]
    ffmpeg_blocks = [b for b in blocks if b.lower().startswith("ffmpeg")]
    if not ffmpeg_blocks:
        return ExtractResult(command=None, no_command=True, all_blocks=blocks)
    return ExtractResult(command=ffmpeg_blocks[-1], no_command=False, all_blocks=blocks)


def _strip_prompt(block: str) -> str:
    """Remove a leading `$ ` shell-prompt marker if present."""
    lines = block.splitlines()
    if lines and lines[0].lstrip().startswith("$ "):
        lines[0] = lines[0].split("$ ", 1)[1]
    return "\n".join(lines).strip()
