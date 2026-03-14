---
status: complete
priority: p2
issue_id: "003"
tags: [code-review, data-integrity, ui]
dependencies: []
---

# Saving config before workspace discovery completes wipes all project configs

## Problem Statement

`SetupScreen` starts workspace discovery in a background worker (`@work(thread=True) _discover_projects`). The Save button is available immediately. If the user presses Save before the worker finishes (or if discovery returns no workspaces), `self.query(ProjectRow)` returns an empty list, `projects` is `{}`, and the entire `config.projects` section is overwritten with an empty dict — silently deleting all per-project settings.

This is a **data loss** scenario: the user's sync/visible/label overrides are permanently erased without warning.

## Findings

- **Location:** `src/tasks_tui/app.py:1398-1414` (`SetupScreen.on_button_pressed`)
- `projects: dict[str, dict] = {}` is built by iterating `self.query(ProjectRow)`
- If no rows are mounted yet, `projects = {}` overwrites the previous config
- The previous config is available in `self._initial["projects"]` but is not used as a fallback

## Proposed Solutions

### Option A — Merge with `self._initial["projects"]` as base (recommended)
```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "setup-save":
        # Start from existing config as base; override with any mounted rows
        projects = dict(self._initial.get("projects", {}))
        for row in self.query(ProjectRow):
            projects[row.project_name] = row.get_values()
        self.dismiss({...})
```
**Pros:** No data loss if discovery hasn't finished; existing rows still update their values.
**Cons:** None — this is strictly safer.
**Effort:** Tiny | **Risk:** Low

### Option B — Disable Save button until discovery completes
Set `#setup-save` to `disabled=True` in `compose`, enable it in `_populate_projects`.
**Pros:** Prevents partial save entirely.
**Cons:** UX degradation — user can't save global settings while projects load.
**Effort:** Small | **Risk:** Low

### Option C — Show a warning notification and keep existing config
If no ProjectRows found and `self._initial["projects"]` is non-empty, warn: "Projects still loading — existing project settings preserved."
**Pros:** Communicates state without blocking.
**Cons:** Still allows partial save of global settings.
**Effort:** Small | **Risk:** Low

## Recommended Action

Option A — cheapest fix, no UX impact, correct behavior.

## Acceptance Criteria

- [ ] Saving before discovery completes does not overwrite existing `config.projects`
- [ ] Saving after discovery completes still persists the current row values
- [ ] Add a test: `test_setup_screen_save_before_discovery_preserves_existing_projects`

## Work Log

- 2026-03-14: Identified during code review of per-project config feature
