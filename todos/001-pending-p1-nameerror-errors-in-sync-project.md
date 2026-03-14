---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, bug, sync]
dependencies: []
---

# NameError: `errors` referenced in `_sync_project` but defined in `run()`

## Problem Statement

`sync.py:_sync_project` references `errors` at lines 239 and 249, but `errors` is only defined in the calling method `run()` (line 118). At runtime, whenever `complete_task_in_list` throws for a closed or orphaned issue, Python raises `NameError: name 'errors' is not defined`.

This NameError is caught by the outer `except Exception` in `run()` (lines 126–128) and reported as a generic project-level error — masking the original exception entirely. The sync mapping is left in a partially inconsistent state with no diagnostic information surfaced to the user.

**Why it matters:** Closed issues fail to complete in Google Tasks, orphaned mappings accumulate, and the actual cause is invisible.

## Findings

- **Location:** `src/tasks_tui/sync.py:239` and `sync.py:249`
- `_sync_project` is a private method; `errors` is a local variable in `run()`
- Both `closed_issues` and `orphaned_ids` error-handling `except` blocks are affected
- No existing test covers the exception path (tests mock success only)

## Proposed Solutions

### Option A — Pass `errors` as a parameter (recommended)
```python
def _sync_project(self, workspace_path: str, db_path: str, project_name: str, errors: list[str]) -> None:
    ...
    except Exception as e:
        errors.append(f"complete {issue.id}: {e}")
```
Call site in `run()`:
```python
self._sync_project(workspace_path, db_path, project_name, errors)
```
**Pros:** Minimal change, clear data flow, errors collected in the right place.
**Cons:** Slightly longer signature.
**Effort:** Small | **Risk:** Low

### Option B — Return errors from `_sync_project`
```python
def _sync_project(...) -> list[str]:
    local_errors: list[str] = []
    ...
    except Exception as e:
        local_errors.append(...)
    return local_errors
```
Call site: `errors.extend(self._sync_project(...))`
**Pros:** No mutation through parameter.
**Cons:** Requires handling empty list return and `.extend()`.
**Effort:** Small | **Risk:** Low

### Option C — Initialize `errors` inside `_sync_project`
Initialize `errors = []` at the top of `_sync_project` and surface them by raising or logging.
**Pros:** Self-contained.
**Cons:** Errors don't bubble back to `run()`'s progress reporting.
**Effort:** Small | **Risk:** Medium (changes error aggregation behavior)

## Recommended Action

Option A — pass `errors` as a parameter.

## Acceptance Criteria

- [ ] `_sync_project` no longer references an undefined `errors` variable
- [ ] Exceptions in closed-issue completion are appended to the outer `errors` list
- [ ] Exceptions in orphaned-entry completion are appended to the outer `errors` list
- [ ] Add a test: `test_sync_project_closed_issue_api_error_is_reported` that patches `complete_task_in_list` to raise and asserts the error message appears in the progress output

## Work Log

- 2026-03-14: Identified during code review of per-project config feature
