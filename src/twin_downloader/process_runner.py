from __future__ import annotations

import ctypes
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from PySide6.QtCore import QThread, Signal

PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d+)?)%")
SIZE_RE = re.compile(r"(?P<done>\d+(?:\.\d+)?\s*[KMGTP]?i?B)\s*(?:/|of)\s*(?P<total>\d+(?:\.\d+)?\s*[KMGTP]?i?B)", re.I)
SPEED_RE = re.compile(r"(?P<speed>\d+(?:\.\d+)?\s*[KMGTP]?i?B/s)", re.I)
ETA_RE = re.compile(r"ETA\s+(?P<eta>[0-9:]+)", re.I)


def _human_bytes(value: str | None) -> str:
    if not value or value in {"NA", "None", "null"}:
        return "—"
    try:
        n = float(value)
    except ValueError:
        return value
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.2f} {units[i]}"


def _format_eta(value: str | None) -> str:
    if not value or value in {"NA", "None", "null"}:
        return "—"
    try:
        sec = max(0, int(float(value)))
    except ValueError:
        return value
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def display_command(command: list[str], redact: bool = True) -> str:
    parts: list[str] = []
    sensitive_next = False
    for arg in command:
        shown = arg
        if redact and sensitive_next:
            shown = "<redacted>"
            sensitive_next = False
        elif redact and arg in {"--key", "--custom-hls-key", "--custom-hls-iv"}:
            sensitive_next = True
        if any(ch in shown for ch in " &\t\n\""):
            parts.append('"' + shown.replace('"', '\\"') + '"')
        else:
            parts.append(shown)
    return " ".join(parts)


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _BASIC_LIMITS(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _EXTENDED_LIMITS(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BASIC_LIMITS),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    """Own a downloader process tree with a Windows Job Object."""

    _LIMIT_KILL_ON_CLOSE = 0x00002000
    _INFO_EXTENDED_LIMIT = 9

    def __init__(self) -> None:
        self.handle: int | None = None
        self.assigned = False
        self.error = ""
        if os.name != "nt":
            return
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
            k32.CreateJobObjectW.restype = ctypes.c_void_p
            k32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            k32.SetInformationJobObject.restype = ctypes.c_int
            k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            k32.AssignProcessToJobObject.restype = ctypes.c_int
            k32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            k32.TerminateJobObject.restype = ctypes.c_int
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.restype = ctypes.c_int
            self._k32 = k32
            h = k32.CreateJobObjectW(None, None)
            if not h:
                raise ctypes.WinError(ctypes.get_last_error())
            info = _EXTENDED_LIMITS()
            info.BasicLimitInformation.LimitFlags = self._LIMIT_KILL_ON_CLOSE
            ok = k32.SetInformationJobObject(h, self._INFO_EXTENDED_LIMIT, ctypes.byref(info), ctypes.sizeof(info))
            if not ok:
                err = ctypes.get_last_error()
                k32.CloseHandle(h)
                raise ctypes.WinError(err)
            self.handle = int(h)
        except Exception as exc:
            self.error = str(exc)
            self.handle = None

    def assign(self, process: subprocess.Popen) -> bool:
        if os.name != "nt" or not self.handle:
            return False
        try:
            ok = self._k32.AssignProcessToJobObject(ctypes.c_void_p(self.handle), ctypes.c_void_p(int(process._handle)))
            if not ok:
                self.error = str(ctypes.WinError(ctypes.get_last_error()))
                return False
            self.assigned = True
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def terminate(self) -> bool:
        if os.name != "nt" or not self.handle:
            return False
        try:
            return bool(self._k32.TerminateJobObject(ctypes.c_void_p(self.handle), 1))
        except Exception:
            return False

    def close(self) -> None:
        if os.name != "nt" or not self.handle:
            return
        h = self.handle
        self.handle = None
        try:
            self._k32.CloseHandle(ctypes.c_void_p(h))
        except Exception:
            pass


class DownloadWorker(QThread):
    output = Signal(str)
    progress = Signal(int)
    metrics = Signal(object)
    finished_ok = Signal(int)
    stop_state = Signal(str)

    def __init__(self, command: list[str], cwd: Path | None = None, log_command: bool = True):
        super().__init__()
        self.command = command
        self.cwd = cwd
        self.log_command = log_command
        self.process: subprocess.Popen[str] | None = None
        self.user_stopped = False
        self._stop_lock = threading.Lock()
        self._stop_started = False
        self._force_stop = False
        self._stop_thread: threading.Thread | None = None
        self._job: _WindowsJob | None = None
        self._log_path: Path | None = None
        self._log_file = None
        self._read_file = None

    def run(self) -> None:
        try:
            if self.log_command:
                self.output.emit("$ " + display_command(self.command, redact=True))

            # CRITICAL STOP DESIGN: do NOT use stdout=PIPE. yt-dlp/N_m3u8DL-RE
            # can spawn FFmpeg/helpers which inherit the pipe. Killing the
            # parent then leaves the Qt reader blocked forever waiting for EOF.
            # A private spool file lets the worker poll the process and output
            # independently, so Stop never depends on a descendant closing a
            # pipe.
            fd, raw_path = tempfile.mkstemp(prefix="twin_dl_", suffix=".log")
            os.close(fd)
            self._log_path = Path(raw_path)
            # Separate write/read handles avoid sharing the file pointer with
            # the downloader's inherited stdout handle on Windows.
            self._log_file = open(self._log_path, "a", encoding="utf-8", errors="replace", buffering=1)
            self._read_file = open(self._log_path, "r", encoding="utf-8", errors="replace", buffering=1)

            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt":
                flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            self.process = subprocess.Popen(
                self.command,
                cwd=str(self.cwd) if self.cwd else None,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                start_new_session=(os.name != "nt"),
            )

            if os.name == "nt":
                self._job = _WindowsJob()
                if self._job.handle:
                    if not self._job.assign(self.process):
                        self.output.emit("[studio] Windows Job Object assignment failed; taskkill fallback is armed.")
                    else:
                        self.output.emit("[studio] Windows Job Object attached (tree-stop protection active).")
                elif self._job.error:
                    self.output.emit(f"[studio] Windows Job Object unavailable; taskkill fallback is armed: {self._job.error}")

            self._drain_output(final=False)
            while self.process.poll() is None:
                self._drain_output(final=False)
                time.sleep(0.05)
            self._drain_output(final=True)
            code = self.process.returncode
            if code == 0:
                self.progress.emit(100)
            self.finished_ok.emit(code if code is not None else -1)
        except Exception as exc:
            self.output.emit(f"[runner error] {exc}")
            self.finished_ok.emit(-1)
        finally:
            self._close_runtime_handles()

    def _drain_output(self, final: bool = False) -> None:
        f = self._read_file
        if not f:
            return
        try:
            f.seek(self._read_pos)
            while True:
                raw = f.readline()
                if not raw:
                    break
                self._read_pos = f.tell()
                line = raw.rstrip()
                if not line:
                    continue
                if line.startswith("MDS_PROGRESS:"):
                    self._parse_machine_progress(line)
                    continue
                self.output.emit(line)
                self._parse_generic_progress(line)
            if final:
                self._read_pos = f.tell()
        except (ValueError, OSError):
            pass

    @property
    def _read_pos(self) -> int:
        return getattr(self, "__read_pos", 0)

    @_read_pos.setter
    def _read_pos(self, value: int) -> None:
        setattr(self, "__read_pos", value)

    def _close_runtime_handles(self) -> None:
        try:
            if self._log_file:
                self._log_file.close()
            if self._read_file:
                self._read_file.close()
        except Exception:
            pass
        self._log_file = None
        self._read_file = None
        if self._job:
            self._job.close()
            self._job = None
        if self._log_path:
            try:
                self._log_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._log_path = None

    def _parse_machine_progress(self, line: str) -> None:
        parts = line[len("MDS_PROGRESS:"):].split("|", 6)
        while len(parts) < 7:
            parts.append("")
        pct, downloaded, total, estimate, speed, eta, title = parts
        try:
            p = int(float(pct.replace("%", "").strip()))
            self.progress.emit(max(0, min(100, p)))
        except ValueError:
            p = None
        total_value = total if total not in {"", "NA", "None"} else estimate
        speed_text = "—"
        if speed not in {"", "NA", "None"}:
            speed_text = _human_bytes(speed) + "/s"
        self.metrics.emit({
            "percent": p,
            "downloaded": _human_bytes(downloaded),
            "total": _human_bytes(total_value),
            "speed": speed_text,
            "eta": _format_eta(eta),
            "title": title or "Downloading",
        })

    def _parse_generic_progress(self, line: str) -> None:
        data: dict[str, object] = {}
        match = PERCENT_RE.search(line)
        if match:
            try:
                pct = int(float(match.group(1)))
                self.progress.emit(max(0, min(100, pct)))
                data["percent"] = pct
            except ValueError:
                pass
        sm = SIZE_RE.search(line)
        if sm:
            data["downloaded"] = sm.group("done")
            data["total"] = sm.group("total")
        sp = SPEED_RE.search(line)
        if sp:
            data["speed"] = sp.group("speed")
        em = ETA_RE.search(line)
        if em:
            data["eta"] = em.group("eta")
        if data:
            self.metrics.emit(data)

    def stop(self) -> None:
        """Immediately terminate the complete downloader tree without blocking Qt."""
        with self._stop_lock:
            self.user_stopped = True
            proc = self.process
            if not proc:
                return
            pid = proc.pid
            if self._stop_started:
                self._force_stop = True
                self.stop_state.emit("force")
                threading.Thread(target=self._force_kill_worker, args=(pid,), daemon=True).start()
                return
            self._stop_started = True
            self._force_stop = True
            self.stop_state.emit("stopping")
            # First click is already a hard tree termination. The second click
            # simply repeats the kill path if Windows needs a fallback.
            self._stop_thread = threading.Thread(target=self._stop_worker, args=(pid,), daemon=True)
            self._stop_thread.start()

    def _kill_tree(self, pid: int) -> None:
        if os.name == "nt":
            # Job termination is the primary mechanism; taskkill /T /F is a
            # second independent mechanism for processes that cannot be put in
            # the job because of Windows job nesting/breakaway restrictions.
            job = self._job
            if job and job.assigned:
                job.terminate()
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            proc = self.process
            if proc and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (OSError, AttributeError):
                    try:
                        proc.kill()
                    except OSError:
                        pass

    def _force_kill_worker(self, pid: int) -> None:
        self._kill_tree(pid)
        proc = self.process
        if proc:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        self.stop_state.emit("stopped")

    def _stop_worker(self, pid: int) -> None:
        self.stop_state.emit("force")
        self._kill_tree(pid)
        proc = self.process
        if proc:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        self.stop_state.emit("stopped")
