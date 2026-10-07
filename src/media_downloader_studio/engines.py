from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .config import jobs_dir
from .job_state import url_id
from .key_specs import parse_key_specs
from .command_profiles import add_repeatable


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    args: list[str]


class Engine:
    key: str
    label: str

    def presets(self) -> list[Preset]:
        raise NotImplementedError

    def build(self, url: str, output: Path, options: dict, tools: dict[str, Path]) -> list[str]:
        raise NotImplementedError

    def example(self, preset: str) -> str:
        raise NotImplementedError


class YtDlpEngine(Engine):
    key = "yt-dlp"
    label = "yt-dlp"

    def presets(self) -> list[Preset]:
        return [
            Preset("Best quality", "Best available video + audio, merged to MP4", ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]),
            Preset("Best MP4 compatibility", "Prefer MP4/H.264 video + M4A audio where available", ["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4"]),
            Preset("Best video", "Highest-quality video stream only", ["-f", "bv*"]),
            Preset("Best audio / MP3", "Best audio stream and extract MP3", ["-f", "ba/b", "-x", "--audio-format", "mp3"]),
            Preset("Custom / selected formats", "Use the video/audio format IDs selected in the GUI", []),
            Preset("List formats", "Open the interactive format picker instead of downloading", ["-F"]),
            Preset("Debug / unplayable", "Developer-oriented diagnostic mode", ["-F", "--allow-unplayable-formats", "-v"]),
        ]

    def build(self, url: str, output: Path, options: dict, tools: dict[str, Path]) -> list[str]:
        args = [
            str(tools["yt-dlp"]), "--newline", "--progress", "--no-warnings",
            "--progress-template",
            "download:MDS_PROGRESS:%(progress._percent_str)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s|%(info.title)s",
        ]
        preset = options["preset"]
        preset_map = {p.name: p.args for p in self.presets()}
        args += preset_map[preset]

        # Reliability defaults: resume .part/fragments and use bounded retry backoff.
        if options.get("resume", True):
            args += ["--continue", "--part"]
        if options.get("no_overwrites", True):
            args += ["--no-overwrites"]
        elif options.get("force_overwrites"):
            args += ["--force-overwrites"]
        retries = options.get("retries", 10)
        if retries is not None:
            args += ["--retries", str(retries), "--fragment-retries", str(retries), "--file-access-retries", "3"]
        retry_sleep = int(options.get("retry_sleep", 2) or 0)
        if retry_sleep > 0:
            args += ["--retry-sleep", f"http:exp={retry_sleep}:20", "--retry-sleep", f"fragment:exp={retry_sleep}:20"]
        timeout = int(options.get("http_timeout", 30) or 0)
        if timeout > 0:
            args += ["--socket-timeout", str(timeout)]

        proxy = options.get("proxy_url", "").strip()
        if proxy:
            args += ["--proxy", proxy]
        bandwidth = options.get("bandwidth_limit", "").strip()
        if bandwidth:
            args += ["--limit-rate", bandwidth]

        if options.get("allow_unplayable") and "--allow-unplayable-formats" not in args:
            args += ["--allow-unplayable-formats"]
        if options.get("concurrent_fragments", 1) > 1:
            args += ["--concurrent-fragments", str(options["concurrent_fragments"])]
        if preset not in {"List formats", "Debug / unplayable"}:
            vf = options.get("video_format", "").strip()
            af = options.get("audio_format", "").strip()
            if vf and af:
                args += ["-f", f"{vf}+{af}"]
            elif vf:
                args += ["-f", vf]
            elif af:
                args += ["-f", af]
        if options.get("subtitles"):
            args += ["--write-subs", "--sub-langs", options.get("subtitle_lang", "all")]
        if options.get("cookies_from_browser"):
            args += ["--cookies-from-browser", options["cookies_from_browser"]]
        if tools.get("deno"):
            # Official yt-dlp executables bundle yt-dlp-ejs; enabling only the local JS runtime
            # avoids an unnecessary GitHub fetch on every metadata/download operation.
            args += ["--js-runtimes", f"deno:{tools['deno']}"]
        # Advanced yt-dlp options exposed by the official CLI.
        for flag, key in [("--playlist-items", "playlist_items"), ("--date", "upload_date"),
                          ("--min-filesize", "min_filesize"), ("--max-filesize", "max_filesize"),
                          ("--format-sort", "format_sort"), ("--download-sections", "download_sections")]:
            value = str(options.get(key, "")).strip()
            if value: args += [flag, value]
        rate = str(options.get("rate_limit", "")).strip()
        if rate: args += ["--limit-rate", rate]
        if options.get("write_thumbnail"): args.append("--write-thumbnail")
        if options.get("write_description"): args.append("--write-description")
        if options.get("write_infojson"): args.append("--write-info-json")
        if options.get("write_metadata"): args.append("--embed-metadata")
        if options.get("extract_audio"):
            args += ["-x", "--audio-format", str(options.get("audio_format_output", "mp3"))]
        if options.get("sponsorblock_mark"): args += ["--sponsorblock-mark", options["sponsorblock_mark"]]
        if options.get("sponsorblock_remove"): args += ["--sponsorblock-remove", options["sponsorblock_remove"]]
        if options.get("cookies_file"): args += ["--cookies", str(options["cookies_file"])]
        add_repeatable(args, "--add-header", options.get("headers", ""))

        template = str(output / "%(title)s [%(id)s].%(ext)s")
        args += ["-o", template, url]
        return args

    def example(self, preset: str) -> str:
        mapping = {p.name: "yt-dlp " + " ".join(p.args) + " URL" for p in self.presets()}
        return mapping[preset]


class NM3U8Engine(Engine):
    key = "n_m3u8dl-re"
    label = "N_m3u8DL-RE"

    def presets(self) -> list[Preset]:
        return [
            Preset("Auto best", "Automatically select the best video/audio/subtitle tracks", ["--auto-select"]),
            Preset("1080p + best audio", "Prefer 1080p video and best audio", ["-sv", 'res="1920*":for=best', "-sa", "best"]),
            Preset("Best video + audio", "Explicit best video and best audio selectors", ["-sv", "best", "-sa", "best"]),
            Preset("Best H.264 + AAC", "Prefer broadly compatible AVC/H.264 and AAC tracks", ["-sv", 'codecs="avc1":for=best', "-sa", 'codecs="mp4a":for=best']),
            Preset("All English audio", "Keep all English audio tracks", ["-sv", "best", "-sa", 'lang="en.*":for=all']),
            Preset("All audio tracks", "Keep all available audio tracks", ["-sv", "best", "-sa", "all"]),
            Preset("Live recording", "Optimized live-stream recording defaults", ["--live-perform-as-vod", "--live-keep-segments"]),
            Preset("Diagnostics", "Debug stream parsing and selection", ["--log-level", "DEBUG"]),
        ]

    def build(self, url: str, output: Path, options: dict, tools: dict[str, Path]) -> list[str]:
        tmp_dir = jobs_dir() / "nre-tmp" / url_id(url)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        # Official syntax is: N_m3u8DL-RE <input> [options]. Keep the input first.
        args = [str(tools["n_m3u8dl-re"]), url,
                "--save-dir", str(output), "--tmp-dir", str(tmp_dir),
                "--thread-count", str(max(1, int(options.get("threads", 10)))),
                "--download-retry-count", str(max(0, int(options.get("retries", 3)))),
                "--http-request-timeout", str(max(1, int(options.get("http_timeout", 100)))),
                "--no-ansi-color", "--no-date-info", "--disable-update-check",
                "--ffmpeg-binary-path", str(tools["ffmpeg"])]
        if options.get("skip_download"):
            args.append("--skip-download")
        if options.get("append_url_params"):
            args.append("--append-url-params")
        if options.get("concurrent"):
            args.append("-mt")
        preset_map = {p.name: p.args for p in self.presets()}
        args += preset_map[options["preset"]]
        if options.get("video_selector"):
            args += ["-sv", options["video_selector"]]
        if options.get("audio_selector"):
            args += ["-sa", options["audio_selector"]]
        if options.get("subtitle_selector"):
            args += ["-ss", options["subtitle_selector"]]
        if options.get("subtitle_only"):
            args.append("--sub-only")
        if options.get("subtitle_format") in {"SRT", "VTT"}:
            args += ["--sub-format", options["subtitle_format"]]
        if options.get("mux_mp4"):
            args += ["-M", "format=mp4:muxer=ffmpeg:bin_path=" + str(tools["ffmpeg"])]
        proxy = options.get("proxy_url", "").strip()
        if proxy:
            args += ["--use-system-proxy", "false", "--custom-proxy", proxy]
        elif options.get("proxy_mode") == "system":
            args += ["--use-system-proxy"]
        bandwidth = options.get("bandwidth_limit", "").strip()
        if bandwidth:
            args += ["--max-speed", bandwidth]
        interface = options.get("network_interface", "").strip()
        if interface:
            args += ["--interface", interface]
        range_value = options.get("segment_range", "").strip()
        if range_value:
            args += ["--custom-range", range_value]
        if options.get("live_real_time_merge"):
            args += ["--live-real-time-merge"]
        if options.get("live_record_limit", "").strip():
            args += ["--live-record-limit", options["live_record_limit"].strip()]
        if options.get("vod_select_parts"):
            args += ["--vod-select-parts"]
        if options.get("nre_cookies_file") or options.get("cookies_file"):
            args += ["--cookies", str(options.get("nre_cookies_file") or options.get("cookies_file"))]
        if options.get("base_url"):
            args += ["--base-url", options["base_url"].strip()]
        add_repeatable(args, "-H", options.get("headers", ""))
        if options.get("task_start_at"):
            args += ["--task-start-at", options["task_start_at"].strip()]
        if options.get("live_wait_time"):
            args += ["--live-wait-time", str(options["live_wait_time"])]
        if options.get("live_idle_timeout"):
            args += ["--live-idle-timeout", str(options["live_idle_timeout"])]
        if options.get("live_take_count"):
            args += ["--live-take-count", str(options["live_take_count"])]
        if options.get("live_pipe_mux"):
            args += ["--live-pipe-mux"]
        if options.get("live_perform_as_vod"):
            args += ["--live-perform-as-vod"]
        if options.get("custom_hls_method"):
            args += ["--custom-hls-method", options["custom_hls_method"]]
        if options.get("custom_hls_key"):
            args += ["--custom-hls-key", options["custom_hls_key"]]
        if options.get("custom_hls_iv"):
            args += ["--custom-hls-iv", options["custom_hls_iv"]]
        if options.get("custom_hls_scope"):
            args += ["--custom-hls-scope", options["custom_hls_scope"]]
        for flag, key in [("--drop-video", "drop_video"), ("--drop-audio", "drop_audio"), ("--drop-subtitle", "drop_subtitle"), ("--ad-keyword", "ad_keyword")]:
            if options.get(key): args += [flag, options[key]]
        for spec in options.get("mux_imports", []):
            if spec: args += ["--mux-import", spec]
        if options.get("vod_list_parts"):
            args += ["--vod-list-parts"]
        if options.get("vod_drop_parts"):
            args += ["--vod-drop-parts", options["vod_drop_parts"]]
        if options.get("authorized_decryption"):
            specs = parse_key_specs(options.get("decryption_key_specs", ""),
                                    options.get("decryption_kid", ""),
                                    options.get("decryption_key", ""))
            if specs:
                mp4d = tools.get("mp4decrypt")
                if not mp4d:
                    raise RuntimeError("Authorized decryption was requested, but mp4decrypt is not installed. Open Toolchain → Repair and retry.")
                for spec in specs:
                    args += ["--key", spec]
                args += ["--decryption-engine", "MP4DECRYPT",
                         "--decryption-binary-path", str(mp4d)]
        return args

    def example(self, preset: str) -> str:
        return "N_m3u8DL-RE URL " + " ".join(next(p.args for p in self.presets() if p.name == preset))


ENGINES: dict[str, Engine] = {
    "yt-dlp": YtDlpEngine(),
    "n_m3u8dl-re": NM3U8Engine(),
}


YTDLP_HOST_HINTS = {
    "youtube.com", "youtu.be", "youtube-nocookie.com", "music.youtube.com",
    "vimeo.com", "dailymotion.com", "twitter.com", "x.com", "instagram.com",
    "facebook.com", "fb.watch", "tiktok.com", "twitch.tv", "reddit.com",
}

def classify_url(url: str) -> str:
    lower = url.lower().strip()
    if lower.endswith(".mpd") or ".mpd?" in lower or lower.endswith(".m3u8") or ".m3u8?" in lower or ".m3u8&" in lower:
        return "stream"
    try:
        host = urlparse(url).netloc.lower().split(":", 1)[0].removeprefix("www.")
        if host:
            if any(host == h or host.endswith("." + h) for h in YTDLP_HOST_HINTS):
                return "web"
            return "web"
    except ValueError:
        pass
    return "unknown"

def recommended_engine(url: str) -> str:
    """Choose the engine from the URL type. Manifest URLs go to N_m3u8DL-RE;
    extractor sites and ordinary web URLs go to yt-dlp.
    """
    return "n_m3u8dl-re" if classify_url(url) == "stream" else "yt-dlp"
