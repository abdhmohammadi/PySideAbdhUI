# Editor/bridge/bridge.py

from PySide6.QtCore import QObject, Signal, Slot
import json


class EditorBridge(QObject):
    """Communication bridge between JavaScript and Python."""
    measurements_received = Signal(dict)
    selection_changed = Signal(dict)
    content_changed = Signal()
    page_clicked = Signal(int)

    # Emitted when JS requests a paste operation (because document.execCommand('paste') 
    # is blocked by browsers for security). Python reads the system clipboard and
    # inserts the content via runJavaScript.
    paste_requested = Signal(str)  # 'text' | 'image'

    # Emitted when JS requests a cut/copy operation (because
    # document.execCommand('cut'/'copy') is unreliable in
    # QtWebEngine). Python writes the text/html to the system
    # clipboard via QGuiApplication.
    cut_requested = Signal(str, str)   # (text, html)
    copy_requested = Signal(str, str)  # (text, html)

    @Slot(str)
    def reportMeasurements(self, data):

        if not data:
            parsed = {}
        else:
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                parsed = {}

        self.measurements_received.emit(parsed)

    @Slot(dict)
    def reportSelection(self, data):

        if isinstance(data, dict):

            self.selection_changed.emit(data)


    @Slot()
    def notifyContentChanged(self): self.content_changed.emit()

    @Slot(int)
    def pageClicked(self, page): self.page_clicked.emit(page)

    @Slot(str)
    def requestPaste(self, kind):
        """Called from JS when the user clicks Paste in the context menu.

        `kind` is 'text' or 'image'. Python reads the system
        clipboard and inserts the content via runJavaScript,
        bypassing the browser's paste permission restriction.
        """
        self.paste_requested.emit(str(kind) if kind else 'text')

    @Slot(str, str)
    def requestCut(self, text, html):
        """Called from JS when the user clicks Cut.

        Python writes (text, html) to the system clipboard via
        QGuiApplication. JS has already deleted the selection
        locally — this method only handles the clipboard side,
        because document.execCommand('cut') is unreliable in
        QtWebEngine.
        """
        self.cut_requested.emit(str(text) if text else '',
                                str(html) if html else '')

    @Slot(str, str)
    def requestCopy(self, text, html):
        """Called from JS when the user clicks Copy.

        Python writes (text, html) to the system clipboard via
        QGuiApplication. The DOM is left untouched (copy does
        not modify the document).
        """
        self.copy_requested.emit(str(text) if text else '',
                                 str(html) if html else '')
