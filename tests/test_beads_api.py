"""Tests for beads_api — dataclass properties and CLI wrappers."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tasks_tui.beads_api import (
    BeadsIssue,
    create_beads_child_issue,
    discover_beads_workspaces,
    list_closed_mapped_issues,
)


def _issue(id="PROJ-001", **kwargs) -> BeadsIssue:
    defaults = dict(
        title="A task",
        status="open",
        priority=2,
        due_at="",
        description="",
        project="myapp",
        db_path="/fake/.beads/beads.db",
    )
    defaults.update(kwargs)
    return BeadsIssue(id=id, **defaults)


# ---------------------------------------------------------------------------
# parent_id property
# ---------------------------------------------------------------------------


class TestParentId:
    def test_top_level_has_no_parent(self):
        assert _issue("PROJ-001").parent_id is None

    def test_child_returns_parent(self):
        assert _issue("PROJ-001.1").parent_id == "PROJ-001"

    def test_grandchild_returns_direct_parent(self):
        assert _issue("PROJ-001.1.1").parent_id == "PROJ-001.1"

    def test_deep_nesting(self):
        assert _issue("PROJ-001.1.2.3").parent_id == "PROJ-001.1.2"


# ---------------------------------------------------------------------------
# depth property
# ---------------------------------------------------------------------------


class TestDepth:
    def test_top_level_is_zero(self):
        assert _issue("PROJ-001").depth == 0

    def test_child_is_one(self):
        assert _issue("PROJ-001.1").depth == 1

    def test_grandchild_is_two(self):
        assert _issue("PROJ-001.1.1").depth == 2


# ---------------------------------------------------------------------------
# create_beads_child_issue
# ---------------------------------------------------------------------------


class TestCreateBeadsChildIssue:
    def _parent(self) -> BeadsIssue:
        return _issue("PROJ-001", db_path="/work/.beads/beads.db")

    def test_calls_bd_create_with_parent_flag(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            result = create_beads_child_issue(self._parent(), "Child task")
        cmd = mock_run.call_args[0][0]
        assert "bd" in cmd
        assert "create" in cmd
        assert "--parent" in cmd
        assert "PROJ-001" in cmd
        assert "--db" in cmd
        assert "/work/.beads/beads.db" in cmd
        assert "Child task" in cmd
        assert "--silent" in cmd

    def test_returns_new_issue_id(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result):
            result = create_beads_child_issue(self._parent(), "Child task")
        assert result == "PROJ-001.1"

    def test_includes_description_when_provided(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            create_beads_child_issue(self._parent(), "Child", description="Some notes")
        cmd = mock_run.call_args[0][0]
        assert "--description" in cmd
        assert "Some notes" in cmd

    def test_omits_description_when_empty(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            create_beads_child_issue(self._parent(), "Child", description="")
        cmd = mock_run.call_args[0][0]
        assert "--description" not in cmd

    def test_includes_due_when_provided(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            create_beads_child_issue(self._parent(), "Child", due="2026-04-01T00:00:00.000Z")
        cmd = mock_run.call_args[0][0]
        assert "--due" in cmd

    def test_omits_due_when_empty(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            create_beads_child_issue(self._parent(), "Child", due="")
        cmd = mock_run.call_args[0][0]
        assert "--due" not in cmd

    def test_omits_priority_when_default(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            create_beads_child_issue(self._parent(), "Child", priority=2)
        cmd = mock_run.call_args[0][0]
        assert "--priority" not in cmd

    def test_includes_priority_when_non_default(self):
        mock_result = MagicMock()
        mock_result.stdout = "PROJ-001.1\n"
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            create_beads_child_issue(self._parent(), "Child", priority=0)
        cmd = mock_run.call_args[0][0]
        assert "--priority" in cmd
        assert "0" in cmd


# ---------------------------------------------------------------------------
# discover_beads_workspaces — Dolt backend detection
# ---------------------------------------------------------------------------


class TestDiscoverBeadsWorkspaces:
    def test_discovers_sqlite_workspace(self, tmp_path):
        beads_dir = tmp_path / "myproject" / ".beads"
        beads_dir.mkdir(parents=True)
        db = beads_dir / "beads.db"
        db.touch()

        with patch("tasks_tui.beads_api._beads_search_root", return_value=tmp_path), \
             patch("tasks_tui.beads_api.REGISTRY_PATH", tmp_path / "no-registry.json"):
            result = discover_beads_workspaces()

        assert str(tmp_path / "myproject") in result
        assert result[str(tmp_path / "myproject")] == str(db)

    def test_discovers_dolt_workspace(self, tmp_path):
        dolt_dir = tmp_path / "doltproject" / ".beads" / "dolt"
        dolt_dir.mkdir(parents=True)
        marker = dolt_dir / ".bd-dolt-ok"
        marker.touch()

        with patch("tasks_tui.beads_api._beads_search_root", return_value=tmp_path), \
             patch("tasks_tui.beads_api.REGISTRY_PATH", tmp_path / "no-registry.json"):
            result = discover_beads_workspaces()

        assert str(tmp_path / "doltproject") in result
        assert result[str(tmp_path / "doltproject")] == str(dolt_dir)

    def test_sqlite_wins_over_dolt_when_both_present(self, tmp_path):
        """Registry SQLite entry takes precedence; Dolt scan skips registered workspaces."""
        ws = tmp_path / "hybrid"
        beads_dir = ws / ".beads"
        dolt_dir = beads_dir / "dolt"
        dolt_dir.mkdir(parents=True)
        (dolt_dir / ".bd-dolt-ok").touch()
        db = beads_dir / "beads.db"
        db.touch()

        with patch("tasks_tui.beads_api._beads_search_root", return_value=tmp_path), \
             patch("tasks_tui.beads_api.REGISTRY_PATH", tmp_path / "no-registry.json"):
            result = discover_beads_workspaces()

        # SQLite db is found first; Dolt scan skips because workspace already registered
        assert str(ws) in result
        assert result[str(ws)] == str(db)


# ---------------------------------------------------------------------------
# list_closed_mapped_issues — uses CLI, not sqlite3
# ---------------------------------------------------------------------------


class TestListClosedMappedIssues:
    CLOSED_ITEMS = [
        {
            "id": "PROJ-001",
            "title": "Done task",
            "status": "closed",
            "priority": 2,
            "due_at": "",
            "description": "desc",
        },
        {
            "id": "PROJ-002",
            "title": "Other task",
            "status": "closed",
            "priority": 1,
            "due_at": "",
            "description": "",
        },
    ]

    def _mock_run(self, items=None):
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(items if items is not None else self.CLOSED_ITEMS)
        return result

    def test_returns_matching_issues(self, tmp_path):
        db = tmp_path / "proj" / ".beads" / "beads.db"
        db.parent.mkdir(parents=True)
        db.touch()

        with patch("tasks_tui.beads_api.subprocess.run", return_value=self._mock_run()):
            issues = list_closed_mapped_issues({"PROJ-001"}, str(db))

        assert len(issues) == 1
        assert issues[0].id == "PROJ-001"

    def test_filters_out_non_matching_ids(self, tmp_path):
        db = tmp_path / "proj" / ".beads" / "beads.db"
        db.parent.mkdir(parents=True)
        db.touch()

        with patch("tasks_tui.beads_api.subprocess.run", return_value=self._mock_run()):
            issues = list_closed_mapped_issues({"PROJ-001", "PROJ-002"}, str(db))

        assert {i.id for i in issues} == {"PROJ-001", "PROJ-002"}

    def test_returns_empty_when_beads_ids_empty(self, tmp_path):
        db = tmp_path / "proj" / ".beads" / "beads.db"
        db.parent.mkdir(parents=True)
        db.touch()
        issues = list_closed_mapped_issues(set(), str(db))
        assert issues == []

    def test_passes_db_path_to_cli(self, tmp_path):
        db = tmp_path / "dolt"
        db.mkdir()

        mock_result = self._mock_run([])
        with patch("tasks_tui.beads_api.subprocess.run", return_value=mock_result) as mock_run:
            list_closed_mapped_issues({"PROJ-001"}, str(db))

        cmd = mock_run.call_args[0][0]
        assert "--db" in cmd
        assert str(db) in cmd
        assert "--status=closed" in cmd or "--status" in cmd

    def test_returns_empty_on_cli_error(self, tmp_path):
        db = tmp_path / "proj" / ".beads" / "beads.db"
        db.parent.mkdir(parents=True)
        db.touch()

        bad_result = MagicMock()
        bad_result.returncode = 1
        bad_result.stdout = ""
        with patch("tasks_tui.beads_api.subprocess.run", return_value=bad_result):
            issues = list_closed_mapped_issues({"PROJ-001"}, str(db))
        assert issues == []
