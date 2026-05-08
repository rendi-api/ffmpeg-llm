"""Disable globally-installed Claude Code plugins during the benchmark.

Snapshots currently-enabled user-scope plugins, disables them all, runs the
benchmark, then restores. Implemented as a context manager with try/finally so
plugins are restored even on Ctrl-C or exception.

We only manage user-scope plugins. Project-scope plugins are pinned to specific
projectPaths and don't activate from this worktree.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

# Resolve `claude` to its full path once. On Windows, npm shims are .CMD files,
# and Python's subprocess (without shell=True) calls CreateProcess directly,
# which doesn't honor PATHEXT. Hardcoding the resolved path side-steps that.
_CLAUDE = shutil.which("claude") or "claude"


@dataclass(frozen=True)
class PluginSnapshot:
    id: str       # e.g. "claude-hud@claude-hud"
    scope: str    # "user"


def list_plugins() -> list[dict]:
    """Return raw `claude plugin list --json` output as a list of dicts."""
    result = subprocess.run(
        [_CLAUDE, "plugin", "list", "--json"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(result.stdout)


def snapshot_enabled_user_plugins(plugins: list[dict] | None = None) -> list[PluginSnapshot]:
    """Filter to currently-enabled, user-scope plugins.

    `plugins` is the parsed output of `claude plugin list --json`. Pass None to
    fetch fresh.
    """
    if plugins is None:
        plugins = list_plugins()
    return [
        PluginSnapshot(id=p["id"], scope=p["scope"])
        for p in plugins
        if p.get("enabled") and p.get("scope") == "user"
    ]


def disable_plugins(snapshot: list[PluginSnapshot]) -> None:
    """Disable each plugin in the snapshot. `claude plugin disable -a` is
    incompatible with `--scope`, so we iterate per plugin instead."""
    for p in snapshot:
        result = subprocess.run(
            [_CLAUDE, "plugin", "disable", p.id, "-s", p.scope],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to disable {p.id} (scope={p.scope}): "
                f"{(result.stderr or result.stdout).strip()}"
            )


def restore_plugins(snapshot: list[PluginSnapshot]) -> list[str]:
    """Re-enable each plugin from the snapshot. Returns ids that failed (best-effort)."""
    failed: list[str] = []
    for p in snapshot:
        result = subprocess.run(
            [_CLAUDE, "plugin", "enable", p.id, "-s", p.scope],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            failed.append(p.id)
    return failed


@contextmanager
def isolated_user_plugins() -> Iterator[list[PluginSnapshot]]:
    """Context manager: disable enabled user-scope plugins, restore on exit.

    Yields the snapshot so callers can log it. Restores via try/finally so
    plugins come back even if the body raises.
    """
    snapshot = snapshot_enabled_user_plugins()
    if snapshot:
        print(f"[plugin-isolation] disabling {len(snapshot)} user plugins: "
              f"{', '.join(p.id for p in snapshot)}", flush=True)
        disable_plugins(snapshot)
    try:
        yield snapshot
    finally:
        if snapshot:
            failed = restore_plugins(snapshot)
            if failed:
                print(f"[plugin-isolation] WARNING: failed to restore: {failed}. "
                      f"Restore manually with: claude plugin enable <id> -s user", flush=True)
            else:
                print(f"[plugin-isolation] restored {len(snapshot)} plugins", flush=True)
