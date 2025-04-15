

from PySide6.QtWidgets import (QWidget, QPushButton, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QHBoxLayout, QComboBox,
                               QCheckBox, QRadioButton)
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect

from PySideAbdhUI.Widgets import Label

class NotifyPropertyChanged(QObject):
    """
    Base ViewModel class for two-way data binding.
    Supports binding properties directly to UI widgets.
    """
    property_changed = Signal(QObject,str, object)  # Emits (property_name, new_value)

    def __init__(self):
        super().__init__()
        self._properties = {}  # Store property values
        self._bindings = {}    # Store UI widget bindings

    def _get_property(self, name):
        """ Get the value of a property. """
        return self._properties.get(name)

    def _set_property(self, name, value):
        if self._properties.get(name) != value:
            self._properties[name] = value
            # Emit signal with THIS instance as the sender
            self.property_changed.emit(self, name, value)  # 🔑 Include "self"
            self._update_bound_widget(name, value)

    def bind_property(self, property_name, default_value=None, widget=None):
        """
        Bind a property dynamically with an optional UI widget.
        - `property_name`: Property name.
        - `default_value`: Initial value.
        - `widget`: Optional UI widget (e.g., QLineEdit, QTextEdit, QPlainTextEdit).
        """
        self._properties[property_name] = default_value
        
        # Create getter and setter dynamically
        def getter(instance): return instance._get_property(property_name)

        def setter(instance, value):
            instance._set_property(property_name, value)
        
        # Attach property dynamically to the instance
        setattr(self.__class__, property_name, property(getter, setter))

        # Bind widget if provided
        if widget:
            self._bindings[property_name] = widget
            self._connect_widget(property_name, widget)
            # Ensure the widget reflects the initial value
            self._update_bound_widget(property_name, default_value)
    

    #def _connect_widget(self, name, widget):
    #    """ Connect UI widget changes to update the model. """
    #    if isinstance(widget, (QLineEdit, Label)):  # Handle QLineEdit, Label
    #        widget.textChanged.connect(lambda text: setattr(self, name, text))

    #    elif isinstance(widget, QPlainTextEdit):  # Handle QPlainTextEdit
    #        widget.textChanged.connect(lambda: setattr(self, name, widget.toPlainText()))
        
    #    elif isinstance(widget, QTextEdit): # Handle QTextEdit
    #        widget.textChanged.connect(lambda: setattr(self, name, widget.toHtml()))

    #from functools import partial
    #from PySide6.QtWidgets import QLineEdit, QLabel, QPlainTextEdit, QTextEdit, QComboBox

    def _connect_widget(self, name, widget):
        """Connect UI widget changes to update the model attribute."""

        if isinstance(widget, (QLineEdit, Label)):
            widget.textChanged.connect(lambda text, attr=name: setattr(self, attr, text))

        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda attr=name, w=widget: setattr(self, attr, w.toPlainText()))

        elif isinstance(widget, QTextEdit):
            widget.textChanged.connect(lambda attr=name, w=widget: setattr(self, attr, w.toHtml()))

        elif isinstance(widget, QComboBox):
            # You can choose either of these depending on what you want to store:
            widget.currentTextChanged.connect(lambda text, attr=name: setattr(self, attr, text))
            # OR, if you want to store the index instead of the text:
            # widget.currentIndexChanged.connect(lambda index, attr=name: setattr(self, attr, index))
        elif isinstance(widget, (QCheckBox, QRadioButton)):
            widget.toggled.connect(lambda checked, attr=name: setattr(self, attr, checked))

    def _update_bound_widget(self, name, value): 
        """Update UI widget when model property changes."""
        widget = self._bindings.get(name)
        #print(name,value, type(value))
        if widget:
            if not isinstance(value, bool):
                if not isinstance(value, str):  value = str(value)

            if isinstance(widget, (QLineEdit, Label)) and widget.text() != value:
                widget.setText(value)

            elif isinstance(widget, QPlainTextEdit) and widget.toPlainText() != value:
                widget.setPlainText(value)

            elif isinstance(widget, QTextEdit) and widget.toHtml() != value:
                widget.setHtml(value)

            elif isinstance(widget, QComboBox):
                # If value matches an item in the combobox, set it
                index = widget.findText(value)
                if index >= 0 and widget.currentIndex() != index:
                    widget.setCurrentIndex(index)
            
            elif isinstance(widget, (QCheckBox, QRadioButton)):
                value = bool(value)
                if widget.isChecked() != value:
                    widget.setChecked(value)

    #def _update_bound_widget(self, name, value):
    #    """ Update UI widget when model property changes. """
    #    widget = self._bindings.get(name)

    #    if not isinstance(value,str): value = str(value)
        
    #    if widget:
    #        if isinstance(widget, (QLineEdit, Label)) and widget.text() != value:
    #            widget.setText(value)
            
    #        elif isinstance(widget, QPlainTextEdit) and widget.toPlainText() != value:
    #            widget.setPlainText(value)
            
    #        elif isinstance(widget, QTextEdit) and widget.toHtml() != value: # Handle QTextEdit
    #            widget.setHtml(value)

class PopupNotifier(QWidget):
    
    active_popups = []  # Keep track of active notifications

    def __init__(self, title_color='#3A3A3A', background_color='#424242', border_color='BLUE'):
        super().__init__()
        self.setMinimumWidth(400)
        self.title_color = title_color
        self.background_color = background_color
        self.border_color = border_color

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(f"background-color: {self.background_color}; border-radius: 10px;")

        # Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(20, 10, 20, 10)
        # Title Label
        self.title_label = QLabel("Notification")
        self.title_label.setStyleSheet(f"font-weight:bold; padding-left:5px;padding:5px; background-color:{self.title_color}; border-top-left-radius:5px; border-top-right-radius:5px; border-bottom-left-radius:0px; border-bottom-right-radius:0px;")
        self.title_label.setFixedHeight(32)

        # Message Label
        self.message_label = QLabel("This is a sample message.")
        self.message_label.setStyleSheet(f"padding:5px; background-color:{self.background_color}; border-top-left-radius:0px; border-top-right-radius:0px; border-bottom-left-radius:0px; border-bottom-right-radius:0px;")
        self.message_label.setWordWrap(True)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        
        
        btn_widget = QWidget()
        btn_widget.setStyleSheet(f"padding:5px; background-color:{self.background_color}; border-top-left-radius:0px; border-top-right-radius:0px; border-bottom-left-radius:5px; border-bottom-right-radius:5px;")
        
        btn_layout = QHBoxLayout(btn_widget)
        #self.countdown_label = QLabel('') # When buttons is hidden
        # Buttons
        self.timer_button = QPushButton("Close (5s)")
        self.timer_button.setStyleSheet("background-color: #FF5555; color: white; padding: 5px; border-radius: 5px;")
        self.timer_button.clicked.connect(self.toggle_timer)

        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet("background-color: #808080; color: white; padding: 5px; border-radius: 5px;")
        self.close_button.clicked.connect(self.close)

        btn_layout.addWidget(self.timer_button)
        btn_layout.addWidget(self.close_button)
        layout.addWidget(btn_widget)
            
        # Auto-close Timer
        self.close_timer = QTimer()
        self.close_timer.timeout.connect(self.update_timer)

        self.remaining_time = 5  # Default countdown time
        self.timer_active = True  # Whether the timer is running

        # Animations
        self.slide_animation = QPropertyAnimation(self, b"geometry")
        self.slide_animation.setDuration(500)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(500)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)


    def show_popup(self, parent: QWidget = None, title='Notifier', message='', position="top-right", delay=5000, buttons= True):
        
        self.setParent(parent)

        if title: self.title_label.setText(title)
        
        self.message_label.setText(message)
        
        self.adjustSize()
        
        self.remaining_time = delay  # Default countdown time
        self.timer_button.setVisible(buttons)
        self.close_button.setVisible(buttons)
        # Get parent geometry if available
        if parent:
            parent_geometry = parent.geometry()
            if position == "top-right":
                start_x = parent_geometry.width() + 10  # Start off-screen (right)
                end_x = parent_geometry.width() - self.width() - 10
                y = 10
            elif position == "top-left":
                start_x = -self.width()  # Start off-screen (left)
                end_x = 10
                y = 10
            elif position == "bottom-right":
                start_x = parent_geometry.width() + 10
                end_x = parent_geometry.width() - self.width() - 10
                y = parent_geometry.height() - self.height() - 10
            elif position == "bottom-left":
                start_x = -self.width()
                end_x = 10
                y = parent_geometry.height() - self.height() - 10
        else:
            # Default position if no parent
            end_x, y = 100, 100
            start_x = end_x + 300  # Start further right

        # Set initial position (off-screen)
        self.setGeometry(start_x, y, self.width(), self.height())

        # Configure slide animation
        self.slide_animation.setStartValue(QRect(start_x, y, self.width(), self.height()))
        self.slide_animation.setEndValue(QRect(end_x, y, self.width(), self.height()))
        self.slide_animation.start()

        # Configure fade-in animation
        self.opacity_animation.start()

        # Start auto-close timer
        self.remaining_time = delay // 1000

        if self.timer_button: self.timer_button.setText(f"Close ({self.remaining_time}s)")
        self.timer_active = True
        self.close_timer.start(1000)

        self.show()


    def update_timer(self):
        if self.timer_active and self.remaining_time > 0:
            self.remaining_time -= 1
            self.timer_button.setText(f"Close ({self.remaining_time}s)")
        if self.remaining_time == 0:
            self.close()

    def toggle_timer(self):
        if self.timer_active:
            self.close_timer.stop()
            self.timer_active = False
            self.timer_button.setText("Keep Open")
            self.timer_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px; border-radius: 5px;")
        else:
            self.close_timer.start(1000)
            self.timer_active = True
            self.timer_button.setText(f"Close ({self.remaining_time}s)")
            self.timer_button.setStyleSheet("background-color: #FF5555; color: white; padding: 5px; border-radius: 5px;")

    def stop_timer(self):
        self.close_timer.stop()
        self.timer_active = False
        self.timer_button.setText("Timer Stopped")
        self.timer_button.setStyleSheet("background-color: #808080; color: white; padding: 5px; border-radius: 5px;")

    def closeEvent(self, event):
        """Intercept close event to ensure animation is used."""
        self.close_popup()
        event.ignore()  # Prevent instant close (handled by animation)

    def close_popup(self):
        """Animate popup before closing."""
        # Animate opacity (fade-out)
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.setDuration(500)  # Fade-out duration
        self.opacity_animation.start()

        # Animate sliding out (off-screen)
        end_x = self.x() + self.width()  # Move to the right (off-screen)
        self.slide_animation.setStartValue(self.geometry())
        self.slide_animation.setEndValue(QRect(end_x, self.y(), self.width(), self.height()))
        self.slide_animation.setDuration(500)
        self.slide_animation.start()

        # Delay the actual close until animation finishes
        QTimer.singleShot(500, self.close)

    @staticmethod
    def Notify(parent: QWidget, title='Notifier', message: str = '', position='bottom-right', delay=5000,
               title_color='#3A3A3A', background_color='#424242', border_color='BLUE',buttons = True):
        
        popup = PopupNotifier(title_color, background_color, border_color)

        popup.show_popup(parent, title, message, position, delay,buttons=buttons)

