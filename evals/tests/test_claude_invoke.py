from pathlib import Path

from runner.claude_invoke import build_argv


def test_vanilla_argv():
    argv = build_argv(model="claude-sonnet-4-6", plugin_dir=None, prompt="hello")
    assert argv == ["claude", "-p", "--model", "claude-sonnet-4-6", "hello"]


def test_with_plugin_argv(tmp_path: Path):
    argv = build_argv(model="claude-sonnet-4-6", plugin_dir=tmp_path, prompt="hello")
    assert argv == [
        "claude", "-p",
        "--model", "claude-sonnet-4-6",
        "--plugin-dir", str(tmp_path),
        "hello",
    ]
