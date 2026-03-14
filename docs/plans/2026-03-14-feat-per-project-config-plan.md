---
title: "feat: Per-project configuration for beads workspaces"
type: feat
status: active
date: 2026-03-14
brainstorm: docs/brainstorms/2026-03-14-per-project-config-brainstorm.md
---

# feat: Per-project configuration for beads workspaces

## Overview

Extend the config system and setup screen to support per-workspace settings: each discovered beads project can independently toggle **sync** (to Google Tasks), **visibility** (show in TUI), and set a **default label**. A redesigned `p` config screen exposes global + per-project settings in one scrollable view, with workspace discovery running in a background worker.

## Problem Statement

The current config is all-or-nothing: beads is either fully enabled or disabled globally, and every workspace syncs to Google Tasks. In practice some workspaces should be hidden from the task view or excluded from sync without disabling beads entirely.

## Proposed Solution

1. Add `projects` section to `config.json` — a dict keyed by workspace name with per-project settings.
2. Extend `SetupScreen` with a PROJECTS section listing all discovered workspaces, each with sync/visible toggles and a label input.
3. Filter beads issues and sync runs using per-project config.
4. Expose `beads_search_root` as a text input in the GLOBAL section of the setup screen.

## Config Schema

```json
{
  "sync": { "enabled": true, "auto_sync_on_start": true },
  "sources": {
    "google_tasks": true,
    "beads": true,
    "beads_search_root": "~/Code"
  },
  "projects": {
    "impellam": { "sync": true, "visible": true, "label": "impellam" },
    "client-work": { "sync": false, "visible": true, "label": "client" }
  }
}
```

**Per-project defaults** (applied when a workspace has no entry or a key is missing):
- `sync`: `true`
- `visible`: `true`
- `label`: workspace name (directory basename)

Sync and visible are **independent** — a hidden project can still sync in the background.

## Label Resolution Order

1. Per-issue override in `~/.config/tasks-tui/labels.json`
2. Per-project default label from `config.projects[workspace_name].label`
3. Workspace name (directory basename)

The existing `get_beads_label(issue_id, default)` already takes a `default` arg — pass the per-project label as `default` instead of `issue.project`.

## Technical Approach

### `config.py`

- Add `"projects": {}` to `DEFAULTS` so the existing `load_config` merge logic preserves the key.
- Add helper:
  ```python
  def get_project_config(name: str, config: dict) -> dict:
      """Return per-project settings with defaults applied for missing keys."""
      PROJECT_DEFAULTS = {"sync": True, "visible": True, "label": name}
      return {**PROJECT_DEFAULTS, **config.get("projects", {}).get(name, {})}
  ```

### `sync.py`

- Pass `config` into `SyncEngine.__init__` (or load it internally).
- In `run()`, skip workspaces where `get_project_config(project_name, self._config)["sync"]` is `False`:
  ```python
  if not get_project_config(project_name, self._config)["sync"]:
      _progress(f"Skipping {project_name} (sync disabled)")
      continue
  ```

### `app.py` — `_load_tasks`

After loading all beads issues, filter by per-project `visible`:
```python
self._beads_issues = [
    i for i in list_beads_issues()
    if get_project_config(i.project, self._config)["visible"]
]
```

### `app.py` — `BeadsItem.compose`

Change `get_beads_label(self.issue.id, self.issue.project)` to:
```python
project_label = get_project_config(self.issue.project, app_config)["label"]
beads_label = get_beads_label(self.issue.id, project_label)
```

`BeadsItem` needs access to the app config — pass it in `__init__` as `project_label: str` (resolved at render time in `_render_tasks`).

### `app.py` — `SetupScreen`

```
┌─────────────────────────────────────────────────┐
│ Configuration                                   │
├─────────────────────────────────────────────────┤
│ GLOBAL SETTINGS                                 │
│ Google Tasks           ▐██ ON                   │
│ Beads                  ▐██ ON                   │
│ Enable sync            ▐██ ON                   │
│ Auto-sync on start     ▐██ ON                   │
│ Search root  [~/Code              ]             │
├─────────────────────────────────────────────────┤
│ PROJECTS               sync  visible  label     │
│ Discovering projects…                           │
│  (populated by background worker)               │
│ impellam                ●      ●    [impellam]  │
│ client-work             ○      ●    [client   ] │
├─────────────────────────────────────────────────┤
│                    [ Save ]                     │
└─────────────────────────────────────────────────┘
```

Key changes:
- Add `Input(value=beads_search_root, id="sw-search-root")` to GLOBAL section.
- Add `Static("Discovering projects…", id="projects-loading")` placeholder.
- On `on_mount`, fire `@work(thread=True)` worker that calls `discover_beads_workspaces()`.
- Worker calls `call_from_thread(self._populate_projects, workspaces)`.
- `_populate_projects` removes the loading placeholder and mounts a `ProjectRow` per workspace.
- `ProjectRow` is a new `Widget` subclass with `Switch(sync)` + `Switch(visible)` + `Input(label)`.
- On save, collect project configs by iterating `self.query(ProjectRow)`.
- First-run screen (`first_run=True`) still shows global-only — no projects section.

### CSS additions (inline in `GTasksApp.CSS`)

```css
.project-row {
    height: 3;
    align: left middle;
    margin-bottom: 0;
}
.project-name {
    width: 14;
    color: $text;
}
.project-sync-label, .project-visible-label {
    width: 8;
    color: $text-muted;
    text-align: center;
}
.project-label-input {
    width: 1fr;
}
#projects-loading {
    color: $text-muted;
    margin: 1 0;
}
```

## Acceptance Criteria

- [ ] `config.json` saves and loads `projects` dict correctly; missing projects default to sync=true, visible=true, label=workspace_name
- [ ] Beads issues from a workspace with `visible=false` do not appear in the TUI task list
- [ ] Beads issues from a workspace with `sync=false` are skipped during sync (no Google Task created/updated)
- [ ] Sync and visible are independent — hidden workspace can still sync
- [ ] `p` config screen shows all discovered workspaces with correct initial values from config
- [ ] Toggling switches and editing label fields persists to `config.json` on Save
- [ ] `beads_search_root` is editable in the GLOBAL section of the setup screen
- [ ] Config screen shows "Discovering projects…" while workspace discovery runs; rows appear when done
- [ ] Per-project label default is used as fallback in `BeadsItem` before falling back to workspace name
- [ ] Per-issue label override (`labels.json`) still wins over per-project default
- [ ] First-run screen is unchanged (global settings only)
- [ ] All existing tests pass; new tests cover per-project filtering

## Dependencies & Risks

- **`load_config` merge depth**: the existing `{**section_defaults, **user_section}` merge is one level deep. `projects` is a flat dict of workspace_name → settings dict — this works as-is once `"projects": {}` is added to `DEFAULTS`.
- **`discover_beads_workspaces()` performance**: runs `bd list` per workspace; wrapping in `@work(thread=True)` prevents UI blocking.
- **`SyncEngine` needs config**: currently loaded inside `app.py` action and `_sync_worker`. Pass config at construction: `SyncEngine(config=self._config).run(...)`.

## Files to Change

| File | Change |
|---|---|
| `src/tasks_tui/config.py` | Add `projects: {}` to DEFAULTS; add `get_project_config()` |
| `src/tasks_tui/sync.py` | Accept config in `__init__`; skip workspaces with `sync=false` |
| `src/tasks_tui/app.py` | Filter issues by `visible`; pass `project_label` to `BeadsItem`; extend `SetupScreen`; add `ProjectRow` widget; add CSS |
| `tests/test_config.py` | Tests for `get_project_config` with defaults and overrides |
| `tests/test_sync.py` | Test workspace skipped when `sync=false` in config |
| `tests/test_app.py` | Test issues filtered by `visible=false`; test label resolution order |
