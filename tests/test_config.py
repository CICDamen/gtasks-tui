"""Tests for config.py — loading and merging configuration."""

import json
from unittest.mock import patch

from tasks_tui.config import DEFAULTS, get_project_config, load_config


class TestLoadConfig:
    def test_returns_defaults_when_file_absent(self, tmp_path):
        missing = tmp_path / "config.json"
        with patch("tasks_tui.config.CONFIG_PATH", missing):
            result = load_config()
        assert result == DEFAULTS

    def test_loads_valid_file(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"sync": {"enabled": False}, "sources": {"beads": False}}))
        with patch("tasks_tui.config.CONFIG_PATH", f):
            result = load_config()
        assert result["sync"]["enabled"] is False
        assert result["sources"]["beads"] is False

    def test_merges_missing_keys_with_defaults(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"sync": {"enabled": False}}))
        with patch("tasks_tui.config.CONFIG_PATH", f):
            result = load_config()
        assert result["sync"]["enabled"] is False
        assert result["sync"]["auto_sync_on_start"] is True  # default preserved
        assert result["sources"]["google_tasks"] is True  # whole section defaults

    def test_returns_defaults_on_corrupt_json(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text("not json {{{")
        with patch("tasks_tui.config.CONFIG_PATH", f):
            result = load_config()
        assert result == DEFAULTS

    def test_returns_defaults_when_file_is_not_dict(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text("[1, 2, 3]")
        with patch("tasks_tui.config.CONFIG_PATH", f):
            result = load_config()
        assert result == DEFAULTS

    def test_returns_defaults_when_section_is_not_dict(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"sync": "yes please"}))
        with patch("tasks_tui.config.CONFIG_PATH", f):
            result = load_config()
        assert result["sync"] == DEFAULTS["sync"]

    def test_does_not_mutate_defaults(self, tmp_path):
        missing = tmp_path / "config.json"
        with patch("tasks_tui.config.CONFIG_PATH", missing):
            result = load_config()
        result["sync"]["enabled"] = False
        # DEFAULTS should be unchanged
        assert DEFAULTS["sync"]["enabled"] is True


class TestGetProjectConfig:
    def test_returns_defaults_for_missing_project(self):
        result = get_project_config("myapp", {})
        assert result == {"sync": True, "visible": True, "label": "myapp"}

    def test_overrides_sync(self):
        config = {"projects": {"myapp": {"sync": False}}}
        result = get_project_config("myapp", config)
        assert result["sync"] is False
        assert result["visible"] is True
        assert result["label"] == "myapp"

    def test_overrides_visible(self):
        config = {"projects": {"myapp": {"visible": False}}}
        result = get_project_config("myapp", config)
        assert result["visible"] is False
        assert result["sync"] is True

    def test_overrides_label(self):
        config = {"projects": {"myapp": {"label": "my-project"}}}
        result = get_project_config("myapp", config)
        assert result["label"] == "my-project"

    def test_uses_name_as_label_when_label_is_none(self):
        config = {"projects": {"myapp": {"label": None}}}
        result = get_project_config("myapp", config)
        assert result["label"] == "myapp"

    def test_unknown_project_gets_defaults(self):
        config = {"projects": {"other": {"sync": False}}}
        result = get_project_config("myapp", config)
        assert result == {"sync": True, "visible": True, "label": "myapp"}

    def test_empty_projects_section(self):
        config = {"projects": {}}
        result = get_project_config("myapp", config)
        assert result == {"sync": True, "visible": True, "label": "myapp"}
