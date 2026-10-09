# Twin Downloader Pro v0.6.10

Twin Downloader Pro is a Windows x64 GUI media control center built around four complementary tool families:

- **yt-dlp** — site-aware extraction, playlists, format inspection, subtitles, metadata, authentication and post-processing.
- **N_m3u8DL-RE** — direct HLS/DASH/MSS downloading, stream selectors, live recording, VOD section control and muxing.
- **FFmpeg / FFprobe** — media merging, conversion, extraction, probing and codec/container diagnostics.
- **Bento4** — authorized MP4/CENC utilities, MP4 inspection/editing and packaging helpers.

The application automatically routes normal website URLs to yt-dlp and direct `.m3u8` / `.mpd` manifests to the stream-oriented backend when appropriate.

## Major v0.6 features

### Download engine
- Automatic URL/engine routing.
- yt-dlp format inspection dialog with exact video/audio IDs.
- N_m3u8DL-RE selector expressions.
- Resume and fragment retry controls.
- Concurrent fragment/stream downloading.
- Retry backoff and request timeout controls.
- Browser-cookie selection and Netscape cookie-file support.
- Proxy/system-proxy controls.
- Output folder and duplicate protection.
- Command preview with sensitive key redaction.

### yt-dlp advanced controls
- Playlist item ranges.
- Upload-date filtering.
- Minimum/maximum file size.
- Format sorting.
- Download sections.
- SponsorBlock mark/remove.
- Rate limiting.
- Thumbnail/description/info-json output.
- Metadata embedding.
- Audio extraction with selectable output format.
- Custom HTTP headers.

### N_m3u8DL-RE advanced controls
- Video/audio/subtitle selectors.
- Drop video/audio/subtitle expressions.
- Cookies and HTTP headers.
- Base URL.
- Network interface/IP binding.
- Scheduled task start.
- Custom HLS method/key/IV/scope.
- Live wait/idle/take-count controls.
- Live pipe mux and live-as-VOD options.
- VOD part listing/drop controls.
- Ad keyword rules.
- Custom segment ranges.
- Real-time merge.
- MP4 muxing through FFmpeg.
- Authorized user-supplied CENC keys.

### Queue
Persistent sequential queue storing URL, engine and output directory.

### Media Lab
FFprobe JSON inspection for local media files or direct media URLs, plus a capability map explaining the supported tool families.

### Toolchain
Tool binaries live in the application's private Local AppData directory. Startup health checks are bounded. Optional helpers cannot trap the application on a checking screen. Repair uses staging extraction so a failed download does not destroy a working installation.

## Important engine rule

N_m3u8DL-RE is a direct stream downloader. A normal YouTube page URL such as `https://youtu.be/...` should be handled by yt-dlp. The GUI detects this and switches/routs accordingly. A direct HLS/DASH manifest such as `.m3u8` or `.mpd` can be handled by N_m3u8DL-RE.

## Authorized decryption

The application does not extract DRM secrets or bypass access controls. Decryption controls are intended only for media and keys the user is legally authorized to use.

Supported key entry forms include:

- Separate KID/track ID + key.
- `KID:KEY`.
- Multiple `KID:KEY` entries.
- N_m3u8DL-RE key-only form when applicable.

Standalone Bento4 `mp4decrypt` is given explicit ID:key pairs because that tool's CLI requires an ID with each key.

## Installation

1. Extract the ZIP.
2. Run `run_windows.bat` or `launcher.py` using Python 3.11+.
3. The first start prepares the private toolchain.
4. If an optional helper is unavailable, the main application remains usable and the Toolchain tab reports the affected feature.

For a clean portable environment, keep the extracted application directory intact.

## Architecture

`bootstrap.py` handles isolated tool acquisition and health checks.

`engines.py` owns backend command construction.

`process_runner.py` owns bounded process execution, progress parsing and hard process-tree stop handling. It uses a private output spool instead of a blocking stdout pipe, plus a Windows Job Object and taskkill fallback.

`format_probe.py` handles yt-dlp format inspection.

`proxy_manager.py` handles public-proxy discovery/testing.

`media_lab.py` handles FFprobe inspection.

`queue_manager.py` persists the download queue.

`capabilities.py` stores the documented capability map exposed by the GUI.

`key_specs.py` normalizes authorized decryption key forms.

## Documentation basis

The feature catalog and command builders are based on the current official documentation for yt-dlp, N_m3u8DL-RE, FFmpeg/FFprobe and Bento4. The application deliberately exposes useful documented features rather than blindly exposing every low-level switch.

## Testing

Run:

```text
python -m compileall -q src
python tests_smoke.py
```

The smoke suite checks URL routing, advanced command options, key parsing, queue persistence and package-level imports that do not require the Windows GUI runtime.

## Runtime testing limitation

A Linux build environment cannot honestly simulate a native Windows/PySide6 GUI session. Windows GUI rendering, Windows binary downloads and actual media-provider responses must be smoke-tested on Windows.
