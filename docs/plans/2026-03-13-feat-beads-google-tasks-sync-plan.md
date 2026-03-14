---
title: "feat: Beads ↔ Google Tasks Two-Way Sync"
type: feat
status: completed
date: 2026-03-13
brainstorm: docs/brainstorms/2026-03-13-beads-google-tasks-sync-brainstorm.md
---

# feat: Beads ↔ Google Tasks Two-Way Sync

## Overview

Add a two-way sync layer between beads issues and Google Tasks to the `tasks-tui` app. Beads issues are pushed to Google Tasks (one-way for new items); both systems stay in sync for existing linked items. Beads is always the source of truth. Sync runs on startup and on demand via a keybinding.

---

## Problem Statement

Currently the TUI displays beads issues and Google Tasks side by side but they are completely independent. Completing something in one place requires manually updating the other. Users checking tasks on mobile (Google Tasks) see a stale, disconnected view from their beads workflow.

---

## Proposed Solution

Introduce a `sync.py` module containing the sync engine and mapping file I/O. Sync is triggered at TUI startup and via a manual `ctrl+s` keybinding. A `~/.beads/gtasks-sync.json` file tracks the beads ↔ Google Tasks relationships and the Google Tasks list ID per beads project.

---

## Key Decisions (from brainstorm + SpecFlow)

| Decision | Choice | Rationale |
|---|---|---|
| Sync trigger | Startup + `ctrl+s` keybinding | `s` stays as subtask; `ctrl+s` is unambiguous |
| Conflict resolution | Beads always wins | Beads is primary workflow; Google Tasks is mobile view |
| New items direction | Beads → Google Tasks only | Don't pollute beads with mobile-created tasks |
| Tasklist per project | One Google Tasks list per beads workspace | Mirrors beads project structure |
| Link tracking | `~/.beads/gtasks-sync.json` with `projects` + `mappings` sections | Clean separation; avoids name-match fragility |
| Closed issue detection | Separate SQLite query for mapped-but-closed/deleted issues | `list_beads_issues()` filters them out; sync needs them |
| Background execution | Textual `@work(thread=True)` worker | Prevents blocking the event loop |
| Mapping file writes | Atomic (write to `.tmp`, then `os.replace`) | Prevents corruption on partial failure |

---

## Mapping File Schema

**`~/.beads/gtasks-sync.json`**

```json
{
  "projects": {
    "/Users/casper/Code/myapp": {
      "tasklist_id": "MDg4...",
      "tasklist_name": "myapp"
    }
  },
  "mappings": [
    {
      "beads_id": "MYAPP-001",
      "beads_db_path": "/Users/casper/Code/myapp/.beads/beads.db",
      "gtask_id": "abc123xyz",
      "gtask_list_id": "MDg4...",
      "last_synced_at": "2026-03-13T10:00:00Z"
    }
  ]
}
```

`projects` stores the authoritative `tasklist_id` per workspace path (avoids name-lookup ambiguity since Google Tasks allows duplicate list names). `mappings` stores per-issue link pairs and the last sync timestamp (for future delta-sync optimisation; not used for conflict resolution in this phase).

---

## Field Mapping

| Beads field | Google Tasks field | Conversion |
|---|---|---|
| `title` | `title` | Direct |
| `status` ∈ {open, in_progress, blocked, deferred} | `status: "needsAction"` | Any active beads status → not completed |
| `status: "closed"` | `status: "completed"` | Close in beads → complete in Google |
| `due_at` (ISO datetime or `""`) | `due` (ISO date or absent) | Strip time component; `""` → omit field |
| Google Tasks `due` → beads `due_at` | Append `T00:00:00.000Z` | UTC midnight; only written when beads wins |
| `description` (may be `None`) | `notes` | Coerce `None` → `""` |

---

## Technical Approach

### New file: `src/tasks_tui/sync.py`

Responsibilities:
- Load and save `~/.beads/gtasks-sync.json` (with atomic write)
- Provide `SyncEngine` class with a single `run()` method
- Emit progress callbacks so the TUI can update its status indicator

### Changes to `src/tasks_tui/tasks_api.py`

Add tasklist management functions:
- `list_tasklists() → list[dict]` — calls `gws tasks tasklists list`
- `create_tasklist(name: str) → dict` — calls `gws tasks tasklists insert --json {"title": name}`

### Changes to `src/tasks_tui/beads_api.py`

Add a query for closed/deleted issues that have active mapping entries:
- `list_closed_mapped_issues(beads_ids: set[str], db_path: str) → list[BeadsIssue]`
  - Queries `WHERE id IN (...) AND (status IN ('closed', 'tombstone') OR deleted_at IS NOT NULL)`

### Changes to `src/tasks_tui/app.py`

- Add `ctrl+s` → `action_sync` binding (replaces nothing; `s` remains as subtask)
- On `on_mount`: call sync worker before or concurrently with `_load_tasks()`
- Add a `sync_status` `Static` widget to the layout showing last sync time or "Syncing…"
- `action_sync()` starts a new `@work(thread=True)` worker if none is running

---

## Implementation Phases

### Phase 1: Infrastructure

**Goal:** Mapping file I/O, tasklist management, closed-issue query. No sync logic yet.

**Tasks:**

- [x] Add `list_tasklists()` to `tasks_api.py` using `gws tasks tasklists list`
- [x] Add `create_tasklist(name)` to `tasks_api.py` using `gws tasks tasklists insert`
- [x] Add `list_closed_mapped_issues(beads_ids, db_path)` to `beads_api.py`
- [x] Create `src/tasks_tui/sync.py` with:
  - `MAPPING_FILE = Path.home() / ".beads" / "gtasks-sync.json"`
  - `load_mapping() → dict` (returns `{"projects": {}, "mappings": []}` if file absent or corrupt)
  - `save_mapping(mapping: dict)` — atomic write via `.tmp` + `os.replace`
  - `MappingEntry` dataclass: `beads_id`, `beads_db_path`, `gtask_id`, `gtask_list_id`, `last_synced_at`
- [x] Write unit tests for `load_mapping` and `save_mapping` (including corrupt-file recovery)

**Files touched:** `tasks_api.py`, `beads_api.py`, `sync.py` (new), `tests/test_sync.py` (new)

---

### Phase 2: Sync Engine

**Goal:** Implement the core sync algorithm in `sync.py`.

**Sync algorithm (`SyncEngine.run()`):**

```
for each beads project (workspace_path, db_path):
    project_name = Path(workspace_path).name
    tasklist_id = get_or_create_tasklist(workspace_path, project_name)

    live_issues = list_beads_issues(db_path)
    mapped_ids = {e.beads_id for e in mapping.entries if e.beads_db_path == db_path}

    # Push new beads issues to Google Tasks
    for issue in live_issues:
        if issue.id not in mapped_ids:
            gtask = create_task(tasklist_id, fields_from_issue(issue))
            add_mapping_entry(issue, gtask, tasklist_id)
        else:
            # Beads wins: update existing Google Task
            gtask_id = entry_for(issue.id).gtask_id
            update_task(tasklist_id, gtask_id, fields_from_issue(issue))
            update_mapping_timestamp(issue.id)

    # Detect closed/deleted issues that are in the mapping
    closed_issues = list_closed_mapped_issues(mapped_ids, db_path)
    for issue in closed_issues:
        gtask_id = entry_for(issue.id).gtask_id
        complete_task(tasklist_id, gtask_id)
        remove_mapping_entry(issue.id)  # or keep with status="closed"

    # Detect orphaned mapping entries (deleted/tombstoned without being in closed query)
    live_ids = {i.id for i in live_issues}
    closed_ids = {i.id for i in closed_issues}
    orphaned = mapped_ids - live_ids - closed_ids
    for beads_id in orphaned:
        gtask_id = entry_for(beads_id).gtask_id
        complete_task(tasklist_id, gtask_id)  # safe fallback: mark complete
        remove_mapping_entry(beads_id)

save_mapping(mapping)  # atomic write once at end
```

**`get_or_create_tasklist(workspace_path, name)`:**
1. Check `mapping.projects[workspace_path]` for a stored `tasklist_id`
2. If found, return it (fast path — no API call)
3. If not found: call `list_tasklists()`, scan by name (first match)
4. If still not found: call `create_tasklist(name)`, store ID in `mapping.projects`

**Tasks:**

- [x] Implement `SyncEngine` class with `run(progress_callback)` method
- [x] Implement `get_or_create_tasklist()` with stored-ID fast path
- [x] Implement `fields_from_issue(issue) → dict` — field mapping + type conversions
- [x] Implement closed/orphaned detection and Google Tasks completion
- [x] Handle `description = None` → `""` in all field mapping
- [x] Handle `due_at` datetime → date-only strip, and reverse conversion
- [x] Write unit tests covering:
  - First-ever sync (no mapping file)
  - New issue → creates Google Task and mapping entry
  - Updated issue → updates Google Task (beads wins)
  - Closed issue → completes Google Task, removes mapping entry
  - Orphaned entry → completes Google Task, removes mapping entry
  - Same project name collision (two workspaces, same final path component)
  - Partial failure recovery (corrupt mapping mid-sync)

**Files touched:** `sync.py`, `tasks_api.py` (field helpers), `tests/test_sync.py`

---

### Phase 3: TUI Integration

**Goal:** Wire sync into the app — startup trigger, keybinding, status indicator.

**Tasks:**

- [x] Add `ctrl+s` to `GTasksApp.BINDINGS` with description "Sync"
- [x] Add `sync_status` `Static` widget to `GTasksApp.compose()` layout (below the task list, above the footer)
- [x] Implement `action_sync()`:
  - Guard: if a sync worker is already running, show "Sync already in progress" notification and return
  - Start `@work(thread=True)` worker that calls `SyncEngine().run(on_progress)`
  - `on_progress` callback calls `self.call_from_thread(self._update_sync_status, msg)`
- [x] Implement `_update_sync_status(msg: str)` — updates the `sync_status` widget text
- [x] Call `action_sync()` from `on_mount` after `_load_tasks()` completes
- [x] On sync completion, call `_load_tasks()` to refresh the list with synced data
- [x] Show "Syncing…" during sync, "Last synced HH:MM" on success, "Sync failed: <reason>" on error
- [x] Add integration test: pressing `ctrl+s` in the TUI triggers the sync worker

**Files touched:** `app.py`, `tests/test_app.py`

---

## Acceptance Criteria

### Functional

- [ ] On TUI startup, sync runs automatically and the task list reflects synced state
- [ ] Pressing `ctrl+s` triggers a manual sync
- [ ] New beads issues appear as Google Tasks in a list named after the beads project
- [ ] Edits to a beads issue (title, status, due date, description) are reflected in the linked Google Task after the next sync
- [ ] Closing a beads issue marks the linked Google Task as completed
- [ ] Deleting/tombstoning a beads issue marks the linked Google Task as completed
- [ ] Google Tasks edits on mobile do NOT overwrite beads (beads wins)
- [ ] First sync on a fresh install creates `~/.beads/gtasks-sync.json` and the Google Tasks lists
- [ ] Two beads projects with the same final directory name each get their own Google Tasks list (identified by workspace path, not name)

### Non-Functional

- [ ] Sync runs in a background thread; the TUI remains responsive during sync
- [ ] Mapping file is written atomically (no corrupt state on interrupted sync)
- [ ] `gws` CLI errors or auth failures show a non-crashing notification in the TUI
- [ ] `description = None` in beads does not cause a crash or API error

### Quality Gates

- [ ] All new code passes `uv run ruff check .` and `uv run ruff format --check .`
- [ ] All existing and new tests pass: `uv run pytest`
- [ ] New `tests/test_sync.py` achieves ≥ 80% coverage of `sync.py`

---

## Dependencies & Prerequisites

- `gws` CLI must support `tasks tasklists list` and `tasks tasklists insert` subcommands (verify before Phase 1)
- `bd` CLI must be available for beads write operations (already used by `update_beads_issue`)
- Python ≥ 3.14 (already required)
- No new Python packages required (all operations via subprocess + stdlib `json`, `pathlib`, `os`)

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `gws` lacks tasklist management subcommands | Medium | High | Verify CLI capabilities before starting Phase 1; may need a workaround via raw `gws` flags |
| Google Tasks API rate limits on large issue sets | Low | Medium | Add a small delay (0.1s) between API calls in Phase 2; document limit |
| Sync takes >5s, user perception of slowness | Medium | Low | Background worker handles this; show "Syncing…" indicator |
| `s` / `ctrl+s` confusion (user expects lowercase s to sync) | Medium | Low | Footer binding label makes `ctrl+s` visible; `s` retains subtask label |
| Mapping file grows unbounded with closed/removed entries | Low | Low | Entries are removed when an issue is closed/orphaned |

---

## References

### Internal

- `src/tasks_tui/tasks_api.py` — Google Tasks CRUD via `gws` CLI; `_gws()` helper at line 92, `TASKLIST_ID` hardcoded at line 9
- `src/tasks_tui/beads_api.py` — `list_beads_issues()` at line 57; close/tombstone filter at line 69; `update_beads_issue()` at line 101
- `src/tasks_tui/app.py` — `BINDINGS` at line 737; `_load_tasks()` at line 764; `action_refresh()` at line 829
- `docs/brainstorms/2026-03-13-beads-google-tasks-sync-brainstorm.md` — design decisions
