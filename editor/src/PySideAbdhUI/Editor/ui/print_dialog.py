"""
Advanced custom print dialog for the Editor.

Features:
  - Auto-detects physical printers via QPrinterInfo
  - Defaults to the system default printer if any exist
  - Falls back to "Save as PDF" when no physical printers
    are available
  - Live page preview at 200 DPI, scaled to fit the dialog
  - Paper size, orientation, color mode, duplex, page range,
    copies, and scale controls
  - Direct print via QPainter — never triggers the OS
    native print dialog
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QScrollArea, QWidget, QFileDialog,
    QRadioButton, QButtonGroup, QLineEdit, QGroupBox,
    QSizePolicy,
)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtGui import QPageLayout, QPixmap, QImage, QPainter, QPageSize, QTransform
from PySide6.QtCore import Qt, QSize, QMarginsF
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo


# Paper sizes offered in the dropdown.
# Maps user-facing label → QPageSize.PageSizeId.
PAPER_SIZES = [
    ("A4 (210 x 297 mm)",     QPageSize.PageSizeId.A4),
    ("A5 (148 x 210 mm)",     QPageSize.PageSizeId.A5),
    ("A3 (297 x 420 mm)",     QPageSize.PageSizeId.A3),
    ("Letter (8.5 x 11 in)",  QPageSize.PageSizeId.Letter),
    ("Legal (8.5 x 14 in)",   QPageSize.PageSizeId.Legal),
    ("Tabloid (11 x 17 in)",  QPageSize.PageSizeId.Tabloid),
    ("B5 (176 x 250 mm)",     QPageSize.PageSizeId.B5),
]

# Preview render DPI. Higher = sharper preview but more memory.
# 360 DPI is a good balance: A4 = 1654 x 2339 px ≈ 4 MP per page.
PREVIEW_DPI = 360

# Maximum preview width on screen (pixels) at 100% zoom.
# The pixmap is scaled down from PREVIEW_DPI to fit this width,
# preserving aspect ratio.
PREVIEW_BASE_WIDTH = 380

# Zoom range for the preview (percent).
ZOOM_MIN = 25
ZOOM_MAX = 400
ZOOM_STEP = 25
ZOOM_DEFAULT = 125


class EditorPrintDialog(QDialog):
    """
    Modal print dialog with built-in page preview and advanced options.

    Usage:
        dialog = EditorPrintDialog(pdf_document, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            printer = dialog.get_printer()
            page_indices = dialog.get_page_indices()
            # render pages[page_indices] to printer via QPainter...
    """

    def __init__(self, pdf_document: QPdfDocument, parent=None):
        super().__init__(parent)
        self.pdf_doc = pdf_document
        self.printer = None
        self.page_indices = list(range(pdf_document.pageCount()))

        # Current zoom level (percent). 100 = fit-to-base-width.
        self.zoom_percent = ZOOM_DEFAULT

        self.setWindowTitle("Print Document")
        self.setModal(True)
        self.resize(1080, 720)

        # Cached full-resolution preview pixmaps, keyed by page index.
        # Re-rendered only when paper size / orientation changes.
        # Zoom changes scale these cached pixmaps instead of
        # re-rendering from the PDF (which is expensive).
        self._preview_cache = {}

        self._build_ui()
        self._render_preview()

    # ------------------------------------------------------
    # UI construction
    # ------------------------------------------------------

    def _build_ui(self):
        outer = QHBoxLayout(self)
        #outer.setContentsMargins(0, 0, 0, 0)
        #outer.setSpacing(0)

        # ── Left: options panel ──
        options_widget = QWidget()
        options_widget.setFixedWidth(320)

        options_layout = QVBoxLayout(options_widget)
        #options_layout.setContentsMargins(12, 12, 12, 12)
        #options_layout.setSpacing(8)

        # ── Printer section ──
        printer_group = QGroupBox("Printer")
        printer_layout = QVBoxLayout(printer_group)
        #printer_layout.setContentsMargins(8, 4, 8, 8)

        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(280)
        self._populate_printers()
        printer_layout.addWidget(self.printer_combo)

        options_layout.addWidget(printer_group)

        # ── Page setup section ──
        page_group = QGroupBox("Page Setup")
        page_form = QFormLayout(page_group)
        #page_form.setContentsMargins(8, 4, 8, 8)
        #page_form.setSpacing(6)

        self.paper_combo = QComboBox()
        for label, _ in PAPER_SIZES:
            self.paper_combo.addItem(label)
        self.paper_combo.setCurrentIndex(0)  # A4 default
        page_form.addRow("Paper size:", self.paper_combo)

        self.orient_combo = QComboBox()
        self.orient_combo.addItem("Portrait", "portrait")
        self.orient_combo.addItem("Landscape", "landscape")
        page_form.addRow("Orientation:", self.orient_combo)

        self.color_combo = QComboBox()
        self.color_combo.addItem("Color", "color")
        self.color_combo.addItem("Grayscale", "grayscale")
        page_form.addRow("Color mode:", self.color_combo)

        self.duplex_combo = QComboBox()
        self.duplex_combo.addItem("One-sided", QPrinter.DuplexMode.DuplexNone)
        self.duplex_combo.addItem("Two-sided (long edge)", QPrinter.DuplexMode.DuplexLongSide)
        self.duplex_combo.addItem("Two-sided (short edge)", QPrinter.DuplexMode.DuplexShortSide)
        page_form.addRow("Duplex:", self.duplex_combo)
        self._update_duplex_support()

        # When printer changes, refresh duplex support
        self.printer_combo.currentIndexChanged.connect(self._update_duplex_support)

        options_layout.addWidget(page_group)

        # ── Pages section ──
        pages_group = QGroupBox("Pages")
        pages_layout = QVBoxLayout(pages_group)
        #pages_layout.setContentsMargins(8, 4, 8, 8)
        #pages_layout.setSpacing(6)

        self.all_pages_radio = QRadioButton("All pages")
        self.all_pages_radio.setChecked(True)
        pages_layout.addWidget(self.all_pages_radio)

        range_row = QHBoxLayout()
        self.range_radio = QRadioButton("Range:")
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("e.g. 1-3, 5, 8-10")
        self.range_edit.setEnabled(False)
        range_row.addWidget(self.range_radio)
        range_row.addWidget(self.range_edit, 1)
        pages_layout.addLayout(range_row)

        # Radio group: only one of All / Range can be checked
        self.pages_group = QButtonGroup(self)
        self.pages_group.addButton(self.all_pages_radio)
        self.pages_group.addButton(self.range_radio)

        self.all_pages_radio.toggled.connect(
            lambda checked: self.range_edit.setEnabled(not checked)
        )

        # Live-validate page range as the user types
        self.range_edit.textChanged.connect(self._update_status)
        self.all_pages_radio.toggled.connect(self._update_status)
        self.range_radio.toggled.connect(self._update_status)

        options_layout.addWidget(pages_group)

        # ── Copies & scale section ──
        copies_group = QGroupBox("Copies & Scale")
        copies_form = QFormLayout(copies_group)
        #copies_form.setContentsMargins(8, 4, 8, 8)
        #copies_form.setSpacing(6)

        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        self.copies_spin.setValue(1)
        copies_form.addRow("Copies:", self.copies_spin)

        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(25, 200)
        self.scale_spin.setValue(100)
        self.scale_spin.setSuffix("%")
        copies_form.addRow("Scale:", self.scale_spin)

        options_layout.addWidget(copies_group)

        # ── Status ──
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; padding: 4px; font-size: 11px;")
        self.status_label.setWordWrap(True)
        options_layout.addWidget(self.status_label)

        options_layout.addStretch()

        # ── Action buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.print_btn = QPushButton("Print")
        self.print_btn.setDefault(True)
        self.print_btn.setMinimumHeight(32)
        
        self.print_btn.clicked.connect(self._on_print)
        btn_row.addWidget(self.print_btn, 1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(32)
        
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn, 1)

        options_layout.addLayout(btn_row)

        outer.addWidget(options_widget)

        # ── Right: preview area ──
        preview_widget = QWidget()
        #preview_widget.setStyleSheet("background: #4a4a4a;")
        preview_layout = QVBoxLayout(preview_widget)
        #preview_layout.setContentsMargins(0, 0, 0, 10)
        #preview_layout.setSpacing(0)

        # Preview header with zoom controls
        header_widget = QWidget()
        #header_widget.setStyleSheet("background: #2d2d2d;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(8)

        header_label = QLabel("Preview")
        #header_label.setStyleSheet("color: white; font-weight: bold;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        # Zoom out button
        self.zoom_out_btn = QPushButton("−")
        #self.zoom_out_btn.setFixedSize(28, 24)
        self.zoom_out_btn.setToolTip("Zoom out")
        
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        header_layout.addWidget(self.zoom_out_btn)

        # Zoom percentage spinbox
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(ZOOM_MIN, ZOOM_MAX)
        self.zoom_spin.setValue(ZOOM_DEFAULT)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setFixedWidth(80)
        
        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        header_layout.addWidget(self.zoom_spin)

        # Zoom in button
        self.zoom_in_btn = QPushButton("+")
        #self.zoom_in_btn.setFixedSize(28, 24)
        self.zoom_in_btn.setToolTip("Zoom in")
        
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        header_layout.addWidget(self.zoom_in_btn)

        # Fit to width button
        self.fit_btn = QPushButton("Fit")
        #self.fit_btn.setFixedHeight(24)
        self.fit_btn.setToolTip("Fit to width")
        
        self.fit_btn.clicked.connect(self._zoom_fit)
        header_layout.addWidget(self.fit_btn)

        # Actual size (100%) button
        self.actual_btn = QPushButton("1:1")
        #self.actual_btn.setFixedHeight(24)
        self.actual_btn.setToolTip("Actual size (100%)")
       
        self.actual_btn.clicked.connect(self._zoom_actual)
        header_layout.addWidget(self.actual_btn)

        preview_layout.addWidget(header_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.preview_container = QWidget()
        self.preview_container.setStyleSheet("background: #4a4a4a;")
        preview_vlayout = QVBoxLayout(self.preview_container)
        preview_vlayout.setAlignment(Qt.AlignCenter)

        # One QLabel per page
        self.page_labels = []
        page_count = self.pdf_doc.pageCount()
        for i in range(page_count):
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            preview_vlayout.addWidget(lbl)
            self.page_labels.append(lbl)

        self.scroll_area.setWidget(self.preview_container)
        preview_layout.addWidget(self.scroll_area, 1)

        # Enable mouse-wheel zoom on the preview area.
        # Ctrl+Wheel = zoom in/out (standard convention).
        # Plain wheel = normal scroll.
        self.scroll_area.wheelEvent = self._on_preview_wheel

        outer.addWidget(preview_widget, 1)

        # ── Wire up re-render on option change ──
        # Paper size, orientation, and color mode all affect the cached
        # preview pixmaps → call _render_preview() (expensive).
        # Zoom changes only scale the cached pixmaps → handled separately.
        self.paper_combo.currentIndexChanged.connect(self._render_preview)
        self.orient_combo.currentIndexChanged.connect(self._render_preview)
        self.color_combo.currentIndexChanged.connect(self._render_preview)

        self._update_status()

    def _populate_printers(self):
        """Fill the printer dropdown with available printers."""
        physical_printers = QPrinterInfo.availablePrinters()
        default_idx = 0
        for i, info in enumerate(physical_printers):
            label = info.printerName()
            if info.isDefault():
                label += "  (default)"
                default_idx = i
            self.printer_combo.addItem(label, info)

        # Always add "Save as PDF" as the last option
        self.printer_combo.addItem("Save as PDF…", None)

        if physical_printers:
            self.printer_combo.setCurrentIndex(default_idx)
        else:
            # No physical printers — force PDF mode
            self.printer_combo.setCurrentIndex(
                self.printer_combo.count() - 1
            )

    def _update_duplex_support(self):
        """Enable/disable duplex options based on printer support."""
        printer_info = self.printer_combo.currentData()
        if printer_info is None:
            # PDF mode — no duplex
            self.duplex_combo.setEnabled(False)
            self.duplex_combo.setCurrentIndex(0)
            return

        self.duplex_combo.setEnabled(True)
        # Could check supportedDuplexModes() here, but most
        # modern printers support at least long-edge duplex.
        # If unsupported, the printer driver will silently
        # fall back to one-sided.

    def _update_status(self):
        """Update the status label at the bottom of options panel."""
        page_count = self.pdf_doc.pageCount()
        selected = self._compute_page_indices()
        if selected is None:
            self.status_label.setText(
                f"⚠ Invalid page range  ·  "
                f"Document has {page_count} page(s)"
            )
            self.print_btn.setEnabled(False)
        else:
            n = len(selected)
            self.status_label.setText(
                f"Document: {page_count} page(s)  ·  "
                f"Printing: {n} page(s)  ·  "
                f"Zoom: {self.zoom_percent}%  ·  "
                f"Preview: {PREVIEW_DPI} DPI"
            )
            self.print_btn.setEnabled(True)

    # ------------------------------------------------------
    # Preview rendering
    # ------------------------------------------------------

    def _render_preview(self):
        """
        Render each PDF page into a full-resolution QPixmap and cache it.

        Called once at dialog open, and again whenever the paper size
        or orientation changes (which changes the page dimensions).
        Zoom changes do NOT call this — they call _apply_zoom() which
        just re-scales the cached pixmaps (much cheaper).
        """
        self._preview_cache.clear()

        page_count = self.pdf_doc.pageCount()
        if page_count == 0:
            return

        is_landscape = (
            self.orient_combo.currentData() == "landscape"
        )
        is_grayscale = (
            self.color_combo.currentData() == "grayscale"
        )

        dpi = PREVIEW_DPI
        for i in range(page_count):
            try:
                page_size = self.pdf_doc.pagePointSize(i)
                w = max(1, int(page_size.width() * dpi / 72.0))
                h = max(1, int(page_size.height() * dpi / 72.0))
                img = self.pdf_doc.render(i, QSize(w, h))

                # Grayscale conversion for preview (matches print output)
                if is_grayscale:
                    img = img.convertToFormat(QImage.Format_Grayscale8)

                # Rotate for landscape preview
                if is_landscape:
                    transform = QTransform().rotate(90)
                    img = img.transformed(transform)

                self._preview_cache[i] = QPixmap.fromImage(img)
            except Exception:
                self._preview_cache[i] = None

        # Apply current zoom to display the cached pixmaps
        self._apply_zoom()

    def _apply_zoom(self):
        """
        Scale the cached full-resolution pixmaps to the current zoom
        level and update the QLabels.

        Cheap operation — just scales pre-rendered pixmaps. Called
        on every zoom change without re-rendering from the PDF.
        """
        zoom = self.zoom_percent / 100.0
        target_w = int(PREVIEW_BASE_WIDTH * zoom)

        for i, lbl in enumerate(self.page_labels):
            pm = self._preview_cache.get(i)
            if pm is None or pm.isNull():
                lbl.setText(f"(failed to render page {i + 1})")
                continue

            # Scale by width, preserve aspect ratio.
            # SmoothTransformation uses bilinear filtering for sharp result.
            aspect = pm.height() / pm.width()
            target_h = int(target_w * aspect)

            scaled = pm.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl.setPixmap(scaled)
            lbl.setFixedSize(target_w, target_h)

    # ------------------------------------------------------
    # Zoom controls
    # ------------------------------------------------------

    def _on_zoom_changed(self, value: int):
        """Called when the zoom spinbox value changes."""
        self.zoom_percent = value
        self._apply_zoom()
        self._update_status()

    def _zoom_in(self):
        """Increase zoom by one step."""
        new = min(ZOOM_MAX, self.zoom_spin.value() + ZOOM_STEP)
        self.zoom_spin.setValue(new)

    def _zoom_out(self):
        """Decrease zoom by one step."""
        new = max(ZOOM_MIN, self.zoom_spin.value() - ZOOM_STEP)
        self.zoom_spin.setValue(new)

    def _zoom_fit(self):
        """Reset to default fit-to-width (100%)."""
        self.zoom_spin.setValue(ZOOM_DEFAULT)

    def _zoom_actual(self):
        """
        Show at "actual size" — 1:1 mapping between PDF points and
        screen pixels (approximate, since screen DPI varies).

        At PREVIEW_DPI=200, an A4 page is 1654x2339 px. At 100% zoom,
        we display it at 380px wide. To show "actual size" (where 1pt
        in the PDF = ~1.38 screen px at 100 DPI screen), we want
        about 826px wide for A4. So 1:1 ≈ 217% on a 100 DPI screen.
        """
        # Estimate based on screen DPI vs preview DPI
        screen_dpi = self.logicalDpiX() or 96
        # Scale factor: at 100%, target_w = PREVIEW_BASE_WIDTH = 380
        # which corresponds to PREVIEW_DPI/96 ≈ 2.08x downscale.
        # For 1:1, we want target_w = (page_width_in_pt) * screen_dpi / 72
        # Approximate A4 width = 595 pt
        actual_target_w = int(595 * screen_dpi / 72.0)
        zoom_for_actual = int(actual_target_w * 100 / PREVIEW_BASE_WIDTH)
        zoom_for_actual = max(ZOOM_MIN, min(ZOOM_MAX, zoom_for_actual))
        self.zoom_spin.setValue(zoom_for_actual)

    def _on_preview_wheel(self, event):
        """
        Handle mouse wheel over the preview area.

        Ctrl+Wheel  → zoom in/out (in ZOOM_STEP increments)
        Plain wheel → normal scroll (default behavior)
        """
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QWheelEvent

        if not isinstance(event, QWheelEvent):
            return

        # Check if Ctrl modifier is held
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()
            event.accept()
            return

        # Plain wheel — fall back to default scroll behavior
        QScrollArea.wheelEvent(self.scroll_area, event)

    # ------------------------------------------------------
    # Page range parsing
    # ------------------------------------------------------

    def _compute_page_indices(self):
        """
        Parse the page range and return a list of 0-based page
        indices, or None if the range is invalid.

        Supported syntaxes:
            "1-3"      → [0, 1, 2]
            "5"        → [4]
            "1-3, 5"   → [0, 1, 2, 4]
            "1-3, 8-10"→ [0, 1, 2, 7, 8, 9]
        """
        total = self.pdf_doc.pageCount()
        if total == 0:
            return []

        if self.all_pages_radio.isChecked():
            return list(range(total))

        text = self.range_edit.text().strip()
        if not text:
            return None

        result = []
        seen = set()
        try:
            for part in text.split(","):
                part = part.strip()
                if not part:
                    continue

                if "-" in part:
                    lo_str, hi_str = part.split("-", 1)
                    lo = int(lo_str.strip())
                    hi = int(hi_str.strip())
                    if lo < 1 or hi > total or lo > hi:
                        return None
                    for p in range(lo, hi + 1):
                        if p - 1 not in seen:
                            seen.add(p - 1)
                            result.append(p - 1)
                else:
                    p = int(part)
                    if p < 1 or p > total:
                        return None
                    if p - 1 not in seen:
                        seen.add(p - 1)
                        result.append(p - 1)
        except ValueError:
            return None

        return sorted(result) if result else None

    # ------------------------------------------------------
    # Print action
    # ------------------------------------------------------

    def _on_print(self):
        """
        Build a QPrinter from the user's selections and accept
        the dialog. The caller then renders pages to this printer
        via QPainter — no system print dialog is invoked.
        """
        # Validate page range
        indices = self._compute_page_indices()
        if indices is None:
            self.status_label.setText("⚠ Invalid page range")
            return

        printer_info = self.printer_combo.currentData()

        if printer_info is None:
            # ── Save as PDF mode ──
            path, _ = QFileDialog.getSaveFileName(
                self, "Save PDF As", "document.pdf",
                "PDF Files (*.pdf)"
            )
            if not path:
                return  # stay on print dialog

            self.printer = QPrinter()
            self.printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            self.printer.setOutputFileName(path)
        else:
            # ── Physical printer mode ──
            self.printer = QPrinter(printer_info)
            self.printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)

        # ── Apply page setup ──
        paper_size_id = PAPER_SIZES[self.paper_combo.currentIndex()][1]
        self.printer.setPageSize(QPageSize(paper_size_id))

        # NOTE: setPageOrientation() is deprecated in PySide6 6.x.
        # Use pageLayout().setOrientation() instead, then push the
        # layout back to the printer.
        orientation = self.orient_combo.currentData()
        try:
            layout = self.printer.pageLayout()
            if orientation == "landscape":
                layout.setOrientation(QPageLayout.Orientation.Landscape)
            else:
                layout.setOrientation(QPageLayout.Orientation.Portrait)
            self.printer.setPageLayout(layout)
        except Exception:
            # Fallback for older PySide6 versions
            try:
                if orientation == "landscape":
                    self.printer.setPageOrientation(
                        QPageLayout.Orientation.Landscape
                    )
                else:
                    self.printer.setPageOrientation(
                        QPageLayout.Orientation.Portrait
                    )
            except Exception:
                pass

        # ── Color mode ──
        if self.color_combo.currentData() == "grayscale":
            self.printer.setColorMode(QPrinter.ColorMode.GrayScale)
        else:
            self.printer.setColorMode(QPrinter.ColorMode.Color)

        # ── Duplex ──
        duplex = self.duplex_combo.currentData()
        try:
            self.printer.setDuplex(duplex)
        except Exception:
            pass  # not all printers support all duplex modes

        # ── Zero margins (editor's .page padding provides content margin) ──
        # NOTE: QPrinter.Unit is deprecated in PySide6 6.x.
        # Use QPageLayout.Unit instead.
        self.printer.setPageMargins(
            QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter
        )

        # ── Copies ──
        self.printer.setCopyCount(self.copies_spin.value())

        # Store selected page indices for the caller
        self.page_indices = indices

        self.accept()

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------

    def get_printer(self) -> QPrinter:
        """Return the configured QPrinter (after exec() returns Accepted)."""
        return self.printer

    def get_page_indices(self) -> list:
        """
        Return the 0-based page indices the user wants to print.

        Only valid after exec() returns Accepted.
        """
        return self.page_indices

    def get_scale_percent(self) -> int:
        """Return the user's chosen scale percentage (25–200)."""
        return self.scale_spin.value()
