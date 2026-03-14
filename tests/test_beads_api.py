"""Tests for beads_api — dataclass properties and CLI wrappers."""

from unittest.mock import MagicMock, patch

import pytest

from tasks_tui.beads_api import BeadsIssue, create_beads_child_issue


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
