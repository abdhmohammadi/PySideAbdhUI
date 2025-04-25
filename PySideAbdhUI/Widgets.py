from PySide6.QtWidgets import QStackedWidget, QLabel, QWidget, QSizePolicy, QFrame
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
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)

    def add_page(self, page: QWidget):

        if page in [self.widget(i) for i in range(self.count())]: return
        
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
    def __init__(self, orientation='horizontal',stroke:int=2, color:str='#888888', parent=None):
        super().__init__(parent)
        #self.setStyleSheet('background-color:#666666;')
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
