from pathlib import Path
import tempfile

from twin_downloader.engines import ENGINES, classify_url, recommended_engine
from twin_downloader.key_specs import parse_key_specs
from twin_downloader.queue_manager import QueueItem, save_queue

assert classify_url("https://youtu.be/FbXOsVByKmk") == "web"
assert recommended_engine("https://youtu.be/FbXOsVByKmk") == "yt-dlp"
assert classify_url("https://example.com/master.m3u8") == "stream"
assert recommended_engine("https://example.com/master.m3u8") == "n_m3u8dl-re"

pair = "53a53c1ed8b7600c07f749ba99c43d72:9e4d30d35b76fafdb8322279faae07cd"
assert parse_key_specs(pair, "", "") == [pair]
assert parse_key_specs("", "53a53c1ed8b7600c07f749ba99c43d72", "9e4d30d35b76fafdb8322279faae07cd") == [pair]
assert parse_key_specs(pair + "\n" + pair, "", "") == [pair]

# Command contracts: advanced options must map to documented flags.
with tempfile.TemporaryDirectory() as td:
    tools = {"yt-dlp": Path(td)/"yt-dlp.exe", "ffmpeg": Path(td)/"ffmpeg.exe", "n_m3u8dl-re": Path(td)/"N_m3u8DL-RE.exe"}
    opts = {"preset":"Best quality", "resume":True, "no_overwrites":True, "retries":3, "retry_sleep":0, "http_timeout":30,
            "threads":8,"concurrent_fragments":8,"subtitles":False,"cookies_from_browser":"","proxy_url":"", "bandwidth_limit":"",
            "allow_unplayable":False,"video_format":"","audio_format":"","playlist_items":"1:3","upload_date":"today-1month",
            "min_filesize":"1M","max_filesize":"2G","rate_limit":"5M","format_sort":"res,fps","download_sections":"*00:10-00:30",
            "write_thumbnail":True,"write_description":True,"write_infojson":True,"write_metadata":True,"extract_audio":False,
            "audio_format_output":"mp3","sponsorblock_mark":"all","sponsorblock_remove":"filler","cookies_file":"cookies.txt","headers":"Referer: https://example.com"}
    cmd = ENGINES["yt-dlp"].build("https://example.com/video", Path(td), opts, tools)
    for flag in ["--playlist-items","--date","--min-filesize","--max-filesize","--limit-rate","--format-sort","--download-sections","--write-thumbnail","--write-description","--write-info-json","--embed-metadata","--sponsorblock-mark","--sponsorblock-remove","--cookies","--add-header"]:
        assert flag in cmd, flag
print("Twin Downloader Pro v0.6 smoke tests: PASS")

# Stop architecture contract: no blocking stdout PIPE and Windows Job Object hooks exist.
runner = Path(__file__).parent / "src" / "twin_downloader" / "process_runner.py"
text = runner.read_text(encoding="utf-8")
assert "stdout=subprocess.PIPE" not in text
assert "class _WindowsJob" in text
assert "_LIMIT_KILL_ON_CLOSE = 0x00002000" in text
assert "taskkill" in text and '"/T", "/F"' in text
assert "stdout=self._log_file" in text
assert "while self.process.poll() is None" in text
print("Stop architecture contract: PASS")
