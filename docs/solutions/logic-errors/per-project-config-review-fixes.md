---
title: "Per-project config: NameError in sync, sort/display label mismatch, data loss on save, dead code"
date: "2026-03-14"
problem_type: [runtime-error, logic-error, data-loss]
component: per-project-config
symptoms:
  - "NameError raised instead of recording error when _sync_project encounters exception on close/orphan"
  - "Beads items sorted by workspace name fallback but displayed with per-project label override"
  - "Saving SetupScreen config before background workspace discovery completes erases all project settings"
  - "Unused _PROJECT_DEFAULTS constant and duplicate _get/_get_str methods in config/app modules"
tags:
  - sync
  - config
  - textual-tui
  - beads
  - google-tasks
  - per-project-config
  - data-loss
  - scope-error
  - dead-code
related_modules:
  - src/tasks_tui/sync.py
  - src/tasks_tui/app.py
  - src/tasks_tui/config.py
severity: p1
---

# Per-project config: 4 bugs found in code review

Code review of the per-project config feature (`docs/plans/2026-03-14-feat-per-project-config-plan.md`) identified one P1 bug, two P2 bugs, and one P3 cleanup. All were fixed with 115/115 tests passing.

---

## Problem

### Bug 1 (P1): NameError in `_sync_project` — `errors` referenced from caller scope

`_sync_project` appended to `errors` in its exception handlers, but `errors` was only a local variable in the calling method `run()`. Python method calls do not inherit the caller's locals — only nested functions/lambdas have closure access.

At runtime, any failure completing a closed or orphaned Google Task would raise `NameError: name 'errors' is not defined` instead of recording the error. That `NameError` was then caught by the outer `except Exception` in `run()`, masking the original API failure entirely. Sync mappings would become inconsistent with no diagnostic surfaced to the user.

### Bug 2 (P2): Sort key used workspace name; display used per-project label

`_render_tasks` contained two independent label resolution paths:
- `_append_beads` (display): `get_project_config(issue.project, self._config)["label"]` — respects per-project label override
- `_sort_key` (sort): `get_beads_label(item.id, item.project)` — falls back to raw workspace name

When a project had a label override (e.g. workspace `"infrastructure-core"`, label `"Infra"`), items were sorted as `"infrastructure-core"` but displayed as `"Infra"`, producing incorrect visual ordering.

### Bug 3 (P2): Saving config before discovery completes wipes all project settings

`SetupScreen` starts workspace discovery in a `@work(thread=True)` background worker on mount, but the Save button is immediately available. If Save is clicked before the worker finishes, `self.query(ProjectRow)` returns `[]` and:

```python
projects: dict[str, dict] = {}  # starts empty
for row in self.query(ProjectRow):  # no rows yet — loop skips
    projects[row.project_name] = row.get_values()
# dismiss() called with projects={} — erases all existing config.projects
```

All per-project sync/visible/label settings are silently deleted.

### Bug 4 (P3): Dead code and duplicate logic

- `_PROJECT_DEFAULTS: dict = {"sync": True, "visible": True, "label": None}` defined in `config.py` but never referenced anywhere
- `_get` and `_get_str` in `SetupScreen` were identical methods (same body, only return type annotation differed)
- `_populate_projects` re-implemented `get_project_config`'s merge inline: `{**{"sync": True, "visible": True, "label": name}, **projects_config.get(name, {})}`
- `workspace_path.split("/")[-1]` instead of `Path(workspace_path).name` (inconsistent with `sync.py`, breaks on trailing slash)

---

## Solution

### Fix 1: Pass `errors` as explicit parameter

**`src/tasks_tui/sync.py`**

```python
# Before
def _sync_project(self, workspace_path: str, db_path: str, project_name: str) -> None:
    ...
    except Exception as e:
        errors.append(f"complete {issue.id}: {e}")  # NameError!

# After
def _sync_project(
    self, workspace_path: str, db_path: str, project_name: str, errors: list[str]
) -> None:
    ...
    except Exception as e:
        errors.append(f"complete {issue.id}: {e}")  # correct
```

Call site in `run()`:
```python
self._sync_project(workspace_path, db_path, project_name, errors)
```

### Fix 2: Use `get_project_config` in sort key

**`src/tasks_tui/app.py` — `_sort_key` inside `_render_tasks`**

```python
# Before
label = get_beads_label(item.id, item.project)

# After
proj_label = get_project_config(item.project, self._config)["label"]
label = get_beads_label(item.id, proj_label)
```

### Fix 3: Seed projects from existing config before iterating rows

**`src/tasks_tui/app.py` — `SetupScreen.on_button_pressed`**

```python
# Before
projects: dict[str, dict] = {}
for row in self.query(ProjectRow):
    projects[row.project_name] = row.get_values()

# After — existing config is the base; mounted rows override only their own entries
projects: dict[str, dict] = dict(self._initial.get("projects", {}))
for row in self.query(ProjectRow):
    projects[row.project_name] = row.get_values()
```

### Fix 4: Dead code cleanup

**`src/tasks_tui/config.py`** — delete `_PROJECT_DEFAULTS` (never referenced).

**`src/tasks_tui/app.py` — `SetupScreen`**:
- Delete `_get_str`; rename all call sites to `_get`
- Replace inline merge with `get_project_config(name, self._initial)`
- Replace `workspace_path.split("/")[-1]` with `Path(workspace_path).name`
- Add `from pathlib import Path` import

---

## Tests Added

```python
# test_sync.py — covers the NameError path for both closed and orphaned issues
def test_complete_api_error_is_reported_in_progress(self, tmp_mapping):
    ...
    with patch("tasks_tui.sync.complete_task_in_list", side_effect=Exception("API down")):
        engine = SyncEngine()
        engine.run(progress=messages.append)
    assert any("error" in m.lower() for m in messages)
    assert any("P-1" in m or "complete" in m for m in messages)

def test_orphan_api_error_is_reported_in_progress(self, tmp_mapping):
    # same pattern, for orphaned entry path

# test_app.py — covers save-before-discovery
async def test_setup_screen_save_before_discovery_preserves_existing_projects():
    with patch.object(SetupScreen, "_discover_projects"):  # prevent worker from running
        async with GTasksApp().run_test() as pilot:
            screen = SetupScreen(config=existing_config)
            await pilot.app.push_screen(screen, capture)
            save_btn = pilot.app.screen.query_one("#setup-save")
            pilot.app.screen.on_button_pressed(save_btn.Pressed(save_btn))
    assert result["projects"]["myapp"] == {"sync": False, "visible": True, "label": "my-label"}
```

---

## Prevention Strategies

### 1. Variable scope bugs (NameError from caller scope)

Python method calls do not inherit the caller's local variables. Only nested functions/lambdas have closure access.

- **Rule:** Every name used in a method body must be a parameter, an attribute on `self`, or a module-level name. Audit all free variables when extracting a code block into a method.
- **Static tools:** `ruff` with `F821` (undefined name), `ty check` — both catch scope errors.
- **Test pattern:** Call each method in isolation, not only through the full call chain. A `NameError` that only appears via one entry point means the method has a hidden dependency.
- **Design:** Prefer collect-and-return over mutating a shared list. `errors.extend(self._sync_project(...))` is explicit; mutating the caller's `errors` list is hidden coupling.

### 2. Dual code path / label mismatch

When a value requires non-trivial derivation, that derivation must live in exactly one function.

- **Rule:** Before adding a feature that changes how a value is derived, grep for every site that currently computes that value. Update all of them, or extract a single helper first.
- **Code review signal:** Two places producing the same type of value (e.g., "a display label for a task") with slightly different logic is a red flag.
- **Test pattern:** Parameterize label/sort tests to exercise all render branches. Assert the same expected output for the same input regardless of which branch is taken.

### 3. Save-before-worker-completes (Textual background workers)

The gap between "worker started" and "worker finished" is a window for data loss.

- **Rule:** Disable save/submit controls at screen mount. Re-enable them only in the worker's completion callback (`call_from_thread` / `on_worker_state_changed`).
- **Fallback rule (used here):** If disabling the button is not desired UX, seed the output from the existing config as a base. Any rows mounted by the worker override specific keys; un-mounted entries are preserved.
- **Textual pattern:** Use a `reactive(_loaded = False)` and `watch__loaded` to toggle button state declaratively.
- **Test pattern:** Mock the worker to a no-op (`patch.object(Screen, "_worker_method")`), trigger save, assert existing config is preserved.

### 4. Dead code / duplication

- **Rule (Boy Scout):** When you add a helper that replaces inline logic, delete the inline logic in the same commit.
- **Rule:** Unused constants must not survive code review. If `_PROJECT_DEFAULTS` is never referenced, delete it.
- **Static tools:** `ruff F401` (unused import/name), coverage threshold enforcement — dead code shows as uncovered.
- **Review signal:** Two methods with the same signature shape and identical bodies are always a candidate for deletion of one.

### Quick reference table

| Bug class | Static tool | Test type | Design gate |
|---|---|---|---|
| Scope / NameError | `ruff F821`, `ty check` | Isolated per-method unit tests | Explicit parameter passing |
| Dual code path | Manual grep + snapshot tests | Parameterized render tests | Single derivation function |
| Worker race condition | Manual review | Async lifecycle test with mocked worker | Seed from existing config; or disable button until ready |
| Dead code / duplication | `ruff F401/F811`, coverage | Coverage threshold | Delete-on-replace discipline |

---

## Related Documentation

No existing `docs/solutions/` directory existed before this entry. This is the first compounded solution.
