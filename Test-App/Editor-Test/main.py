"""
Editor test driver — main window.

Shows the Editor widget on the left and a side panel on the right
with a "Start testing" button, live progress log, and final
pass/fail percentage.

Usage:
    python main.py

The script expects the editor package to be importable. If running
from the Editor_0.5.1_fixed directory, it just works. If running
from elsewhere, set PYTHONPATH or copy the editor package alongside.
"""

from __future__ import annotations

from pathlib import Path
import sys
import os

# Make the editor package importable when running from the
# Editor_0.5.1_fixed directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTextEdit, QLabel, QFrame, QProgressBar, QSplitter
)

from editor.src.PySideAbdhUI.Editor.editor import Editor
from test_runner import EditorTestRunner, TestResult, TestSuiteResult, TESTS


# ──────────────────────────────────────────────────────────────
# Side panel
# ──────────────────────────────────────────────────────────────

class TestPanel(QWidget):
    """Side panel with Start button, progress log, and final %."""

    def __init__(self, editor: Editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._runner: EditorTestRunner | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Title ──
        title = QLabel("Test Runner")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # ── Start button ──
        self.start_btn = QPushButton("Start testing")
        self.start_btn.setMinimumHeight(40)
        start_font = QFont()
        start_font.setPointSize(11)
        start_font.setBold(True)
        self.start_btn.setFont(start_font)
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)

        # ── Progress bar ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("0 / 0")
        layout.addWidget(self.progress_bar)

        # ── Summary line (passed / failed / total) ──
        self.summary_label = QLabel("No tests run yet.")
        self.summary_label.setStyleSheet("color: #666; font-size: 10pt;")
        layout.addWidget(self.summary_label)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Live progress log ──
        log_label = QLabel("Progress:")
        log_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setStyleSheet(
            "QTextEdit { background: #1e1e1e; color: #d4d4d4; "
            "border: 1px solid #3c3c3c; }"
        )
        layout.addWidget(self.log, 1)  # stretch=1

        # ── Final result banner ──
        self.final_label = QLabel("")
        self.final_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_label.setMinimumHeight(50)
        self.final_label.setFont(QFont("", 14, QFont.Weight.Bold))
        self.final_label.setFrameShape(QFrame.Shape.Box)
        self.final_label.setFrameShadow(QFrame.Shadow.Sunken)
        self.final_label.setStyleSheet(
            "QLabel { background: #f0f0f0; color: #666; "
            "border: 2px solid #999; border-radius: 4px; }"
        )
        layout.addWidget(self.final_label)

    def _on_start(self):
        if self._runner and self._runner._running:
            return  # already running

        # Reset UI
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Running...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0 / 0")
        self.summary_label.setText("Running tests...")
        self.final_label.setText("")
        self.final_label.setStyleSheet(
            "QLabel { background: #f0f0f0; color: #666; "
            "border: 2px solid #999; border-radius: 4px; }"
        )
        self.log.clear()
        self._append_log("=== Starting test suite ===", "header")

        # Create runner and connect signals
        self._runner = EditorTestRunner(self._editor, self)
        self._runner.progress.connect(self._on_progress)
        self._runner.finished.connect(self._on_finished)

        # Start (slight delay to let UI update)
        QTimer.singleShot(100, self._runner.start)

    def _on_progress(self, result: TestResult):
        # Update progress bar
        total = len(TESTS)
        total_seen = len(self._runner._results)

        # Format the log entry
        icon = "[+]" if result.passed else "[x]"

        line = f'{icon} [{result.category}] {result.name}'
        detail_line = f'    -> {result.detail} ({result.duration_ms:.0f}ms)'

        self._append_log(line, "pass" if result.passed else "fail")
        self._append_log(detail_line, "detail")

        # Update progress bar
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(total_seen)
        self.progress_bar.setFormat(f"{total_seen} / {total}")

        # Update summary
        passed = sum(1 for r in self._runner._results if r.passed)
        failed = sum(1 for r in self._runner._results if not r.passed)
        self.summary_label.setText(
            f"Passed: {passed}   Failed: {failed}   Total: {total_seen}/{total}"
        )

        # Auto-scroll to bottom
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log.setTextCursor(cursor)

    def _on_finished(self, suite: TestSuiteResult):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start testing")

        percent = suite.percent
        passed = suite.passed
        failed = suite.failed
        total = suite.total

        # Final banner
        if failed == 0:
            self.final_label.setText(f"ALL PASSED\n{passed}/{total} ({percent:.1f}%)")
            self.final_label.setStyleSheet(
                "QLabel { background: #4ecca3; color: white; "
                "border: 2px solid #3a9d7a; border-radius: 4px; }"
            )
        elif passed == 0:
            self.final_label.setText(f"ALL FAILED\n{failed}/{total} ({100-percent:.1f}% fail)")
            self.final_label.setStyleSheet(
                "QLabel { background: #e74c3c; color: white; "
                "border: 2px solid #c0392b; border-radius: 4px; }"
            )
        else:
            self.final_label.setText(
                f"{passed}/{total} passed ({percent:.1f}%)\n{failed} failure(s)"
            )
            self.final_label.setStyleSheet(
                "QLabel { background: #f39c12; color: white; "
                "border: 2px solid #d68910; border-radius: 4px; }"
            )

        # Final log summary
        self._append_log("", "")
        self._append_log(
            f"=== Finished: {passed}/{total} passed ({percent:.1f}%) ===",
            "header"
        )
        if failed > 0:
            self._append_log("Failed tests:", "fail")
            for r in suite.results:
                if not r.passed:
                    self._append_log(f"  - [{r.category}] {r.name}", "fail")
                    self._append_log(f"      {r.detail}", "detail")

    def _append_log(self, text: str, kind: str):
        color_map = {
            "header": "#569cd6",  # blue
            "pass":   "#4ecca3",  # green
            "fail":   "#e74c3c",  # red
            "detail": "#888888",  # gray
            "":       "#d4d4d4",  # default
        }
        color = color_map.get(kind, "#d4d4d4")
        # Escape HTML special chars in text
        safe = (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
        self.log.append(f'<span style="color:{color};">{safe}</span>')


# ──────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor — Test Driver")
        self.resize(1400, 900)

        # Central widget with horizontal splitter
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # ── Left: Editor ──
        self.editor = Editor()
        splitter.addWidget(self.editor)

        # ── Right: Test panel ──
        self.panel = TestPanel(self.editor)
        self.panel.setMinimumWidth(380)
        self.panel.setMaximumWidth(500)
        splitter.addWidget(self.panel)

        # Set splitter proportions (editor gets more space)
        splitter.setSizes([950, 450])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        self.setCentralWidget(central)


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def main():
    # QtWebEngine needs this attribute set BEFORE QApplication is created
    # on some platforms.
    QApplication.setApplicationName("Editor Test Driver")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
