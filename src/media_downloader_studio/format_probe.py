from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QThread, Signal


@dataclass
class MediaFormat:
    format_id: str
    kind: str
    resolution: str
    fps: str
    codec: str
    ext: str
    bitrate: str
    size: str
    language: str
    note: str


def _size(fmt: dict) -> str:
    value = fmt.get("filesize") or fmt.get("filesize_approx")
    if not value:
        return "—"
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return "—"


class YtDlpProbeWorker(QThread):
    ready = Signal(object, object)
    failed = Signal(str)

    def __init__(self, url: str, tools: dict[str, Path], cookies_browser: str = "", proxy_url: str = ""):
        super().__init__()
        self.url = url
        self.tools = tools
        self.cookies_browser = cookies_browser
        self.proxy_url = proxy_url

    def run(self):
        cmd = [str(self.tools["yt-dlp"]), "-J", "--no-warnings", "--no-playlist", self.url]
        if self.cookies_browser:
            cmd[1:1] = ["--cookies-from-browser", self.cookies_browser]
        if self.proxy_url:
            cmd[1:1] = ["--proxy", self.proxy_url]
        if self.tools.get("deno"):
            cmd[1:1] = ["--js-runtimes", f"deno:{self.tools['deno']}"]
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if cp.returncode != 0:
                self.failed.emit((cp.stderr or cp.stdout or "Format inspection failed.").strip())
                return
            info = json.loads(cp.stdout.strip().splitlines()[-1])
            formats = []
            for f in info.get("formats", []):
                vcodec = f.get("vcodec") or "none"
                acodec = f.get("acodec") or "none"
                if vcodec != "none" and acodec != "none":
                    kind = "Video+Audio"
                elif vcodec != "none":
                    kind = "Video"
                elif acodec != "none":
                    kind = "Audio"
                else:
                    continue
                resolution = f.get("resolution") or (f"{f.get('width')}x{f.get('height')}" if f.get("height") else "audio")
                codec = "/".join(x for x in [vcodec if vcodec != "none" else "", acodec if acodec != "none" else ""] if x)
                br = f.get("tbr") or f.get("abr") or f.get("vbr")
                formats.append(MediaFormat(
                    str(f.get("format_id", "")), kind, str(resolution), str(f.get("fps") or "—"), codec or "—",
                    str(f.get("ext") or "—"), f"{br:.0f} kbps" if isinstance(br, (int, float)) else "—", _size(f),
                    str(f.get("language") or "—"), str(f.get("format_note") or ""),
                ))
            self.ready.emit(info, formats)
        except Exception as exc:
            self.failed.emit(str(exc))
