"""Human-readable capability catalog derived from the official tool documentation.

The catalog is deliberately data-driven so the GUI can explain what each backend is
for without hard-coding feature descriptions into event handlers.
"""
from __future__ import annotations

TOOL_CAPABILITIES = {
    "yt-dlp": {
        "purpose": "Site-aware downloader for thousands of websites and media services.",
        "strengths": [
            "site extraction and authentication", "format inspection and exact format IDs",
            "playlists/channels/batch URLs", "DASH/HLS/ISM fragment downloads",
            "subtitles and automatic subtitles", "chapters and SponsorBlock integration",
            "metadata, thumbnails and descriptions", "audio extraction through FFmpeg",
            "retries, fragment concurrency, rate limits and resume", "browser cookies and custom headers",
        ],
        "advanced": [
            "format sorting", "download sections", "playlist item ranges", "date/filesize filters",
            "multistream selection", "JSON metadata output", "cookies-from-browser", "proxy and geo options",
            "post-processors and remuxing", "live/playlist handling",
        ],
    },
    "N_m3u8DL-RE": {
        "purpose": "Dedicated HLS/DASH/MSS stream downloader with detailed stream selection.",
        "strengths": [
            "M3U8/DASH/ISM direct manifests", "video/audio/subtitle selectors",
            "custom headers and Netscape cookies", "segment retries and concurrency",
            "VOD section selection/drop", "live recording controls", "real-time merge",
            "custom HLS decryption parameters", "muxing and local media import",
            "network interface binding and proxy support",
        ],
        "advanced": [
            "regex selectors by codec/resolution/language/frame rate", "custom segment ranges",
            "task scheduling", "ad URL keyword matching", "PowerShell completion",
            "configuration files and response files", "subtitle repair and live VTT correction",
        ],
    },
    "FFmpeg / FFprobe": {
        "purpose": "Universal media conversion/muxing backend and machine-readable media inspector.",
        "strengths": [
            "transcoding and stream copy", "format/container conversion", "audio extraction",
            "filters and complex filtergraphs", "stream mapping", "codec/format inspection",
            "protocol and device inspection", "bitstream filters and metadata operations",
        ],
        "advanced": ["codec inventory", "muxer/demuxer inventory", "filter inventory", "JSON probing", "multi-input pipelines"],
    },
    "Bento4": {
        "purpose": "MP4/CENC/DASH/HLS packaging and MP4 structure toolkit.",
        "strengths": [
            "authorized MP4 decryption", "MP4 atom/box inspection", "MP4 metadata editing",
            "fragment/split/extract operations", "MP4 muxing", "DASH packaging", "HLS packaging",
            "MP4-to-HLS/DASH conversion", "encryption/packaging workflows",
        ],
        "advanced": ["mp4info", "mp4dump", "mp4edit", "mp4extract", "mp4fragment", "mp4split", "mp4tag", "mp4dash", "mp4hls"],
    },
}


def all_features_text() -> str:
    lines = []
    for name, data in TOOL_CAPABILITIES.items():
        lines.append(f"{name}\n  {data['purpose']}")
        lines.extend(f"  • {item}" for item in data["strengths"])
        lines.extend(f"  + {item}" for item in data["advanced"])
        lines.append("")
    return "\n".join(lines)
