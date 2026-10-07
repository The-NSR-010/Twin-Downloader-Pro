from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .bootstrap import tool_versions
from .config import load_settings, save_settings
from .engines import ENGINES, classify_url, recommended_engine
from .format_probe import MediaFormat, YtDlpProbeWorker
from .job_state import append_history, clear_active_job, history, recent_success, save_active_job
from .key_specs import parse_key_specs
from .process_runner import DownloadWorker, display_command
from .proxy_manager import ProxyRecord, ProxyScanWorker
from .themes import THEMES, stylesheet, palette
from .capabilities import all_features_text
from .media_lab import ffprobe_json, summarize_probe
from .queue_manager import QueueItem, load_queue, save_queue

APP_STYLE = r"""
QMainWindow, QWidget { background: #0b1020; color: #e7eaf2; font-family: Segoe UI, Arial; font-size: 10pt; }
QFrame#Card, QGroupBox { background: #11182b; border: 1px solid #24304a; border-radius: 12px; }
QGroupBox { margin-top: 12px; padding: 18px 14px 14px 14px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 7px; color: #aab6d1; }
QLabel#Title { font-size: 24pt; font-weight: 700; color: #ffffff; }
QLabel#Subtitle { color: #91a0bd; font-size: 10pt; }
QLabel#Muted { color: #8491ab; }
QLabel#MetricValue { color: #ffffff; font-size: 12pt; font-weight: 700; }
QLabel#MetricLabel { color: #7f8ba5; font-size: 8.5pt; }
QLineEdit, QComboBox, QSpinBox { background: #0c1324; border: 1px solid #2b3855; border-radius: 8px; padding: 9px; color: #f2f5fb; min-height: 22px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #6d5dfc; }
QComboBox QAbstractItemView { background: #11182b; color: #fff; selection-background-color: #2b3563; }
QPushButton { background: #1b2540; border: 1px solid #334263; border-radius: 9px; padding: 9px 14px; font-weight: 600; min-height: 22px; }
QPushButton:hover { background: #253254; }
QPushButton:disabled { color: #6e7890; background: #121a2e; border-color: #202b43; }
QPushButton#Primary { background: #6d5dfc; border-color: #7c70ff; color: white; }
QPushButton#Danger { background: #4a1d2a; border-color: #7a3044; }
QPushButton#Success { background: #163d31; border-color: #29664e; }
QListWidget, QTableWidget { background: #0b1120; border: 1px solid #24304a; border-radius: 10px; gridline-color: #202b42; }
QListWidget::item { background: #0d1425; border: 1px solid #25324e; border-radius: 10px; padding: 12px; margin: 4px 6px; }
QListWidget::item:selected { background: #202a4a; border-color: #6d5dfc; }
QTableWidget::item { padding: 7px; }
QTableWidget::item:selected { background: #2b3563; }
QHeaderView::section { background: #121a2e; color: #aab6d1; padding: 8px; border: 0; border-bottom: 1px solid #27344e; }
QPlainTextEdit { background: #070b15; border: 1px solid #202b42; border-radius: 10px; color: #cbd5e7; font-family: Consolas, monospace; font-size: 9pt; padding: 5px; }
QProgressBar { background: #0c1324; border: 1px solid #27344e; border-radius: 8px; min-height: 18px; text-align: center; }
QProgressBar::chunk { background: #6d5dfc; border-radius: 7px; }
QCheckBox { spacing: 8px; min-height: 22px; }
QTabWidget::pane { border: 1px solid #24304a; border-radius: 10px; top: -1px; }
QTabBar::tab { background: #0c1324; border: 1px solid #202c45; padding: 10px 18px; margin-right: 4px; border-radius: 7px; }
QTabBar::tab:selected { background: #1b2540; border-color: #6d5dfc; }
QSplitter::handle { background: #141d31; width: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0b1020; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #344260; min-height: 38px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #4b5b80; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def _scroll_wrap(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setWidget(widget)
    area.verticalScrollBar().setSingleStep(22)
    return area


def _std_icon(name: str):
    style = QApplication.style()
    pix = getattr(QStyle, name, QStyle.SP_FileIcon)
    return style.standardIcon(pix)


def _set_tool_button(button: QPushButton, icon_name: str, tooltip: str) -> None:
    button.setIcon(_std_icon(icon_name))
    button.setToolTip(tooltip)
    button.setIconSize(button.sizeHint().boundedTo(button.sizeHint()).size() if False else button.iconSize())


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—"):
        super().__init__(); self.setObjectName("Card")
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 9, 12, 9); lay.setSpacing(2)
        self.value = QLabel(value); self.value.setObjectName("MetricValue")
        caption = QLabel(label); caption.setObjectName("MetricLabel")
        lay.addWidget(self.value); lay.addWidget(caption)


class SetupOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("Card")
        layout = QVBoxLayout(self); layout.setContentsMargins(42, 34, 42, 34)
        self.title = QLabel("Checking private toolchain…"); self.title.setObjectName("Title")
        self.status = QLabel("Validating yt-dlp, N_m3u8DL-RE, FFmpeg, Deno and Bento4."); self.status.setObjectName("Subtitle"); self.status.setWordWrap(True)
        self.bar = QProgressBar(); self.bar.setRange(0, 100)
        layout.addStretch(); layout.addWidget(self.title); layout.addWidget(self.status); layout.addSpacing(12); layout.addWidget(self.bar); layout.addStretch()

    def update_status(self, message: str, value: int | None):
        self.status.setText(message)
        if value is not None: self.bar.setValue(value)


class FormatPickerDialog(QDialog):
    def __init__(self, info: dict, formats: list[MediaFormat], parent=None):
        super().__init__(parent); self.setWindowTitle("Select video and audio formats"); self.resize(1120, 720); self.setMinimumSize(850, 560); self.setStyleSheet(parent.styleSheet() if parent else stylesheet("Midnight"))
        self.video_id = ""; self.audio_id = ""
        root = QVBoxLayout(self)
        title = QLabel(info.get("title") or "Available formats"); title.setObjectName("Title"); title.setWordWrap(True)
        meta = QLabel(f"Choose exact streams • {len(formats)} formats detected"); meta.setObjectName("Subtitle")
        root.addWidget(title); root.addWidget(meta)
        self.video_table = self._table(); self.audio_table = self._table()
        self._populate(self.video_table, [f for f in formats if f.kind in {"Video", "Video+Audio"}]); self._populate(self.audio_table, [f for f in formats if f.kind == "Audio"])
        split = QSplitter(Qt.Vertical)
        for name, table in [("Video / combined streams", self.video_table), ("Audio-only streams", self.audio_table)]:
            box = QGroupBox(name); lay = QVBoxLayout(box); lay.addWidget(table); split.addWidget(box)
        split.setSizes([390, 230]); root.addWidget(split, 1)
        hint = QLabel("For video-only + audio-only selections, yt-dlp merges the chosen streams with FFmpeg."); hint.setObjectName("Muted"); hint.setWordWrap(True); root.addWidget(hint)
        row = QHBoxLayout(); cancel = QPushButton("Cancel"); use = QPushButton("Use selected formats"); use.setObjectName("Primary"); row.addStretch(); row.addWidget(cancel); row.addWidget(use); root.addLayout(row)
        cancel.clicked.connect(self.reject); use.clicked.connect(self._accept_selection); self.video_table.doubleClicked.connect(lambda *_: self._accept_selection())

    @staticmethod
    def _table() -> QTableWidget:
        t = QTableWidget(0, 10); t.setHorizontalHeaderLabels(["ID", "Type", "Resolution", "FPS", "Codec", "Ext", "Bitrate", "Size", "Language", "Note"])
        t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setSelectionMode(QAbstractItemView.SingleSelection); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.verticalHeader().setVisible(False); t.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        h = t.horizontalHeader(); h.setSectionResizeMode(QHeaderView.ResizeToContents); h.setSectionResizeMode(9, QHeaderView.Stretch)
        return t

    @staticmethod
    def _populate(table: QTableWidget, formats: list[MediaFormat]):
        table.setRowCount(len(formats))
        for row, f in enumerate(formats):
            vals = [f.format_id, f.kind, f.resolution, f.fps, f.codec, f.ext, f.bitrate, f.size, f.language, f.note]
            for col, value in enumerate(vals): table.setItem(row, col, QTableWidgetItem(value))
        if table.rowCount(): table.selectRow(0)

    def _selected_id(self, table: QTableWidget) -> str:
        rows = table.selectionModel().selectedRows(); return table.item(rows[0].row(), 0).text() if rows else ""

    def _accept_selection(self):
        self.video_id = self._selected_id(self.video_table); self.audio_id = self._selected_id(self.audio_table)
        if not self.video_id and not self.audio_id: QMessageBox.warning(self, "Choose a format", "Select at least one stream."); return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings(); self.tools: dict[str, Path] = {}; self.worker: DownloadWorker | None = None; self.probe_worker: YtDlpProbeWorker | None = None; self.proxy_worker: ProxyScanWorker | None = None
        self._current_url = ""; self._force_redownload = False; self._saw_encryption_hint = False; self.queue_items = load_queue(); self.queue_running = False
        self.setWindowTitle("Twin Downloader Pro"); self.resize(1500, 960); self.setMinimumSize(900, 600); self.setStyleSheet(stylesheet(self.settings.get("theme", "Midnight"))); QApplication.instance().setPalette(palette(self.settings.get("theme", "Midnight")))
        self._build_ui(); self._apply_icons(); self._connect_signals(); self._refresh_presets(); self._refresh_history(); self._update_command()

    def _build_ui(self):
        central = QWidget(); root = QVBoxLayout(central); root.setContentsMargins(16, 12, 16, 12); root.setSpacing(9)
        header = QHBoxLayout(); title_col = QVBoxLayout(); title_col.setSpacing(2)
        title = QLabel("Twin Downloader Pro"); title.setObjectName("Title"); subtitle = QLabel("Professional media control center • extraction • streaming • processing • diagnostics"); subtitle.setObjectName("Subtitle")
        title_col.addWidget(title); title_col.addWidget(subtitle); header.addLayout(title_col); header.addStretch(); self.status_badge = QLabel("●  Toolchain: checking"); self.status_badge.setObjectName("Muted"); header.addWidget(self.status_badge, alignment=Qt.AlignTop); header.addSpacing(12); header.addWidget(QLabel("Theme"), alignment=Qt.AlignTop); self.theme_combo=QComboBox(); self.theme_combo.addItems(list(THEMES)); self.theme_combo.setCurrentText(self.settings.get("theme","Midnight") if self.settings.get("theme","Midnight") in THEMES else "Midnight"); self.theme_combo.setMinimumWidth(125); header.addWidget(self.theme_combo, alignment=Qt.AlignTop); root.addLayout(header)
        self.tabs = QTabWidget(); self.tabs.setUsesScrollButtons(True); self.tabs.setDocumentMode(True); self.tabs.addTab(self._build_download_tab(), "Download"); self.tabs.addTab(self._build_advanced_tab(), "Advanced"); self.tabs.addTab(self._build_queue_tab(), "Queue"); self.tabs.addTab(self._build_media_lab_tab(), "Media Lab"); self.tabs.addTab(self._build_proxy_tab(), "Proxy Lab"); self.tabs.addTab(self._build_decrypt_tab(), "Authorized Decryption"); self.tabs.addTab(self._build_history_tab(), "History"); self.tabs.addTab(self._build_debug_tab(), "Live Console"); self.tabs.addTab(self._build_toolchain_tab(), "Toolchain"); root.addWidget(self.tabs, 1)
        self.setCentralWidget(central); self.overlay = SetupOverlay(central); self.overlay.setGeometry(central.rect()); self.overlay.raise_(); self.overlay.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay") and self.overlay.isVisible():
            self.overlay.setGeometry(self.centralWidget().rect())

    def _build_download_tab(self):
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(8,10,8,8); outer.setSpacing(12)
        source = QFrame(); source.setObjectName("Card"); sl = QGridLayout(source); sl.setContentsMargins(16,14,16,14); sl.setHorizontalSpacing(10); sl.setVerticalSpacing(9)
        sl.addWidget(QLabel("ENGINE"),0,0); self.engine_combo = QComboBox(); self.engine_combo.addItem("yt-dlp","yt-dlp"); self.engine_combo.addItem("N_m3u8DL-RE","n_m3u8dl-re"); self.engine_combo.setCurrentIndex(0 if self.settings.get("tool")=="yt-dlp" else 1); sl.addWidget(self.engine_combo,0,1)
        self.url_kind = QLabel("Waiting for URL"); self.url_kind.setObjectName("Muted"); sl.addWidget(self.url_kind,0,2,alignment=Qt.AlignRight)
        self.url_input = QLineEdit(); self.url_input.setPlaceholderText("Paste a supported web URL, direct media URL, .m3u8 or .mpd manifest…"); self.inspect_btn = QPushButton("Inspect formats"); sl.addWidget(self.url_input,1,0,1,2); sl.addWidget(self.inspect_btn,1,2); sl.setColumnStretch(1,1); outer.addWidget(source)
        # Persistent primary action bar: outside both scrollable columns so the main controls are always visible.
        run=QFrame(); run.setObjectName("Card"); r=QVBoxLayout(run); r.setContentsMargins(14,10,14,10); r.setSpacing(7)
        top_run=QHBoxLayout(); top_run.setSpacing(10); self.current_item=QLabel("Ready"); self.current_item.setObjectName("Muted"); self.current_item.setWordWrap(True); top_run.addWidget(self.current_item,1)
        self.start_btn=QPushButton("▶  Start download"); self.start_btn.setObjectName("Primary"); self.start_btn.setMinimumHeight(36); self.stop_btn=QPushButton("■  Stop"); self.stop_btn.setObjectName("Danger"); self.stop_btn.setMinimumHeight(36); self.clear_btn=QPushButton("Clear"); self.clear_btn.setMinimumHeight(36); top_run.addWidget(self.start_btn); top_run.addWidget(self.stop_btn); top_run.addWidget(self.clear_btn); r.addLayout(top_run)
        progress_row=QHBoxLayout(); progress_row.setSpacing(10); self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setFormat("Ready"); self.progress.setMinimumHeight(20); progress_row.addWidget(self.progress,1); self.run_status=QLabel("No active job"); self.run_status.setObjectName("Muted"); self.run_status.setMinimumWidth(220); progress_row.addWidget(self.run_status); r.addLayout(progress_row)
        metrics=QHBoxLayout(); metrics.setSpacing(8); self.metric_total=MetricCard("TOTAL SIZE"); self.metric_done=MetricCard("DOWNLOADED"); self.metric_speed=MetricCard("SPEED"); self.metric_eta=MetricCard("ETA"); [metrics.addWidget(w) for w in [self.metric_total,self.metric_done,self.metric_speed,self.metric_eta]]; r.addLayout(metrics)
        outer.addWidget(run)
        splitter = QSplitter(Qt.Horizontal); splitter.setChildrenCollapsible(False)
        left = QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,8,0); ll.setSpacing(12)
        presets=QGroupBox("Command presets"); pl=QVBoxLayout(presets); self.preset_list=QListWidget(); self.preset_list.setMinimumHeight(275); self.preset_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.preset_list.verticalScrollBar().setSingleStep(18); pl.addWidget(self.preset_list); self.preset_hint=QLabel(); self.preset_hint.setObjectName("Muted"); self.preset_hint.setWordWrap(True); pl.addWidget(self.preset_hint); ll.addWidget(presets)
        media=QGroupBox("Media & reliability options"); g=QGridLayout(media); g.setHorizontalSpacing(12); g.setVerticalSpacing(10); g.setColumnStretch(1,1)
        g.addWidget(QLabel("Video / selector"),0,0); self.video_select=QLineEdit(); g.addWidget(self.video_select,0,1,1,2)
        g.addWidget(QLabel("Audio / selector"),1,0); self.audio_select=QLineEdit(); g.addWidget(self.audio_select,1,1,1,2)
        g.addWidget(QLabel("Subtitles"),2,0); self.subtitle_check=QCheckBox("Download"); self.subtitle_lang=QLineEdit("en"); self.subtitle_lang.setMaximumWidth(120); g.addWidget(self.subtitle_check,2,1); g.addWidget(self.subtitle_lang,2,2)
        g.addWidget(QLabel("Threads"),3,0); self.threads=QSpinBox(); self.threads.setRange(1,64); self.threads.setValue(int(self.settings.get("threads",8))); self.concurrent=QCheckBox("Concurrent fragments / streams"); self.concurrent.setChecked(True); g.addWidget(self.threads,3,1); g.addWidget(self.concurrent,3,2)
        g.addWidget(QLabel("Retries"),4,0); self.retries=QSpinBox(); self.retries.setRange(0,100); self.retries.setValue(int(self.settings.get("retries",10))); self.retry_sleep=QSpinBox(); self.retry_sleep.setRange(0,30); self.retry_sleep.setSuffix(" s base backoff"); self.retry_sleep.setValue(int(self.settings.get("retry_sleep",2))); g.addWidget(self.retries,4,1); g.addWidget(self.retry_sleep,4,2)
        g.addWidget(QLabel("HTTP timeout"),5,0); self.http_timeout=QSpinBox(); self.http_timeout.setRange(5,300); self.http_timeout.setSuffix(" s"); self.http_timeout.setValue(int(self.settings.get("http_timeout",30))); self.bandwidth=QLineEdit(self.settings.get("bandwidth_limit","")); self.bandwidth.setPlaceholderText("Optional limit, e.g. 5M"); g.addWidget(self.http_timeout,5,1); g.addWidget(self.bandwidth,5,2)
        self.resume_check=QCheckBox("Resume interrupted/partial downloads"); self.resume_check.setChecked(bool(self.settings.get("resume",True))); self.allow_unplayable=QCheckBox("Allow/list unplayable formats (diagnostic only)"); self.mux_mp4=QCheckBox("Prefer MP4 muxing when supported"); self.mux_mp4.setChecked(True); g.addWidget(self.resume_check,6,0,1,3); g.addWidget(self.allow_unplayable,7,0,1,3); g.addWidget(self.mux_mp4,8,0,1,3)
        g.addWidget(QLabel("Browser cookies"),9,0); self.cookies_browser=QComboBox(); self.cookies_browser.addItems(["","chrome","edge","firefox","brave"]); g.addWidget(self.cookies_browser,9,1,1,2); g.addWidget(QLabel("Advanced stream"),10,0); self.segment_range=QLineEdit(); self.segment_range.setPlaceholderText("Optional segment range, e.g. 00:05-01:30"); g.addWidget(self.segment_range,10,1,1,2); self.live_mode=QCheckBox("Live recording mode"); self.live_real_time=QCheckBox("Real-time merge"); g.addWidget(self.live_mode,11,0,1,2); g.addWidget(self.live_real_time,11,2); ll.addWidget(media)
        proxybox=QGroupBox("Network proxy"); pg=QGridLayout(proxybox); self.proxy_mode=QComboBox(); self.proxy_mode.addItem("Off","off"); self.proxy_mode.addItem("Manual / selected","manual"); self.proxy_mode.addItem("System proxy (N_m3u8 only)","system"); idx=max(0,self.proxy_mode.findData(self.settings.get("proxy_mode","off"))); self.proxy_mode.setCurrentIndex(idx); self.proxy_input=QLineEdit(self.settings.get("proxy_url","")); self.proxy_input.setPlaceholderText("http://host:port or socks5://host:port"); self.open_proxy_tab=QPushButton("Find/test free proxies…"); pg.addWidget(QLabel("Mode"),0,0); pg.addWidget(self.proxy_mode,0,1); pg.addWidget(self.proxy_input,1,0,1,2); pg.addWidget(self.open_proxy_tab,2,0,1,2); ll.addWidget(proxybox); ll.addStretch()
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(8,0,0,0); rl.setSpacing(12)
        cmd=QGroupBox("Generated backend command"); cl=QVBoxLayout(cmd); self.command_preview=QPlainTextEdit(); self.command_preview.setReadOnly(True); self.command_preview.setMinimumHeight(145); self.command_preview.setMaximumHeight(220); cl.addWidget(self.command_preview); cr=QHBoxLayout(); self.copy_command=QPushButton("Copy command"); self.open_output=QPushButton("Open output folder"); cr.addWidget(self.copy_command); cr.addWidget(self.open_output); cr.addStretch(); cl.addLayout(cr); rl.addWidget(cmd)
        out=QGroupBox("Output folder"); ol=QHBoxLayout(out); self.output_input=QLineEdit(self.settings.get("output_dir","")); self.browse_output=QPushButton("Browse…"); ol.addWidget(self.output_input,1); ol.addWidget(self.browse_output); rl.addWidget(out)
        live=QGroupBox("Live progress feed"); lv=QVBoxLayout(live); self.live_feed=QPlainTextEdit(); self.live_feed.setReadOnly(True); self.live_feed.setMaximumBlockCount(800); self.live_feed.setMinimumHeight(180); lv.addWidget(self.live_feed); rl.addWidget(live); rl.addStretch()
        splitter.addWidget(_scroll_wrap(left)); splitter.addWidget(_scroll_wrap(right)); splitter.setSizes([620,700]); splitter.setStretchFactor(0,1); splitter.setStretchFactor(1,1); outer.addWidget(splitter,1); return page

    def _build_proxy_tab(self):
        page=QWidget(); layout=QVBoxLayout(page); banner=QLabel("Choose one mode: Manual = you paste a proxy; Auto = Studio fetches public candidates from the internet, tests them from this PC, then optionally selects the fastest alive HTTP/HTTPS proxy. SOCKS candidates are displayed but require backend support."); banner.setWordWrap(True); banner.setObjectName("Subtitle"); layout.addWidget(banner)
        controls=QFrame(); controls.setObjectName("Card"); g=QGridLayout(controls); self.proxy_country=QLineEdit(); self.proxy_country.setPlaceholderText("ISO-2 country: IN, US, DE"); self.proxy_protocol=QComboBox(); self.proxy_protocol.addItems(["HTTP","HTTPS","SOCKS4","SOCKS5"]); self.proxy_protocol.setCurrentText(str(self.settings.get("proxy_protocol","http")).upper()); self.proxy_limit=QSpinBox(); self.proxy_limit.setRange(5,100); self.proxy_limit.setValue(int(self.settings.get("proxy_max_test",30))); self.proxy_auto=QCheckBox("Automatically select fastest alive HTTP proxy"); self.proxy_auto.setChecked(bool(self.settings.get("proxy_auto_select",True))); self.scan_proxy_btn=QPushButton("Fetch + test public proxies"); self.scan_proxy_btn.setObjectName("Primary"); self.use_proxy_btn=QPushButton("Use selected proxy"); self.proxy_status=QLabel("Idle"); self.proxy_status.setObjectName("Muted"); g.addWidget(QLabel("Country"),0,0); g.addWidget(self.proxy_country,0,1); g.addWidget(QLabel("Protocol"),0,2); g.addWidget(self.proxy_protocol,0,3); g.addWidget(QLabel("Test count"),1,0); g.addWidget(self.proxy_limit,1,1); g.addWidget(self.proxy_auto,2,0,1,2); g.addWidget(self.scan_proxy_btn,2,2); g.addWidget(self.use_proxy_btn,2,3); g.addWidget(self.proxy_status,3,0,1,4); layout.addWidget(controls)
        self.proxy_table=QTableWidget(0,9); self.proxy_table.setHorizontalHeaderLabels(["Proxy","Protocol","Country","City","Anonymity","Uptime","Latency","Alive","Source"]); self.proxy_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.proxy_table.setSelectionMode(QAbstractItemView.SingleSelection); self.proxy_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.proxy_table.verticalHeader().setVisible(False); self.proxy_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); h=self.proxy_table.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.Stretch); [h.setSectionResizeMode(i,QHeaderView.ResizeToContents) for i in range(1,9)]; layout.addWidget(self.proxy_table,1); return page

    def _build_decrypt_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(12)

        # Compact hero / safety banner.
        banner = QFrame(); banner.setObjectName("InfoCard")
        bl = QHBoxLayout(banner); bl.setContentsMargins(16, 12, 16, 12); bl.setSpacing(12)
        badge = QLabel("AUTHORIZED USE"); badge.setObjectName("Badge")
        banner_text = QLabel("Supply your own authorized keys only. Twin Downloader Pro does not obtain, extract, or bypass DRM credentials.")
        banner_text.setObjectName("Subtitle"); banner_text.setWordWrap(True)
        bl.addWidget(badge, 0, Qt.AlignTop); bl.addWidget(banner_text, 1)
        outer.addWidget(banner)

        # Bento4 workspace.
        box = QGroupBox("Bento4  •  MP4 decryption")
        box.setObjectName("FeatureGroup")
        root = QVBoxLayout(box); root.setContentsMargins(16, 22, 16, 16); root.setSpacing(12)

        files = QFrame(); files.setObjectName("InnerCard")
        fg = QGridLayout(files); fg.setContentsMargins(12, 12, 12, 12); fg.setHorizontalSpacing(10); fg.setVerticalSpacing(8); fg.setColumnStretch(1, 1)
        self.dec_input = QLineEdit(); self.dec_input.setPlaceholderText("Select the encrypted .mp4 / .m4s file")
        self.dec_output = QLineEdit(); self.dec_output.setPlaceholderText("Where the decrypted MP4 should be written")
        binp = QPushButton("Browse…"); bout = QPushButton("Choose…")
        fg.addWidget(QLabel("INPUT MEDIA"), 0, 0); fg.addWidget(self.dec_input, 0, 1); fg.addWidget(binp, 0, 2)
        fg.addWidget(QLabel("OUTPUT FILE"), 1, 0); fg.addWidget(self.dec_output, 1, 1); fg.addWidget(bout, 1, 2)
        root.addWidget(files)

        keys = QFrame(); keys.setObjectName("InnerCard")
        kg = QGridLayout(keys); kg.setContentsMargins(12, 12, 12, 12); kg.setHorizontalSpacing(10); kg.setVerticalSpacing(8); kg.setColumnStretch(1, 1)
        key_title = QLabel("KEY INPUT"); key_title.setObjectName("SectionLabel")
        key_hint = QLabel("Use either the two-field form or the multi-line KID:KEY form below."); key_hint.setObjectName("Muted")
        self.dec_kid = QLineEdit(); self.dec_kid.setPlaceholderText("32-character KID / track ID")
        self.dec_key = QLineEdit(); self.dec_key.setPlaceholderText("32-character 128-bit key"); self.dec_key.setEchoMode(QLineEdit.Password)
        self.dec_key_specs = QPlainTextEdit(); self.dec_key_specs.setPlaceholderText("One per line:\nKID:KEY\nKID:KEY\n\nExample: 53a53c1ed8b7600c07f749ba99c43d72:9e4d30d35b76fafdb8322279faae07cd")
        self.dec_key_specs.setMaximumHeight(96); self.dec_key_specs.setMinimumHeight(78)
        kg.addWidget(key_title, 0, 0, 1, 2); kg.addWidget(key_hint, 1, 0, 1, 2)
        kg.addWidget(QLabel("KID / TRACK ID"), 2, 0); kg.addWidget(self.dec_kid, 2, 1)
        kg.addWidget(QLabel("KEY"), 3, 0); kg.addWidget(self.dec_key, 3, 1)
        kg.addWidget(QLabel("MULTIPLE KEYS"), 4, 0, Qt.AlignTop); kg.addWidget(self.dec_key_specs, 4, 1)
        root.addWidget(keys)

        key_note = QLabel("Accepted: separate KID + key, one KID:KEY, or multiple KID:KEY lines. Standalone mp4decrypt requires an ID with every key.")
        key_note.setObjectName("Muted"); key_note.setWordWrap(True)
        root.addWidget(key_note)

        action = QFrame(); action.setObjectName("ActionCard")
        ag = QHBoxLayout(action); ag.setContentsMargins(12, 10, 12, 10); ag.setSpacing(10)
        self.dec_authorized = QCheckBox("I confirm I am authorized to decrypt this media")
        self.dec_authorized.setToolTip("Required before an authorized decryption job can start.")
        self.dec_run = QPushButton("Decrypt media"); self.dec_run.setObjectName("Primary"); self.dec_run.setMinimumWidth(150)
        ag.addWidget(self.dec_authorized, 1); ag.addWidget(self.dec_run)
        root.addWidget(action)
        outer.addWidget(box)

        # N_m3u8DL-RE integration kept separate because its key syntax and workflow differ.
        nbox = QGroupBox("N_m3u8DL-RE  •  Authorized CENC keys")
        nbox.setObjectName("FeatureGroup")
        ng = QVBoxLayout(nbox); ng.setContentsMargins(16, 22, 16, 16); ng.setSpacing(10)
        self.nre_dec_enable = QCheckBox("Enable user-supplied decryption keys for N_m3u8DL-RE downloads")
        self.nre_dec_enable.setToolTip("Pass only keys that you are authorized to use for the selected media.")
        ng.addWidget(self.nre_dec_enable)
        nfields = QFrame(); nfields.setObjectName("InnerCard")
        nfg = QGridLayout(nfields); nfg.setContentsMargins(12, 12, 12, 12); nfg.setHorizontalSpacing(10); nfg.setVerticalSpacing(8); nfg.setColumnStretch(1, 1)
        self.nre_dec_kid = QLineEdit(); self.nre_dec_kid.setPlaceholderText("Optional KID / track ID")
        self.nre_dec_key = QLineEdit(); self.nre_dec_key.setPlaceholderText("Optional key"); self.nre_dec_key.setEchoMode(QLineEdit.Password)
        self.nre_dec_specs = QPlainTextEdit(); self.nre_dec_specs.setPlaceholderText("KID:KEY (one per line)\nOR\nKEY-only when the same key applies to all tracks")
        self.nre_dec_specs.setMaximumHeight(76)
        nfg.addWidget(QLabel("KID / TRACK ID"), 0, 0); nfg.addWidget(self.nre_dec_kid, 0, 1)
        nfg.addWidget(QLabel("KEY"), 1, 0); nfg.addWidget(self.nre_dec_key, 1, 1)
        nfg.addWidget(QLabel("KEY SPECS"), 2, 0, Qt.AlignTop); nfg.addWidget(self.nre_dec_specs, 2, 1)
        ng.addWidget(nfields)
        nhelp = QLabel("N_m3u8DL-RE accepts its documented key forms; key-only input is intentionally kept here and is not used for standalone mp4decrypt.")
        nhelp.setObjectName("Muted"); nhelp.setWordWrap(True); ng.addWidget(nhelp)
        outer.addWidget(nbox)

        logbox = QGroupBox("Decryption activity")
        logbox.setObjectName("FeatureGroup")
        ll = QVBoxLayout(logbox); ll.setContentsMargins(16, 22, 16, 12)
        self.dec_log = QPlainTextEdit(); self.dec_log.setReadOnly(True); self.dec_log.setMaximumBlockCount(1500); self.dec_log.setPlaceholderText("Authorized decryption output will appear here…")
        ll.addWidget(self.dec_log, 1); outer.addWidget(logbox, 1)

        binp.clicked.connect(self._browse_dec_input); bout.clicked.connect(self._browse_dec_output); self.dec_run.clicked.connect(self._run_decrypt)
        return page

    def _build_history_tab(self):
        page=QWidget(); lay=QVBoxLayout(page); row=QHBoxLayout(); info=QLabel("Recent local job history used for duplicate warnings and troubleshooting."); info.setObjectName("Subtitle"); self.history_refresh=QPushButton("Refresh"); row.addWidget(info); row.addStretch(); row.addWidget(self.history_refresh); lay.addLayout(row); self.history_table=QTableWidget(0,5); self.history_table.setHorizontalHeaderLabels(["Time","Status","Engine","URL","Output"]); self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.history_table.verticalHeader().setVisible(False); h=self.history_table.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.ResizeToContents); h.setSectionResizeMode(1,QHeaderView.ResizeToContents); h.setSectionResizeMode(2,QHeaderView.ResizeToContents); h.setSectionResizeMode(3,QHeaderView.Stretch); h.setSectionResizeMode(4,QHeaderView.Stretch); lay.addWidget(self.history_table,1); return page

    def _build_debug_tab(self):
        page=QWidget(); lay=QVBoxLayout(page); tip=QLabel("Full backend output. Sensitive decryption keys are redacted from displayed commands."); tip.setObjectName("Subtitle"); lay.addWidget(tip); self.debug=QPlainTextEdit(); self.debug.setReadOnly(True); self.debug.setMaximumBlockCount(5000); lay.addWidget(self.debug,1); clear=QPushButton("Clear console"); clear.clicked.connect(self.debug.clear); row=QHBoxLayout(); row.addWidget(clear); row.addStretch(); lay.addLayout(row); return page

    def _build_toolchain_tab(self):
        page=QWidget(); lay=QVBoxLayout(page); info=QLabel("Every application start validates the private binaries. Missing or broken tools are repaired in the app data directory; global PATH is not modified."); info.setObjectName("Subtitle"); info.setWordWrap(True); lay.addWidget(info); self.tool_status_list=QListWidget(); self.tool_status_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); lay.addWidget(self.tool_status_list,1); return page

    def _build_advanced_tab(self):
        page = QWidget(); outer = QVBoxLayout(page); scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); lay = QVBoxLayout(body)
        yt = QGroupBox("yt-dlp — extraction, filtering, metadata and post-processing"); g = QGridLayout(yt); g.setColumnStretch(1,1); g.setColumnStretch(3,1)
        self.adv_playlist=QLineEdit(); self.adv_playlist.setPlaceholderText("1:10,15,-2"); self.adv_date=QLineEdit(); self.adv_date.setPlaceholderText("YYYYMMDD or today-1month")
        self.adv_min_size=QLineEdit(); self.adv_max_size=QLineEdit(); self.adv_rate=QLineEdit(); self.adv_rate.setPlaceholderText("5M"); self.adv_format_sort=QLineEdit(); self.adv_format_sort.setPlaceholderText("res,fps,hdr:12,codec"); self.adv_sections=QLineEdit(); self.adv_sections.setPlaceholderText("*00:05-00:30")
        self.adv_mark=QLineEdit(); self.adv_mark.setPlaceholderText("all,-filler"); self.adv_remove=QLineEdit(); self.adv_remove.setPlaceholderText("sponsor,selfpromo"); self.adv_cookies=QLineEdit(); self.adv_cookies.setPlaceholderText("Optional Netscape cookies.txt")
        self.adv_headers=QPlainTextEdit(); self.adv_headers.setPlaceholderText("One header per line: User-Agent: ...\nReferer: https://..."); self.adv_headers.setMaximumHeight(70)
        self.adv_thumbnail=QCheckBox("Thumbnail"); self.adv_description=QCheckBox("Description"); self.adv_infojson=QCheckBox("Info JSON"); self.adv_metadata=QCheckBox("Embed metadata"); self.adv_extract=QCheckBox("Extract audio")
        self.adv_audio_format=QComboBox(); self.adv_audio_format.addItems(["mp3","m4a","opus","aac","flac","wav","alac","vorbis"])
        rows=[("Playlist items",self.adv_playlist,"Upload date",self.adv_date),("Min file size",self.adv_min_size,"Max file size",self.adv_max_size),("Rate limit",self.adv_rate,"Format sort",self.adv_format_sort),("Download sections",self.adv_sections,"SponsorBlock mark",self.adv_mark),("SponsorBlock remove",self.adv_remove,"Cookies file",self.adv_cookies)]
        for r,(a,w,b,x) in enumerate(rows): g.addWidget(QLabel(a),r,0); g.addWidget(w,r,1); g.addWidget(QLabel(b),r,2); g.addWidget(x,r,3)
        g.addWidget(QLabel("Headers"),5,0); g.addWidget(self.adv_headers,5,1,1,3); g.addWidget(self.adv_thumbnail,6,0); g.addWidget(self.adv_description,6,1); g.addWidget(self.adv_infojson,6,2); g.addWidget(self.adv_metadata,6,3); g.addWidget(self.adv_extract,7,0); g.addWidget(QLabel("Audio format"),7,1); g.addWidget(self.adv_audio_format,7,2); lay.addWidget(yt)
        n=QGroupBox("N_m3u8DL-RE — stream selection, live control, HLS and network"); ng=QGridLayout(n); ng.setColumnStretch(1,1); ng.setColumnStretch(3,1)
        self.adv_n_headers=QPlainTextEdit(); self.adv_n_headers.setPlaceholderText("User-Agent: ...\nReferer: ..."); self.adv_n_headers.setMaximumHeight(65); self.adv_n_cookies=QLineEdit(); self.adv_n_cookies.setPlaceholderText("Netscape cookies.txt"); self.adv_base_url=QLineEdit(); self.adv_interface=QLineEdit(); self.adv_task=QLineEdit(); self.adv_task.setPlaceholderText("yyyyMMddHHmmss")
        self.adv_hls_method=QComboBox(); self.adv_hls_method.addItems(["","AES_128","AES_128_ECB","CENC","CHACHA20","NONE","SAMPLE_AES","SAMPLE_AES_CTR"]); self.adv_hls_key=QLineEdit(); self.adv_hls_iv=QLineEdit(); self.adv_hls_scope=QComboBox(); self.adv_hls_scope.addItems(["","ALL","VIDEO","AUDIO"])
        self.adv_live_wait=QSpinBox(); self.adv_live_wait.setRange(0,3600); self.adv_live_idle=QSpinBox(); self.adv_live_idle.setRange(0,86400); self.adv_live_take=QSpinBox(); self.adv_live_take.setRange(0,1000); self.adv_live_take.setValue(16); self.adv_drop_video=QLineEdit(); self.adv_drop_audio=QLineEdit(); self.adv_drop_sub=QLineEdit(); self.adv_ad_keyword=QLineEdit(); self.adv_vod_list=QCheckBox("List VOD parts only"); self.adv_vod_drop=QLineEdit(); self.adv_live_pipe=QCheckBox("Live pipe mux"); self.adv_live_vod=QCheckBox("Treat live as VOD"); self.adv_append=QCheckBox("Append URL query parameters to segments")
        rows=[("Cookies",self.adv_n_cookies,"Base URL",self.adv_base_url),("Interface/IP",self.adv_interface,"Task start",self.adv_task),("HLS method",self.adv_hls_method,"HLS scope",self.adv_hls_scope),("HLS key",self.adv_hls_key,"HLS IV",self.adv_hls_iv),("Drop video",self.adv_drop_video,"Drop audio",self.adv_drop_audio),("Drop subtitle",self.adv_drop_sub,"Ad keyword",self.adv_ad_keyword),("VOD drop IDs",self.adv_vod_drop,"Live wait sec",self.adv_live_wait)]
        for r,(a,w,b,x) in enumerate(rows): ng.addWidget(QLabel(a),r,0); ng.addWidget(w,r,1); ng.addWidget(QLabel(b),r,2); ng.addWidget(x,r,3)
        ng.addWidget(QLabel("Live idle timeout"),7,0); ng.addWidget(self.adv_live_idle,7,1); ng.addWidget(QLabel("Initial segment count"),7,2); ng.addWidget(self.adv_live_take,7,3); ng.addWidget(QLabel("Headers"),8,0); ng.addWidget(self.adv_n_headers,8,1,1,3); ng.addWidget(self.adv_vod_list,9,0); ng.addWidget(self.adv_live_pipe,9,1); ng.addWidget(self.adv_live_vod,9,2); ng.addWidget(self.adv_append,9,3); lay.addWidget(n)
        hint=QLabel("Advanced fields map directly to documented backend options. Blank fields keep the backend defaults."); hint.setObjectName("Subtitle"); hint.setWordWrap(True); lay.addWidget(hint); lay.addStretch(); scroll.setWidget(body); outer.addWidget(scroll); return page

    def _build_queue_tab(self):
        page=QWidget(); lay=QVBoxLayout(page); info=QLabel("Persistent sequential queue. Each item stores URL, engine and output folder."); info.setObjectName("Subtitle"); lay.addWidget(info)
        self.queue_table=QTableWidget(0,4); self.queue_table.setHorizontalHeaderLabels(["Status","Engine","URL","Output"]); self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.queue_table.verticalHeader().setVisible(False); self.queue_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); self.queue_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch); lay.addWidget(self.queue_table,1)
        row=QHBoxLayout(); self.queue_add=QPushButton("Add current URL"); self.queue_remove=QPushButton("Remove selected"); self.queue_clear=QPushButton("Clear queue"); self.queue_start=QPushButton("▶ Start queue"); self.queue_start.setObjectName("Primary"); row.addWidget(self.queue_add); row.addWidget(self.queue_remove); row.addWidget(self.queue_clear); row.addStretch(); row.addWidget(self.queue_start); lay.addLayout(row); self._refresh_queue(); return page

    def _build_media_lab_tab(self):
        page=QWidget(); lay=QVBoxLayout(page); top=QGroupBox("Media Inspector — FFprobe"); g=QGridLayout(top); self.lab_input=QLineEdit(); self.lab_input.setPlaceholderText("Local media file or direct media URL"); browse=QPushButton("Browse…"); self.lab_probe=QPushButton("Probe JSON"); self.lab_probe.setObjectName("Primary"); g.addWidget(self.lab_input,0,0,1,2); g.addWidget(browse,0,2); g.addWidget(self.lab_probe,0,3); lay.addWidget(top)
        self.lab_summary=QTableWidget(0,2); self.lab_summary.setHorizontalHeaderLabels(["Property","Value"]); self.lab_summary.setEditTriggers(QAbstractItemView.NoEditTriggers); self.lab_summary.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.lab_summary.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); lay.addWidget(self.lab_summary,1)
        box=QGroupBox("Official capability map"); bl=QVBoxLayout(box); self.capabilities=QPlainTextEdit(all_features_text()); self.capabilities.setReadOnly(True); bl.addWidget(self.capabilities); lay.addWidget(box,2); browse.clicked.connect(self._lab_browse); self.lab_probe.clicked.connect(self._lab_probe); return page

    def _refresh_queue(self):
        if not hasattr(self,"queue_table"): return
        self.queue_table.setRowCount(len(self.queue_items))
        for r,item in enumerate(self.queue_items):
            for c,v in enumerate([item.status,item.engine,item.url,item.output_dir]): self.queue_table.setItem(r,c,QTableWidgetItem(str(v)))

    def _queue_add_current(self):
        url=self._valid_url()
        if not url: return
        self.queue_items.append(QueueItem(url,self.engine_combo.currentData(),self.output_input.text().strip())); save_queue(self.queue_items); self._refresh_queue(); self.run_status.setText("Added to queue")

    def _queue_remove(self):
        rows=self.queue_table.selectionModel().selectedRows()
        for idx in sorted([r.row() for r in rows],reverse=True): self.queue_items.pop(idx)
        save_queue(self.queue_items); self._refresh_queue()

    def _queue_clear(self): self.queue_items.clear(); self.queue_running=False; save_queue(self.queue_items); self._refresh_queue()

    def _queue_start(self):
        if not self.queue_items: QMessageBox.information(self,"Queue empty","Add at least one URL first."); return
        self.queue_running=True; self._start_next_queue()

    def _start_next_queue(self):
        if not self.queue_items: self.queue_running=False; self.run_status.setText("Queue completed"); return
        item=self.queue_items[0]; item.status="running"; save_queue(self.queue_items); self._refresh_queue(); self.url_input.setText(item.url); self.engine_combo.setCurrentIndex(max(0,self.engine_combo.findData(item.engine))); self.output_input.setText(item.output_dir); self.tabs.setCurrentIndex(0); self._start()

    def _lab_browse(self):
        f,_=QFileDialog.getOpenFileName(self,"Choose media file","","Media files (*.mp4 *.mkv *.webm *.mov *.m4a *.ts *.mp3);;All files (*.*)")
        if f: self.lab_input.setText(f)

    def _lab_probe(self):
        source=self.lab_input.text().strip(); ffprobe=self.tools.get("ffprobe")
        if not source: return
        if not ffprobe: QMessageBox.warning(self,"FFprobe unavailable","Repair the FFmpeg toolchain first."); return
        ok,data=ffprobe_json(ffprobe,source); self.lab_summary.setRowCount(0)
        if not ok: QMessageBox.warning(self,"FFprobe failed",str(data)); return
        rows=summarize_probe(data); self.lab_summary.setRowCount(len(rows))
        for r,(a,b) in enumerate(rows): self.lab_summary.setItem(r,0,QTableWidgetItem(a)); self.lab_summary.setItem(r,1,QTableWidgetItem(b))

    def _connect_signals(self):
        self.engine_combo.currentIndexChanged.connect(self._engine_changed); self.url_input.textChanged.connect(self._url_changed); self.preset_list.currentRowChanged.connect(self._preset_changed)
        for w in [self.video_select,self.audio_select,self.subtitle_lang,self.output_input,self.proxy_input,self.bandwidth,self.nre_dec_kid,self.nre_dec_key,self.nre_dec_specs,self.dec_key_specs,self.segment_range]: w.textChanged.connect(self._update_command)
        for w in [self.subtitle_check,self.allow_unplayable,self.mux_mp4,self.concurrent,self.resume_check,self.nre_dec_enable,self.live_mode,self.live_real_time]: w.stateChanged.connect(self._update_command)
        for w in [self.threads,self.retries,self.retry_sleep,self.http_timeout]: w.valueChanged.connect(self._update_command)
        self.cookies_browser.currentIndexChanged.connect(self._update_command); self.proxy_mode.currentIndexChanged.connect(self._update_command); self.browse_output.clicked.connect(self._browse_output); self.copy_command.clicked.connect(self._copy_command); self.open_output.clicked.connect(self._open_output); self.inspect_btn.clicked.connect(self._inspect_formats); self.start_btn.clicked.connect(self._start); self.stop_btn.clicked.connect(self._stop); self.clear_btn.clicked.connect(self._clear); self.open_proxy_tab.clicked.connect(lambda: self.tabs.setCurrentIndex(1)); self.scan_proxy_btn.clicked.connect(self._scan_proxies); self.use_proxy_btn.clicked.connect(self._use_selected_proxy); self.proxy_table.doubleClicked.connect(lambda *_: self._use_selected_proxy()); self.history_refresh.clicked.connect(self._refresh_history); self.theme_combo.currentTextChanged.connect(self._theme_changed)
        self.stop_btn.setEnabled(False); self.start_btn.setEnabled(False); self.clear_btn.setEnabled(False); self.inspect_btn.setEnabled(False); self.dec_run.setEnabled(False)

    def _theme_changed(self,name):
        self.settings["theme"]=name
        app = QApplication.instance()
        if app: app.setPalette(palette(name))
        self.setStyleSheet(stylesheet(name))
        self._apply_icons()

    def _engine(self): return ENGINES[self.engine_combo.currentData()]
    def _engine_changed(self): self.settings["tool"]=self.engine_combo.currentData(); self._refresh_presets(); self.inspect_btn.setText("Inspect formats" if self.engine_combo.currentData()=="yt-dlp" else "Stream selector help"); self._update_command()
    def _refresh_presets(self):
        self.preset_list.clear()
        for p in self._engine().presets(): item=QListWidgetItem(f"{p.name}\n{p.description}"); item.setData(Qt.UserRole,p.name); item.setToolTip(p.description); self.preset_list.addItem(item)
        if self.preset_list.count(): self.preset_list.setCurrentRow(0)
    def _preset_changed(self,row:int):
        if row>=0: p=self._engine().presets()[row]; self.preset_hint.setText(self._engine().example(p.name)); self._update_command()
    def _url_changed(self):
        labels={"stream":"● Stream manifest detected","web":"● Web/direct URL detected","unknown":"● Waiting for a valid URL"}; self.url_kind.setText(labels[classify_url(self.url_input.text())]); self._update_command()

    def _effective_proxy(self)->str:
        return self.proxy_input.text().strip() if self.proxy_mode.currentData()=="manual" else ""

    def _options(self)->dict:
        preset=self.preset_list.currentItem().data(Qt.UserRole) if self.preset_list.currentItem() else self._engine().presets()[0].name
        return {
            "preset":preset,"video_format":self.video_select.text().strip(),"audio_format":self.audio_select.text().strip(),
            "video_selector":self.video_select.text().strip(),"audio_selector":self.audio_select.text().strip(),
            "subtitle_selector":self.subtitle_lang.text().strip() if self.subtitle_check.isChecked() else "",
            "subtitle_lang":self.subtitle_lang.text().strip() or "en","subtitles":self.subtitle_check.isChecked(),
            "threads":self.threads.value(),"concurrent_fragments":self.threads.value() if self.concurrent.isChecked() else 1,
            "concurrent":self.concurrent.isChecked(),"allow_unplayable":self.allow_unplayable.isChecked(),"mux_mp4":self.mux_mp4.isChecked(),
            "retries":self.retries.value(),"retry_sleep":self.retry_sleep.value(),"http_timeout":self.http_timeout.value(),
            "cookies_from_browser":self.cookies_browser.currentText(),"resume":self.resume_check.isChecked(),
            "no_overwrites":not self._force_redownload,"force_overwrites":self._force_redownload,"proxy_url":self._effective_proxy(),
            "proxy_mode":self.proxy_mode.currentData(),"bandwidth_limit":self.bandwidth.text().strip(),
            "authorized_decryption":self.nre_dec_enable.isChecked(),"decryption_kid":self.nre_dec_kid.text().strip(),"decryption_key":self.nre_dec_key.text().strip(),"decryption_key_specs":self.nre_dec_specs.toPlainText().strip(),
            "segment_range":self.segment_range.text().strip(),"live_real_time_merge":self.live_real_time.isChecked(),
            "vod_select_parts":self.live_mode.isChecked() and self.engine_combo.currentData()=="n_m3u8dl-re",
            "playlist_items":self.adv_playlist.text().strip(),"upload_date":self.adv_date.text().strip(),"min_filesize":self.adv_min_size.text().strip(),"max_filesize":self.adv_max_size.text().strip(),"rate_limit":self.adv_rate.text().strip(),"format_sort":self.adv_format_sort.text().strip(),"download_sections":self.adv_sections.text().strip(),"sponsorblock_mark":self.adv_mark.text().strip(),"sponsorblock_remove":self.adv_remove.text().strip(),"write_thumbnail":self.adv_thumbnail.isChecked(),"write_description":self.adv_description.isChecked(),"write_infojson":self.adv_infojson.isChecked(),"write_metadata":self.adv_metadata.isChecked(),"extract_audio":self.adv_extract.isChecked(),"audio_format_output":self.adv_audio_format.currentText(),"cookies_file":self.adv_cookies.text().strip(),"headers":self.adv_headers.toPlainText().strip(),
            "nre_cookies_file":self.adv_n_cookies.text().strip(),"base_url":self.adv_base_url.text().strip(),"task_start_at":self.adv_task.text().strip(),"custom_hls_method":self.adv_hls_method.currentText(),"custom_hls_key":self.adv_hls_key.text().strip(),"custom_hls_iv":self.adv_hls_iv.text().strip(),"custom_hls_scope":self.adv_hls_scope.currentText(),"drop_video":self.adv_drop_video.text().strip(),"drop_audio":self.adv_drop_audio.text().strip(),"drop_subtitle":self.adv_drop_sub.text().strip(),"ad_keyword":self.adv_ad_keyword.text().strip(),"vod_list_parts":self.adv_vod_list.isChecked(),"vod_drop_parts":self.adv_vod_drop.text().strip(),"live_wait_time":self.adv_live_wait.value(),"live_idle_timeout":self.adv_live_idle.value(),"live_take_count":self.adv_live_take.value(),"live_pipe_mux":self.adv_live_pipe.isChecked(),"live_perform_as_vod":self.adv_live_vod.isChecked(),"append_url_params":self.adv_append.isChecked(),"network_interface":self.adv_interface.text().strip(),"headers":self.adv_headers.toPlainText().strip(),
            "skip_download":False,"subtitle_only":False,"subtitle_format":"SRT"
        }

    def _update_command(self):
        if not hasattr(self,"command_preview") or not self.tools: return
        try: self.command_preview.setPlainText(display_command(self._engine().build(self.url_input.text().strip() or "<URL>",Path(self.output_input.text() or "<OUTPUT>"),self._options(),self.tools),redact=True))
        except Exception as exc: self.command_preview.setPlainText(f"Unable to generate command: {exc}")

    def set_tools(self,tools:dict[str,Path]):
        self.tools={k:v for k,v in tools.items() if not k.startswith("__") and isinstance(v, Path)}
        failures=tools.get("__failures__", {})
        self.status_badge.setText("●  Toolchain: ready" if not failures else "●  Toolchain: ready with optional components unavailable")
        self.status_badge.setStyleSheet("color:#69e6a7;font-weight:700;")
        self.overlay.hide()
        self.start_btn.setEnabled("yt-dlp" in self.tools or "n_m3u8dl-re" in self.tools)
        self.clear_btn.setEnabled(True)
        self.inspect_btn.setEnabled("yt-dlp" in self.tools)
        self.dec_run.setEnabled("mp4decrypt" in self.tools)
        self._update_tool_status(); self._update_command()
        self._log("[bootstrap] Toolchain health check complete.")
        if failures: self._log("[bootstrap] Optional component issues: "+str(failures))
    def setup_failed(self,message:str):
        self.status_badge.setText("●  Toolchain: limited")
        self.status_badge.setStyleSheet("color:#ffbd5c;font-weight:700;")
        self.overlay.hide()
        self.start_btn.setEnabled(False)
        self.inspect_btn.setEnabled(False)
        self._log("[bootstrap error] "+message)
        QMessageBox.warning(self,"Toolchain needs attention",message+"\n\nThe checking screen has been closed so the application cannot become stuck. Use Toolchain → Repair after checking your network connection.")
    def setup_status(self,message:str,value:int|None): self.overlay.update_status(message,value); self._log("[bootstrap] "+message)
    def _update_tool_status(self):
        self.tool_status_list.clear(); versions=tool_versions(self.tools)
        self.tool_status_list.addItem(f"✓ Python          {sys.version.split()[0]}")
        try:
            import PySide6; self.tool_status_list.addItem(f"✓ PySide6         {PySide6.__version__}")
        except Exception: pass
        for key,path in self.tools.items(): self.tool_status_list.addItem(f"✓ {key:<15} {versions.get(key,'ready')}\n    {path}")

    def _browse_output(self):
        folder=QFileDialog.getExistingDirectory(self,"Choose output folder",self.output_input.text());
        if folder: self.output_input.setText(folder); self.settings["output_dir"]=folder
    def _open_output(self):
        path=Path(self.output_input.text()); path.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
    def _copy_command(self): QApplication.clipboard().setText(self.command_preview.toPlainText()); self.run_status.setText("Command copied")
    def _valid_url(self):
        url=self.url_input.text().strip()
        # Accept a pasted Markdown link and recover the actual URL instead of passing
        # literal brackets/parentheses to a downloader.
        if url.startswith("[") and "](" in url and url.endswith(")"):
            url = url[url.find("](") + 2:-1].strip()
        if not url.startswith(("http://","https://")):
            QMessageBox.warning(self,"URL required","Enter an http:// or https:// URL first."); return None
        if url != self.url_input.text().strip():
            self.url_input.setText(url)
        return url

    def _inspect_formats(self):
        url=self._valid_url();
        if not url: return
        if self.engine_combo.currentData()!="yt-dlp": QMessageBox.information(self,"N_m3u8DL-RE selectors","N_m3u8DL-RE uses selector expressions such as res=\"1920*\":for=best and lang=en:for=best."); return
        if self._effective_proxy() and self.cookies_browser.currentText():
            if QMessageBox.warning(self,"Cookies through proxy","You selected browser cookies and a proxy. Public proxies can observe traffic metadata. Continue only if you trust this proxy.",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        self.inspect_btn.setEnabled(False); self.inspect_btn.setText("Inspecting…"); self.run_status.setText("Reading metadata…"); self.probe_worker=YtDlpProbeWorker(url,self.tools,self.cookies_browser.currentText(),self._effective_proxy()); self.probe_worker.ready.connect(self._formats_ready); self.probe_worker.failed.connect(self._formats_failed); self.probe_worker.start()
    def _formats_ready(self,info,formats):
        self.inspect_btn.setEnabled(True); self.inspect_btn.setText("Inspect formats"); dlg=FormatPickerDialog(info,formats,self)
        if dlg.exec()==QDialog.Accepted:
            self.video_select.setText(dlg.video_id); self.audio_select.setText(dlg.audio_id)
            for row,p in enumerate(self._engine().presets()):
                if p.name=="Custom / selected formats": self.preset_list.setCurrentRow(row); break
            self.run_status.setText(f"Selected video {dlg.video_id or '—'} / audio {dlg.audio_id or '—'}")
        self.probe_worker=None
    def _formats_failed(self,message): self.inspect_btn.setEnabled(True); self.inspect_btn.setText("Inspect formats"); self._log("[format probe] "+message); QMessageBox.critical(self,"Format inspection failed",message); self.probe_worker=None

    def _start(self):
        url=self._valid_url();
        if not url:return
        selected_engine=self.engine_combo.currentData()
        auto_engine=recommended_engine(url)
        if selected_engine == "n_m3u8dl-re" and auto_engine == "yt-dlp":
            host=urlparse(url).netloc.lower()
            choice=QMessageBox.question(
                self,"URL requires yt-dlp",
                f"This URL is a website/video page ({host}), not an M3U8/MPD manifest.\n\n"
                "N_m3u8DL-RE is for HLS/DASH/MSS stream inputs and cannot resolve YouTube pages. "
                "Switch to yt-dlp automatically?",
                QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)
            if choice != QMessageBox.Yes:
                return
            self.engine_combo.setCurrentIndex(max(0,self.engine_combo.findData("yt-dlp")))
            selected_engine="yt-dlp"
            self._refresh_presets()
        elif selected_engine == "yt-dlp" and auto_engine == "n_m3u8dl-re" and classify_url(url) == "stream":
            self.run_status.setText("Manifest detected; yt-dlp can handle many manifests, so continuing with yt-dlp.")
        if self.engine_combo.currentData()=="yt-dlp" and self._options()["preset"]=="List formats": self._inspect_formats(); return
        if self._effective_proxy() and self.cookies_browser.currentText():
            if QMessageBox.warning(self,"Public proxy + browser cookies","Do not send authenticated browser cookies through an untrusted public proxy. Continue only if this is a proxy you trust.",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        output=Path(self.output_input.text().strip()); output.mkdir(parents=True,exist_ok=True); self._force_redownload=False
        old=recent_success(url,output)
        if old:
            choice=QMessageBox.question(self,"Already downloaded","This URL was previously completed in this output folder. Download it again?\n\nChoose No to leave the existing result untouched.",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if choice!=QMessageBox.Yes:return
            self._force_redownload=True
        command=self._engine().build(url,output,self._options(),self.tools); self._current_url=url; self._saw_encryption_hint=False
        save_active_job(url,{"engine":self.engine_combo.currentData(),"output_dir":str(output.resolve()),"status":"running"})
        self.debug.clear(); self.live_feed.clear(); self._reset_metrics(); self.progress.setValue(0); self.progress.setFormat("Downloading — %p%"); self.run_status.setText("Running — resume/retry protection enabled" if self.resume_check.isChecked() else "Running"); self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.engine_combo.setEnabled(False); self.inspect_btn.setEnabled(False)
        self.worker=DownloadWorker(command); self.worker.stop_state.connect(self._stop_state); self.worker.output.connect(self._log); self.worker.progress.connect(self.progress.setValue); self.worker.metrics.connect(self._update_metrics); self.worker.finished_ok.connect(self._finished); self.worker.start()
    def _reset_metrics(self):
        for card in [self.metric_total,self.metric_done,self.metric_speed,self.metric_eta]: card.value.setText("—")
        self.current_item.setText("Preparing download…")
    def _update_metrics(self,data):
        if "total" in data:self.metric_total.value.setText(str(data["total"]));
        if "downloaded" in data:self.metric_done.value.setText(str(data["downloaded"]));
        if "speed" in data:self.metric_speed.value.setText(str(data["speed"]));
        if "eta" in data:self.metric_eta.value.setText(str(data["eta"]));
        if data.get("title"):self.current_item.setText(str(data["title"]));
        parts=[]
        if data.get("percent") is not None:parts.append(f"{data['percent']}%")
        for k,label in [("downloaded","done"),("total","total"),("speed","speed"),("eta","ETA")]:
            if data.get(k):parts.append(f"{label}: {data[k]}")
        if parts:self.live_feed.appendPlainText("  •  ".join(parts)); self.live_feed.verticalScrollBar().setValue(self.live_feed.verticalScrollBar().maximum())
    def _stop(self):
        if self.worker and self.worker.isRunning():
            self._log("[studio] Stop requested — terminating downloader and child processes…")
            # v0.6.6 uses hard tree termination on the first click. The
            # second click remains available as an independent fallback.
            self.run_status.setText("Force stopping… terminating the complete process tree")
            self.stop_btn.setText("Force stop")
            self.start_btn.setEnabled(False)
            self.worker.stop()
    def _stop_state(self, state: str):
        if state == "stopping":
            self.stop_btn.setText("Force stop")
            self.stop_btn.setEnabled(True)
        elif state == "force":
            self.stop_btn.setText("Force stop")
            self.stop_btn.setEnabled(True)
        elif state == "stopped":
            self.stop_btn.setEnabled(False)

    def _apply_icons(self):
        # Small native Windows/Qt icons keep the UI familiar without adding a
        # heavy icon dependency. Tooltips explain what each action does.
        mapping = [
            ("inspect_btn", "SP_FileDialogInfoView", "Inspect available formats/streams"),
            ("open_proxy_tab", "SP_DirOpenIcon", "Open the Proxy Lab and test public proxies"),
            ("copy_command", "SP_FileDialogToParent", "Copy the generated backend command"),
            ("open_output", "SP_DirOpenIcon", "Open the output folder in Explorer"),
            ("browse_output", "SP_DirOpenIcon", "Choose the download destination"),
            ("start_btn", "SP_MediaPlay", "Start the current download"),
            ("stop_btn", "SP_MediaStop", "Stop; click again to force-stop the entire process tree"),
            ("clear_btn", "SP_DialogResetButton", "Clear the current download form"),
            ("scan_proxy_btn", "SP_BrowserReload", "Fetch and test public proxies"),
            ("use_proxy_btn", "SP_ArrowRight", "Use the selected proxy"),
            ("history_refresh", "SP_BrowserReload", "Refresh local download history"),
            ("lab_probe", "SP_FileDialogInfoView", "Inspect media streams with FFprobe"),
            ("dec_run", "SP_DialogApplyButton", "Run authorized MP4 decryption"),
            ("queue_add", "SP_FileDialogNewFolder", "Add the current URL to the queue"),
            ("queue_remove", "SP_DialogCancelButton", "Remove selected queue items"),
            ("queue_clear", "SP_DialogResetButton", "Clear the queue"),
            ("queue_start", "SP_MediaPlay", "Start queued downloads"),
        ]
        for attr, icon_name, tip in mapping:
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setIcon(_std_icon(icon_name)); widget.setToolTip(tip)
        # Tab icons provide quick visual navigation and scale cleanly on high DPI.
        tab_icons = ["SP_DownloadIcon", "SP_FileDialogDetailedView", "SP_FileDialogListView", "SP_FileDialogInfoView", "SP_DirOpenIcon", "SP_DialogApplyButton", "SP_FileIcon", "SP_ComputerIcon", "SP_ComputerIcon"]
        for i, name in enumerate(tab_icons):
            if i < self.tabs.count(): self.tabs.setTabIcon(i, _std_icon(name))

    def _finished(self,code):
        stopped=bool(self.worker and self.worker.user_stopped); self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.stop_btn.setText("Stop"); self.engine_combo.setEnabled(True); self.inspect_btn.setEnabled(True)
        status="completed" if code==0 else ("stopped" if stopped else "failed")
        append_history({"url":self._current_url,"output_dir":str(Path(self.output_input.text()).resolve()),"engine":self.engine_combo.currentData(),"status":status,"code":code})
        if code==0: clear_active_job(self._current_url); self.progress.setValue(100); self.progress.setFormat("Completed — %p%"); self.run_status.setText("Download completed successfully")
        elif stopped: self.progress.setFormat("Stopped — partial data kept for resume"); self.run_status.setText("Stopped by user; restart the same URL to resume where supported")
        else: self.progress.setFormat("Interrupted / failed — %p%"); self.run_status.setText(f"Exited with code {code}; retrying the same URL can resume partial data")
        self._log(f"[studio] Job {status} (code {code}).")
        if code != 0 and self._saw_encryption_hint:
            if QMessageBox.information(self,"Encrypted media detected","The backend reported encrypted/protected media. If you legally possess the decryption key, open Authorized Decryption and provide it there. The application will not obtain or extract DRM keys.",QMessageBox.Ok)==QMessageBox.Ok:
                self.tabs.setCurrentIndex(2)
        self.worker=None; self._force_redownload=False; self._refresh_history(); self._update_command()
        if self.queue_running:
            if code == 0:
                if self.queue_items: self.queue_items.pop(0)
                save_queue(self.queue_items); self._refresh_queue(); self._start_next_queue()
            else:
                if self.queue_items: self.queue_items[0].status="failed"
                self.queue_running=False; save_queue(self.queue_items); self._refresh_queue()
    def _clear(self): self.url_input.clear(); self.video_select.clear(); self.audio_select.clear(); self.debug.clear(); self.live_feed.clear(); self.progress.setValue(0); self.progress.setFormat("Ready"); self.run_status.setText("No active job"); self.current_item.setText("Ready"); self._reset_metrics(); self.current_item.setText("Ready")

    def _scan_proxies(self):
        if self.proxy_worker and self.proxy_worker.isRunning(): return
        self.proxy_table.setRowCount(0); self.scan_proxy_btn.setEnabled(False); self.proxy_status.setText("Starting scan…"); self.proxy_worker=ProxyScanWorker(self.proxy_limit.value(),self.proxy_country.text(),self.proxy_protocol.currentText().lower()); self.proxy_worker.status.connect(self.proxy_status.setText); self.proxy_worker.ready.connect(self._proxies_ready); self.proxy_worker.failed.connect(self._proxies_failed); self.proxy_worker.start()
    def _proxies_ready(self,records:list[ProxyRecord]):
        self.scan_proxy_btn.setEnabled(True); self.proxy_table.setRowCount(len(records)); alive=[r for r in records if r.alive]
        for row,r in enumerate(records):
            vals=[r.url,r.protocol,r.country,r.city,r.anonymity,r.uptime,r.latency_text,"✓ Alive" if r.alive else "✕ Dead/untested",r.source]
            for col,val in enumerate(vals): self.proxy_table.setItem(row,col,QTableWidgetItem(str(val)))
        self.proxy_status.setText(f"{len(alive)} alive {self.proxy_protocol.currentText()} proxies out of {len(records)} tested.")
        if records and self.proxy_auto.isChecked() and alive:
            best=alive[0]; self.proxy_input.setText(best.url); self.proxy_mode.setCurrentIndex(max(0,self.proxy_mode.findData("manual"))); self.proxy_status.setText(self.proxy_status.text()+f"  Auto-selected: {best.url} ({best.latency_text})")
        self.proxy_worker=None
    def _proxies_failed(self,message): self.scan_proxy_btn.setEnabled(True); self.proxy_status.setText("Proxy scan failed: "+message); self.proxy_worker=None
    def _use_selected_proxy(self):
        rows=self.proxy_table.selectionModel().selectedRows()
        if not rows: QMessageBox.information(self,"Select proxy","Choose a proxy row first."); return
        url=self.proxy_table.item(rows[0].row(),0).text(); self.proxy_input.setText(url); self.proxy_mode.setCurrentIndex(max(0,self.proxy_mode.findData("manual"))); self.proxy_status.setText(f"Selected {url}"); self.tabs.setCurrentIndex(0)

    def _browse_dec_input(self):
        f,_=QFileDialog.getOpenFileName(self,"Choose encrypted MP4","","MP4 files (*.mp4 *.m4s);;All files (*.*)");
        if f:self.dec_input.setText(f); self.dec_output.setText(str(Path(f).with_name(Path(f).stem+".decrypted.mp4")))
    def _browse_dec_output(self):
        f,_=QFileDialog.getSaveFileName(self,"Choose output MP4",self.dec_output.text() or "decrypted.mp4","MP4 files (*.mp4)");
        if f:self.dec_output.setText(f)
    def _run_decrypt(self):
        if not self.dec_authorized.isChecked(): QMessageBox.warning(self,"Authorization required","Confirm that you are authorized to decrypt this media."); return
        inp=Path(self.dec_input.text()); out=Path(self.dec_output.text()); kid=self.dec_kid.text().strip(); key=self.dec_key.text().strip(); specs=self.dec_key_specs.toPlainText().strip()
        if not inp.exists() or not out.name:
            QMessageBox.warning(self,"Missing information","Choose an input and output file first."); return
        try:
            parsed=parse_key_specs(specs,kid,key)
        except ValueError as exc:
            QMessageBox.warning(self,"Invalid key format",str(exc)); return
        if not parsed:
            QMessageBox.warning(self,"Missing key","Enter either separate KID + key or one/more KID:KEY entries."); return
        if any(":" not in item for item in parsed):
            QMessageBox.warning(self,"KID required","mp4decrypt requires an ID with each key. Key-only input is supported by N_m3u8DL-RE, not by standalone mp4decrypt."); return
        if "mp4decrypt" not in self.tools:
            QMessageBox.warning(self,"mp4decrypt unavailable","Install/repair Bento4 from the Toolchain tab, then retry."); return
        cmd=[str(self.tools["mp4decrypt"]),"--show-progress"]
        for keyarg in parsed: cmd += ["--key",keyarg]
        cmd += [str(inp),str(out)]
        self.dec_log.clear(); self.dec_log.appendPlainText(display_command(cmd,redact=True)); self.dec_run.setEnabled(False); self.worker=DownloadWorker(cmd,log_command=False); self.worker.output.connect(self.dec_log.appendPlainText); self.worker.finished_ok.connect(self._decrypt_finished); self.worker.start()
    def _decrypt_finished(self,code): self.dec_run.setEnabled(True); self.dec_log.appendPlainText("Completed." if code==0 else f"mp4decrypt exited with code {code}."); self.worker=None

    def _refresh_history(self):
        if not hasattr(self,"history_table"):return
        items=history(); self.history_table.setRowCount(min(len(items),100))
        for row,item in enumerate(items[:100]):
            when=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(item.get("timestamp",0))) if item.get("timestamp") else "—"; vals=[when,item.get("status","—"),item.get("engine","—"),item.get("url","—"),item.get("output_dir","—")]
            for col,val in enumerate(vals): self.history_table.setItem(row,col,QTableWidgetItem(str(val)))

    def _log(self,text):
        lower=text.lower()
        if any(k in lower for k in ["encrypted", "decryption key", "mp4decrypt", "cenc", "drm"]): self._saw_encryption_hint=True
        if hasattr(self,"debug"): self.debug.appendPlainText(text); self.debug.verticalScrollBar().setValue(self.debug.verticalScrollBar().maximum())
        if hasattr(self,"live_feed") and any(k in text.lower() for k in ["[download]","error","ffmpeg","retry","warning"]): self.live_feed.appendPlainText(text)

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning(): self.worker.stop(); self.worker.wait(2500)
        if self.probe_worker and self.probe_worker.isRunning(): self.probe_worker.terminate(); self.probe_worker.wait(1000)
        if self.proxy_worker and self.proxy_worker.isRunning(): self.proxy_worker.terminate(); self.proxy_worker.wait(1000)
        save_queue(self.queue_items)
        self.settings.update({"output_dir":self.output_input.text(),"tool":self.engine_combo.currentData(),"threads":self.threads.value(),"retries":self.retries.value(),"retry_sleep":self.retry_sleep.value(),"http_timeout":self.http_timeout.value(),"resume":self.resume_check.isChecked(),"proxy_mode":self.proxy_mode.currentData(),"proxy_url":self.proxy_input.text(),"proxy_auto_select":self.proxy_auto.isChecked(),"proxy_max_test":self.proxy_limit.value(),"proxy_protocol":self.proxy_protocol.currentText().lower(),"bandwidth_limit":self.bandwidth.text(),"theme":self.theme_combo.currentText()}); save_settings(self.settings); event.accept()
