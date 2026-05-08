"""Headless `claude -p` driver, using OAuth auth (Max plan).

Globally-installed plugins are isolated separately via
`runner.plugin_isolation.isolated_user_plugins()` — see `runner/run.py`.

See evals/README.md "Verified headless invocation".
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Resolve `claude` once. Windows npm shims are .CMD; Python subprocess without
# shell=True calls CreateProcess directly which doesn't honor PATHEXT.
_CLAUDE = shutil.which("claude") or "claude"


@dataclass
class InvokeResult:
    stdout: str
    stderr: str
    returncode: int


def build_argv(model: str, plugin_dir: Path | None) -> list[str]:
    """Build the claude argv. The prompt is passed via stdin in `invoke()`,
    NOT as a positional argument — Windows CreateProcess truncates argv values
    at embedded newlines, mangling multi-line prompts."""
    argv = ["claude", "-p", "--model", model]
    if plugin_dir is not None:
        argv += ["--plugin-dir", str(plugin_dir)]
    return argv


def invoke(
    *,
    model: str,
    plugin_dir: Path | None,
    prompt: str,
    timeout_s: int = 300,
) -> InvokeResult:
    """Spawn `claude -p`, passing the prompt via stdin. Auth via Max OAuth.

    On timeout or non-zero exit we return an InvokeResult with whatever stdout
    we got plus an explanatory stderr. The caller (runner.run) keeps going so
    one slow or failing prompt doesn't kill the whole batch.
    """
    argv = build_argv(model=model, plugin_dir=plugin_dir)
    argv[0] = _CLAUDE  # resolve `claude` -> full path (handles Windows .CMD)
    try:
        result = subprocess.run(
            argv, input=prompt, capture_output=True, text=True, timeout=timeout_s,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        return InvokeResult(
            stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
            stderr=f"[runner] timed out after {timeout_s}s",
            returncode=-1,
        )
    return InvokeResult(
        stdout=result.stdout, stderr=result.stderr, returncode=result.returncode
    )
