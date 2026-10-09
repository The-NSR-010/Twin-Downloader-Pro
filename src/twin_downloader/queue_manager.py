from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import time

from .config import app_data_dir

QUEUE_FILE = app_data_dir() / "queue.json"

@dataclass
class QueueItem:
    url: str
    engine: str
    output_dir: str
    added_at: float = 0.0
    status: str = "queued"

    def __post_init__(self):
        if not self.added_at:
            self.added_at = time.time()


def load_queue() -> list[QueueItem]:
    try:
        raw = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return [QueueItem(**x) for x in raw if isinstance(x, dict)]
    except (OSError, ValueError, TypeError):
        return []


def save_queue(items: list[QueueItem]) -> None:
    try:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_FILE.write_text(json.dumps([asdict(x) for x in items], indent=2), encoding="utf-8")
    except OSError:
        pass
