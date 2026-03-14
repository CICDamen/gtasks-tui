# Per-Project Configuration for tasks-tui

**Date:** 2026-03-14
**Status:** Brainstorm — not yet planned

---

## What We're Building

Extend the configuration system to support per-project (per-beads-workspace) settings:
each discovered beads workspace can be individually toggled for **sync**, **visibility in the TUI**,
and given a **default label**. A redesigned `p` config screen exposes both global settings
and the per-project controls in a single scrollable view.

---

## Why This Approach

The current config is all-or-nothing: beads is either enabled or disabled globally, and every
discovered workspace syncs to Google Tasks. In practice you may have personal projects you don't
want cluttering your task view, or client workspaces you want to display but not sync.

The scrollable-rows approach fits the existing Textual modal pattern (single screen, save on
confirm) and requires no new navigation concepts. Project rows are dynamically populated from
`discover_beads_workspaces()` at screen open, so new workspaces appear automatically.

---

## Config Schema Changes

Add a top-level `projects` dict to `config.json`, keyed by workspace name (directory basename).
Only workspaces with non-default settings need entries — missing projects fall back to defaults.

```json
{
  "sync": {
    "enabled": true,
    "auto_sync_on_start": true
  },
  "sources": {
    "google_tasks": true,
    "beads": true,
    "beads_search_root": "~/Code"
  },
  "projects": {
    "impellam": {
      "sync": true,
      "visible": true,
      "label": "impellam"
    },
    "client-work": {
      "sync": false,
      "visible": true,
      "label": "client"
    }
  }
}
```

**Default values per project** (applied when key is absent):
- `sync`: `true`
- `visible`: `true`
- `label`: workspace name (directory basename)

---

## Label Resolution Order

When deciding what `[label]` to show for a beads issue:

1. Per-issue override in `~/.config/tasks-tui/labels.json` (set via `e` edit screen)
2. Per-project default label from `config.projects[workspace_name].label`
3. Workspace name (directory basename)

This keeps fine-grained per-issue control intact while adding a sensible project-level default.

---

## TUI — Updated Setup Screen (`p`)

The `SetupScreen` (opened via `p` or on first run) gets a new **PROJECTS** section below the
global toggles. Rendered as a scrollable list of rows, one per discovered workspace.

```
┌─────────────────────────────────────────────────┐
│ Configuration                                   │
├─────────────────────────────────────────────────┤
│ GLOBAL SETTINGS                                 │
│ Google Tasks           ▐██ ON                   │
│ Beads                  ▐██ ON                   │
│ Enable sync            ▐██ ON                   │
│ Auto-sync on start     ▐██ ON                   │
├─────────────────────────────────────────────────┤
│ PROJECTS               sync  visible  label     │
│ impellam                ●      ●      [impellam]│
│ client-work             ○      ●      [client  ]│
│ personal                ●      ○      [personal]│
├─────────────────────────────────────────────────┤
│                    [ Save ]                     │
│             esc  cancel                         │
└─────────────────────────────────────────────────┘
```

Each project row: project name (static) + Switch for sync + Switch for visible + Input for label.

**First-run setup screen** keeps only the global section (no projects) to avoid overwhelming
new users. After first launch, `p` opens the full screen including projects.

---

## Code Changes

**`config.py`**
- Add `"projects": {}` to `DEFAULTS`
- Add `get_project_config(name: str, config: dict) -> dict` helper that returns merged
  per-project settings with defaults
- `_deep_copy` needs to handle the nested `projects` dict

**`beads_api.py`**
- `get_beads_label(issue_id, default)` checks per-project config before falling back to
  `labels.json` then workspace name
- `list_beads_issues()` in app.py filters by `visible` config for each workspace

**`sync.py`**
- `SyncEngine.run()` skips workspaces where `projects[name].sync == false`

**`app.py`**
- `_load_tasks()` passes per-project `visible` flag to workspace filtering
- `SetupScreen` gains a project rows section; discovers workspaces in `on_mount`
- `SetupScreen.compose()` conditionally shows projects section based on `first_run` flag

---

## Resolved Questions

- **Sync vs. visible are independent.** A hidden project (`visible=false`) can still sync to
  Google Tasks silently. Useful to keep Google Tasks up-to-date without cluttering the TUI view.

- **`beads_search_root` goes in the TUI screen.** Add it as a text `Input` in the GLOBAL section
  so it's discoverable without editing JSON directly.

- **Workspace discovery on config screen open uses a background worker.** Show
  "Discovering projects…" while the scan runs, then populate the project rows. Prevents the
  screen from blocking on open.

---

## Out of Scope

- Bidirectional sync or direction control
- Mapping a workspace to a specific Google Tasks list (stays one-per-project, auto-named)
- Multiple Google accounts
- Adding non-beads trackers (Linear, GitHub Issues, etc.)
