# Changelog

## 0.6.8 — Persistent download controls

- Moved Start, Stop, Clear, live progress and download metrics outside the scrollable download columns so primary controls are always visible.
- Kept advanced settings and command configuration scrollable independently.

## 0.6.8 — UI/UX refinement

- Reorganized Authorized Decryption into clear Bento4, N_m3u8DL-RE, action and activity sections.
- Improved spacing, hierarchy, cards, labels, tabs and theme-aware selection states.
- Preserved existing decryption input attributes and backend behavior.

## 0.6.6 — Hard-stop architecture

- Replaced blocking stdout PIPE consumption with a private spool-file reader so descendant FFmpeg/helper processes can never hold the Qt worker hostage by inheriting a pipe.
- First Stop now immediately requests hard process-tree termination; there is no misleading graceful-only phase.
- Added a Windows Job Object with `KILL_ON_JOB_CLOSE` as the primary tree-termination boundary.
- Kept `taskkill /PID /T /F` as an independent Windows fallback for job nesting/breakaway edge cases.
- Added a second-click force path that repeats the kill operation independently.
- Added deterministic polling of process state and output, so completion does not depend on stdout EOF.
- Added cleanup for temporary output spool files and Windows job handles.
- Fixed release/package version metadata so the v0.6.6 archive contains v0.6.6 source.

## 0.6.4 — Twin Downloader Pro

- Reworked Stop into a non-blocking, repeatable two-stage process-tree cancellation.
- First Stop requests graceful termination; second Stop escalates to full process-tree termination.
- Stop no longer blocks the Qt GUI while waiting for a child process.
- Added native Qt/Windows-style action icons and feature tooltips throughout the main workflows.
- Added icons to the main navigation tabs.
- Reworked all themes with theme-specific selected text, hover, disabled, danger/success and widget colors.
- Added a theme-aware Qt palette so native combo/list/table selections remain readable in Light and other themes.
- Light theme selection contrast corrected for inputs, tables, lists, tabs and text editors.
- Application now starts maximized and uses responsive scrolling for lower desktop resolutions.
- Reduced fixed margins and improved tab navigation for compact displays.
- Preserved all v0.6.x downloader, queue, Media Lab, Bento4, proxy and advanced-engine features.

## 0.6.3

- Added Windows process-tree stop fallback.
