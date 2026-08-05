from PySide6.QtWidgets import QLineEdit, QMenu, QSizePolicy, QStackedWidget, QLabel, QWidget, QFrame, QWidgetAction,QHBoxLayout
from PySide6.QtCore import Signal, QPropertyAnimation, QRect, QEasingCurve, QParallelAnimationGroup,QTimer
from PySide6.QtGui import QAction, QIcon, Qt
from PySide6.QtCore import Qt, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPen, QColor, QFont

class StackedWidget(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.animation_duration = 400
        self.animating = False
        self.target_index = 0
        self.setProperty('class', 'stack')
        # Set a solid background to prevent flickering
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)

    def add_page(self, page: QWidget, allow_same_tyoes=True):
        
        if not allow_same_tyoes:
            for i in range(self.count()):
            
                # Remove any existing widget of the same type
                for i in range(self.count() - 1, -1, -1):  # Iterate backwards to safely remove
                    if type(self.widget(i)) == type(page):
                        widget_to_remove = self.widget(i)
                        self.removeWidget(widget_to_remove)
                        print('removed:', widget_to_remove.__class__)
                        widget_to_remove.deleteLater()  # Clean up the widget
            
                    
        page.setAutoFillBackground(True)
        
        self.addWidget(page)
        
        self.go_last()

    def go_next(self):
        
        new_index = self.currentIndex() + 1
        
        if new_index < self.count(): self.setCurrentIndexAnimated(new_index)

    def go_back(self):

        new_index = self.currentIndex() - 1
        
        if new_index >= 0: self.setCurrentIndexAnimated(new_index)

    def goto_index(self, index): self.setCurrentIndexAnimated(index)

    def go_last(self): self.setCurrentIndexAnimated(self.count() - 1)

    def go_first(self): self.setCurrentIndexAnimated(0)

    def setCurrentIndexAnimated(self, index):

        if index < 0 or index >= self.count() or index == self.currentIndex(): return
        
        if self.animating: return

        self.target_index = index
        current_widget = self.currentWidget()
        current_widget.hide()
        next_widget = self.widget(index)
        
        direction = 1 if index > self.currentIndex() else -1
        
        self.setCurrentWidgetAnimated(next_widget, direction)

    def setCurrentWidgetAnimated(self, next_widget: QWidget, direction=-1):
        
        if self.animating: return

        self.animating = True
        current_widget = self.currentWidget()

        size = self.size()
        width = size.width()

        # Set geometry only
        next_widget.setGeometry(width * direction, 0, width, self.height())
        next_widget.show()
        next_widget.raise_()

        # Animate transition
        anim_out = QPropertyAnimation(current_widget, b"geometry")
        anim_out.setDuration(self.animation_duration)
        anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_out.setStartValue(QRect(0, 0, width, self.height()))
        anim_out.setEndValue(QRect(-width * direction, 0, width, self.height()))

        anim_in = QPropertyAnimation(next_widget, b"geometry")
        anim_in.setDuration(self.animation_duration)
        anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_in.setStartValue(QRect(width * direction, 0, width, self.height()))
        anim_in.setEndValue(QRect(0, 0, width, self.height()))

        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(anim_out)
        self.animation_group.addAnimation(anim_in)
        self.animation_group.finished.connect(self._on_animation_finished)
        self.animation_group.start()
        current_widget.hide()


    def _on_animation_finished(self):
        
        self.setCurrentIndex(self.target_index)
        self.animating = False
        self.animation_group.deleteLater()

        # Important: activate layout and adjust size
        widget = self.currentWidget()
        widget.setGeometry(0, 0, self.width(), self.height())
        widget.updateGeometry()
        widget.adjustSize()
       
        layout = widget.layout()
       
        if layout: layout.activate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.animating:
            current = self.currentWidget()
            if current:
                #current.setGeometry(0, 0, self.width(), self.height())
                layout = current.layout()
                if layout:
                    layout.activate()

 
class Separator(QFrame):
    def __init__(self, orientation='horizontal',stroke:int=1, color:str="#888888D1", parent=None):
        super().__init__(parent)
        
        if orientation == 'horizontal': self.setFrameShape(QFrame.Shape.HLine)
        else: self.setFrameShape(QFrame.Shape.VLine)
        
        self.setFrameShadow(QFrame.Shadow.Plain)  # No 3D effect
        self.setLineWidth(1)              
        self.setMidLineWidth(0)
        self.setStyleSheet(f"color: {color}; background-color: {color}; max-height: {stroke}px;")
        
        self.setLineWidth(stroke)

class Label(QLabel):
    def __init__(self,text:str=''):
        super().__init__()
        super().setText(text)
        
    textChanged = Signal(str)  # Define a custom signal

    def setText(self, text: str):
        if text != self.text():  # Emit signal only if text is actually changed
            super().setText(text)
            self.textChanged.emit(text)


class RingProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._min = 0
        self._max = 100
        self._ring_color = QColor("#4CAF50")
        self._bg_color = QColor("#E0E0E0")
        self._text_color = QColor("#333333")
        self._ring_width = 10
        self._show_text = True
        self._font_size = 20
        self.setMinimumSize(120, 120)

    def setValue(self, val):
        self._value = max(self._min, min(self._max, val))
        self.update()

    def value(self):
        return self._value

    def setRange(self, min_val, max_val):
        self._min = min_val
        self._max = max_val
        self.update()

    def setRingColor(self, color):
        self._ring_color = QColor(color)
        self.update()

    def setBackgroundColor(self, color):
        self._bg_color = QColor(color)
        self.update()

    def setRingWidth(self, width):
        self._ring_width = width
        self.update()

    def setShowText(self, visible):
        self._show_text = visible
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height()) - 2 * self._ring_width
        rect = self.rect().adjusted(self._ring_width, self._ring_width,
                                    -self._ring_width, -self._ring_width)

        # background ring
        pen = QPen()
        pen.setWidth(self._ring_width)
        pen.setColor(self._bg_color)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        # progress arc
        if self._max > self._min:
            fraction = (self._value - self._min) / (self._max - self._min)
        else:
            fraction = 0
        span_angle = int(360 * fraction * 16)
        pen.setColor(self._ring_color)
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, -span_angle)

        # percentage text
        if self._show_text:
            font = QFont()
            font.setPointSize(self._font_size)
            painter.setFont(font)
            painter.setPen(self._text_color)
            text = f"{self._value}%"
            painter.drawText(self.rect(), Qt.AlignCenter, text)

        painter.end()


class _AutoHideMenu(QMenu):
    """A QMenu that notifies a callback whenever actions are added/removed."""
    
    def __init__(self, on_changed_callback, parent=None):
        super().__init__(parent)
        self._on_changed = on_changed_callback

    def addAction(self, *args, **kwargs):
        result = super().addAction(*args, **kwargs)
        self._on_changed()
        return result

    def addActions(self, actions):
        super().addActions(actions)
        self._on_changed()

    def insertAction(self, before, action):
        super().insertAction(before, action)
        self._on_changed()

    def removeAction(self, action):
        super().removeAction(action)
        self._on_changed()

class SearchBox(QLineEdit):
    """Animated search box with an auto‑hiding popup menu button."""

    def __init__(self, parent=None, expanded_width=200, duration=300):
        super().__init__(parent)
        self._custom_panel = None
        self._panel_widget_action = None
        self._expanded_width = expanded_width
        self._duration = duration
        
        # --- Popup menu (hidden by default) ---
        self._popup_menu = _AutoHideMenu(self._update_menu_action_visibility, self)

        self._menu_action = QAction(QIcon(":/icons/v-ellipsis.svg"), "Options", self)
        self._menu_action.setMenu(self._popup_menu)
        self.addAction(self._menu_action, QLineEdit.ActionPosition.LeadingPosition)
        self._menu_action.setVisible(False)          # hidden while menu is empty

        # --- Search icon ---
        self._search_action = QAction(QIcon(":/icons/search.svg"), "Search", self)
        self.addAction(self._search_action, QLineEdit.ActionPosition.LeadingPosition)

        self._collapsed_width = 32 if len(self._popup_menu.actions()) == 0 else 2*32
        
        self.setFixedWidth(self._collapsed_width)
        
        # --- Appearance ---
        self.setPlaceholderText("Search…")
        self.setClearButtonEnabled(True)

        # --- Animation ---
        self._animation = QPropertyAnimation(self, b"expandingWidth")
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def setPopupPanel(self, widget):
        """
        Attach a custom popup panel *after* any existing menu items.
        Pass None to remove only the panel.
        """
        # --- Remove existing panel if any ---
        if self._panel_widget_action is not None:
            self._popup_menu.removeAction(self._panel_widget_action)
            self._panel_widget_action = None
            self._custom_panel = None

        if widget is None:
            self._update_menu_action_visibility()
            return

        # --- Create / add the panel action ---
        self._panel_widget_action = QWidgetAction(self._popup_menu)
        self._panel_widget_action.setDefaultWidget(widget)
        self._popup_menu.addAction(self._panel_widget_action)   # always appended

        self._custom_panel = widget
        self._update_menu_action_visibility()
    # ---------- Qt property for animation ----------
    def getExpandingWidth(self) -> int: return self.width()

    def setExpandingWidth(self, width: int): self.setFixedWidth(width)

    expandingWidth = Property(int, getExpandingWidth, setExpandingWidth)

    # ---------- Public API ----------
    def popupMenu(self) -> QMenu:
        """
        Return the popup menu that opens when the menu button is clicked.
        The developer can add actions, separators, etc. directly.

        Example:
            search.popupMenu().addAction("Settings")
            search.popupMenu().addAction("About")
        """
        return self._popup_menu

    # ---------- Internal helper ----------
    def _update_menu_action_visibility(self):
        """Show the menu button only when the menu contains at least one action."""
        self._menu_action.setVisible(len(self._popup_menu.actions()) > 0)
        self._collapsed_width = 32 if len(self._popup_menu.actions()) == 0 else 2*32
        self.setFixedWidth(self._collapsed_width)

    # ---------- Focus animation ----------
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._animate_to(self._expanded_width)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if not self.text().strip() and self._popup_menu.isHidden():
            self._animate_to(self._collapsed_width)

    def _animate_to(self, target_width: int):
        
        if self.width() == target_width: return
        
        self._animation.stop()
        self._animation.setStartValue(self.width())
        self._animation.setEndValue(target_width)
        self._animation.start()

