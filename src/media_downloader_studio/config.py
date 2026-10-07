from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "TwinDownloaderPro"
LEGACY_APP_NAME = "MediaDownloaderStudio"


def app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.name == "posix" and os.environ.get("XDG_DATA_HOME"):
        root = Path(os.environ["XDG_DATA_HOME"])
    else:
        root = Path.home() / ".local" / "share"
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_dir() -> Path:
    path = app_data_dir() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def jobs_dir() -> Path:
    path = app_data_dir() / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_dir_default() -> Path:
    path = Path.home() / "Downloads" / "TwinDownloaderPro"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return app_data_dir() / "settings.json"


def history_file() -> Path:
    return app_data_dir() / "history.json"


def load_settings() -> dict:
    defaults = {
        "output_dir": str(output_dir_default()),
        "tool": "yt-dlp",
        "theme": "Midnight",
        "threads": 8,
        "retries": 10,
        "retry_sleep": 2,
        "http_timeout": 30,
        "proxy_mode": "off",
        "proxy_url": "",
        "proxy_auto_select": True,
        "proxy_max_test": 30,
        "proxy_protocol": "http",
        "resume": True,
        "duplicate_policy": "ask",
        "bandwidth_limit": "",
    }
    try:
        data = json.loads(config_file().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults.update(data)
    except (OSError, ValueError):
        pass
    return defaults


def save_settings(data: dict) -> None:
    try:
        config_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
