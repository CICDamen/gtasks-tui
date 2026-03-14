# tasks-tui

A terminal UI for managing tasks across Google Tasks and [Beads](https://github.com/steveyegge/beads) issue trackers, with automatic bidirectional sync.

## Features

- View and manage Google Tasks in the terminal
- Browse Beads issues from all local workspaces alongside your tasks
- Label column with `[label]` tagging for both sources
- Due date column with urgency color coding
- Bidirectional sync: Beads issues push to Google Tasks automatically
- Configurable: enable/disable individual sources and sync

## Prerequisites

- [`gws`](https://github.com/googleworkspace/cli) — Google Workspace CLI, authenticated with your account
- [`bd`](https://github.com/steveyegge/beads) — Beads CLI (optional, required for Beads integration)

## Installation

```bash
uv sync
uv run tasks
```

Or install it globally:

```bash
uv tool install .
tasks
```

## Keybindings

| Key | Action |
|-----|--------|
| `n` | New task |
| `s` | New subtask (under selected task or Beads issue) |
| `e` | Edit selected task |
| `enter` | Open task detail view |
| `space` | Toggle complete / uncomplete |
| `d` | Delete task |
| `ctrl+s` | Sync Beads → Google Tasks |
| `ctrl+q` / `q` | Quit |

## Labels

Labels appear in the `[label]` column to the left of the task title.

**Google Tasks** — stored as a `[label]` prefix in the task title itself, e.g. `[work] Buy milk`. When creating or editing a task, enter the label in the label field; the TUI stores and parses it automatically.

**Beads** — the project name is used as the default label. You can override it per-issue via the edit screen (`e`). Labels are stored in `~/.config/tasks-tui/labels.json` and do not modify the Beads issue itself.

## Beads Sync

When `ctrl+s` is pressed (or on startup), the sync engine pushes all active Beads issues to Google Tasks:

- **New issue** → creates a Google Task in a dedicated task list named after the project
- **Updated issue** → overwrites the Google Task (Beads is source of truth)
- **Closed / deleted issue** → marks the Google Task as completed and removes the mapping

The sync mapping lives at `~/.beads/gtasks-sync.json`.

### Workspace discovery

Beads workspaces are discovered from two sources:

1. `~/.beads/registry.json` — workspaces registered with the Beads daemon
2. `~/Code/*/.beads/beads.db` — directory scan for SQLite and Dolt-backed workspaces not in the registry

## Configuration

Create `~/.config/tasks-tui/config.json` to customise behaviour. All keys are optional and fall back to their defaults.

```json
{
  "sync": {
    "enabled": true,
    "auto_sync_on_start": true
  },
  "sources": {
    "google_tasks": true,
    "beads": true
  }
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `sync.enabled` | `true` | Allow `ctrl+s` to trigger sync. Set to `false` to disable sync entirely. |
| `sync.auto_sync_on_start` | `true` | Run a sync automatically when the app starts. |
| `sources.google_tasks` | `true` | Load and display Google Tasks. |
| `sources.beads` | `true` | Load and display Beads issues from local workspaces. |
| `sources.beads_search_root` | `"~/Code"` | Directory scanned for `*/.beads/beads.db` workspaces not in the registry. Set to your projects root. |

**Example — Beads only, no sync:**

```json
{
  "sources": { "google_tasks": false },
  "sync": { "enabled": false }
}
```

**Example — Google Tasks only:**

```json
{
  "sources": { "beads": false },
  "sync": { "enabled": false }
}
```
