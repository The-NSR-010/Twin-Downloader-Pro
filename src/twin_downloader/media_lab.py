from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable


def run_capture(command: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        cp = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return cp.returncode, ((cp.stdout or "") + ("\n" + cp.stderr if cp.stderr else "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "Operation timed out."
    except OSError as exc:
        return 127, str(exc)


def ffprobe_json(ffprobe: Path, source: str) -> tuple[bool, dict | str]:
    cmd = [str(ffprobe), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", source]
    code, text = run_capture(cmd, 60)
    if code:
        return False, text[-12000:]
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, "FFprobe returned non-JSON output."


def bento_inspect(executable: Path, source: str, mode: str = "info") -> tuple[int, str]:
    modes = {
        "info": ["--format", "json"],
        "dump": [],
    }
    return run_capture([str(executable), *modes.get(mode, []), source], 45)


def build_bento_transform(tool: str, source: Path, output: Path | None = None, extra: Iterable[str] = ()) -> list[str]:
    cmd = [tool]
    cmd.extend(extra)
    cmd.append(str(source))
    if output:
        cmd.append(str(output))
    return cmd


def summarize_probe(data: dict) -> list[tuple[str, str]]:
    result = []
    fmt = data.get("format", {})
    if fmt:
        result.extend([
            ("Container", str(fmt.get("format_name", "—"))),
            ("Duration", str(fmt.get("duration", "—"))),
            ("Size", str(fmt.get("size", "—"))),
            ("Bit rate", str(fmt.get("bit_rate", "—"))),
        ])
    for i, stream in enumerate(data.get("streams", []), 1):
        kind = stream.get("codec_type", "stream")
        title = f"{kind.title()} #{i}"
        detail = " / ".join(str(x) for x in [stream.get("codec_name"), stream.get("profile"), stream.get("width"), stream.get("height"), stream.get("sample_rate")] if x)
        result.append((title, detail or "—"))
    return result
