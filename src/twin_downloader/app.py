from __future__ import annotations

import sys
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from .bootstrap import BootstrapError, ensure_tools
from .ui import MainWindow


class BootstrapWorker(QThread):
    status = Signal(str, object)
    ready = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            tools = ensure_tools(lambda msg, pct: self.status.emit(msg, pct))
            self.ready.emit(tools)
        except BootstrapError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unexpected bootstrap error: {exc}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Twin Downloader Pro")
    app.setOrganizationName("TwinDownloaderPro")
    window = MainWindow()
    # Start maximized so the responsive layout fills any desktop resolution.
    window.showMaximized()

    bootstrap = BootstrapWorker()
    bootstrap.status.connect(window.setup_status)
    bootstrap.ready.connect(window.set_tools)
    bootstrap.failed.connect(window.setup_failed)
    bootstrap.start()
    window._bootstrap = bootstrap

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
