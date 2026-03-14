---
status: complete
priority: p3
issue_id: "004"
tags: [code-review, quality, cleanup]
dependencies: []
---

# Dead code and minor simplifications from per-project config implementation

## Problem Statement

Four small issues introduced (or exposed) by the per-project config feature add unnecessary complexity:

1. `_PROJECT_DEFAULTS` is defined but never used
2. `_get` and `_get_str` are identical methods
3. `_populate_projects` reinvents `get_project_config`'s merge logic inline
4. `workspace_path.split("/")[-1]` instead of `Path(workspace_path).name`

None are bugs, but they add confusion and maintenance surface.

## Findings

### 1. Dead constant `_PROJECT_DEFAULTS` — `config.py:22`
```python
_PROJECT_DEFAULTS: dict = {"sync": True, "visible": True, "label": None}  # never referenced
```
The defaults are hardcoded inline in `get_project_config`, `_populate_projects`, and `ProjectRow.get_values`. This constant was likely a placeholder that was never wired up.

### 2. Duplicate `_get` / `_get_str` — `app.py:SetupScreen`
```python
def _get(self, section: str, key: str) -> bool:
    return self._initial.get(section, {}).get(key, DEFAULTS[section][key])

def _get_str(self, section: str, key: str) -> str:
    return self._initial.get(section, {}).get(key, DEFAULTS[section][key])
```
Identical bodies; only the return type annotation differs (and Python doesn't enforce it).

### 3. Inline default merge duplicates `get_project_config` — `app.py:1394`
```python
proj = {**{"sync": True, "visible": True, "label": name}, **projects_config.get(name, {})}
```
This is exactly what `get_project_config(name, self._initial)` does.

### 4. `split("/")[-1]` — `app.py:1393`
`sync.py` uses `Path(workspace_path).name`. The inconsistency is minor but `split("/")` breaks on trailing slashes.

## Proposed Solutions

All four are mechanical, safe removals/replacements:

1. Delete `_PROJECT_DEFAULTS` from `config.py`
2. Delete `_get_str`; rename its call sites to `_get`
3. Replace inline merge with `get_project_config(name, self._initial)`
4. Replace `workspace_path.split("/")[-1]` with `Path(workspace_path).name`

**Combined effort:** Small — ~10 lines changed
**Risk:** Low — no behavior change

## Acceptance Criteria

- [ ] `_PROJECT_DEFAULTS` removed; all tests still pass
- [ ] `_get_str` removed; `_get` used throughout `SetupScreen`
- [ ] `_populate_projects` calls `get_project_config` instead of duplicating the merge
- [ ] `Path(workspace_path).name` used consistently

## Work Log

- 2026-03-14: Identified during code review of per-project config feature
