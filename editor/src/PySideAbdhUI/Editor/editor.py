import base64
import enum
import json
from html.parser import HTMLParser
from pathlib import Path
import re
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPageLayout, QPageSize, QShortcut
from PySide6.QtCore import QBuffer, QEventLoop, QIODevice, QMarginsF, QMimeData, QTimer, QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QMessageBox

from .ui.dialog import MathFormulaDialog, TableDialog, DialogCode

from .bridge.bridge import EditorBridge
from .core.document import Document
from .core.html_loader import html_tags_to_document, html_string_to_document
from .core.image import Image
from .core.math import MathBlock
from .core.page import Page
from .core.paragraph import Paragraph
from .core.table import Table
from .layout.renderer import PageRenderer
from .versions import __document_version__


class PageMode(enum.StrEnum):
    """
    <strong>Options:</strong>
    <ol>
    <li>paged</li>
    <li>continuous</li>
    </ol>

    """
    PAGED         = "paged"
    CONTINUOUS    = "continuous"

DEFUALT_FONT_FAMILY = "\"Segoe UI\", Tahoma, Geneva, Verdana, sans-serif"
DEFUALT_MARGIN = "60px"
DEFUALT_BACKGROUND = "#121212"
DEFUALT_DIRECTION = "auto"

class _ImgParser(HTMLParser):
    """
    Extracts attributes from the first <img> tag in an HTML fragment.

    Used by Editor._image_from_html to round-trip Image blocks
    without losing alt / width / height attributes (the previous
    regex-based parser only recovered `src`).
    """

    def __init__(self):
        super().__init__()
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        # Only capture the first <img>; ignore nested or duplicate tags.
        if tag.lower() == "img" and not self.attrs: self.attrs = dict(attrs)

class Editor(QWebEngineView):

    # Maximum number of polling attempts (50 ms each) before giving up
    # waiting for the JS side to report Editor.ready = true.
    # ~10 seconds total. Prevents infinite polling if script.js fails
    # to load or has a syntax error.
    MAX_READY_RETRIES = 200
    document:Document = None
    bridge:EditorBridge = None
    renderer:PageRenderer = None
    channel:QWebChannel = None
    math_engine_loaded = Signal(str)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.document = Document()
        self.document.append(Paragraph())
        self.bridge = EditorBridge()
        self.renderer = PageRenderer()
        
        self._last_focused_block_id = ""
        self._last_copied_html = ""
        self._last_copied_text = ""

        self._ready_retries = 0
        self._load_generation = 0
        
        self._editor_is_ready = False
        self._full_html_loaded = False  # True when loaded via setHtml

        self._pending_operations = [] # ← list of (js, callback) tuples

        
        self._format_state = {}
        self._selected_math = None
        self._selected_table = None
        self._selected_image = None

        self._page_mode = PageMode.PAGED            # 'paged' or 'continuous'
        self._page_margin = DEFUALT_MARGIN          # standard A4 margin
        self._background_color = DEFUALT_BACKGROUND # Initial background color
        self._page_direction = DEFUALT_DIRECTION
        self._global_font = DEFUALT_FONT_FAMILY

        self.channel = QWebChannel(self.page())

        self.channel.registerObject("bridge", self.bridge)

        self.page().setWebChannel(self.channel)

        self._configure_settings()

        self.bridge.content_changed.connect(self._on_content_changed)
        self.bridge.selection_changed.connect(self._on_selection_changed)
        self.bridge.paste_requested.connect(self._on_paste_requested)
        self.bridge.cut_requested.connect(self._on_cut_requested)
        self.bridge.copy_requested.connect(self._on_copy_requested)

        # Keyboard shortcut (e.g., Ctrl+Shift+Space)
        shortcut1 = QShortcut(QKeySequence("Ctrl+Shift+2"), self)
        shortcut1.activated.connect(self.insert_half_space)

        shortcut2 = QShortcut(QKeySequence("Alt++"),self)
        shortcut2.activated.connect(self.insert_formula)

        shortcut3 = QShortcut(QKeySequence("Alt+T"),self)
        shortcut3.activated.connect(self.insert_table)
        
        shortcut4 = QShortcut(QKeySequence("Alt+I"),self)
        shortcut4.activated.connect(self.insert_image)

        self._resources = Path(__file__).resolve().parent / "resources"

        html = (self._resources / "base.html").read_text(encoding="utf-8")

        self.page().setHtml(html, QUrl.fromLocalFile(str(self._resources) + "/"))

        self.loadFinished.connect(self.initialize)

    def _flush_pending_operations(self):
        """Execute all queued JS operations."""
        if not self._pending_operations: return

        for js, callback in self._pending_operations:
            if callback:
                self.page().runJavaScript(js, callback)
            else:
                self.page().runJavaScript(js)
        self._pending_operations.clear()

    def initialize(self, ok):
        if not ok: return
        self._load_generation += 1
        self.wait_until_ready()

    def wait_until_ready(self):
        gen = self._load_generation
        def on_ready(ready):
            # FIX: Ignore callbacks from older page loads
            if gen != self._load_generation:
                return
            self._editor_ready(ready)
        self.page().runJavaScript("window.Editor && Editor.ready;", on_ready)


    def _editor_ready(self, ready):

        if not ready:

            self._ready_retries += 1

            if self._ready_retries > self.MAX_READY_RETRIES:
                # Give up silently rather than poll forever.
                return

            QTimer.singleShot(50, self.wait_until_ready)

            return

        # Reset the retry counter so subsequent set_document() calls
        # get a fresh polling budget.
        self._ready_retries = 0
        self._editor_is_ready = True
        # ── FLUSH PENDING OPERATIONS HERE ──
        # This is the best place: Editor.ready is true, bridge is
        # connected, DOM is built. Execute all queued operations.
        self._flush_pending_operations()

        if getattr(self, '_full_html_loaded', False):
            # Content was loaded via setHtml() with scripts already
            # in the page. Don't call refresh() — it would replace
            # the DOM via setDocument(), breaking all event listeners
            # and element references that the user's script set up
            # during DOMContentLoaded.
            #
            # Instead, apply the page mode, paginate the existing DOM,
            # and make it editable, preserving the script's event handlers.
            self._full_html_loaded = False

            # Apply the page mode (paged vs continuous) that was
            # requested in load_blocks(). The mode must be set BEFORE
            # paginateAll() runs, because paginateAll() checks
            # editorMode and skips splitting in continuous mode.
            
            js_page_mode = json.dumps(self._page_mode or PageMode.PAGED)

            js_margin = json.dumps(self._page_margin or DEFUALT_MARGIN)

            js_font = json.dumps(self._global_font or DEFUALT_FONT_FAMILY)

            js_direction = json.dumps(self._page_direction or DEFUALT_DIRECTION)

            js_color = json.dumps(self._background_color or DEFUALT_BACKGROUND)
            
            js = f"""
            (function() {{
                return new Promise(function(resolve) {{
                    function doInit() {{
                        var result = "[]";
                        try 
                        {{
                            if(window.Editor && Editor.setMode) Editor.setMode({js_page_mode});

                            if(window.Editor && Editor.setPageMargin) Editor.setPageMargin({js_margin});
                        
                            if(window.Editor && Editor.setPageDirection) Editor.setPageDirection({js_direction});

                            if(window.Editor && Editor.setBackgroundColor) Editor.setBackgroundColor({js_color});

                            if(window.Editor && Editor.setGlobalFont) Editor.setGlobalFont({js_font});

                            result = Editor.paginateAll();
                            Editor.makeEditable();
                        }}
                        catch(e) 
                        {{
                            console.error('Editor init error:', e);
                        }}
                        finally 
                        {{
                            if (window.Editor && Editor.hideLoading) Editor.hideLoading();
                            var ed = document.getElementById('editor');
                            if (ed) ed.style.visibility = '';
                        }}
                        resolve(result);
                    }}
                    
                    // Wait for fonts before paginating — see refresh()
                    // for the full rationale. Without this, text height
                    // measurements use fallback font metrics and lines
                    // at the bottom of each page get clipped.
                    if (document.fonts && document.fonts.ready) 
                    {{
                        document.fonts.ready.then(doInit, doInit);
                    }} 
                    else 
                    {{
                        doInit();
                    }}
                }});
            }})();
            """

            def on_paginated(data):
                if data: self._apply_paginated_structure(data)

            self.page().runJavaScript(js, on_paginated)

        elif len(self.document): self.refresh()


    def refresh(self):
        """
        Push the current document to JS as a single draft page,
        let paginateAll() split it into real pages, then read the
        final structure back into the Python document model.
        """

        draft_page = Page()

        for block in self.document.blocks: draft_page.add(block)

        self.document.clear_pages()

        self.document.add_page(draft_page)

        html = self.renderer.render_document(self.document)

        # Hide #editor during the measure → paginate cycle to avoid
        # the "one giant clipped page" flash before paginateAll()
        # splits it into proper pages.
        #
        # BUT: if the loading overlay is already visible (during
        # initial boot or file open), skip the visibility toggle.
        # The overlay is semi-transparent (75% opacity), so toggling
        # #editor visibility underneath it causes a visible blink.
        # The overlay already hides the content — the extra
        # visibility:hidden is redundant in that case.
        #
        # ── Wait for document.fonts.ready before paginating ──
        # paginateAll() uses getBoundingClientRect() to find where
        # content overflows the page. If fonts haven't loaded yet,
        # the browser uses FALLBACK font metrics for measurement.
        # Once the real fonts load, text reflows and takes different
        # space — but pagination isn't re-run, so lines that now
        # overflow get clipped by .page { overflow: hidden }.
        #
        # Waiting for document.fonts.ready ensures the measurements
        # use the real font metrics. The promise resolves immediately
        # if fonts are already loaded, so there's no penalty in the
        # warm-cache case.
        js = f"""
        (function() 
        {{
            var root = document.getElementById('editor');
            var overlay = document.getElementById('loading-overlay');
            var overlayVisible = overlay && overlay.classList.contains('visible');
            if (root && !overlayVisible) root.style.visibility = 'hidden';
            Editor.setDocument({json.dumps(html)});
            
            return new Promise(function(resolve) 
            {{
                function doPaginate() 
                {{
                    requestAnimationFrame(function() 
                    {{
                        requestAnimationFrame(function() 
                        {{
                            var result = Editor.paginateAll();
                            if (root && !overlayVisible) root.style.visibility = '';
                            resolve(result);
                        }});
                    }});
                }}
                
                // Wait for fonts before measuring — see comment above.
                if (document.fonts && document.fonts.ready) 
                {{
                    document.fonts.ready.then(doPaginate, doPaginate);
                }} 
                else 
                {{
                    doPaginate();
                }}
            }});
        }})();
        """
        
        def on_paginated(data):
            # FIX: Abort if a new full HTML load (setHtml) has started
            if getattr(self, '_full_html_loaded', False):
                return

            if data:
                self._apply_paginated_structure(data)

            self.page().runJavaScript("Editor.makeEditable();")
            self._inject_metadata()
            self.page().runJavaScript('if(window.Editor&&Editor.hideLoading)Editor.hideLoading();'
            )

        self.page().runJavaScript(js, on_paginated)
  
    # Show a dialog that allows the user to edit page margins.
    def showMarginDialog(self):
        """Open a dialog to set page margins."""

        # Create the dialog window.
        dialog = QDialog(self)

        # Set dialog caption.
        dialog.setWindowTitle("Page Margins")

        # Create a form layout for margin controls.
        layout = QFormLayout(dialog)

        # Dictionary used to store spin boxes by margin name.
        spins = {}

        # Create one spin box for each page margin.
        for label, key in [ ("Top:", 'top'), ("Right:", 'right'), ("Bottom:", 'bottom'), ("Left:", 'left')]:

            # Create numeric editor.
            spin = QDoubleSpinBox()

            # Allow values from 0 to 50 mm.
            spin.setRange(0, 50)

            # Increment/decrement step size.
            spin.setSingleStep(1)

            # Display units after the numeric value.
            spin.setSuffix(" mm")

            # Initialize with current margin value.
            spin.setValue(20)

            # Add control to the form.
            layout.addRow(label, spin)

            # Store reference for later retrieval.
            spins[key] = spin

        # Create standard OK/Cancel buttons.
        buttons = QDialogButtonBox( QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        # Accept dialog when OK is pressed.
        buttons.accepted.connect(dialog.accept)

        # Reject dialog when Cancel is pressed.
        buttons.rejected.connect(dialog.reject)

        # Add button row to layout.
        layout.addWidget(buttons)

        # Show dialog modally and wait for user response.
        if dialog.exec() == QDialog.DialogCode.Accepted:

            # Apply new margin values.
            self.set_page_margin(f'{spins['top'].value()}mm {spins['right'].value()}mm {spins['bottom'].value()}mm {spins['left'].value()}mm')
    
    def set_page_margin(self, margin: str):

        self._page_margin = margin

        js_margin = json.dumps(margin)

        js = f"Editor.setPageMargin({js_margin});"

        if not self._editor_is_ready:
            self._pending_operations.append((js,None))
            return

        self.page().runJavaScript(js)        
        
    def set_background_color(self, color: str):

        self._background_color = color or DEFUALT_BACKGROUND
        js_color = json.dumps(self._background_color)
        
        js  = f"Editor.setBackgroundColor({js_color});"

        if not self._editor_is_ready:
            self._pending_operations.append((js, None))
            return

        self.page().runJavaScript(js) 

    def get_page_margin(self) -> str: return self._page_margin

    def get_background_color(self) -> str:
        """Return the current background color (e.g. '#121212')."""
        return self._background_color

    def _configure_settings(self):

        settings = self.page().settings()

        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)


    def _on_selection_changed(self, data):
        if isinstance(data, dict) and data.get("type") == "Math":
            self._selected_math = data
            self._selected_table = None
            self._selected_image = None

        elif isinstance(data, dict) and data.get("type") == "Table":
            self._selected_table = data
            self._selected_math = None
            self._selected_image = None
        elif isinstance(data, dict) and data.get("type") == "Image":
            self._selected_image = data
            self._selected_math = None
            self._selected_table = None
        elif isinstance(data, dict) and data.get("type") == "Format":
            # Text-format state at cursor — emitted by selectionchange
            # so the host app can update toolbar button states.
            self._format_state = data
            # Store the block ID at cursor position. Used by
            # insert_image() to pass back to JS so the image
            # lands at the right position even after the editor
            # loses focus to QFileDialog.
            self._last_focused_block_id = data.get("blockId", "")
        else:
            self._selected_math = None
            self._selected_table = None
            self._selected_image = None

    
    def get_selected_math(self):
        """Return the currently selected math formula data, or None."""
        return self._selected_math


    def set_document(self, document):

        self.document = document

        self._ready_retries = 0

        self.wait_until_ready()

    def clear_document(self):
        
        """Reset the editor to an empty document."""
        if len(self.document):
            self.document = Document()
            self.document.append(Paragraph())
            self._ready_retries = 0
            self.refresh()


    def insert_formula(self):

        dialog = MathFormulaDialog(self)

        if dialog.exec() != DialogCode.Accepted: return

        formula = dialog.get_formula()

        if formula is None: return

        inline = dialog.is_inline()

        self.insert_math_formula(formula, inline=inline)

    def insert_math_formula(self, formula: str, inline: bool = False):
        """Insert a math formula at the current cursor position."""
        if not formula: return

        js_formula = json.dumps(formula)
        js_inline = "true" if inline else "false"
        self.page().runJavaScript(f"Editor.insertMathFormula({js_formula}, {js_inline});")

    def update_math_formula(self, formula_id: str, formula: str, inline: bool = False):
        """Update an existing math formula by its element id."""
        if not formula_id or not formula: return

        js_id = json.dumps(formula_id)
        js_formula = json.dumps(formula)
        js_inline = "true" if inline else "false"
        self.page().runJavaScript(
            f"Editor.updateMathFormula({js_id}, {js_formula}, {js_inline});"
        )

    # ------------------------------------------------------
    # Table operations
    def insert_table(self):
        """
        Open a TableDialog asking the user for rows/columns, then
        insert a new table at the current cursor position.

        The new table includes a <colgroup> (required for column
        resizing), a single <thead> row of <th> cells, and the
        requested number of <tbody> rows of <td> cells.

        After insertion, the first cell of the new table is
        selected so subsequent add_row/add_column calls work
        immediately.
        """

        dialog = TableDialog(self)
        if dialog.exec() != DialogCode.Accepted: return

        rows, cols = dialog.get_size()

        if rows < 1 or cols < 1: return

        self.page().runJavaScript(f"Editor.insertTable({int(rows)}, {int(cols)});")

    def delete_table(self):
        """
        Delete the currently selected table.

        Removes the entire <div class='block' data-type='Table'>
        containing the selected <table> from the DOM. If no table
        is selected, this is a no-op.
        """

        self.page().runJavaScript("Editor.deleteTable();")

    def add_row(self):
        """
        Add a new row to the currently selected table.

        The row is inserted immediately after the currently
        selected row (or appended to the end if no row is
        selected). The new row contains empty <td> cells matching
        the table's column count. The new row's first cell becomes
        the selected cell.

        No-op if no table is selected.
        """

        self.page().runJavaScript("Editor.addRow();")

    def add_column(self):
        """
        Add a new column to the currently selected table.

        A <col> is inserted in the <colgroup> after the currently
        selected column, and a new cell (<th> in <thead>, <td>
        elsewhere) is inserted at the same index in every row.
        The new column's cell in the current row becomes selected.

        No-op if no table is selected.
        """

        self.page().runJavaScript("Editor.addColumn();")

    def remove_row(self):
        """
        Remove the currently selected row from the selected table.

        The row that took its place (or the last row if the
        removed row was last) becomes selected. At least one row
        is always kept — if the table has only one row, this is
        a no-op.

        No-op if no table is selected.
        """

        self.page().runJavaScript("Editor.removeRow();")

    def remove_column(self):
        """
        Remove the currently selected column from the selected
        table.

        Removes the corresponding <col> from <colgroup> and the
        cell at that index from every row. The column that took
        its place (or the last column) becomes selected. At least
        one column is always kept.

        No-op if no table is selected.
        """

        self.page().runJavaScript("Editor.removeColumn();")

    def get_selected_table(self):
        """
        Return info about the currently selected table, or None.

        The returned dict (when not None) has the same shape as
        the JS-reported selection:
            {
                'type': 'Table',
                'tableId': str,
                'row': int,    # index within tbody
                'col': int,    # cell index within row
                'rows': int,   # total rows in table
                'cols': int,   # total columns in table
                'inHeader': bool
            }
        """

        return self._selected_table

    # ------------------------------------------------------
    # Image operations
    def insert_image(self):
        """
        Open a file dialog to pick an image, then insert it at the
        current cursor position as an Image block.

        The image is embedded as a base64 data URL rather than a
        file path. This makes the document fully portable — it
        doesn't break if the image file is moved or deleted, and
        it works the same way across all platforms.

        The block ID at the last known cursor position is passed
        to JS so the image lands in the right place — the editor
        loses focus when QFileDialog opens, so JS can't rely on
        its own selection state.
        """

        from PySide6.QtWidgets import QFileDialog

        # Capture the block ID BEFORE opening the dialog (the
        # selectionchange reporter updates it continuously while
        # the user is editing).
        block_id = self._last_focused_block_id

        # Also ask JS to save the exact caret Range (not just the
        # block ID) before the dialog steals focus. QFileDialog is a
        # native modal window, so the page's live selection can't be
        # trusted to survive it — but a Range saved just before still
        # points at the right spot, letting insertImage() split the
        # paragraph at the caret instead of only landing after it.
        self.page().runJavaScript(
            "if(window.Editor&&Editor.saveCursorRangeForInsert)"
            "Editor.saveCursorRangeForInsert();"
        )

        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.svg *.webp *.bmp);;All Files (*.*)")
        
        if not path: return

        # Convert the image file to a base64 data URL. This embeds
        # the image directly in the document — no external file
        # dependency, fully portable, survives save/load round-trips.
        data_url = self._file_to_data_url(path)
        
        if not data_url: return

        alt = ""

        js_src = json.dumps(data_url)
        js_alt = json.dumps(alt)
        js_block_id = json.dumps(block_id) if block_id else "null"
        self.page().runJavaScript(f"Editor.insertImage({js_src}, {js_alt}, {js_block_id});")

    @staticmethod
    def _file_to_data_url(path) -> str:
        """
        Convert an image file to a base64 data URL.

        Returns a string like:
            "data:image/png;base64,iVBORw0KGgo..."

        Returns empty string on failure (file not readable, unsupported format, etc.).
        """
        path = Path(path)
        if not path.exists() or not path.is_file(): return ""

        # Determine MIME type from extension
        ext = path.suffix.lower()
        mime_map = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif":  "image/gif",
            ".svg":  "image/svg+xml",
            ".webp": "image/webp",
            ".bmp":  "image/bmp",
        }
        mime = mime_map.get(ext, "image/png")

        try:
            data = path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except OSError:
            return ""


    def remove_image(self):
        """
        Remove the currently selected image block.

        Deletes the entire <div class='block' data-type='Image'>
        from the DOM. No-op if no image is selected.
        """

        self.page().runJavaScript("Editor.deleteImage();")

    def paste_image_from_clipboard(self):
        """
        Paste an image from the system clipboard into the editor.

        Reads the clipboard via QGuiApplication.clipboard().image()
        (more reliable in Qt than navigator.clipboard.read() in JS),
        converts the QImage to a PNG data URL, and inserts it as a
        new Image block at the current cursor position.

        If the clipboard has no image, this is a no-op.
        """

        clipboard = QGuiApplication.clipboard()
        if not clipboard:
            return

        image = clipboard.image()
        if image.isNull():
            # No image in clipboard — try JS clipboard API as fallback
            self.page().runJavaScript("if(window.Editor&&Editor.pasteImageFromClipboard)"
                "Editor.pasteImageFromClipboard();")
            return

        # Convert QImage to PNG data URL
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.data()).decode("ascii")

        js_url = json.dumps(data_url)
        js_block_id = (
            json.dumps(self._last_focused_block_id)
            if self._last_focused_block_id else "null"
        )
        self.page().runJavaScript(
            f"if(window.Editor&&Editor.insertImageFromDataUrl)"
            f"Editor.insertImageFromDataUrl({js_url}, '', {js_block_id});"
        )

    def cut_text(self):
        """Cut current selection to clipboard."""
        self.page().runJavaScript(
            "if(window.Editor&&Editor.cut)Editor.cut();"
        )

    def copy_text(self):
        """Copy current selection to clipboard."""
        self.page().runJavaScript(
            "if(window.Editor&&Editor.copy)Editor.copy();"
        )

    def paste_text(self):
        """Paste from clipboard at current cursor position."""
        self.page().runJavaScript("if(window.Editor && Editor.paste)Editor.paste();")

    def delete_text(self):
        """Delete current selection (no clipboard)."""
        self.page().runJavaScript(
            "if(window.Editor&&Editor.delete)Editor.delete();"
        )

    def get_selected_image(self):
        """
        Return info about the currently selected image, or None.

        The returned dict (when not None) has the shape:
            {
                'type': 'Image',
                'imageId': str,
                'src': str,
                'width': str,        # current display width attribute
                'height': str,       # current display height attribute
                'naturalWidth': int,  # intrinsic image width
                'naturalHeight': int  # intrinsic image height
            }
        """

        return self._selected_image

    # ------------------------------------------------------
    # Text formatting
    # ------------------------------------------------------
    #
    # All formatting methods operate on the current selection
    # inside a .page. If the cursor is collapsed (no selection),
    # the format applies to text typed next.
    #
    # The host app should connect to bridge.selection_changed
    # (already wired to _on_selection_changed) and call
    # get_format_state() to update toolbar button states when
    # the cursor moves.
    #
    # Color values: any CSS color string — "#ff0000", "red",
    # "rgb(255,0,0)", etc.
    #
    # Font family: any CSS font-family value — "Arial",
    # "Times New Roman", "Courier New", etc.
    #
    # Font size: integer pixels (16) or CSS string ("16px",
    # "1.2em", "120%"). Integers are auto-suffixed with "px".
    # ------------------------------------------------------

    def format_bold(self):
        """Toggle bold on the current selection."""
        self.page().runJavaScript("Editor.formatBold();")

    def format_italic(self):
        """Toggle italic on the current selection."""
        self.page().runJavaScript("Editor.formatItalic();")

    def format_underline(self):
        """Toggle underline on the current selection."""
        self.page().runJavaScript("Editor.formatUnderline();")

    def format_strikethrough(self):
        """Toggle strikethrough on the current selection."""
        self.page().runJavaScript("Editor.formatStrikethrough();")

    def format_subscript(self):
        """Toggle subscript on the current selection."""
        self.page().runJavaScript("Editor.formatSubscript();")

    def format_superscript(self):
        """Toggle superscript on the current selection."""
        self.page().runJavaScript("Editor.formatSuperscript();")

    def format_text_color(self, color: str):
        """Set text color. Accepts any CSS color: '#ff0000', 'red', 'rgb(255,0,0)'."""
        js_color = json.dumps(str(color))
        self.page().runJavaScript(f"Editor.formatTextColor({js_color});")

    def format_highlight(self, color: str):
        """Set highlight (background) color. Accepts any CSS color."""
        js_color = json.dumps(str(color))
        self.page().runJavaScript(f"Editor.formatHighlight({js_color});")

    def format_font_family(self, font: str):
        """Set font family. Accepts any CSS font-family: 'Arial', 'Times New Roman'."""
        js_font = json.dumps(str(font))
        self.page().runJavaScript(f"Editor.formatFontFamily({js_font});")

    def format_font_size(self, size):
        """
        Set font size. Accepts an integer (treated as pixels) or a
        CSS string with units: 16, '16px', '1.2em', '120%', '14pt'.
        """
        js_size = json.dumps(str(size))
        self.page().runJavaScript(f"Editor.formatFontSize({js_size});")

    def format_align_left(self):
        """Align current paragraph(s) left."""
        self.page().runJavaScript("Editor.formatAlignLeft();")

    def format_align_center(self):
        """Center-align current paragraph(s)."""
        self.page().runJavaScript("Editor.formatAlignCenter();")

    def format_align_right(self):
        """Right-align current paragraph(s)."""
        self.page().runJavaScript("Editor.formatAlignRight();")

    def format_align_justify(self):
        """Justify current paragraph(s)."""
        self.page().runJavaScript("Editor.formatAlignJustify();")

    def format_indent(self):
        """Increase indentation of current paragraph(s)."""
        self.page().runJavaScript("Editor.formatIndent();")

    def format_outdent(self):
        """Decrease indentation of current paragraph(s)."""
        self.page().runJavaScript("Editor.formatOutdent();")

    def format_ordered_list(self):
        """Toggle numbered list on current paragraph(s)."""
        self.page().runJavaScript("Editor.formatOrderedList();")

    def format_unordered_list(self):
        """Toggle bulleted list on current paragraph(s)."""
        self.page().runJavaScript("Editor.formatUnorderedList();")

    def format_line_height(self, value: str):
        """
        Set line height on the current selection.

        Accepts any CSS line-height value: '1.5', '2', '24px',
        '150%', 'normal'. Wraps the selection in a <span> with
        the specified line-height.
        """
        js_value = json.dumps(str(value))
        self.page().runJavaScript(f"Editor.formatLineHeight({js_value});")

    def format_letter_spacing(self, value: str):
        """
        Set letter spacing on the current selection.

        Accepts any CSS letter-spacing value: '0.5px', '2px',
        '0.1em', 'normal'. Wraps the selection in a <span> with
        the specified letter-spacing.
        """
        js_value = json.dumps(str(value))
        self.page().runJavaScript(f"Editor.formatLetterSpacing({js_value});")

    def format_clear(self):
        """Remove all formatting (bold, color, font, etc.) from selection."""
        self.page().runJavaScript("Editor.formatClear();")

    def insert_half_space(self):
        """
        Insert a half-space (Zero Width Non-Joiner, U+200C) at the
        current cursor position.

        Commonly used in Persian/Arabic typography to prevent
        letter joining (e.g. برای اینکه).
        """
        self.page().runJavaScript(
            "if(window.Editor&&Editor.insertHalfSpace)Editor.insertHalfSpace();"
        )

    def pick_text_color(self):
        """
        Open a QColorDialog and apply the chosen color as text color
        to the current selection.
        """
        from PySide6.QtWidgets import QColorDialog

        initial = "#000000"
        state = getattr(self, '_format_state', {})
        if state and state.get("foreColor"):
            tc = state["foreColor"]
            if tc.startswith("rgb"):
                # Convert "rgb(r, g, b)" to hex
                parts = tc.strip("rgb() ").split(",")
                if len(parts) == 3:
                    r, g, b = [int(p.strip()) for p in parts]
                    initial = f"#{r:02x}{g:02x}{b:02x}"
            
            elif tc.startswith("#"): initial = tc

        color = QColorDialog.getColor(QColor(initial), self, "Text Color")
        
        if color.isValid(): self.format_text_color(color.name())

    def pick_background_color(self):
        """
        Open a QColorDialog and apply the chosen color as text color
        to the current selection.
        """
        from PySide6.QtWidgets import QColorDialog

        initial = "#000000"
        state = getattr(self, '_format_state', {})
        if state and state.get("foreColor"):
            tc = state["foreColor"]
            if tc.startswith("rgb"):
                # Convert "rgb(r, g, b)" to hex
                parts = tc.strip("rgb() ").split(",")
                if len(parts) == 3:
                    r, g, b = [int(p.strip()) for p in parts]
                    initial = f"#{r:02x}{g:02x}{b:02x}"
            elif tc.startswith("#"):
                initial = tc

        color = QColorDialog.getColor(QColor(initial), self, "Text Color")
        
        if color.isValid():
            self.set_background_color(color.name())


    def pick_highlight_color(self):
        """
        Open a QColorDialog and apply the chosen color as highlight
        (background) color to the current selection.
        """
        from PySide6.QtWidgets import QColorDialog

        initial = "#ffff00"  # yellow default for highlight
        state = getattr(self, '_format_state', {})
        if state and state.get("hiliteColor"):
            hc = state["hiliteColor"]
            if hc.startswith("rgb"):
                parts = hc.strip("rgb() ").split(",")
                if len(parts) == 3:
                    r, g, b = [int(p.strip()) for p in parts]
                    initial = f"#{r:02x}{g:02x}{b:02x}"
            elif hc.startswith("#"):
                initial = hc

        color = QColorDialog.getColor(QColor(initial), self, "Highlight Color")
        if color.isValid():
            self.format_highlight(color.name())

    def get_format_state(self) -> dict:
        """
        Return the current format state at the cursor position.

        Keys (all present when cursor is in a .page):
            bold, italic, underline, strikeThrough,
            subscript, superscript — bool
            justifyLeft, justifyCenter, justifyRight, justifyFull — bool
            insertOrderedList, insertUnorderedList — bool
            fontName — str (e.g. 'Arial')
            fontSize — str (HTML size 1-7, often unreliable)
            fontSizePx — str (pixel size from wrapping span, e.g. '16px')
            foreColor — str (e.g. 'rgb(255, 0, 0)')
            hiliteColor — str

        Returns empty dict if cursor is not in a .page.
        """
        return self._format_state

    def query_format_state(self, callback=None):
        """
        Synchronously query the current format state from JS.

        Use get_format_state() for the cached state (updated on
        selectionchange). Use this method only if you need a
        fresh snapshot at a specific moment. The result is
        passed to the callback as a parsed dict.
        """
        def on_result(data):
            if data and callback:
                try:
                    import json as _json
                    callback(_json.loads(data))
                except (ValueError, TypeError):
                    callback({})

        self.page().runJavaScript("Editor.queryFormatState();", on_result if callback else None)

    def set_global_font(self,family:str):
        current = self._global_font
        self._global_font = family or current

        js_font = json.dumps(self._global_font)
        js = f"Editor.setGlobalFont({js_font});"
        
        if not self._editor_is_ready:
            self._pending_operations.append((js, None))
            return

        self.page().runJavaScript(js)

    # ------------------------------------------------------
    # Body direction (RTL / LTR)
    # ------------------------------------------------------
    #
    # Sets the `dir` attribute on the body.
    # Values: 'ltr', 'rtl', or 'auto'
    def set_page_direction(self,direction:str):
        
        direction = direction.lower().strip()

        if direction not in ('ltr', 'rtl', 'auto'): direction = DEFUALT_DIRECTION 

        self._page_direction = direction

        js_dir = json.dumps(direction)
        js = f"Editor.setPageDirection({js_dir});"
        
        if not self._editor_is_ready:
            self._pending_operations.append((js, None))  # ← tuple: (js, callback)
            return

        self.page().runJavaScript(js)
    # ------------------------------------------------------
    # Text direction (RTL / LTR)
    # ------------------------------------------------------
    #
    # Sets the `dir` attribute on the block element (<p>, <h1>,
    # <li>, <td>, etc.) containing the cursor. The chosen
    # direction is remembered and automatically applied to new
    # paragraphs created by pressing Enter, until the user
    # changes direction again.
    #
    # Values: 'ltr', 'rtl', or 'auto'
    # ------------------------------------------------------   
    def format_direction(self, direction: str):
        """
        Set text direction for the current block.

        `direction` must be one of:
            'ltr'  — left-to-right (English, French, etc.)
            'rtl'  — right-to-left (Arabic, Hebrew, Persian, etc.)
            'auto' — browser decides based on content

        The chosen direction is remembered and applied to new
        paragraphs created by pressing Enter.
        """
        direction = direction.lower().strip()

        if direction not in ('ltr', 'rtl', 'auto'): return
        
        self._last_direction = direction
        
        js_dir = json.dumps(direction)
        
        self.page().runJavaScript(f"Editor.formatDirection({js_dir});")

    def format_rtl(self):
        """Set current block to right-to-left direction."""
        self.format_direction('rtl')

    def format_ltr(self):
        """Set current block to left-to-right direction."""
        self.format_direction('ltr')

    def format_direction_auto(self):
        """Set current block to auto-detect direction from content."""
        self.format_direction('auto')

    def get_direction(self) -> str:
        """
        Return the current text direction at the cursor position.

        Returns one of 'ltr', 'rtl', or 'auto'. Falls back to the
        last explicitly-set direction if the cursor isn't in a
        block with a `dir` attribute.
        """
        return getattr(self, '_last_direction', None) or 'ltr'

    def query_direction(self, callback=None):
        """
        Asynchronously query the current direction from JS.

        The result is passed to `callback` as a string. Use
        get_direction() for the cached value.
        """
        def on_result(data):
            if callback and data: callback(str(data))
            elif callback: callback('ltr')

        self.page().runJavaScript("Editor.queryDirection();",  on_result if callback else None)

    # ------------------------------------------------------
    # Document loading — two pipelines
    # ------------------------------------------------------
    #
    # Pipeline 1 (file/string → editor):
    #   load_html_file()      → load_html_string()
    #   load_html_string()    → html_string_to_document()
    #                            (extract CSS, strip :root/body,
    #                             extract scripts, extract body
    #                             content from .page-content divs,
    #                             split into blocks)
    #                         → _build_full_html(document)
    #                         → setHtml(full_html)
    #                         → _editor_ready → paginateAll + makeEditable
    #
    # Pipeline 2 (blocks → editor):
    #   load_blocks()         → html_tags_to_document()
    #                            (strip :root/body from provided CSS,
    #                             create blocks from html_list)
    #                         → _build_full_html(document)
    #                         → setHtml(full_html)
    #                         → _editor_ready → paginateAll + makeEditable
    #
    # Both pipelines converge at _build_full_html + setHtml, then
    # the JS-side _editor_ready handles pagination and editing.
    # ------------------------------------------------------
    def open_text_file(self):
        path, _ = QFileDialog.getOpenFileName(self,"Open Text","","Text File(*.txt)")

        if not path: return

        with open(path, mode="r",encoding="utf-8") as f: text = f.read()

        # ── Build one <p> per line, not one giant <p> full of <br> ──
        #
        # The previous implementation wrapped the ENTIRE text file in a
        # single <p> with <br> between lines:
        #
        #     text = f"<body><div><p>{text.replace(chr(10), '<br>')}</p></div></body>"
        #
        # That produced ONE giant Paragraph block containing thousands of
        # <br> tags. The pagination system's splitTextBlock() walker
        # iterates text nodes (NodeFilter.SHOW_TEXT) and skips <br>
        # elements, so its split-point detection became unreliable:
        #   - splits could land mid-line (cutting words in half)
        #   - <br> elements at split boundaries were lost or duplicated
        #   - the tail on the next page started mid-line
        #
        # The correct model is one <p> per source line. This matches
        # what the pagination system was designed for: each <p> is an
        # independent block that can be moved whole to the next page
        # when it overflows. Empty lines become empty <p> blocks
        # (which render as blank lines and are themselves movable
        # blocks, so they don't collapse or get lost).
        #
        # We also escape the text so user content like "<script>" or
        # "&amp;" in the .txt file is treated as text, not HTML.
        from html import escape as _html_escape

        lines = text.split("\n")
        # Build a flat list of <p>...</p> blocks (no wrapping <div> —
        # the loader treats top-level elements as blocks, and a wrapping
        # <div> would put everything back into one container).
        paragraphs = "".join(
            f"<p>{_html_escape(line)}</p>" for line in lines
        )
        body = f"<body>{paragraphs}</body>"

        self.load_html_string(body, page_mode=PageMode.PAGED, preserve_block_class=True)
    
    def load_html_file(self, allow_scripts=False, preserve_block_class=True):

        path, _ = QFileDialog.getOpenFileName(self,"Open html","","HTML File(*.html)")
        
        if not path: return

        html_string = Path(path).read_text(encoding="utf-8-sig")

        self.load_html_string(html_string, allow_scripts=allow_scripts, preserve_block_class=preserve_block_class)

    def load_blocks(self, html_list:list[str], 
                    page_mode="paged", custom_css="", custom_scripts=None,
                    allow_scripts=False, preserve_block_class=False, callback=None):

        self._page_mode = page_mode
        if not html_list: html_list = ["<p></p>"]
        # 1. Process blocks + CSS + scripts into a Document
        document = html_tags_to_document(html_list, custom_css, custom_scripts, 
                                         allow_scripts, preserve_block_class)
        
        # 2-4. Build full HTML
        full_html = self._build_full_html(document)

        # 5. Load the page
        self.document = document
        self._ready_retries = 0
        self._full_html_loaded = True  # flag: skip _inject_metadata

        resources = Path(__file__).resolve().parent / "resources"
        self.page().setHtml(full_html, QUrl.fromLocalFile(str(resources) + "/"))

        if callback: QTimer.singleShot(0, callback)

    def load_html_string(self, html_string, page_mode= PageMode.PAGED, allow_scripts=False, preserve_block_class=True):
        
        self._page_mode = page_mode

        document = html_string_to_document(html_string, 
                                           allow_scripts=allow_scripts, 
                                           preserve_block_class=preserve_block_class)

        # Build full HTML and load via setHtml
        full_html = self._build_full_html(document)

        self.document = document
        self._ready_retries = 0
        self._full_html_loaded = True

        resources = Path(__file__).resolve().parent / "resources"
        self.page().setHtml(full_html, QUrl.fromLocalFile(str(resources) + "/"))
    
    # Content-change pipeline
    #
    # When the user edits content inside a page, JS debounces the
    # input event and calls bridge.notifyContentChanged(). Python
    # then:
    #
    #   1. Reads the current DOM back into the document model
    #      (sync_from_dom).
    #   2. Checks whether any page now overflows its fixed height
    #      (_maybe_repaginate).
    #   3. If so, asks JS to re-run paginateAll() and reads the
    #      corrected structure back.
    #
    # Without step 2-3, content that overflows a page is silently
    # clipped by the .page { overflow: hidden } CSS rule and the
    # user's edit appears to vanish.
    def _on_content_changed(self):

        # Guard against reentrant calls — when user scripts modify
        # the DOM rapidly (e.g. toggling answers), multiple
        # content_changed signals can fire before the first
        # sync_from_dom callback returns. This causes qwebchannel.js
        # callback slot collisions ("execCallbacks[id] is not a function").
        if getattr(self, '_sync_in_progress', False):
            # Mark that a re-sync is needed after the current one finishes
            self._sync_pending = True
            return

        self._sync_in_progress = True
        self._sync_pending = False

        def wrapped_callback():
            self._maybe_repaginate()
            self._sync_in_progress = False
            if getattr(self, '_sync_pending', False):
                # Another change happened during sync — re-sync
                self._on_content_changed()

        self.sync_from_dom(wrapped_callback)

    def _on_cut_requested(self, text, html):
        """
        Handle cut requests from the JS context menu.

        JS has already deleted the selection from the DOM and sent
        us the (text, html) of what was cut. We just need to write
        it to the system clipboard via Qt — document.execCommand
        ('cut') is unreliable in QtWebEngine, so the clipboard
        write must go through Python.

        The HTML is also stored in self._last_copied_html as a
        backup — Qt's clipboard may not reliably preserve HTML
        on all platforms, so when pasting with "Preserve source
        formatting" we fall back to this stored copy.
        """
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import QMimeData

        clipboard = QGuiApplication.clipboard()
        if not clipboard:
            return

        # Store the HTML as backup for formatted paste
        self._last_copied_html = html or ""
        self._last_copied_text = text or ""

        mime = QMimeData()
        mime.setText(text or "")
        if html:
            mime.setHtml(html)
        clipboard.setMimeData(mime)

    def _on_copy_requested(self, text, html):
        """
        Handle copy requests from the JS context menu.

        JS captured the selection's (text, html) and sent it to us.
        We write it to the system clipboard via Qt — the DOM is
        left untouched (copy does not modify the document).

        The HTML is also stored in self._last_copied_html as a
        backup for formatted paste.
        """
        clipboard = QGuiApplication.clipboard()
        if not clipboard:
            return

        # Store the HTML as backup for formatted paste
        self._last_copied_html = html or ""
        self._last_copied_text = text or ""

        mime = QMimeData()
        mime.setText(text or "")
        if html:
            mime.setHtml(html)
        clipboard.setMimeData(mime)

    def _on_paste_requested(self, kind):
        """
        Handle paste requests from the JS context menu.

        `kind` can be:
            'text'             — paste as plain text (default)
            'text_formatted'   — paste preserving source HTML formatting
            'image'            — paste image from clipboard

        Reads the system clipboard via Qt (bypassing the browser's
        paste permission) and inserts the content via runJavaScript.

        For 'image': if the system clipboard has no image (e.g.
        the image was cut/copied inside the editor, where
        navigator.clipboard.write() is blocked), falls back to
        the JS-side internal image buffer via Editor.pasteImageFromBuffer().
        """
        clipboard = QGuiApplication.clipboard()
        if not clipboard: return

        def _insert_image_from_qimage(image):
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            image.save(buffer, "PNG")
            data_url = "data:image/png;base64," + base64.b64encode(buffer.data()).decode("ascii")
            js_url = json.dumps(data_url)
            js_block_id = json.dumps(self._last_focused_block_id) if self._last_focused_block_id else "null"
            
            self.page().runJavaScript(f"if(window.Editor&&Editor.insertImageFromDataUrl)"
                f"Editor.insertImageFromDataUrl({js_url}, '', {js_block_id});")

        def _insert_text(text):
            # Use the atomic paste function that restores the saved
            # selection AND inserts the text in one JS call. This
            # avoids the async gap where the selection would be lost
            # between Python reading the clipboard and calling back.
            js_text = json.dumps(text)
            self.page().runJavaScript(f"if(window.Editor&&Editor.pasteTextAtSelection)"
                f"Editor.pasteTextAtSelection({js_text});")

        def _insert_html(html):
            # Insert HTML content preserving source formatting.
            # Uses execCommand('insertHTML') which is allowed (not
            # blocked like 'paste').
            js_html = json.dumps(html)
            self.page().runJavaScript(
                f"if(window.Editor&&Editor.pasteHtmlAtSelection)"
                f"Editor.pasteHtmlAtSelection({js_html});"
            )

        if kind == 'image':
            # Try system clipboard image first
            image = clipboard.image()
            if not image.isNull():
                _insert_image_from_qimage(image)
            else:
                # No image in system clipboard — fall back to the
                # JS-side internal buffer (populated by _copyImage
                # when an image is cut/copied inside the editor).
                self.page().runJavaScript(
                    "if(window.Editor&&Editor.pasteImageFromBuffer)"
                    "Editor.pasteImageFromBuffer();"
                )
        elif kind == 'text_formatted':
            # Paste preserving source formatting (HTML)
            mime = clipboard.mimeData()
            if mime and mime.hasImage():
                # Clipboard has an image — paste as image
                image = clipboard.image()
                if not image.isNull():
                    _insert_image_from_qimage(image)
                    return

            text = clipboard.text()
            stored_html = getattr(self, '_last_copied_html', '')
            stored_text = getattr(self, '_last_copied_text', '')

            # If the clipboard text matches our last internal copy,
            # use the stored raw HTML directly — Qt wraps clipboard
            # HTML in <html><body><!--StartFragment-->... which is
            # unreliable to parse back. The stored HTML is the raw
            # DOM innerHTML, which is exactly what we want.
            if stored_html and text == stored_text:
                _insert_html(stored_html)
                return

            # Otherwise, try the clipboard HTML (external copy)
            clip_html = mime.html() if mime and mime.hasHtml() else ""
            if clip_html:
                # Strip Qt's surrounding markers
                import re as _re
                # Extract content between StartFragment/EndFragment
                frag_match = _re.search(
                    r'<!--StartFragment-->(.*?)<!--EndFragment-->',
                    clip_html, _re.DOTALL
                )
                if frag_match:
                    clip_html = frag_match.group(1)
                else:
                    # Strip <html><head>...</head><body>...</body></html>
                    clip_html = _re.sub(
                        r'^\s*<html[^>]*>.*?<body[^>]*>(.*?)</body>\s*</html>\s*$',
                        r'\1', clip_html, flags=_re.DOTALL | _re.IGNORECASE
                    )
                _insert_html(clip_html)
            elif text:
                _insert_text(text)
        else:
            # Default: plain text paste
            mime = clipboard.mimeData()
            if mime and mime.hasImage():
                # Clipboard has an image — paste as image
                image = clipboard.image()
                if not image.isNull():
                    _insert_image_from_qimage(image)
                    return

            text = clipboard.text()
            if text:
                _insert_text(text)

    def _maybe_repaginate(self):

        js = """
        (function() {
            var pages = document.querySelectorAll('.pages-wrapper > .page');
            for (var i = 0; i < pages.length; i++) {
                var c = pages[i].querySelector('.page-content');
                if (c && c.scrollHeight - c.clientHeight > 2) return true;
            }
            return false;
        })();
        """

        def on_check(overflow):

            if not overflow: return

            self.page().runJavaScript("Editor.paginateAll();", self._on_repaginated)

        self.page().runJavaScript(js, on_check)

    def _on_repaginated(self, data):

        if data: self._apply_paginated_structure(data)

    # Call for data export
    def sync_from_dom(self, callback=None):
        # Guard: if a sync is already in progress, queue this one
        # to prevent qwebchannel.js callback slot collisions.
        if getattr(self, '_dom_sync_busy', False):
            prev_callback = getattr(self, '_dom_sync_queued', None)

            def chained():
                if prev_callback: prev_callback()
                if callback: callback()

            self._dom_sync_queued = chained
            return

        self._dom_sync_busy = True
        self._dom_sync_queued = None

        js = "Editor.exportDocument();"

        def on_result(data):
            self._dom_sync_busy = False
            # LIST OF PAGES--> LIST OF BLOCKS
            # (stringify)
            if data: self._apply_paginated_structure(data)

            if callback is not None: callback()

            # If another sync was queued during this one, run it
            queued = getattr(self, '_dom_sync_queued', None)
            if queued:
                self._dom_sync_queued = None
                self.sync_from_dom(queued)

        self.page().runJavaScript(js, on_result)

    def _apply_paginated_structure(self, data):

        try:
            pages_data = json.loads(data) if data else []
            
        except json.JSONDecodeError:
            # Malformed payload from JS — preserve existing model
            # rather than crash. Logs would be appropriate here in
            # production.
            pages_data = []

        self.document.clear_pages()

        new_blocks = []

        for page_blocks in pages_data:

            page = Page()

            for info in page_blocks:

                block = self._block_from_info(info)

                page.add(block)

                new_blocks.append(block)

            self.document.add_page(page)

        self.document.set_blocks(new_blocks)

    def _block_from_info(self, info):

        block_id = info.get("id", "")
        block_type = info.get("type", "Paragraph")
        html = info.get("html", "")
        block_style = info.get("style", "")
        outer_html = info.get("outer_html", "")

        # Reuse the existing block instance when the id matches, so
        # Python-side references (selection, observers, etc.) stay
        # valid and we only mutate the html payload.
        for block in self.document.blocks:

            if block.id == block_id:

                if hasattr(block, "html"):

                    block.html = html

                if hasattr(block, "style"):

                    block.style = block_style

                if hasattr(block, "outer_html"):

                    block.outer_html = outer_html

                if hasattr(block, "content") and block_type == "Math":
                    # Extract formula from data-formula attribute
                    import re
                    match = re.search(r'data-formula="([^"]*)"', html)
                    if match:
                        block.content = match.group(1).replace("&quot;", '"')

                return block

        # New block — typically the tail of a split paragraph or
        # table that JS gave a fresh UUID to.
        if block_type == "Table":

            return Table(html=html, id=block_id, style=block_style, outer_html=outer_html)

        if block_type == "Image":

            img = self._image_from_html(html, block_id, block_style)
            img.outer_html = outer_html
            return img

        if block_type == "Math":

            math = self._math_from_html(html, block_id, block_style)
            math.outer_html = outer_html
            return math

        return Paragraph(html=html, id=block_id, style=block_style, outer_html=outer_html)

    @staticmethod
    def _image_from_html(html, block_id, block_style=""):
        """
        Parse an <img> HTML fragment into an Image block, preserving
        all attributes (src, alt, width, height, style) rather than
        just src.
        """

        parser = _ImgParser()

        try: parser.feed(html)
        except Exception: pass

        return Image(
            src=parser.attrs.get("src", ""),
            alt=parser.attrs.get("alt", ""),
            width=parser.attrs.get("width", ""),
            height=parser.attrs.get("height", ""),
            img_style=parser.attrs.get("style", ""),
            id=block_id,
            style=block_style,
        )

    @staticmethod
    def _math_from_html(html: str, block_id: str, block_style: str = ""):
        """
        Parse a math block HTML fragment into a Math block.
        Extracts the formula content and is_inline flag from the HTML.

        Expected formats:
        - Block: <div class="math-block" data-formula="..."></div>
        - Inline: <span class="math-inline" data-formula="..."></span>
        """
        # Determine if inline or block
        is_inline = "math-inline" in html

        # Extract formula from data-formula attribute
        match = re.search(r'data-formula="([^"]*)"', html)
        formula = match.group(1).replace("&quot;", '"') if match else ""

        return MathBlock(
            content=formula,
            is_inline=is_inline,
            id=block_id,
            style=block_style,
        )

    # Metadata injection
    def _inject_metadata(self):
        """
        Push the document's metadata into the live <head> via JS.

        - Clears any previously-injected custom elements
        - Writes custom_css into <style id="custom-style">
        - Adds <meta name="abdh-document" content="...">
        - If metadata.allow_scripts is True, appends each script
          (external or inline) to <head>

        Called at the end of refresh() so the editor's <head>
        reflects the currently-loaded document.

        SKIPPED when _full_html_loaded is True — CSS and scripts
        are already in the page (loaded via setHtml), so injecting
        them again would cause duplicates and timing issues.
        """

        # Skip if loaded via setHtml (CSS/scripts already in page)
        if getattr(self, '_full_html_loaded', False):
            self._full_html_loaded = False  # reset for next refresh
            return

        meta = self.document.metadata

        # Clear stale custom elements first
        self.page().runJavaScript("Editor.clearCustomElements();")

        # Custom CSS (body rules already stripped by html_loader)
        if meta.custom_css:
            js_css = json.dumps(meta.custom_css)
            self.page().runJavaScript(
                f"Editor.setCustomStyle({js_css});"
            )

        # abdh-document meta tag
        content = f"version={meta.version}; page-system={meta.page_system}"
        js_content = json.dumps(content)
        self.page().runJavaScript(
            f'Editor.setMeta("abdh-document", {js_content});'
        )

        # Scripts (only if allowed at load time)
        if meta.allow_scripts and meta.scripts:
            # Build a SINGLE runJavaScript call that injects all scripts
            # AND dispatches DOMContentLoaded. Each runJavaScript call
            # is async and queued — if we call them separately, the
            # fireContentLoaded() might execute before the scripts
            # have finished registering their event listeners.
            js_parts = ["(function(){"]
            for entry in meta.scripts:
                if entry.inline:
                    js_inline = json.dumps(entry.inline)
                    js_parts.append(f"Editor.addScript(null, {js_inline});")
                elif entry.src:
                    js_src = json.dumps(entry.src)
                    js_parts.append(f"Editor.addScript({js_src}, null);")
            js_parts.append("Editor.fireContentLoaded();")
            js_parts.append("})();")
            self.page().runJavaScript("".join(js_parts))

        # ── Apply page layout settings ──
        meta = self.document.metadata 
    
    # Save
    def save_html_file(self):
        
        path, _ = QFileDialog.getSaveFileName(self,"Save html","","HTML File(*.html)")
        if not path: return

        # ── Strip editor-internal noise from a CLONE before saving ──
        #
        # Two categories of "noise" are removed from the saved file:
        #
        # (A) Rendered KaTeX HTML inside .math-block / .math-inline
        #     spans. These are presentation — rebuilt from
        #     data-formula on the next load by renderMathFormulas().
        #     Storing them causes size bloat, KaTeX-version coupling,
        #     and round-trip parser bugs (the original bug report).
        #
        # (B) Fixed editor resource tags in <head>:
        #       <link id="katex-style" href="KaTeX/katex.min.css">
        #       <link id="preserved-style" href="style.css">
        #       <script src="qrc:///qtwebchannel/qwebchannel.js">
        #       <script src="script.js">
        #       <script src="KaTeX/katex.min.js">
        #       <script src="KaTeX/auto-render.min.js">
        #     These are re-added by _build_full_html() on every load,
        #     so storing them in the saved file is pure duplication.
        #     User-added scripts are marked with data-custom="true"
        #     (see Editor.addScript in script.js) and are PRESERVED.
        #
        # What survives in the saved <head>:
        #   - <meta> tags (charset, viewport, abdh-document)
        #   - <title>
        #   - <style id="custom-style"> with user CSS
        #   - <script data-custom="true"> elements (user scripts)
        #
        # CRITICAL: we strip a CLONE of the document, not the live
        # DOM. Stripping the live DOM would erase rendered formulas
        # from the editor view and detach the fixed scripts/CSS that
        # the running editor still needs. By cloning first, the
        # saved file gets the stripped form; the on-screen editor
        # is completely unaffected.
        #
        # NOTE: PDF / print / PNG export paths deliberately do NOT
        # strip — those outputs need the full live DOM (rendered
        # formulas AND editor resources) to produce correct visual
        # output.

        strip_and_serialize_js = """
        (function() {
            var clone = document.documentElement.cloneNode(true);

            // (A) Strip rendered KaTeX HTML from math wrappers.
            // data-formula attribute is preserved; children are rebuilt
            // by renderMathFormulas() on next load.
            clone.querySelectorAll('.math-block, .math-inline').forEach(function(el) {
                while (el.firstChild) el.removeChild(el.firstChild);
                el.setAttribute('contenteditable', 'false');
            });

            // (B) Strip fixed editor resource tags.
            // User-added scripts (data-custom="true") are kept.
            clone.querySelectorAll('link#katex-style, link#preserved-style').forEach(function(el) {
                el.remove();
            });
            clone.querySelectorAll('script:not([data-custom="true"])').forEach(function(el) {
                el.remove();
            });

            return '<!DOCTYPE html>\\n' + clone.outerHTML;
        })();
        """

        def on_stripped(serialized):
            if not serialized:
                # Unexpected — fall back to live toHtml() so save still works
                self.page().toHtml(lambda html: open(path, 'w', encoding='utf-8').write(html))
                return
            with open(path, 'w', encoding='utf-8') as f:
                f.write(serialized)

        self.page().runJavaScript(strip_and_serialize_js, on_stripped)

    # ------------------------------------------------------
    # PDF export / printing
    # ------------------------------------------------------
    #
    # Two complementary entry points:
    #
    #   save_pdf(path, ...)      → write a .pdf file directly
    #   save_pdf_async(path,...) → same, but blocks the calling
    #                              thread until the file is written
    #   print_document(printer)  → send to a physical printer or
    #                              system print dialog
    #
    # Both rely on Chromium's renderer, so the PDF reflects the
    # CURRENT live DOM (including any unsaved edits) — no
    # sync_from_dom call is needed beforehand.
    # ------------------------------------------------------

    @staticmethod
    def _resolve_page_size(page_size):
        """
        Resolve a page-size argument to a QPageSize.PageSizeId.

        Accepts:
          - A QPageSize.PageSizeId enum value (returned as-is)
          - A QPageSize instance (its id is returned)
          - A string like 'A4', 'Letter', 'Legal', 'A5', 'Tabloid'
            (case-insensitive)
        Falls back to A4 if the value is unknown.
        """
        from PySide6.QtGui import QPageSize

        # Already an enum value
        if isinstance(page_size, QPageSize.PageSizeId):
            return page_size

        # A QPageSize instance
        if isinstance(page_size, QPageSize):
            return page_size.id()

        # String → enum by name
        if isinstance(page_size, str):
            name = page_size.strip().lower().replace("-", "").replace("_", "")
            # Map common names to QPageSize.PageSizeId
            name_map = {
                "a0": QPageSize.PageSizeId.A0,
                "a1": QPageSize.PageSizeId.A1,
                "a2": QPageSize.PageSizeId.A2,
                "a3": QPageSize.PageSizeId.A3,
                "a4": QPageSize.PageSizeId.A4,
                "a5": QPageSize.PageSizeId.A5,
                "a6": QPageSize.PageSizeId.A6,
                "letter": QPageSize.PageSizeId.Letter,
                "legal":  QPageSize.PageSizeId.Legal,
                "tabloid": QPageSize.PageSizeId.Tabloid,
                "ledger":  QPageSize.PageSizeId.Ledger,
                "executive": QPageSize.PageSizeId.ExecutiveStandard,
                "b5": QPageSize.PageSizeId.B5,
                "b4": QPageSize.PageSizeId.B4,
                "com10": QPageSize.PageSizeId.Comm10E,
            }
            return name_map.get(name, QPageSize.PageSizeId.A4)

        return QPageSize.PageSizeId.A4

    def save_pdf(self, page_size="A4", orientation="portrait",  margins=(0, 0, 0, 0), callback=None):
        """
        Save the current document as a PDF file.

        Rendering happens in the Chromium backend; the PDF reflects
        the live DOM at the moment of the call, including any user
        edits that have not yet been synced to the Python model.

        Args:
            path: Output file path (must end with .pdf). The file
                  is opened in 'wb' mode and overwritten if it
                  exists.
            page_size: Page size. Accepts a string ('A4', 'A5',
                       'Letter', 'Legal', 'Tabloid', 'B5', ...),
                       a QPageSize.PageSizeId enum value, or a
                       QPageSize instance. Default 'A4'.
            orientation: 'portrait' (default) or 'landscape'.
            margins: Tuple (top, right, bottom, left) in millimeters.
                     Default 20 mm on all sides. Pass (0,0,0,0) for
                     no margins — useful when the editor's own page
                     margins already produce the desired padding.
            callback: Optional callable(bool) invoked when the PDF
                      has been written (True) or failed (False).
                      Called from the Qt event loop thread.

        Notes:
            - Asynchronous in Qt. For a blocking variant, use
              save_pdf_async().
            - The 'pages' produced by this method are the visual
              pages as Chromium lays them out for printing — they
              do NOT match the editor's logical .page divs 1:1.
              If the editor is in 'paged' mode with the same page
              size and margins, the result will be visually
              identical to the on-screen pages.
        """

        size_id = self._resolve_page_size(page_size)
        page_size_obj = QPageSize(size_id)

        orient = QPageLayout.Orientation.Portrait
        
        if str(orientation).lower().strip() == "landscape": orient = QPageLayout.Orientation.Portrait

        top, right, bottom, left = margins
        margins_obj = QMarginsF(left, top, right, bottom)  # LTRB
        min_margins = QMarginsF(0, 0, 0, 0)

        layout = QPageLayout(page_size_obj, orient, margins_obj, QPageLayout.Unit.Millimeter, min_margins)

        path, _ = QFileDialog.getSaveFileName(self,"Save Pdf","","PDF File(*.pdf)")
        
        if not path: return

        target_path = str(path)

        def on_pdf_finished(pdf_bytes):
            try:
                if not pdf_bytes:
                    if callback: callback(False)
                    return
                
                with open(target_path, "wb") as f: f.write(bytes(pdf_bytes))

                if callback: callback(True)
            
            except OSError:
                if callback: callback(False)

        self.page().printToPdf(on_pdf_finished, layout)

    def save_pdf_async(self, page_size="A4", orientation="portrait", margins=(0, 0, 0, 0)) -> bool:
        """
        Synchronous variant of save_pdf — blocks the calling thread
        until the PDF file has been written.

        Returns True on success, False on failure.

        Use this only from a worker thread; calling it from the
        GUI thread will deadlock because printToPdf needs the event
        loop to deliver its callback.
        """
        loop = QEventLoop()
        result = [False]

        def cb(ok):
            result[0] = bool(ok)
            loop.quit()

        self.save_pdf(page_size=page_size, orientation=orientation,
                      margins=margins, callback=cb)
        loop.exec()
        return result[0]

    def print_document(self, printer=None, callback=None, show_preview=True):
        """
        Print the document using a single custom dialog.

        Replaces the previous QPrintPreviewDialog-based implementation,
        which on Windows invoked the system (Microsoft) print dialog
        when the user clicked Print. This version uses EditorPrintDialog
        — a self-contained dialog with built-in page preview, printer
        picker, and direct-print button. No second (system) dialog ever
        appears.

        Pipeline (all async, no GUI freeze):
          1. printToPdf() renders the live DOM to PDF bytes
          2. QPdfDocument loads the bytes (async, statusChanged)
          3. EditorPrintDialog shows pages + printer picker
          4. On Print click, QPainter.drawImage rasterizes each
             PDF page directly to the chosen QPrinter.

        Printer auto-detection:
          - If physical printers are installed, the system default
            printer is pre-selected in the dialog dropdown.
          - If no physical printers exist, "Save as PDF" is the
            only option.
          - The user can always switch to "Save as PDF" via the
            dropdown.

        Args:
            printer: Optional pre-configured QPrinter. If given
                     AND show_preview=False, prints directly to
                     that printer with no dialog. Ignored when
                     show_preview=True (the dialog's selection
                     wins).
            callback: Optional callable(bool) — True after a
                      successful print, False on cancel/failure.
            show_preview: If True (default), show EditorPrintDialog.
                          If False, print directly using `printer`.

        Margins:
            PDF is generated with A4 + zero margins. The editor's
            .page already has padding:var(--page-margin) applied
            via CSS, so the content area in the PDF already has
            the correct margins baked in. The QPrinter is also
            configured with zero margins, so the rasterized PDF
            page maps 1:1 to the physical sheet — no doubling.

        Requires PySide6 ≥ 6.4 (for QtPdf).
        """
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtGui import (
            QPageLayout, QPageSize, QPainter, QImage, QTransform,
        )
        from PySide6.QtCore import QMarginsF, QSize, QSizeF, QRectF, Qt
        from .ui.print_dialog import EditorPrintDialog

        # ── Hold strong references on self ──
        # PySide6 will GC local closures before Qt fires their
        # callbacks. Park everything in a dict on self and clear
        # it when the pipeline finishes.
        self._print_pipeline = {
            "callback": callback,
            "printer": printer,
            "show_preview": show_preview,
            "doc": None,
            "temp_path": None,
            "on_pdf": None,
            "on_status": None,
            "render_fn": None,
            "dialog": None,
        }
        pipe = self._print_pipeline

        def _cleanup():
            """Release all references so closures can be GC'd."""
            # Delete the temp PDF file too — we don't need it
            # once printing is done.
            temp = pipe.get("temp_path") if pipe else None
            if temp:
                try:
                    import os
                    os.unlink(temp)
                except OSError:
                    pass
            self._print_pipeline = None

        def _render_pages(target_printer):
            """
            Render PDF pages to the given printer via QPainter.

            This is the ONLY place where actual printing happens.
            No system dialog is invoked — we paint directly to the
            QPrinter's paint engine.

            ── Coordinate system (CRITICAL) ──
            QPrinter's painter does NOT use points by default. It
            uses logical pixels at the printer's resolution mode
            (ScreenResolution = 96 DPI by default, HighResolution
            = 1200+ DPI). So a 595pt-wide A4 page is 794 painter
            units wide at 96 DPI.

            The correct approach: get the painter's VIEWPORT, which
            gives us the page dimensions in the painter's native
            units. Then fit the image to that, ignoring points
            entirely. This avoids any DPI mismatch.

            Honors:
              - Page selection (only the pages the user picked)
              - Scale percentage (e.g., 50% = half size, centered)
              - Landscape orientation (rotates each page image 90°)
              - Grayscale (converts image to grayscale before draw)
              - Paper size mismatch (fits PDF page to printer page)
            """
            doc = pipe["doc"]

            # Force zero margins — editor's .page padding provides
            # the content margin; printer must add none.
            # NOTE: QPrinter.Unit is deprecated in PySide6 6.x.
            # Use QPageLayout.Unit instead.
            try:
                target_printer.setPageMargins(
                    QMarginsF(0, 0, 0, 0),
                    QPageLayout.Unit.Millimeter,
                )
            except Exception:
                pass

            # ── Pull user-selected options from the dialog ──
            page_indices = list(range(doc.pageCount()))
            scale_percent = 100
            grayscale = False
            landscape = False

            dialog = pipe.get("dialog")
            if dialog is not None:
                try:
                    page_indices = dialog.get_page_indices()
                except Exception:
                    page_indices = list(range(doc.pageCount()))
                try:
                    scale_percent = dialog.get_scale_percent()
                except Exception:
                    scale_percent = 100
                # Read orientation via pageLayout().orientation() —
                # the most compatible API across PySide6 versions.
                try:
                    layout = target_printer.pageLayout()
                    if layout.orientation() == \
                            QPageLayout.Orientation.Landscape:
                        landscape = True
                except Exception:
                    pass
                try:
                    if target_printer.colorMode() == \
                            QPrinter.ColorMode.GrayScale:
                        grayscale = True
                except Exception:
                    pass

            # ── Render DPI for the rasterized image ──
            # Fixed at 300 DPI — good balance of quality and memory.
            # The pixel dimensions don't affect print size; only the
            # target_rect (in painter units) does.
            RENDER_DPI = 300

            painter = QPainter(target_printer)
            try:
                # ── Get the painter's viewport ──
                # This is the page area in the painter's NATIVE
                # coordinate system (whatever DPI mode the printer
                # is in). Using this avoids all unit-conversion bugs.
                viewport = painter.viewport()
                printer_w = viewport.width()
                printer_h = viewport.height()

                first = True
                for i in page_indices:
                    if i < 0 or i >= doc.pageCount():
                        continue
                    if not first:
                        target_printer.newPage()
                    first = False

                    # ── Step 1: render the PDF page to an image ──
                    pdf_page_size = doc.pagePointSize(i)
                    render_w = max(1, int(
                        pdf_page_size.width() * RENDER_DPI / 72.0
                    ))
                    render_h = max(1, int(
                        pdf_page_size.height() * RENDER_DPI / 72.0
                    ))
                    img = doc.render(i, QSize(render_w, render_h))

                    # ── Step 2: apply grayscale if requested ──
                    if grayscale:
                        img = img.convertToFormat(
                            QImage.Format_Grayscale8
                        )

                    # ── Step 3: apply landscape rotation ──
                    if landscape:
                        transform = QTransform().rotate(90)
                        img = img.transformed(transform)

                    # ── Step 4: fit image to page ──
                    # Compute scale factor that fits the image
                    # inside the printer's page (preserving aspect).
                    # Image pixel dimensions and printer viewport
                    # dimensions are in different units, but the
                    # RATIO is dimensionless and correct.
                    img_w = img.width()
                    img_h = img.height()

                    fit_scale_w = printer_w / img_w
                    fit_scale_h = printer_h / img_h
                    fit_scale = min(fit_scale_w, fit_scale_h)

                    # ── Step 5: apply user's scale percentage ──
                    user_scale = scale_percent / 100.0
                    effective_scale = fit_scale * user_scale

                    final_w = img_w * effective_scale
                    final_h = img_h * effective_scale

                    # ── Step 6: center on the printer's page ──
                    x = (printer_w - final_w) / 2.0
                    y = (printer_h - final_h) / 2.0

                    target_rect = QRectF(x, y, final_w, final_h)

                    # ── Step 7: draw ──
                    # Qt scales the image to fit target_rect in the
                    # painter's coordinate system.
                    painter.drawImage(target_rect, img)
            finally:
                painter.end()

        def _proceed_to_dialog():
            """Once QPdfDocument is Ready, open the print dialog."""
            cb = pipe["callback"]

            if pipe["show_preview"]:
                # ── Custom dialog: ONE window, NO system dialog ──
                dialog = EditorPrintDialog(pipe["doc"], self)
                pipe["dialog"] = dialog

                if dialog.exec() == EditorPrintDialog.DialogCode.Accepted:
                    target = dialog.get_printer()
                    if target is None:
                        _cleanup()
                        if cb: cb(False)
                        return
                    _render_pages(target)
                    _cleanup()
                    if cb: cb(True)
                else:
                    _cleanup()
                    if cb: cb(False)
            else:
                # ── No dialog — print directly to provided printer ──
                target = pipe["printer"]
                if target is None:
                    _cleanup()
                    if cb: cb(False)
                    return
                _render_pages(target)
                _cleanup()
                if cb: cb(True)

        def on_status_changed(status):
            """Fires when QPdfDocument finishes loading."""
            cb = pipe["callback"]
            if status == QPdfDocument.Status.Ready:
                _proceed_to_dialog()
            elif status == QPdfDocument.Status.Error:
                _cleanup()
                if cb: cb(False)

        def on_pdf(pdf_bytes):
            """Fires when Chromium finishes generating the PDF."""
            cb = pipe["callback"]
            if not pdf_bytes:
                _cleanup()
                if cb: cb(False)
                return

            import tempfile
            import os
            fd, temp_path = tempfile.mkstemp(
                suffix=".pdf", prefix="editor_print_"
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(bytes(pdf_bytes))
            except OSError:
                _cleanup()
                if cb: cb(False)
                return

            pipe["temp_path"] = temp_path

            doc = QPdfDocument()
            pipe["doc"] = doc

            # Connect BEFORE load() so we don't miss the Ready signal.
            pipe["on_status"] = on_status_changed
            doc.statusChanged.connect(on_status_changed)

            doc.load(temp_path)

        # Store callbacks so they survive past this function's return
        pipe["on_pdf"] = on_pdf
        pipe["render_fn"] = _render_pages

        # ── PDF generation layout ──
        # A4 + ZERO margins. The editor's .page div already has
        # padding: var(--page-margin) applied via CSS, so the content
        # area in the resulting PDF already has the correct margins.
        # Setting non-zero margins here would DOUBLE the margin.
        page_size_obj = QPageSize(QPageSize.PageSizeId.A4)
        zero_margins = QMarginsF(0, 0, 0, 0)
        layout = QPageLayout(
            page_size_obj,
            QPageLayout.Orientation.Portrait,
            zero_margins,
            QPageLayout.Unit.Millimeter,
            zero_margins,
        )

        # Step 1: kick off PDF generation (async, non-blocking)
        self.page().printToPdf(on_pdf, layout)

    # Export document pages as PNG images.
    # Each logical page becomes a separate image file.
    def export_as_images(self):
        """Capture each .page element as a separate PNG image.

        Uses ``self.grab()`` to snapshot the widget. The widget is
        temporarily resized to fit one page at a time at zoom 1.0,
        making the output zoom-independent and matching the editor's
        CSS pixel dimensions. Each page is saved as a separate file.
        """

        # Temporarily disable browser scrollbars so they do not appear
        # in captured screenshots.
        self.toggle_scroll_visibility(False)

        # JavaScript used to collect geometry information for every page.
        # Execute geometry collection and continue through callback.
        self.page().runJavaScript("Editor.collectPageGeometry()", self._on_page_geometry)
    
        # Receive page geometry data generated by JavaScript and begin
    # the capture process.
    
    def _on_page_geometry(self, data):
        """Receive page geometry from JS, then capture pages one by one."""

        try:
            # Convert JSON string into Python objects if necessary.
            self._img_pages = (json.loads(data) if isinstance(data, str) else data)

        # Ignore malformed or missing data.
        except (json.JSONDecodeError, TypeError):
            self._img_pages = None

        # Abort export if no pages were detected.
        if not self._img_pages:
            QMessageBox.information(self,"Image Export","No pages found.")
            return

        # Store the current widget size so it can be restored later.
        self._img_orig_size = self.size()

        # Store the current browser zoom level.
        self._img_orig_zoom = self.zoomFactor()

        # Store minimum size constraints.
        self._img_orig_min_size = self.minimumSize()

        # Store maximum size constraints.
        self._img_orig_max_size = self.maximumSize()

        # Container that will hold captured page images.
        self._img_results = []

        # Start with the first page.
        self._img_idx = 0

        # Begin page-by-page capture.
        self._capture_next_page()

    # Capture the next page in the export sequence.
    def _capture_next_page(self):
        """Resize widget to fit one page at zoom=1.0, scroll to it, and grab."""

        # If every page has been processed, finish export.
        if self._img_idx >= len(self._img_pages):
            self._finish_image_capture()
            return

        # Retrieve geometry for the current page.
        pg = self._img_pages[self._img_idx]

        # Width of the page.
        page_w = pg['width']

        # Height of the page.
        page_h = pg['height']

        # Scroll position required to view the page.
        scroll_y = pg['scrollY']

        # Disable browser zoom to ensure a 1:1 mapping between CSS
        # pixels and captured image pixels.
        self.setZoomFactor(1.0)

        # Resize the widget so it exactly matches the page size.
        self.setMinimumSize(page_w, page_h)
        self.setMaximumSize(page_w, page_h)
        self.resize(page_w, page_h)

        # Scroll the target page into view.
        # Execute the scroll operation.
        self.page().runJavaScript(f"window.scrollTo(0, {scroll_y});")

        # Allow Chromium layout and rendering to settle before capture.
        QTimer.singleShot(200, self._grab_current_page)
    
    
    # Capture the currently visible page.
    def _grab_current_page(self):
        """Grab the widget content as a QPixmap."""

        # Capture the rendered widget contents.
        pixmap = self.grab()

        # Store the captured image.
        self._img_results.append(pixmap)

        # Advance to the next page.
        self._img_idx += 1

        # Continue the capture process.
        self._capture_next_page()

        # Restore editor state and save captured images.
    
    def _finish_image_capture(self):

        # Restore scrollbar visibility after export.
        self.toggle_scroll_visibility(True)
        
        # Restore the original zoom level.
        self.setZoomFactor(self._img_orig_zoom)

        # Restore minimum size constraints.
        self.setMinimumSize(self._img_orig_min_size)

        # Restore maximum size constraints.
        self.setMaximumSize(self._img_orig_max_size)

        # Restore original widget dimensions.
        self.resize(self._img_orig_size)

        # Ask the user to select an output directory.
        directory = QFileDialog.getExistingDirectory(self, "Select Folder")

        # Continue only if a folder was selected.
        if directory:
            directory = directory.replace('\\','/')
                # Save each page as a separate image file.
            for i, pixmap in enumerate(self._img_results):

                # Build full output path.
                filepath = f'{directory}/page_{i+1}.png'

                # Save image.
                pixmap.save(filepath, "PNG")

                # Inform the user that export completed successfully.
            QMessageBox.information(self,"Image Export", f"Saved {len(self._img_results)} page image(s) to:\n{directory}")

        # Release image buffers.
        self._img_results = []

        # Release page geometry cache.
        self._img_pages = None
    
    def toggle_scroll_visibility(self,visible:bool=True):

        if visible: 
              js='document.documentElement.style.overflow = ""; document.body.style.overflow = "";'
        else: js='document.documentElement.style.overflow ="hidden"; document.body.style.overflow = "hidden";'
        
        self.page().runJavaScript(js)


    def page_count(self):

        return len(self.document.pages)

    # ------------------------------------------------------
    # Mode switching (paged vs continuous)
    # ------------------------------------------------------
    #
    # Paged mode (default):
    #   - Content is split into fixed-size pages (A4-like)
    #   - Page-number markers appear between pages
    #   - Tables/paragraphs split across page boundaries
    #
    # Continuous mode:
    #   - All content on a single growing page (no splitting)
    #   - No page-number markers
    #   - Page just grows tall to fit all content
    #
    # Switching modes triggers a refresh() so the layout updates.
    # ------------------------------------------------------
    def switch_page_mode(self):
        
        mode  = PageMode.CONTINUOUS if self._page_mode == PageMode.PAGED else PageMode.PAGED
        self.set_page_mode(mode)
        
    def set_page_mode(self, mode):
        
        mode = mode.lower().strip()
        if mode not in PageMode: mode = PageMode.PAGED
        self._page_mode = mode
        js_mode = json.dumps(mode)

        js = f"""
        (function() 
        {{
            if (window.Editor && Editor.setMode) Editor.setMode({js_mode});
            var result = Editor.paginateAll();
            return result;
        }})();
        """

        def on_paginated(data):
            if data:  self._apply_paginated_structure(data)

        if not self._editor_is_ready:
            self._pending_operations.append((js, on_paginated))  # ← callback preserved!
            return

        self.page().runJavaScript(js, on_paginated)

    def get_page_mode(self): return self._page_mode

    def _build_full_html(self, document:Document)->str:
        
        #resources = Path(__file__).resolve().parent / "resources"

        # 1. Process blocks → render to block HTML (NOT page-wrapped)
        draft_page = Page()
        for block in document.blocks: draft_page.add(block)
        
        document.clear_pages()
        
        document.add_page(draft_page)
        
        # Use render_blocks to get JUST the block divs, not wrapped in .page
        blocks_html = self.renderer.render_blocks(draft_page)

        # 2. Process styles
        custom_css = document.metadata.custom_css or ""

        # 3. Find scripts
        script_tags = ""
        
        if document.metadata.allow_scripts:
            for entry in document.metadata.scripts:
                if entry.inline:
                    script_tags += f"\n<script>{entry.inline}</script>"
                elif entry.src:
                    script_tags += f'\n<script src="{entry.src}"></script>'
                
        # 4. Build the exact HTML structure
        meta_content = f"version={__document_version__}; page-system={document.metadata.page_system}"

        # Apply mode class on #editor if continuous
        mode = getattr(self, '_page_mode', 'paged')
        editor_class = 'class="continuous-mode"' if mode == PageMode.CONTINUOUS else ''

        full_html = f'''
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta name="abdh-document" content="{meta_content}">
                <title>Editor</title>
                <link id="katex-style" rel="stylesheet" href="KaTeX/katex.min.css">
                <link id="preserved-style" rel="stylesheet" href="style.css">
                <style id="custom-style">
                    {custom_css}
                </style>
                <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
                <script src="script.js"></script>
                <script src="KaTeX/katex.min.js"></script>
                <script src="KaTeX/auto-render.min.js"></script>
                {script_tags}
            </head>
            <body>
                <div id="editor" {editor_class} style="visibility:hidden;">
                    <div class="pages-wrapper">
                        <div class="page" data-page="0">
                            <div class="page-content">
                                {blocks_html}
                            </div>
                        </div>
                    </div>
                </div>

                <div id="loading-overlay" class="loading-overlay visible">
                    <div class="loading-container">
                        <div class="loading-spinner"></div>
                        <div class="loading-text">Loading…</div>
                    </div>
                </div>

                <div id="context-menu" class="context-menu" style="display:none;direction: ltr;"></div>
            </body>
        </html>
        '''
        
        return full_html

    def export_blocks(self, callback=None):
        """
        Extract all blocks (with all user-applied properties) as a
        list of plain dicts. First syncs the DOM back to the Python
        document model so pending edits are captured.

        Each dict has: id, type, html, style, outer_html, and any
        subclass-specific fields (src, width, height, content, etc.)

        Args:
            callback: called with the list of block dicts after sync.
        """
        def on_synced():
            block_list = self.document.to_list()
            
            if callback: callback(block_list)

        self.sync_from_dom(on_synced)

    # Block the calling thread until the complete Chromium page HTML (including <style>) is ready.
    def export_blocks_async(self)->list[dict]:

        # Create a local event loop that will be stopped when toHtml returns.
        loop = QEventLoop()

        # Container list that captures the full page HTML from the toHtml callback.
        blocks:list[dict] = []

        # Callback invoked by page().toHtml; stores the HTML and exits the event loop.
        def cb(blocks_):
            for b in blocks_:
                blocks.append(b)
            
            loop.quit()

        # Request the complete page HTML from Chromium and wire the result to cb.
        self.export_blocks(cb)

        # Block here until the toHtml callback fires and loop.quit() is called.
        loop.exec()

        # Return the captured full-page HTML document string.
        return blocks
    
    def get_pages_content_async(self):
        
        loop = QEventLoop()
        contents = []
        def cb(data):
            if data: contents.extend(json.loads(data))

            loop.quit()
            
        self.page().runJavaScript("Editor.getPageContents()", cb)

        loop.exec()

        return contents
    
    def get_content_html(self, callback=None):
        """
        Sync the live DOM back to Python, then return the full body
        HTML (all blocks concatenated).

        Use this instead of document.to_html() when you want the
        CURRENT content including user edits that haven't been
        synced yet. document.to_html() only reads the Python model,
        which may be stale — this method syncs first.

        Args:
            callback: called with the HTML string after sync completes.

        Example:
            # Get current content (including unsaved edits)
            editor.get_content_html(lambda html: print(html))

            # Save to file
            editor.get_content_html(lambda html:
                open("output.html", "w", encoding="utf-8").write(html))
        """
        def on_synced():
            html = self.document.to_html()
            if callback:
                callback(html)

        self.sync_from_dom(on_synced)