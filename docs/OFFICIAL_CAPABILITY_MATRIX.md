# Official capability matrix used by Twin Downloader Pro

This matrix is a product-design summary, not a copy of vendor documentation.

| Tool | Primary job | Features surfaced in Twin Downloader Pro |
|---|---|---|
| yt-dlp | Site-aware extraction | URL extraction, format inspection, exact format IDs, playlists, subtitles, cookies, headers, proxy, retries, fragment concurrency, rate limiting, date/size filtering, playlist ranges, sections, metadata, thumbnail/description/info JSON, SponsorBlock, audio extraction |
| N_m3u8DL-RE | Direct HLS/DASH/ISM | Select/drop expressions, cookies, headers, base URL, retries, concurrency, live recording, live merge, VOD parts, custom HLS parameters, custom range, interface binding, proxy, scheduling, mux imports, FFmpeg muxing |
| FFmpeg | Media processing | Mux, remux, transcode, extract audio, filters, stream mapping, format/codec/protocol support |
| FFprobe | Inspection | JSON stream/container inspection, duration, bitrate, codecs, dimensions, sample rate and stream inventory |
| Bento4 | MP4/DASH/HLS toolkit | mp4decrypt, mp4info, mp4dump, mp4edit, mp4extract, mp4fragment, mp4split, mp4tag, mp4mux discovery and diagnostics |

## Design principles

1. A feature must map to a documented backend capability before being exposed.
2. Optional helpers never block startup.
3. Feature-specific missing dependencies are reported at the point of use.
4. Sensitive key values are redacted from generated command previews and logs.
5. Authorized decryption is limited to user-supplied keys; no key extraction or access-control bypass is implemented.
6. Normal website URLs are routed to yt-dlp; direct manifests are routed to the stream engine when appropriate.
7. The application does not pretend that every backend option is safe or useful as a GUI checkbox; low-level expert controls remain available as text fields where that is more reliable.
