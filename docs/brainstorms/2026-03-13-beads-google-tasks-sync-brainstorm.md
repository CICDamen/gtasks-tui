# Beads ↔ Google Tasks Two-Way Sync

**Date:** 2026-03-13
**Status:** Brainstorm
**Author:** Casper

---

## What We're Building

A two-way synchronization layer between beads issues and Google Tasks, surfaced inside the existing `tasks-tui` app. Users can trigger sync manually via a keybinding or it runs automatically on startup. Beads is the source of truth — new beads issues push to Google Tasks, but new Google Tasks do not create beads issues.

---

## Scope

### In scope
- Sync triggered on startup and via a manual keybinding (`S`)
- Fields synced: title, status/completion, due date, description/notes
- New beads issues are created as Google Tasks (beads → Google Tasks one-way for new items)
- Both systems updated for edits to already-linked items (true two-way for existing pairs)
- One Google Tasks list per beads project (list named after the project)
- Beads wins on conflict (most recent beads state overwrites Google Tasks)
- Link tracking via a mapping file at `~/.beads/gtasks-sync.json`
- Sync status indicator visible in the TUI

### Out of scope
- New Google Tasks creating beads issues
- Subtask sync
- Attachment or label sync
- Webhook/real-time sync

---

## Why This Approach

### Sync mapping file (`~/.beads/gtasks-sync.json`)

Keeps beads issues clean (no embedded foreign IDs), survives title changes, is human-readable and easy to reset. Each entry maps a beads issue ID → Google Task ID + last-synced timestamp.

```json
{
  "mappings": [
    {
      "beads_id": "PROJ-001",
      "gtask_id": "abc123",
      "gtask_list_id": "MDg...",
      "last_synced_at": "2026-03-13T10:00:00Z"
    }
  ]
}
```

### Beads wins on conflict

Beads is the primary workflow tool — Google Tasks is the mobile/calendar view. Preserving beads state avoids surprising overwrites during morning phone check-ins.

### One list per project

Mirrors how beads is structured (one registry entry per project/workspace). Makes Google Tasks useful as a per-project view.

---

## Field Mapping

| Beads field | Google Tasks field | Notes |
|---|---|---|
| `title` | `title` | Direct string mapping |
| `status` (any non-closed) | `status: "needsAction"` | Beads "open"/"in_progress"/"blocked" → not completed |
| `status: "closed"` | `status: "completed"` | Closing in beads completes in Google Tasks |
| `due_at` | `due` | ISO 8601 date (Google Tasks uses date only, no time) |
| `description` | `notes` | Plain text only |

---

## Sync Algorithm

### On startup / manual trigger

1. Load `~/.beads/gtasks-sync.json` mapping
2. For each beads project:
   - Find or create the matching Google Tasks list (named after project)
   - List all open beads issues
   - For each issue with an existing mapping → update Google Task with beads fields (beads wins)
   - For each issue without a mapping → create new Google Task, save mapping
   - For each Google Task in the list without a beads mapping → skip (not created in beads)
   - For each Google Task whose mapped beads issue is now closed → mark task completed in Google Tasks

### Conflict resolution

Beads always wins. On sync, beads fields are written to Google Tasks unconditionally (no timestamp comparison needed for this phase).

---

## UI Changes

- **Keybinding `S`** — triggers manual sync, shows progress in status bar
- **Startup sync** — runs in background thread, shows "Syncing..." indicator
- **Status bar** — shows last sync time after successful sync
- **Error handling** — surface sync errors as non-blocking notifications (don't crash the TUI)

---

## Implementation Touchpoints

| File | Change |
|---|---|
| `src/tasks_tui/sync.py` | New module: sync engine, mapping file I/O |
| `src/tasks_tui/app.py` | Call sync on startup, add `S` keybinding |
| `src/tasks_tui/tasks_api.py` | Existing Google Tasks CRUD — already has what's needed |
| `src/tasks_tui/beads_api.py` | May need `list_all_issues()` across all projects |
| `~/.beads/gtasks-sync.json` | New mapping file (created on first sync) |

---

## Open Questions

_None — all resolved during brainstorm._

## Resolved Questions

- **Sync trigger:** Startup + manual keybinding `S`
- **Conflict resolution:** Beads wins unconditionally
- **New items:** Beads → Google Tasks only (not the reverse)
- **Fields to sync:** Title, status/completion, due date, description/notes
- **Linking mechanism:** `~/.beads/gtasks-sync.json` mapping file (recommended over title matching or embedding IDs in beads)
- **Google Tasks list:** One list per beads project, named after the project
