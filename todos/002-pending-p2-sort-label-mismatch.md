---
status: complete
priority: p2
issue_id: "002"
tags: [code-review, bug, ui]
dependencies: []
---

# Sort key uses project name; display uses per-project label override

## Problem Statement

In `_render_tasks`, the `_sort_key` function resolves a Beads item's label using `get_beads_label(item.id, item.project)` — which falls back to the workspace name (e.g. `"infrastructure-core"`). But `_append_beads` displays items using `get_project_config(issue.project, self._config)["label"]` — which applies the per-project label override (e.g. `"Infra"`).

The result: items are sorted by their workspace name but displayed with their configured label. A user who sets a label override will see items ordered incorrectly relative to how they appear visually.

## Findings

- **Location:** `src/tasks_tui/app.py:1041` (`_sort_key`) vs `app.py:1012` (`_append_beads`)
- `_sort_key` for beads: `label = get_beads_label(item.id, item.project)` — ignores `config.projects`
- `_append_beads`: `proj_label = get_project_config(issue.project, self._config)["label"]` — respects `config.projects`
- Reproduces as soon as any project has a `label` override in config

## Proposed Solutions

### Option A — Build a project label cache once (recommended)
```python
# Before sorting:
label_cache = {
    i.project: get_project_config(i.project, self._config)["label"]
    for i in self._beads_issues
}

def _sort_key(entry):
    kind, item = entry
    if kind == "beads":
        label = get_beads_label(item.id, label_cache.get(item.project, item.project))
        ...
```
Also pass `label_cache` into `_append_beads` to use the same resolved label.
**Pros:** Single source of truth, also eliminates repeated `get_project_config` calls during render.
**Cons:** Slight refactor needed to thread the cache into `_append_beads`.
**Effort:** Small | **Risk:** Low

### Option B — Inline fix in `_sort_key`
Replace:
```python
label = get_beads_label(item.id, item.project)
```
With:
```python
label = get_beads_label(item.id, get_project_config(item.project, self._config)["label"])
```
**Pros:** Minimal change, immediately correct.
**Cons:** `get_project_config` now called twice per item (once in sort, once in render).
**Effort:** Tiny | **Risk:** Low

## Recommended Action

Option B as a quick fix; Option A if cleaning up the render loop more broadly.

## Acceptance Criteria

- [ ] Sort order for Beads items uses the same label resolution as display
- [ ] Items with a per-project `label` override are sorted by that label, not the workspace name
- [ ] Add a test: with two projects having label overrides, verify the sorted display order matches the configured labels

## Work Log

- 2026-03-14: Identified during code review of per-project config feature
