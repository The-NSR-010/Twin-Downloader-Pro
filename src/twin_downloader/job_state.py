from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .config import history_file, jobs_dir


def _safe_load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def url_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:20]


def history() -> list[dict]:
    data = _safe_load(history_file(), [])
    return data if isinstance(data, list) else []


def append_history(item: dict, max_items: int = 200) -> None:
    items = history()
    item = dict(item)
    item.setdefault("timestamp", int(time.time()))
    items.insert(0, item)
    _safe_write(history_file(), items[:max_items])


def recent_success(url: str, output_dir: Path) -> dict | None:
    out = str(output_dir.resolve())
    for item in history():
        if item.get("url") == url and item.get("output_dir") == out and item.get("status") == "completed":
            return item
    return None


def job_file(url: str) -> Path:
    return jobs_dir() / f"{url_id(url)}.json"


def save_active_job(url: str, data: dict) -> None:
    payload = dict(data)
    payload["url"] = url
    payload["updated_at"] = int(time.time())
    _safe_write(job_file(url), payload)


def load_active_job(url: str) -> dict | None:
    data = _safe_load(job_file(url), None)
    return data if isinstance(data, dict) else None


def clear_active_job(url: str) -> None:
    try:
        job_file(url).unlink(missing_ok=True)
    except OSError:
        pass
