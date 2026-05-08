"""Headless `claude --bare -p` driver.

`--bare` skips hooks, plugin sync, auto-memory, keychain reads, and CLAUDE.md
auto-discovery — giving us a clean baseline. Plugins still load via explicit
`--plugin-dir`. Auth is `ANTHROPIC_API_KEY` only.

See evals/README.md "Verified headless invocation".
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InvokeResult:
    stdout: str
    stderr: str
    returncode: int


def build_argv(model: str, plugin_dir: Path | None, prompt: str) -> list[str]:
    argv = ["claude", "--bare", "-p", "--model", model]
    if plugin_dir is not None:
        argv += ["--plugin-dir", str(plugin_dir)]
    argv.append(prompt)
    return argv


def invoke(
    *,
    model: str,
    plugin_dir: Path | None,
    prompt: str,
    timeout_s: int = 120,
) -> InvokeResult:
    """Spawn `claude --bare -p`. Caller is responsible for ANTHROPIC_API_KEY in env."""
    argv = build_argv(model=model, plugin_dir=plugin_dir, prompt=prompt)
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout_s
    )
    return InvokeResult(
        stdout=result.stdout, stderr=result.stderr, returncode=result.returncode
    )
