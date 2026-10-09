from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .config import tools_dir

ProgressCallback = Callable[[str, int | None], None]

YT_DLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
N_M3U8_URL = "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.6.0-beta/N_m3u8DL-RE_v0.6.0-beta_win-x64_20260629.zip"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DENO_URL = "https://github.com/denoland/deno/releases/download/v2.9.6/deno-x86_64-pc-windows-msvc.zip"
DENO_SHA512 = "c0bb52a96ba040cb5c80c52c1f98181fb47ee9d2bf3ce20227ae4738fa258bc2298a354386b3865ccca181ed51b6f9a1f77fc9b22d03b0cd0c2d038df659085c"
BENTO4_URL = "https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-microsoft-win32.zip"
# Official Bento4 downloads page currently points to this Windows binary.
# mp4decrypt has no useful standalone --version mode, so probe it with --help.
MP4DECRYPT_PROBE_ARGS = []

# Bento4 command-line tools commonly return non-zero usage errors when invoked
# without their required positional arguments. Presence + process launch is the
# important health signal; these markers are accepted as valid executable probes.
BENTO_USAGE_MARKERS = (
    "missing output filename", "cannot open input", "cannot open input file",
    "no input", "usage", "version", "bento4", "mp4 file", "mp4 atom",
)


class BootstrapError(RuntimeError):
    pass


def _download(url: str, destination: Path, progress: ProgressCallback, expected_sha512: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never restart an already-completed download. A caller that wants a repair
    # must explicitly remove the target first. This prevents repeated downloads
    # when startup checks are triggered more than once.
    if destination.is_file() and destination.stat().st_size > 0:
        if expected_sha512:
            digest = hashlib.sha512()
            with destination.open("rb") as cached:
                for chunk in iter(lambda: cached.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest().lower() == expected_sha512.lower():
                progress(f"Using cached {destination.name}", 100)
                return
            destination.unlink(missing_ok=True)
        else:
            progress(f"Using cached {destination.name}", 100)
            return
    request = urllib.request.Request(url, headers={"User-Agent": "TwinDownloaderPro/0.6.1"})
    try:
        with urllib.request.urlopen(request, timeout=75) as response, destination.open("wb") as out:
            total = response.headers.get("Content-Length")
            total_bytes = int(total) if total else None
            read = 0
            digest = hashlib.sha512()
            last_percent = -1
            last_emit = 0.0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                read += len(chunk)
                percent = int(read * 100 / total_bytes) if total_bytes else None
                # Do not emit one GUI event per network chunk. Large downloads can
                # otherwise flood the Qt event loop and make the checking screen
                # appear frozen. Emit only meaningful progress changes.
                now = time.monotonic()
                if percent is None:
                    if now - last_emit >= 0.75:
                        progress(f"Downloading {destination.name}", None)
                        last_emit = now
                elif percent >= 100 or percent - last_percent >= 2 or now - last_emit >= 1.0:
                    progress(f"Downloading {destination.name}", percent)
                    last_percent = percent
                    last_emit = now
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise BootstrapError(f"Could not download {url}: {exc}") from exc
    if expected_sha512 and digest.hexdigest().lower() != expected_sha512.lower():
        destination.unlink(missing_ok=True)
        raise BootstrapError(f"SHA-512 verification failed for {destination.name}")


def _extract_zip(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        root = target.resolve()
        for member in zf.infolist():
            member_path = (target / member.filename).resolve()
            if root != member_path and root not in member_path.parents:
                raise BootstrapError(f"Unsafe archive path: {member.filename}")
        zf.extractall(target)


def _find_executable(root: Path, names: tuple[str, ...]) -> Path | None:
    if not root.exists():
        return None
    for name in names:
        direct = root / name
        if direct.is_file():
            return direct
    # Fallback is intentionally used only when the expected flat path is absent.
    for name in names:
        try:
            for match in root.rglob(name):
                if match.is_file():
                    return match
        except OSError:
            continue
    return None


def _make_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    except OSError:
        pass


def _probe(path: Path, args: list[str], marker: str | None = None) -> tuple[bool, str]:
    """Run a bounded health probe.

    Many CLI media tools intentionally return a non-zero code when --help is
    supplied without the positional input/output files they normally require.
    That is not evidence that the executable is broken. For optional Bento4
    utilities we therefore accept recognizable tool/help/version output even
    when the process exit code is non-zero.
    """
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return False, "missing"
    try:
        cp = subprocess.run(
            [str(path), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=12, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = ((cp.stdout or "") + "\n" + (cp.stderr or "")).strip()
        low = text.lower()
        exe = path.stem.lower()
        recognizable = (
            exe in low
            or "bento4" in low
            or "ffmpeg version" in low
            or "ffprobe version" in low
            or "ffplay version" in low
            or "deno " in low
            or "usage:" in low
            or "usage " in low
            or "options:" in low
            or "version" in low
            or any(marker_text in low for marker_text in BENTO_USAGE_MARKERS)
        )
        if marker:
            ok = marker.lower() in low
        else:
            ok = cp.returncode == 0 or recognizable
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "ready")
        return ok, first[:180]
    except subprocess.TimeoutExpired:
        return False, "health probe timed out"
    except Exception as exc:
        return False, str(exc)


def _install_zip_tool(url: str, archive_name: str, directory: Path, names: tuple[str, ...], progress: ProgressCallback) -> Path:
    # Download/extract into a staging directory first. Never destroy a working
    # installation merely because a repair download failed.
    root = tools_dir()
    archive = root / (archive_name + ".download")
    staging = root / (directory.name + "_staging")
    shutil.rmtree(staging, ignore_errors=True)
    _download(url, archive, progress)
    try:
        _extract_zip(archive, staging)
        found = _find_executable(staging, names)
        if not found:
            raise BootstrapError(f"Expected executable {names[0]} was not found after extraction.")
        shutil.rmtree(directory, ignore_errors=True)
        directory.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), str(directory))
        found = _find_executable(directory, names)
        if not found:
            raise BootstrapError(f"Expected executable {names[0]} was not found after installation.")
        return found
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


def ensure_tools(progress: ProgressCallback = lambda *_: None) -> dict[str, Path]:
    """Prepare the private toolchain without allowing optional components to block startup.

    Required for normal downloading: yt-dlp, FFmpeg/FFprobe.
    Stream-engine tools: N_m3u8DL-RE.
    Optional helpers: Deno and Bento4/mp4decrypt.

    Every probe is bounded. A failed optional repair is reported but does not dead-lock
    the application; feature-specific UI disables only the affected feature.
    """
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64", "x64"}:
        raise BootstrapError("Media Downloader Studio currently targets Windows x64.")

    root = tools_dir(); bin_dir = root / "bin"; bin_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    failures: dict[str, str] = {}

    def check(name: str, path: Path | None, args: list[str], marker: str | None = None) -> bool:
        if not path:
            return False
        ok, detail = _probe(path, args, marker)
        progress(f"{name}: {'ready' if ok else 'unavailable'} — {detail}", None)
        return ok

    def install(name: str, installer):
        try:
            progress(f"Installing {name}…", None)
            path = installer()
            return path
        except Exception as exc:
            failures[name] = str(exc)
            progress(f"{name}: installation skipped — {exc}", None)
            return None

    # 1. yt-dlp: primary required downloader
    progress("Checking core downloader…", 5)
    yt = bin_dir / "yt-dlp.exe"
    if not check("yt-dlp", yt, ["--version"]):
        yt.unlink(missing_ok=True)
        got = install("yt-dlp", lambda: (_download(YT_DLP_URL, yt, progress), yt)[1])
        if got and check("yt-dlp", got, ["--version"]): paths["yt-dlp"] = got
    else: paths["yt-dlp"] = yt

    # 2. FFmpeg + FFprobe: required for merging/post-processing
    progress("Checking media backend…", 20)
    ff_dir = root / "ffmpeg"
    ffmpeg = _find_executable(ff_dir, ("ffmpeg.exe", "ffmpeg"))
    if not check("FFmpeg", ffmpeg, ["-version"], "ffmpeg version"):
        got = install("FFmpeg", lambda: _install_zip_tool(FFMPEG_URL, "ffmpeg.zip", ff_dir, ("ffmpeg.exe", "ffmpeg"), progress))
        ffmpeg = got or ffmpeg
    if ffmpeg and check("FFmpeg", ffmpeg, ["-version"], "ffmpeg version"):
        paths["ffmpeg"] = ffmpeg
        ffplay = _find_executable(ff_dir, ("ffplay.exe", "ffplay"))
        if ffplay and check("FFplay", ffplay, ["-version"], "ffplay version"): paths["ffplay"] = ffplay
        ffprobe = _find_executable(ff_dir, ("ffprobe.exe", "ffprobe"))
        if ffprobe and check("FFprobe", ffprobe, ["-version"], "ffprobe version"):
            paths["ffprobe"] = ffprobe
        else:
            failures["ffprobe"] = "FFprobe is missing beside FFmpeg"

    # 3. HLS/DASH engine: independently optional so yt-dlp can still launch
    progress("Checking stream engine…", 40)
    n_dir = root / "n_m3u8dl-re"
    n_exe = _find_executable(n_dir, ("N_m3u8DL-RE.exe", "N_m3u8DL-RE"))
    if not check("N_m3u8DL-RE", n_exe, ["--version"]):
        got = install("N_m3u8DL-RE", lambda: _install_zip_tool(N_M3U8_URL, "N_m3u8DL-RE.zip", n_dir, ("N_m3u8DL-RE.exe", "N_m3u8DL-RE"), progress))
        n_exe = got or n_exe
    if n_exe and check("N_m3u8DL-RE", n_exe, ["--version"]): paths["n_m3u8dl-re"] = n_exe

    # 4. Deno is a JS runtime enhancement. Official yt-dlp executables bundle EJS,
    # so a missing Deno must never make the app fail to start.
    progress("Checking JavaScript runtime…", 62)
    deno = bin_dir / "deno.exe"
    if check("Deno", deno, ["--version"], "deno"):
        paths["deno"] = deno
    else:
        deno.unlink(missing_ok=True)
        archive = root / "deno.zip"
        def install_deno():
            _download(DENO_URL, archive, progress, DENO_SHA512)
            temp_dir = root / "_deno_extract"; shutil.rmtree(temp_dir, ignore_errors=True)
            _extract_zip(archive, temp_dir); found = _find_executable(temp_dir, ("deno.exe",))
            if not found: raise BootstrapError("Deno executable was not found after extraction")
            shutil.copy2(found, deno); shutil.rmtree(temp_dir, ignore_errors=True); archive.unlink(missing_ok=True)
            return deno
        got = install("Deno", install_deno)
        if got and check("Deno", got, ["--version"], "deno"): paths["deno"] = got

    # 5. Bento4/mp4decrypt is OPTIONAL. Never include it in fatal startup checks.
    progress("Checking optional decryption helper…", 78)
    bento_dir = root / "bento4"
    mp4decrypt = _find_executable(bento_dir, ("mp4decrypt.exe", "mp4decrypt"))
    if mp4decrypt:
        # Do not reinstall an existing executable merely because a CLI usage
        # probe returns non-zero. mp4decrypt normally requires input/output
        # arguments, so a usage error is expected for an empty probe.
        ok, detail = _probe(mp4decrypt, MP4DECRYPT_PROBE_ARGS)
        progress(f"mp4decrypt: {'ready' if ok else 'installed — usage probe returned non-zero'} — {detail}", None)
        paths["mp4decrypt"] = mp4decrypt
    else:
        got = install("mp4decrypt", lambda: _install_zip_tool(BENTO4_URL, "bento4.zip", bento_dir, ("mp4decrypt.exe", "mp4decrypt"), progress))
        if got:
            paths["mp4decrypt"] = got
            check("mp4decrypt", got, MP4DECRYPT_PROBE_ARGS)
        else:
            failures["mp4decrypt"] = failures.get("mp4decrypt", "Optional tool unavailable")
    # Discover the broader Bento4 toolkit without making any helper mandatory.
    for bname, candidates, probe_args in [
        ("mp4info", ("mp4info.exe","mp4info"), ["--help"]), ("mp4dump", ("mp4dump.exe","mp4dump"), ["--help"]),
        ("mp4edit", ("mp4edit.exe","mp4edit"), ["--help"]), ("mp4extract", ("mp4extract.exe","mp4extract"), ["--help"]),
        ("mp4fragment", ("mp4fragment.exe","mp4fragment"), ["--help"]), ("mp4split", ("mp4split.exe","mp4split"), ["--help"]),
        ("mp4tag", ("mp4tag.exe","mp4tag"), ["--help"]), ("mp4mux", ("mp4mux.exe","mp4mux"), ["--help"]),
    ]:
        exe = _find_executable(bento_dir, candidates)
        if exe:
            ok, detail = _probe(exe, probe_args)
            progress(f"{bname}: {'ready' if ok else 'installed — usage probe returned non-zero'} — {detail}", None)
            paths[bname] = exe

    for path in paths.values(): _make_executable(path)

    if "yt-dlp" not in paths:
        raise BootstrapError("The required yt-dlp downloader could not be prepared. Check your internet connection and run Toolchain → Repair.")
    if "ffmpeg" not in paths:
        progress("FFmpeg is unavailable; downloads can continue where no merge/post-processing is required.", None)

    # Persist a diagnostic summary for the UI and support cases.
    paths["__failures__"] = failures  # type: ignore[assignment]
    progress("Toolchain check complete — application ready", 100)
    return paths

def tool_versions(paths: dict[str, Path]) -> dict[str, str]:
    specs = {
        "yt-dlp": (["--version"], None),
        "n_m3u8dl-re": (["--version"], None),
        "ffmpeg": (["-version"], "ffmpeg version"),
        "deno": (["--version"], "deno"),
        "mp4decrypt": (MP4DECRYPT_PROBE_ARGS, "mp4decrypt"),
        "ffprobe": (["-version"], "ffprobe version"),
        "ffplay": (["-version"], "ffplay version"),
        "mp4mux": (["--help"], None),
        "mp4tag": (["--help"], None),
        "mp4split": (["--help"], None),
        "mp4fragment": (["--help"], None),
        "mp4extract": (["--help"], None),
        "mp4edit": (["--help"], None),
        "mp4dump": (["--help"], None),
        "mp4info": (["--help"], None),
    }
    out: dict[str, str] = {}
    for key, path in paths.items():
        args, marker = specs.get(key, ([], None))
        ok, detail = _probe(path, args, marker)
        out[key] = detail if ok else f"ERROR: {detail}"
    return out
