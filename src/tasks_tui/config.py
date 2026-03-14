"""App configuration loaded from ~/.config/tasks-tui/config.json."""

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "tasks-tui" / "config.json"

DEFAULTS: dict = {
    "sync": {
        "enabled": True,
        "auto_sync_on_start": True,
    },
    "sources": {
        "google_tasks": True,
        "beads": True,
        "beads_search_root": "~/Code",
    },
    "projects": {},
}

def get_project_config(name: str, config: dict) -> dict:
    """Return per-project settings with defaults applied. Label defaults to workspace name."""
    entry = config.get("projects", {}).get(name, {})
    return {
        "sync": entry.get("sync", True),
        "visible": entry.get("visible", True),
        "label": entry.get("label") or name,
    }


def load_config() -> dict:
    """Load config from disk, merging with defaults. Missing keys fall back to defaults."""
    if not CONFIG_PATH.exists():
        return _deep_copy(DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text())
        if not isinstance(data, dict):
            return _deep_copy(DEFAULTS)
        result = {}
        for section, section_defaults in DEFAULTS.items():
            user_section = data.get(section, {})
            if not isinstance(user_section, dict):
                user_section = {}
            if section == "projects":
                result[section] = user_section  # pass through as-is; no fixed defaults to merge
            else:
                result[section] = {**section_defaults, **user_section}
        return result
    except (json.JSONDecodeError, OSError):
        return _deep_copy(DEFAULTS)


def save_config(config: dict) -> None:
    """Atomically write config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2))
    os.replace(tmp, CONFIG_PATH)


def _deep_copy(d: dict) -> dict:
    return {k: dict(v) if isinstance(v, dict) else v for k, v in d.items()}
