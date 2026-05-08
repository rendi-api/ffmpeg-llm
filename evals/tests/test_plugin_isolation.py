from unittest.mock import patch

import pytest

from runner.plugin_isolation import (
    PluginSnapshot,
    isolated_user_plugins,
    snapshot_enabled_user_plugins,
)


SAMPLE_PLUGIN_LIST = [
    {"id": "claude-hud@claude-hud", "scope": "user", "enabled": True, "version": "0.1.0"},
    {"id": "github@official", "scope": "project", "enabled": False, "version": "1.0"},
    {"id": "superpowers@official", "scope": "project", "enabled": True, "version": "5.0"},
    {"id": "superpowers@official", "scope": "user", "enabled": True, "version": "5.1"},
    {"id": "disabled-tool@x", "scope": "user", "enabled": False, "version": "0.1"},
]


def test_snapshot_filters_to_enabled_user_only():
    snap = snapshot_enabled_user_plugins(plugins=SAMPLE_PLUGIN_LIST)
    assert len(snap) == 2
    ids = {p.id for p in snap}
    assert ids == {"claude-hud@claude-hud", "superpowers@official"}
    assert all(p.scope == "user" for p in snap)


def test_snapshot_empty_when_no_user_enabled():
    snap = snapshot_enabled_user_plugins(plugins=[
        {"id": "x@y", "scope": "project", "enabled": True, "version": "1"},
    ])
    assert snap == []


def test_isolated_context_restores_on_exception():
    """Even if the body raises, restore_plugins must be called."""
    snapshot_value = [PluginSnapshot(id="x@y", scope="user")]

    with patch("runner.plugin_isolation.snapshot_enabled_user_plugins",
               return_value=snapshot_value), \
         patch("runner.plugin_isolation.disable_plugins") as disable, \
         patch("runner.plugin_isolation.restore_plugins", return_value=[]) as restore:

        with pytest.raises(RuntimeError, match="boom"):
            with isolated_user_plugins() as snap:
                assert snap == snapshot_value
                raise RuntimeError("boom")

        disable.assert_called_once()
        restore.assert_called_once_with(snapshot_value)


def test_isolated_context_skips_disable_when_nothing_enabled():
    """If snapshot is empty, don't bother calling disable/restore."""
    with patch("runner.plugin_isolation.snapshot_enabled_user_plugins", return_value=[]), \
         patch("runner.plugin_isolation.disable_plugins") as disable, \
         patch("runner.plugin_isolation.restore_plugins") as restore:

        with isolated_user_plugins() as snap:
            assert snap == []

        disable.assert_not_called()
        restore.assert_not_called()
