import random
import sys
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

class HScrollArea(QScrollArea):
    """Mouse wheel scrolls horizontally; left‑drag scrolls vertically."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_active = False
        self._last_drag_pos = None

    # -------- original wheel‑to‑horizontal behavior --------
    def wheelEvent(self, event):
        sb = self.horizontalScrollBar()
        delta = event.angleDelta().y()
        sb.setValue(sb.value() - delta)
        event.accept()

    # -------- drag‑to‑vertical behavior (using .position().toPoint()) --------
    def viewportEvent(self, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_active = True
            self._last_drag_pos = event.position().toPoint()   # <-- updated
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return True

        elif event.type() == QEvent.MouseMove and self._drag_active:
            current_pos = event.position().toPoint()           # <-- updated
            delta = current_pos - self._last_drag_pos
            if not delta.isNull():
                vbar = self.verticalScrollBar()
                vbar.setValue(vbar.value() - delta.y())
                self._last_drag_pos = current_pos
            event.accept()
            return True

        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self._drag_active:
            self._drag_active = False
            self._last_drag_pos = None
            self.viewport().setCursor(Qt.ArrowCursor)
            event.accept()
            return True

        return super().viewportEvent(event)



# CARD

class Card(QWidget):

    def __init__(self, widget:QWidget):

        super().__init__()
        widget.setParent(self)

        self.widget = widget
        self._pref_w = 0
        self._pref_h = 0
        self.update_preferred_size()
    
    def resizeEvent(self, event): self.widget.setGeometry(self.rect())
    
    def mouseMoveEvent(self, event:QMouseEvent):
    
        return super().mouseMoveEvent(event)
    
    def preferredWidth(self): return self._pref_w

    def preferredHeight(self): return self._pref_h

    def update_preferred_size(self):
        sz = self.widget.size()
        self._pref_w = sz.width() + 5
        self._pref_h = sz.height() + 5
        self.setMinimumSize(self._pref_w, self._pref_h)

# HORIZONTAL SKYLINE MASONRY ENGINE

class SkylineEngine:
    """
    Cards flow LEFT → RIGHT across multiple visible rows.

    On reset() the skyline is pre-allocated with enough rows to fill
    the viewport height — this gives cards multiple vertical lanes to
    choose from instead of cramming everything into one strip.

    If a tall card needs more rows than currently exist, the skyline
    grows dynamically, pushing content below the viewport and enabling
    the vertical scrollbar.
    """

    def __init__(self, row_height=10, spacing=10):
        self.row_height = row_height
        self.spacing = spacing
        self.sky = []

    def reset(self, height):
        # Pre-allocate rows to fill the viewport — this is what creates
        # multiple visible lanes instead of a single horizontal strip.
        rows = max(1, (height + self.spacing) // self.row_height)
        self.sky = [0] * rows

    def _ensure_rows(self, needed):
        """Extend the skyline when a card is taller than the current rows."""
        while len(self.sky) < needed:
            self.sky.append(0)

    def best(self, w, h):
        span = max(1, (h + self.spacing + self.row_height - 1) // self.row_height)
        self._ensure_rows(span)

        best_y = 0
        best_x = 10 ** 9

        for i in range(len(self.sky) - span + 1):
            x = max(self.sky[i:i + span])
            if x < best_x:
                best_x = x
                best_y = i

        return best_x, best_y, span

    def apply(self, y, span, x, w):
        for i in range(y, y + span):
            self.sky[i] = x + w + self.spacing

    def width(self):
        return max(self.sky) if self.sky else 0

    def height(self):
        if not self.sky:
            return 0
        return len(self.sky) * self.row_height - self.spacing


# MASONRY VIEW  (horizontal-flow, vertical-aware)
class MasonryView(QWidget):

    load_more_requested = Signal()
    MARGIN = 12

    def __init__(self, parent=None):

        super().__init__(parent)

        self.engine = SkylineEngine(row_height=10, spacing=5)
        self.cards = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scrollarea = HScrollArea()
        self.scrollarea.setWidgetResizable(True)

        self.scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scrollarea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.container = QWidget()
        self.scrollarea.setWidget(self.container)

        layout.addWidget(self.scrollarea)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def add_card(self, card:Card):
        
        card.setParent(self.container)
        self.cards.append(card)
        self.reflow()

    def reflow(self):

        m = self.MARGIN
        viewport_h = self.scrollarea.viewport().height()
        
        if viewport_h < 1: return

        # Pre-allocate rows to fill the viewport height.
        # Cards that don't fit in the existing lanes will extend
        # the skyline beyond the viewport → vertical scrollbar activates.
        rh = self.engine.row_height
        self.engine.reset(viewport_h - 2 * m + rh*10) #########

        max_bottom = 0

        for card in self.cards:

            w = card.preferredWidth()
            h = card.preferredHeight()

            x, row, span = self.engine.best(w, h)

            rh = self.engine.row_height
            sp = self.engine.spacing

            px = m + x
            py = m + row * rh
            ph = span * rh - sp

            card.setGeometry(px, py, w, ph)

            self.engine.apply(row, span, x, w)

            max_bottom = max(max_bottom, py + ph)

        content_w = m + self.engine.width() + m

        # Natural content height from placed cards
        natural_h = max_bottom + m

        # Always extend at least one visual card-row below the viewport
        # so the vertical scrollbar is always active and functional.
        rh = self.engine.row_height
        overflow_h = viewport_h + 2 * m + rh * 6      # ~60 px below viewport
        content_h = max(natural_h, overflow_h)

        self.container.setMinimumWidth(content_w)
        self.container.setMinimumHeight(content_h)

    def clear(self): 
        self.cards.clear()

    def update_view(self):

        for card in self.cards:
            
            card.update_preferred_size()
        
        self.reflow()
        

# DEMO WINDOW

class Window(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Ultra Masonry Demo — Horizontal Flow")

        layout = QVBoxLayout(self)
        self.view = MasonryView()

        layout.addWidget(self.view)

        self.generate_test_data()

    def generate_test_data(self):

        for i in range(30):

            w = random.randint(120, 300)
            h = random.randint(80, 250)
            label = QLabel(f"Card {i}")
            label.setFixedSize(w,h)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c1 = random.randint(50, 255)
            c2 = random.randint(50, 255)
            c3 = random.randint(50, 255)
            
            label.setStyleSheet(f"""
                background: rgb({c1}, {c2}, {c3});
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
            """)
            card = Card(label)

            self.view.add_card(card)




# RUN

if __name__ == "__main__":

    app = QApplication(sys.argv)

    win = Window()
    win.resize(900, 600)
    win.show()

    sys.exit(app.exec())
