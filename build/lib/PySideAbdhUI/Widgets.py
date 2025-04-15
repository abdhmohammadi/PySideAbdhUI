from PySide6.QtWidgets import QStackedWidget, QLabel, QWidget
from PySide6.QtCore import Signal, QPropertyAnimation, QRect, QEasingCurve, QParallelAnimationGroup
from PySide6.QtGui import Qt

class StackedWidget(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.animation_duration = 400
        self.animating = False
        self.target_index = 0

        # Set a solid background to prevent flickering
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.white)
        self.setPalette(palette)

    def add_page(self, page:QWidget):
        """Add a new page and switch to it immediately"""
        if isinstance(page,type(self.currentWidget())): return
        page.setAutoFillBackground(True)  # Prevent transparent background flicker
        self.addWidget(page)
        self.go_last()

    def go_next(self):
        """Animate transition to next page"""
        new_index = self.currentIndex() + 1
        if new_index < self.count():
            self.setCurrentIndexAnimated(new_index)

    def go_back(self):
        """Animate transition to previous page"""
        new_index = self.currentIndex() - 1
        if new_index >= 0:
            self.setCurrentIndexAnimated(new_index)

    def go_last(self):
        """Jump to last page with animation"""
        self.setCurrentIndexAnimated(self.count() - 1)

    def go_first(self):
        """Jump to first page with animation"""
        self.setCurrentIndexAnimated(0)

    def setCurrentIndexAnimated(self, index):
        if self.animating:
            return
        if index < 0 or index >= self.count() or index == self.currentIndex():
            return

        self.animating = True
        self.target_index = index

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        direction = 1 if index > self.currentIndex() else -1
        width = self.width()

        # Position next widget off-screen and ensure it's shown
        next_widget.setGeometry(width * direction, 0, width, self.height())
        next_widget.show()
        next_widget.raise_()  # Bring to front

        # Configure animations
        anim_out = QPropertyAnimation(current_widget, b"geometry")
        anim_out.setDuration(self.animation_duration)
        anim_out.setEasingCurve(QEasingCurve.OutCubic)
        anim_out.setStartValue(QRect(0, 0, width, self.height()))
        anim_out.setEndValue(QRect(-width * direction, 0, width, self.height()))

        anim_in = QPropertyAnimation(next_widget, b"geometry")
        anim_in.setDuration(self.animation_duration)
        anim_in.setEasingCurve(QEasingCurve.OutCubic)
        anim_in.setStartValue(QRect(width * direction, 0, width, self.height()))
        anim_in.setEndValue(QRect(0, 0, width, self.height()))

        # Group animations
        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(anim_out)
        self.animation_group.addAnimation(anim_in)
        self.animation_group.finished.connect(self._on_animation_finished)
        self.animation_group.start()

    def _on_animation_finished(self):
        """Cleanup after animation completes"""
        prev_widget = self.currentWidget()
        self.setCurrentIndex(self.target_index)
        prev_widget.hide()  # Hide old widget after index change
        self.currentWidget().setGeometry(0, 0, self.width(), self.height())
        self.animating = False
        self.animation_group.deleteLater()

class Label(QLabel):
    def __init__(self,text:str=''):
        super().__init__()
        super().setText(text)
        
    textChanged = Signal(str)  # Define a custom signal

    def setText(self, text: str):
        if text != self.text():  # Emit signal only if text is actually changed
            super().setText(text)
            self.textChanged.emit(text)
