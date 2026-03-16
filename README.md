# gtasks-tui

A terminal UI for viewing and managing [Google Tasks](https://tasks.google.com/tasks/).

## Prerequisites

- [`gws`](https://github.com/googleworkspace/cli) — Google Workspace CLI, authenticated with your account

## Installation

```bash
uv sync
uv run gtasks
```

Or install globally:

```bash
uv tool install .
gtasks
```

## Keybindings

| Key | Action |
|-----|--------|
| `n` | New task |
| `s` | New subtask |
| `enter` | Open task detail |
| `e` | Edit selected task |
| `space` | Toggle complete / uncomplete |
| `d` | Delete task |
| `f` | Filter completed tasks by date |
| `r` | Refresh |
| `ctrl+q` / `q` | Quit |

## Labels

Labels appear as `[label]` to the left of the task title. When creating or editing a task, enter the label in the label field — the TUI stores it as a `[label]` prefix in the task title (e.g. `[work] Buy milk`) and parses it back automatically.

## Development

```bash
uv run textual run --dev gtasks_tui.app:GTasksApp  # CSS hot-reload
uv run textual console                              # Textual devtools
```
