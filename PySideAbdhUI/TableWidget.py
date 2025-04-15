from PySide6.QtWidgets import QTableWidget, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer

# QTableWidget with Auto-hide scrollbar
class TableWidget(QTableWidget):
    
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        # Hide the vertical scrollbar initially
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  

        # Add a QGraphicsOpacityEffect to the scrollbar for smooth fading
        self.scrollbar = self.verticalScrollBar()
        self.opacity_effect = QGraphicsOpacityEffect(self.scrollbar)
        self.scrollbar.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)  # Start fully transparent

        # Animation for opacity
        self.scrollbar_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.scrollbar_animation.setDuration(300)  # Animation duration in milliseconds
        self.scrollbar_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Timer to check mouse position periodically
        self.mouse_check_timer = QTimer(self)
        self.mouse_check_timer.timeout.connect(self.check_mouse_position)
        self.mouse_check_timer.start(100)  # Check every 100ms

    def check_mouse_position(self):
        # Get the mouse position relative to the table
        mouse_pos = self.mapFromGlobal(self.cursor().pos())
        table_rect = self.rect()

        # Define the edge area (e.g., last 20 pixels on the right)
        edge_area = 20
        near_scrollbar = mouse_pos.x() >= table_rect.width() - edge_area and table_rect.contains(mouse_pos)

        if near_scrollbar:
            self.show_scrollbar()
        else:
            self.hide_scrollbar()

    def show_scrollbar(self):
        if self.scrollbar_animation.state() == QPropertyAnimation.Running:
            self.scrollbar_animation.stop()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollbar_animation.setStartValue(self.opacity_effect.opacity())
        self.scrollbar_animation.setEndValue(1.0)  # Fully visible
        self.scrollbar_animation.start()

    def hide_scrollbar(self):
        if self.scrollbar_animation.state() == QPropertyAnimation.Running:
            self.scrollbar_animation.stop()
        self.scrollbar_animation.setStartValue(self.opacity_effect.opacity())
        self.scrollbar_animation.setEndValue(0.0)  # Fully transparent
        self.scrollbar_animation.finished.connect(self.finish_hide_scrollbar)
        self.scrollbar_animation.start()

    def finish_hide_scrollbar(self):
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollbar_animation.finished.disconnect(self.finish_hide_scrollbar)
