
import enum

from PySide6.QtWidgets import (QButtonGroup, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                                QPushButton, QRadioButton, QSpinBox, QVBoxLayout)

class DialogCode(enum.IntEnum):
    Rejected                  = 0x0
    Accepted                  = 0x1

class MathFormulaDialog(QDialog):
    """A modal dialog to input a math formula and choose inline/block mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Math Formula")
        self.setModal(True)

        # ---- Widgets ----
        self.formula_edit = QLineEdit()
        self.formula_edit.setPlaceholderText("e.g. \\frac{a}{b}")

        self.inline_radio = QRadioButton("Inline")
        self.block_radio = QRadioButton("Block")
        self.inline_radio.setChecked(True)

        # Group the radio buttons so only one can be selected
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.inline_radio, 0)   # id 0 = inline
        self.mode_group.addButton(self.block_radio, 1)    # id 1 = block

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")

        # ---- Layout ----
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Formula input
        layout.addWidget(QLabel("Math formula (LaTeX, without delimiters):"))
        layout.addWidget(self.formula_edit)

        # Mode selection
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(QLabel("Display mode:"))
        radio_layout.addWidget(self.inline_radio)
        radio_layout.addWidget(self.block_radio)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(btn_ok)
        button_layout.addWidget(btn_cancel)
        layout.addLayout(button_layout)

        # ---- Connections ----
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        # Pressing Enter in the line edit also accepts
        self.formula_edit.returnPressed.connect(self.accept)

        # ---- Final setup ----
        self.formula_edit.setFocus()
        self.resize(450, 150)
        #self.center_on_parent(parent)

    def get_formula(self):
        """Return the raw LaTeX string or None if the dialog was rejected."""
        if self.result() != DialogCode.Accepted: return None

        formula = self.formula_edit.text().strip()

        return formula

    def is_inline(self):
        """Return True when the dialog mode is inline math."""
        return self.mode_group.checkedId() == 0


class TableDialog(QDialog):
    """A modal dialog to choose the size (rows x columns) of a new table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Table")
        self.setModal(True)

        # ---- Widgets ----
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setValue(3)

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 20)
        self.cols_spin.setValue(3)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")

        # ---- Layout ----
        form = QFormLayout()
        form.addRow("Rows:", self.rows_spin)
        form.addRow("Columns:", self.cols_spin)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(btn_ok)
        button_layout.addWidget(btn_cancel)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(form)
        layout.addLayout(button_layout)

        # ---- Connections ----
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        # ---- Final setup ----
        self.rows_spin.setFocus()
        self.resize(280, 130)

    def get_size(self):
        """Return a (rows, cols) tuple of integers."""
        return (self.rows_spin.value(), self.cols_spin.value())
