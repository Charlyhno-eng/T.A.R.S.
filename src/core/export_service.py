from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from core.exporter import host_platform
from core.paths import resource_directory


class ExportService(QObject):
    """Run a native export in a separate process while Qt stays responsive."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._log = ""
        self._destination = ""
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._error)

    @Property(str, constant=True)
    def platform(self) -> str:
        return host_platform()

    @Property(bool, constant=True)
    def toolsAvailable(self) -> bool:
        return bool(getattr(sys, "frozen", False)) or importlib.util.find_spec("PyInstaller") is not None

    @Property(bool, notify=changed)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=changed)
    def log(self) -> str:
        return self._log

    @Slot(str)
    def start(self, target: str) -> None:
        if self._running or target != host_platform() or not self.toolsAvailable:
            return
        destination = QFileDialog.getExistingDirectory(None, "Export T.A.R.S.", str(Path.home()))
        if not destination:
            return
        self._destination = destination
        self._log = ""
        self._running = True
        if getattr(sys, "frozen", False):
            args = ["--export-copy", destination]
        else:
            args = [str(resource_directory() / "scripts" / "build_app.py"),
                    "--platform", target, "--output", destination]
        self._process.setProgram(sys.executable)
        self._process.setArguments(args)
        self._process.start()
        self.changed.emit()

    def _read_output(self) -> None:
        # Keep the complete build log on the child process output; display its
        # latest section so multi-minute dependency collection stays readable.
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._log = (self._log + text)[-12000:]
        self.changed.emit()

    def _finished(self, code: int, status) -> None:
        self._read_output()
        self._running = False
        if code == 0 and status == QProcess.NormalExit:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._destination))
        else:
            self._log += f"\nExport failed (exit {code}).\n"
        self.changed.emit()

    def _error(self, error) -> None:
        self._log += f"\n{self._process.errorString()}\n"
        if error == QProcess.FailedToStart:
            self._running = False
        self.changed.emit()

    def shutdown(self) -> None:
        if self._running:
            self._process.terminate()
            if not self._process.waitForFinished(3000):
                self._process.kill()
                self._process.waitForFinished(1000)
