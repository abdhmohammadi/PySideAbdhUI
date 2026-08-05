import os

from PySide6.QtWidgets import (QComboBox, QFontComboBox, QRadioButton, QSizePolicy, QApplication, QMainWindow, 
                               QWidget, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QPushButton, QLabel, QFrame)

from PySide6.QtCore import (Qt, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve,
                            QRect, QSize, QEvent, QTimer, Property, Signal)
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QBrush, QPixmap, QPainterPath, QMouseEvent, QIcon, QColor, QPen

from .Widgets import StackedWidget
# Use a relative import from the utils module:
from .utils import get_icon, ThemeManager

theme_manager = ThemeManager()

############################# Customized QMainWindow ################################
# Layout of the window: QGridLayout 2x3
# Titlebar:         [0,0]-[0,2],  (stretched in 3 columns)
# Window content :  [1,1]
# Left menu panel:  [0-1,0],      (stretched into 2 rows)
# Right menu panel: [0-1,2],      (stretched into 2 rows)
#####################################################################################

class AbdhWindow(QMainWindow):
    fontChanged= Signal(str,int)
    themeChanged = Signal(str)
    titlebar = None
    app_title = ""
    control_button_size = QSize(40, 32)
    logo_size = QSize(32, 32)
    pane_width = 250
    pane_min_width = 48
    titlebar_height = 42
    _lock_size_connected = False
    # Pined  : The left panel sets to column 0 and is able to open/close
    #          just in this column and auto-close is disabled.
    # Unpined: The left panel sets to column 0 with column-span = 2. it is
    #          able to auto-close.
    RESIZE_MARGIN = 8
    MIN_WINDOW_WIDTH = 400
    MIN_WINDOW_HEIGHT = 300

    # ── Animation tuning constants ──────────────────────────────────────────
    # Duration for the maximize geometry animation (milliseconds).
    # 320 ms gives enough room for the two-phase coil→spring motion while
    # still feeling responsive.  Any shorter and the coil keyframe at 10 %
    # would be invisible; any longer and the user perceives lag.
    _MAXIMIZE_ANIM_DURATION = 320

    # Duration for the restore geometry animation (milliseconds).
    # Intentionally shorter than maximize (250 ms) so the restore feels
    # snappier and lighter — the window "lands" rather than "expands".
    _RESTORE_ANIM_DURATION = 250

    # Duration for the opacity dip that accompanies each animation.
    # Finishes well before the geometry animation so the window is fully
    # opaque while it is still settling into its final shape.
    _MAXIMIZE_OPACITY_DURATION = 260
    _RESTORE_OPACITY_DURATION = 210

    # Rounded-corner radius for the window frame (pixels).  When maximized
    # this animates to 0 so the window sits flush against the screen edges.
    _BORDER_RADIUS_NORMAL = 8
    _BORDER_RADIUS_MAXIMIZED = 0

    # Coil inset for maximize animation (pixels).  At the 10 % keyframe
    # the window briefly shrinks inward by this amount from every edge,
    # creating a visual "tension before release" that makes the subsequent
    # expansion feel more powerful.
    _MAXIMIZE_COIL_INSET = 8

    # Overshoot inset for restore animation (pixels).  At the 85 %
    # keyframe the window briefly becomes slightly smaller than the
    # target geometry, then settles — giving a subtle "bounce" that
    # feels like the window is landing on a surface.
    _RESTORE_OVERSHOOT_INSET = 4
    
    def __init__(self):

        font,size = theme_manager.get_current_font()
 
        theme_manager.update_qss_font(size, font)
 
        theme_manager.apply_theme(QApplication.instance(), theme_manager.get_current_theme_name())
        
        super().__init__()

        # Track if the window is opening for the first time and used to fade-in animation at start
        self.first_show = True
        self.initialized = False

        # configuration of the window with start position and size
        # First we hide normal border of the window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        # Enable translucent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # To start the window in center of screen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Calculate the window dimensions based on the golden ratio
        window_width = int(screen_width * 1.618 * 0.5)
        window_height = int(screen_height * 1.618 * 0.5)
        self.resize(window_width, window_height)

        # Center the window on the screen
        x = int((screen_width - window_width) / 2)
        y = int((screen_height - window_height) / 2)

        self.move(x, int(y * 0.70))

        # Resize state (replaces broken QSizeGrip approach)
        self._resizing = False
        self._resize_dir = None
        self._resize_start_geo = None
        self._resize_start_pos = None

        # Titlebar drag state
        self._drag_start_position = None

        # Size-lock state: when True the window cannot be resized by the
        # layout system — only explicit setGeometry() calls from user
        # actions (edge drag, maximize/restore) can change the size.
        self._size_locked = False

        # Panel state
        self.overlay = False
        self.expanded = True

        # ── Maximize/restore animation state ──────────────────────────────
        # Guard flag: True while a maximize/restore animation is in progress.
        # Prevents rapid double-clicks from creating overlapping animations
        # that fight over the geometry property.
        self._is_animating = False

        # Animated border-radius backing field (see the Qt Property below).
        # Drives the rounded-corner transition in paintEvent.
        self._border_radius = float(self._BORDER_RADIUS_NORMAL)

        # Parallel animation group that drives both the geometry and opacity
        # animations simultaneously.  Created fresh each time a maximize or
        # restore is triggered so there is no risk of stale state.
        self._maximize_anim_group = None

        self.initUI()
    
    @property
    def theme(self):
        return {"theme": theme_manager.get_current_theme_name(), "path":  theme_manager.template_path }
    
    # ── Qt Property for animated border radius ────────────────────────────
    # Exposing _border_radius as a Qt Property allows QPropertyAnimation to
    # interpolate it frame-by-frame, giving us a smooth corner-radius
    # transition that stays in sync with the geometry animation.       
    def _get_border_radius(self) -> float: return self._border_radius

    def _set_border_radius(self, value: float):
        self._border_radius = value
        self.update()  # Trigger a repaint so paintEvent uses the new radius

    borderRadius = Property(float, _get_border_radius, _set_border_radius)

    # ─── Size lock (prevents internal widgets from resizing the window) ──────

    def _lock_size(self):
        """Lock the window to its current size by setting both minimum and
        maximum size to the current dimensions.  This is the ONLY reliable
        way to prevent Qt's layout system from auto-growing the window when
        an internal widget (e.g. an expandable QTreeWidget) changes its
        sizeHint.  The layout will reflow inside the locked window instead
        of pushing the window boundary outward."""
        s = self.size()
        self.setMinimumSize(s)
        self.setMaximumSize(s)
        self._size_locked = True

    def _unlock_size(self):
        """Relax the size constraints so that user-initiated resize
        operations (edge drag, maximize/restore animations) can change
        the window size.  Re-lock with _lock_size() afterwards."""
        self.setMinimumSize(self.MIN_WINDOW_WIDTH, self.MIN_WINDOW_HEIGHT)
        self.setMaximumSize(QSize(16777215, 16777215))  # QWIDGETSIZE_MAX
        self._size_locked = False

    def _connect_lock_after_animation(self, animation: QPropertyAnimation):
        """Connect an animation's finished signal to _lock_size so the
        window is re-locked as soon as the animation completes.
        Any previous _lock_size connection on this animation is removed
        first to avoid duplicate calls."""
        if self._lock_size_connected:
            animation.finished.disconnect(self._lock_size)
            self._lock_size_connected = False
        
        animation.finished.connect(self._lock_size)
        self._lock_size_connected = True
    
    
    def initUI(self, app_title: str = '', direction= Qt.LayoutDirection.LeftToRight, logo: QPixmap = None):

        title =  [self.windowTitle().strip(), app_title]

        app_title = ' | '.join(title).strip().strip('|')

        self.setWindowTitle(app_title)

        # Main widget and layout
        self.main_widget = QWidget(self)
        self.main_widget.setProperty('class', 'window-background-layer')
        
        self.main_widget.setLayoutDirection(direction) 

        self.main_widget.setContentsMargins(1, 1, 1, 1)
        self.setCentralWidget(self.main_widget)

        # Grid layout
        self.main_layout = QGridLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Left panel, location -->[0,0], stretched in 2 rows
        self.left_panel = QFrame(self)

        # Uses object name property to correspond the named stylesheet in qss file
        self.left_panel.setProperty('class', 'left-sidebar-background-layer')
        self.left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_panel.setFixedWidth(self.pane_width)
        # Fixed horizontally (since setFixedWidth locks width), Expanding vertically
        self.left_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.left_panel_layout = QVBoxLayout(self.left_panel)
        # Content margin for leftpanel:
        # If we set the left margin to a larger value, the mouse
        # effect will appear equally large inside the panel.
        self.left_panel_layout.setContentsMargins(0, self.titlebar_height, 0, 5)
        self.left_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Right panel, location -->[0,2], stretched in 2 rows
        self.right_panel = QFrame(self)
        # Uses object name property to correspond the named stylesheet in qss file
        self.right_panel.setProperty('class', 'right-sidebar-background-layer')
        self.right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.right_panel.setMinimumWidth(0)   # Start with zero width
        self.right_panel.setMaximumWidth(0)   # Also limit max width when collapsed

        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.setSpacing(5)
        self.right_panel_layout.setContentsMargins(10, self.titlebar_height, 10, 10)

        # There are a number of custom styles can be applied to the UI.
        # Changing it will affects all UI objects of the application.
        self.right_panel_layout.addWidget(QLabel('THEME')) # index:0
        
        theme_selector = QComboBox()
        theme_selector.addItems(theme_manager.get_all_themes())
        theme_selector.setCurrentText(theme_manager.get_current_theme_name())
        theme_selector.currentTextChanged.connect(lambda _, sender= theme_selector:self.on_theme_switch(sender=sender))
        
        self.right_panel_layout.addWidget(theme_selector)# index: 1
        

        self.right_panel_layout.addWidget(QLabel('FONT')) # index 2
        # Global Font in the application domain 
        fonts = QFontDatabase.families()
        fw = QWidget() # Font widgets
        hl = QHBoxLayout(fw)
        hl.setContentsMargins(0,0,0,0)

        font, size = theme_manager.get_current_font()

        combo2 = QFontComboBox()
        combo2.setFontFilters(QFontComboBox.FontFilter.AllFonts)
        combo2.setWritingSystem(QFontDatabase.WritingSystem.Any)  # or QFontDatabase.Any
        combo2.setCurrentFont(QFont(font,size))
        combo2.setPlaceholderText("Select a font")

        combo2.addItems(fonts)
        hl.addWidget(combo2)

        combo3 = QComboBox()
        combo3.setFixedWidth(50)
        combo3.setPlaceholderText("Select font size")
        combo3.addItems(['8','10','12', '14', '16', '18', '20', '22', '24'])
        combo3.setCurrentText(str(size))
        hl.addWidget(combo3)

        self.right_panel_layout.addWidget(fw) # index 3
        
        # Changes the application font, this change affects all objects in the application
        combo2.currentFontChanged.connect(lambda _, c2=combo2, c3=combo3: self.on_font_changed(c2,c3))
        combo3.currentIndexChanged.connect(lambda _,c2=combo2,c3=combo3:self.on_font_changed(c2,c3))

        # Page direction options: It is provided Left-to-Right
        # The direction is applied on the mantent of main frame, and titlebar,
        # left panel and right panel are not affected currently.
        direction = theme_manager.get_direction()

        radio1 = QRadioButton('Right to left direction')
        radio1.clicked.connect(lambda checked: (
            self.set_direction(Qt.LayoutDirection.RightToLeft if checked else Qt.LayoutDirection.LeftToRight),
            theme_manager.set_direction(Qt.LayoutDirection.RightToLeft if checked  else Qt.LayoutDirection.LeftToRight))
            )
        
        radio1.setChecked(direction == Qt.LayoutDirection.RightToLeft)

        self.right_panel_layout.addWidget(radio1) # index 4
        self.right_panel_layout.top_index = 4
        self.right_panel_layout.addStretch(1)

        # Toggle button for left menu
        top_commands_layout = QHBoxLayout()
        top_commands_layout.setContentsMargins(10, 0, 10, 0)
        self.toggle_button = QPushButton("")
        self.toggle_button.setProperty('class', 'mini')
        self.toggle_button.setIcon(QIcon(":/icons/menu.svg"))
        self.toggle_button.setMinimumWidth(self.pane_min_width)

        top_commands_layout.addWidget(self.toggle_button)

        top_commands_layout.addStretch()

        self.pin_button = QPushButton("", self)
        self.pin_button.setProperty('class', 'mini')
        self.pin_button.setIcon(QIcon(":/icons/pin.svg"))
        self.pin_button.clicked.connect(self.toggle_overlay)

        top_commands_layout.addWidget(self.pin_button)

        self.left_panel_layout.addLayout(top_commands_layout) # index 0
        self.left_panel_layout.top_index = 0
        self.left_panel_layout.addStretch(1)
        # Stacked widget for pages
        self.stacked_widget = StackedWidget()
        self.stacked_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Set an object name for the parent widget
        self.toggle_button.clicked.connect(lambda _, frame=self.left_panel, 
                                           stack=self.stacked_widget: 
                                           self.animate_content(frame, stack))

        # Custom title bar
        self.titlebar = self._create_titlebar(self.windowTitle(), logo)

        self.main_layout.addWidget(self.stacked_widget, 1, 1, 1, 2)
        self.main_layout.addWidget(self.right_panel, 0, 2, 2, 1)
        self.main_layout.addWidget(self.left_panel, 0, 0, 2, 1, Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addWidget(self.titlebar, 0, 0, 1, 3)

        # Column stretch: extra horizontal space goes to the content area (col 1)
        # Col 0 = left panel (fixed width, no stretch)
        # Col 1 = content area (expanding, stretch=1)
        # Col 2 = right panel (variable, no stretch)
        self.main_layout.setColumnStretch(0, 0)
        self.main_layout.setColumnStretch(1, 1)
        self.main_layout.setColumnStretch(2, 0)

        # Enable mouse tracking for edge-resize cursor feedback
        self.setMouseTracking(True)

        # Window state
        self.is_maximized = False                 # Track the current state of the window
        self.original_geometry = self.geometry()  # Store the original geometry

        # ── Maximize/restore animation setup ──────────────────────────────
        # NOTE: We no longer create a single reusable QPropertyAnimation here.
        # Instead, a fresh QParallelAnimationGroup is built inside
        # _start_maximize_animation() / _start_restore_animation() each time
        # the user clicks the button.  This avoids stale start/end values when
        # an animation is interrupted mid-flight and guarantees that every
        # animation frame is computed from the correct current geometry.

        self.initialized = True
        # Install global event filter to detect clicks anywhere
        QApplication.instance().installEventFilter(self)

    def on_theme_switch(self,sender:QComboBox):

        theme_name = sender.currentText()

        theme_manager.apply_theme(QApplication.instance(),theme_name)

        self.themeChanged.emit(theme_name)
    
    def on_font_changed(self,c2:QFontComboBox,c3:QComboBox):
        
        # Get the text of the selected item 
        sz = 8 + 2*c3.currentIndex()
        family = c2.currentFont().family()

        theme_manager.update_qss_font(sz, family)
        
        theme_manager.apply_theme(QApplication.instance(), theme_manager.get_current_theme_name())
        
        self.fontChanged.emit(family,sz)
    
    # ─── Panel toggling ───────────────────────────────────────────────────────
    def switch_settings_button(self, on=True): self.settings_button.setVisible(on)

    def switch_navigations(self, on=True):
        self.back_button.setVisible(on)
        self.forward_button.setVisible(on)

    def toggle_overlay(self):

        self.overlay = not self.overlay
        self.expanded = not self.overlay
        if self.overlay:
            # In overlay state the left panel spans column 0 with col-span 2.
            # It auto-closes when the mouse clicks outside of it.
            self.main_layout.removeWidget(self.left_panel)
            self.left_panel.setFixedWidth(self.pane_min_width)
            self.main_layout.addWidget(self.left_panel, 0, 0, 2, 2, Qt.AlignmentFlag.AlignLeft)
            # Keep the left margin so content is not hidden behind the panel
            self.stacked_widget.setContentsMargins(self.pane_min_width, 0, 0, 0)
        else:
            self.main_layout.removeWidget(self.left_panel)
            self.main_layout.addWidget(self.left_panel, 0, 0, 2, 1, Qt.AlignmentFlag.AlignLeft)
            self.stacked_widget.setContentsMargins(0, 0, 0, 0)

        self.pin_button.setVisible(self.expanded)

    def animate_content(self, frame: QFrame, stack: StackedWidget):

        if self.overlay:
            self.toggle_frame(frame, self.pane_min_width)
        else:
            start_width = frame.width()
            end_width = self.pane_min_width if self.expanded else self.pane_width

            # Frame animation (animate both minimumWidth and maximumWidth to avoid layout conflicts)
            frame_min_anim = QPropertyAnimation(frame, b"minimumWidth")
            frame_min_anim.setStartValue(start_width)
            frame_min_anim.setEndValue(end_width)
            frame_min_anim.setDuration(400)
            frame_min_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

            frame_max_anim = QPropertyAnimation(frame, b"maximumWidth")
            frame_max_anim.setStartValue(start_width)
            frame_max_anim.setEndValue(end_width)
            frame_max_anim.setDuration(400)
            frame_max_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

            # Parallel animation group
            self.anim_group = QParallelAnimationGroup()
            self.anim_group.addAnimation(frame_min_anim)
            self.anim_group.addAnimation(frame_max_anim)

            # After the panel animation finishes, reset the stacked_widget's
            # minimumWidth to 0 so it can freely expand when the window is
            # resized by the user.  The layout with column stretch handles
            # the stacked_widget size automatically.
            def _on_content_anim_finished():
                stack.setMinimumWidth(0)
                stack.setMaximumWidth(16777215)
                self.anim_group.deleteLater()

            self.anim_group.finished.connect(_on_content_anim_finished)

            self.anim_group.start()

        self.expanded = not self.expanded
        self.pin_button.setVisible(self.expanded)

    def open_settings(self): self.toggle_frame(self.right_panel, 0)
    
    def toggle_frame(self, sender:QFrame, min:int):
        
        sender.animation = QPropertyAnimation(sender, b"minimumWidth")
        sender.animation.setDuration(400)  # Animation duration in ms
        sender.animation.setEasingCurve(QEasingCurve.Type.OutCubic)  # Smooth effect

        # Stop any running animation before starting a new one
        sender.animation.stop() 
        
        if  sender.width() < self.pane_width:
            sender.animation.setStartValue(min)
            # Expand to set width
            sender.animation.setEndValue(self.pane_width)
        else:
            sender.animation.setStartValue(self.pane_width)
            sender.animation.setEndValue(min)  # Collapse to 0 width
        
        sender.animation.finished.connect(sender.animation.deleteLater)
        sender.animation.start()

    # ─── Window show ──────────────────────────────────────────────────────────
    def show(self):
        if not self.initialized: raise RuntimeError("Window has not been initialized yet! Call window.initUI() before show()")
        
        super().show()

    # ─── Titlebar ─────────────────────────────────────────────────────────────
    def _create_titlebar(self, title_text, title_logo: QPixmap):

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Logo icon
        self.logo_label = QLabel()
        self.logo_label.setStyleSheet(
            'border-radius:0px;padding: 0px;background-color:transparent; margin:8px 10px 4px 8px;'
        )
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setAlignment(self.logo_label, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.logo_label)

        if title_logo:
            pixmap = QPixmap(title_logo).scaled(self.logo_size, 
                                                Qt.AspectRatioMode.KeepAspectRatio, 
                                                Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)

        # Navigation buttons
        self.back_button = QPushButton('')
        self.back_button.setToolTip('Navigation back')
        self.back_button.setProperty('class', 'mini')
        self.back_button.setIcon(QIcon(":/icons/arrow-left.svg"))
        self.back_button.clicked.connect(self.stacked_widget.go_back)
        layout.addWidget(self.back_button)
        layout.setAlignment(self.back_button, Qt.AlignmentFlag.AlignTop)

        self.forward_button = QPushButton('')
        self.forward_button.setProperty('class', 'mini')
        self.forward_button.setIcon(QIcon(":/icons/arrow-right.svg"))
        self.forward_button.clicked.connect(self.stacked_widget.go_next)
        layout.addWidget(self.forward_button)
        layout.setAlignment(self.forward_button, Qt.AlignmentFlag.AlignTop)

        # Title label
        self.title_label = QLabel("PySideAbdhUI | Window")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setContentsMargins(4, 4, 0, 0)
        self.title_label.setText(title_text)
        self.title_label.setProperty('class', 'caption')
        layout.addWidget(self.title_label)
        layout.setAlignment(self.title_label, Qt.AlignmentFlag.AlignTop)
        
        self.__header_toolbar = QHBoxLayout()

        # Spacer to push buttons to the right
        layout.addStretch()

        # Settings button
        self.settings_button = QPushButton("", self)
        self.settings_button.setProperty('class', 'mini')
        self.settings_button.setToolTip('Setting')
        self.settings_button.setIcon(QIcon(":/icons/settings.svg"))
        self.settings_button.clicked.connect(
            lambda _, sender=self.right_panel, min_width=0: self.toggle_frame(sender, min_width)
        )
        layout.addWidget(self.settings_button)
        layout.setAlignment(self.settings_button, Qt.AlignmentFlag.AlignTop)

        # Minimize button
        self.minimize_button = QPushButton("")
        self.minimize_button.setProperty('class', 'mini')
        self.minimize_button.setIcon(QIcon(":/icons/minus.svg"))
        self.minimize_button.clicked.connect(self.showMinimized)
        layout.addWidget(self.minimize_button)
        layout.setAlignment(self.minimize_button, Qt.AlignmentFlag.AlignTop)

        # Maximize/Restore button
        self.maximize_button = QPushButton("")
        self.maximize_button.setProperty('class', 'mini')
        self.maximize_button.setIcon(QIcon(":/icons/square.svg"))
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)
        layout.addWidget(self.maximize_button)
        layout.setAlignment(self.maximize_button, Qt.AlignmentFlag.AlignTop)

        # Close button
        self.close_button = QPushButton('', self)
        self.close_button.setProperty('class', 'close-button')
        self.close_button.setIcon(QIcon(":/icons/x.svg"))
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)
        layout.setAlignment(self.close_button, Qt.AlignmentFlag.AlignTop)

        titlebar = QWidget()
        titlebar.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        # Uses object name property to correspond the named stylesheet in qss file
        titlebar.setObjectName('Titlebar')
        titlebar.setFixedHeight(self.titlebar_height)
        titlebar.setLayout(layout)

        return titlebar
        
    # ─── Helpers ──────────────────────────────────────────────────────────────

    def set_direction(self, direction: Qt.LayoutDirection = Qt.LayoutDirection.LeftToRight):
        self.stacked_widget.setLayoutDirection(direction)

    def update_navigation_buttons(self, can_go_back, can_go_forward):
        self.back_button.setVisible(can_go_back)
        self.forward_button.setVisible(can_go_forward)

    def add_right_panel_item(self, item: QWidget, align_bottom=False):
        
        if align_bottom:
            self.right_panel_layout.addWidget(item)
        else:
            idx = self.right_panel_layout.top_index + 1

            self.right_panel_layout.insertWidget(idx, item)

            self.right_panel_layout.top_index = idx


    def add_left_panel_item(self, item: QWidget, align_bottom=False):

        # Automatically set the class name from ./resources/qss-templete.qss
        if isinstance(item, QPushButton): item.setProperty("class","MenuItem")

        if align_bottom: self.left_panel_layout.addWidget(item)
        else:
            idx = self.left_panel_layout.top_index + 1

            self.left_panel_layout.insertWidget(idx, item)

            self.left_panel_layout.top_index = idx 

    def left_panel_item(self, index):
        return self.left_panel_layout.itemAt(index).widget()

    # ─── Maximize / Restore ───────────────────────────────────────────────────
    def toggle_maximize_restore(self):
        """Toggle between maximized and restored window states.
        Guards against rapid clicks with an _is_animating flag so that
        overlapping animations never fight over the geometry property.
        The maximize/restore icon is now updated only AFTER the animation
        finishes, keeping the visual feedback in sync with the transition."""

        # Ignore clicks while an animation is already running
        if self._is_animating: return

        if self.is_maximized: self._start_restore_animation()
        
        else: self._start_maximize_animation()

        # Note: is_maximized is flipped inside _on_maximize_anim_finished /
        # _on_restore_anim_finished so the state only changes when the
        # animation actually completes.

    # ── Animation builders ────────────────────────────────────────────────
    # Each builder constructs a fresh QParallelAnimationGroup containing:
    #   1. Geometry animation  – multi-phase motion with keyframes:
    #        Maximize: coil (shrink) → spring (expand to full screen)
    #        Restore:  shrink → overshoot → settle
    #   2. Opacity animation   – nuanced multi-keyframe dip that masks
    #      layout jitter during the resize, then smoothly returns to 1.0
    #   3. Border-radius animation – smooths the rounded corners to/from 0
    #
    # Using a fresh group every time avoids stale start values when an
    # animation is interrupted mid-flight.

    def _start_maximize_animation(self):
        """Build and start the maximize (expand to full-screen) animation.

        The animation has two visual phases driven by geometry keyframes:
          Phase 1  (0 %-10 %): "Coil" — the window briefly shrinks inward
              by a few pixels, building visual tension like a compressed spring.

          Phase 2  (10 %-100 %): "Spring" — the window rapidly expands
              to fill the screen with InOutQuint easing, which has a
              strong acceleration curve that makes the expansion feel
              powerful and decisive.
        """

        # Stop any previous maximize/restore animation group that might
        # still be referenced (safety net — the guard flag should already
        # prevent this, but defensive programming costs nothing here).
        self._stop_maximize_anim_group()

        self._is_animating = True
        self._unlock_size()

        # Capture the current geometry as the starting point.
        # Using self.geometry() is correct even if a previous animation was
        # interrupted because we always stop the old group first.
        start_geo = QRect(self.geometry())

        # Store the original (restored) geometry BEFORE we overwrite it.
        # Clamp it so that the stored geometry is always fully visible on
        # screen — this prevents the "shrinking window on repeated
        # maximize/restore" bug that existed in the original code.
        clamped_geo = QRect(start_geo)
        screen_geo = QApplication.primaryScreen().availableGeometry()

        # Only adjust edges that actually overflow; leave in-bounds edges
        # untouched so the stored position is as close as possible to what
        # the user had before maximizing.
        if clamped_geo.right() > screen_geo.right():
            clamped_geo.setRight(screen_geo.right() - 5)
        if clamped_geo.bottom() > screen_geo.bottom():
            clamped_geo.setBottom(screen_geo.bottom() - 5)
        if clamped_geo.left() < screen_geo.left():
            clamped_geo.setLeft(screen_geo.left() + 5)
        if clamped_geo.top() < screen_geo.top():
            clamped_geo.setTop(screen_geo.top() + 5)

        # Preserve the original (pre-maximize) size only if the window
        # hasn't already been clamped to something smaller.  This prevents
        # the progressive-shrink bug: if clamping reduced the rect we keep
        # the original *size* but adjust the *position* so it fits.
        if clamped_geo.width() < start_geo.width() or clamped_geo.height() < start_geo.height():
            
            self.original_geometry = QRect(clamped_geo.topLeft(),
                start_geo.size() if start_geo.width() <= screen_geo.width() and start_geo.height() <= screen_geo.height()
                else clamped_geo.size())
        else:
            self.original_geometry = QRect(start_geo)

        # Target: full available screen geometry (excluding taskbar / dock)
        end_geo = screen_geo

        # ── 1. Geometry animation (coil + spring) ─────────────────────
        geo_anim = QPropertyAnimation(self, b"geometry")
        geo_anim.setDuration(self._MAXIMIZE_ANIM_DURATION)

        # Phase 1 — Coil: briefly shrink the window inward from all edges.
        # This creates a visual "wind-up" that makes the subsequent
        # expansion feel more dynamic, like a spring being released.
        inset = self._MAXIMIZE_COIL_INSET
        coil_geo = QRect(start_geo.left() + inset, start_geo.top() + inset,
                         start_geo.width() - 2 * inset, start_geo.height() - 2 * inset)

        geo_anim.setStartValue(start_geo)
        geo_anim.setKeyValueAt(0.10, coil_geo)   # coil at 10 %
        geo_anim.setEndValue(end_geo)             # spring to full screen

        # InOutQuint has a steep acceleration curve (t^5) which makes the
        # spring phase feel like the window is being "launched" outward
        # with increasing force, then gently decelerating as it fills
        # the screen.  Much more dramatic than InOutCubic.
        geo_anim.setEasingCurve(QEasingCurve.Type.InOutQuint)

        # ── 2. Opacity animation ──────────────────────────────────────
        # Multi-keyframe opacity curve that is carefully choreographed
        # with the geometry phases:
        #   0 %–5 %   : quick initial dip (window starts to move)
        #   5 %–12 %  : deeper dip during the coil phase (tension)
        #   12 %–50 % : hold at lowest point while the spring expands
        #               and internal widgets reflow at high speed
        #   50 %–80 % : smooth recovery as the window decelerates
        #   80 %–100 %: fully opaque, final position settling
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(self._MAXIMIZE_OPACITY_DURATION)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setKeyValueAt(0.05, 0.92)   # quick initial dip
        opacity_anim.setKeyValueAt(0.12, 0.75)   # deep dip during coil
        opacity_anim.setKeyValueAt(0.50, 0.80)   # hold through fast expand
        opacity_anim.setKeyValueAt(0.80, 0.95)   # recovering
        opacity_anim.setEndValue(1.0)             # fully opaque
        # InOutSine gives the smoothest possible opacity transitions —
        # no visible stepping or banding even at low opacity values.
        opacity_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        # ── 3. Border-radius animation ────────────────────────────────
        # Smoothly flatten the corners from 8 px → 0 px so the maximized
        # window sits flush against the screen edges with no visible gap.
        # The corners flatten slightly faster than the geometry expands,
        # so by the time the window reaches the screen edge the corner
        # radius is already near zero — no awkward "rounded corner
        # sticking out past the screen" artifact.
        radius_anim = QPropertyAnimation(self, b"borderRadius")
        radius_anim.setStartValue(float(self._BORDER_RADIUS_NORMAL))
        radius_anim.setEndValue(float(self._BORDER_RADIUS_MAXIMIZED))
        radius_anim.setDuration(self._MAXIMIZE_ANIM_DURATION)
        # OutCubic for radius: flatten quickly at the start, then ease
        # into the final 0 value.  This ensures corners are mostly flat
        # before the window edge reaches the screen boundary.
        radius_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── Parallel group ────────────────────────────────────────────
        group = QParallelAnimationGroup(self)
        group.addAnimation(geo_anim)
        group.addAnimation(opacity_anim)
        group.addAnimation(radius_anim)

        # When the geometry animation finishes: re-lock the window size
        # so Qt's layout system cannot auto-grow it, and update state.
        geo_anim.finished.connect(self._lock_size)
        group.finished.connect(self._on_maximize_anim_finished)

        self._maximize_anim_group = group
        group.start()

    def _start_restore_animation(self):
        """Build and start the restore (shrink back to original size) animation.

        The animation has two visual phases driven by geometry keyframes:
          Phase 1  (0 %–85 %): The window rapidly shrinks from maximized
              to slightly *past* the target geometry (overshoot), using
              OutCubic easing so most of the motion happens early.
          Phase 2  (85 %–100 %): The window gently settles from the
              overshoot position to the exact target geometry, creating
              a subtle "bounce" that makes the landing feel natural.
        """

        self._stop_maximize_anim_group()

        self._is_animating = True
        self._unlock_size()

        # Start from the current (maximized) geometry
        start_geo = QRect(self.geometry())
        # End at the previously stored original (restored) geometry
        end_geo = QRect(self.original_geometry)

        # ── 1. Geometry animation (shrink + overshoot settle) ─────────
        geo_anim = QPropertyAnimation(self, b"geometry")
        geo_anim.setDuration(self._RESTORE_ANIM_DURATION)

        # Phase 2 — Overshoot: at 85 % the window is slightly smaller
        # than the target in every dimension, creating a brief "squish"
        # before it settles to the exact target size.  This gives the
        # restore a tactile "landing" feel — like the window is touching
        # down on a surface and compressing slightly before resting.
        oi = self._RESTORE_OVERSHOOT_INSET
        overshoot_geo = QRect(
            end_geo.left() + oi,
            end_geo.top() + oi,
            end_geo.width() - 2 * oi,
            end_geo.height() - 2 * oi,
        )

        geo_anim.setStartValue(start_geo)
        geo_anim.setKeyValueAt(0.85, overshoot_geo)  # overshoot past target
        geo_anim.setEndValue(end_geo)                 # settle to exact target

        # OutCubic starts fast (the window quickly leaves the maximized
        # state) and eases out gently, which feels lighter and more
        # graceful than the powerful InOutQuint used for maximize.
        geo_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── 2. Opacity animation ──────────────────────────────────────
        # Similar multi-keyframe curve to maximize but shorter duration
        # and shallower dip — the restore is visually "lighter" than the
        # maximize so the opacity change should be subtler too.
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(self._RESTORE_OPACITY_DURATION)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setKeyValueAt(0.06, 0.92)   # quick initial dip
        opacity_anim.setKeyValueAt(0.20, 0.80)   # deeper during fast shrink
        opacity_anim.setKeyValueAt(0.55, 0.90)   # recovering
        opacity_anim.setEndValue(1.0)             # fully opaque
        opacity_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        # ── 3. Border-radius animation ────────────────────────────────
        # Bring the rounded corners back for the restored (non-maximized)
        # window so it looks like a floating card again.  The corners
        # round slightly ahead of the geometry settling so the "card"
        # shape is visible before the window has fully stopped moving.
        radius_anim = QPropertyAnimation(self, b"borderRadius")
        radius_anim.setStartValue(float(self._BORDER_RADIUS_MAXIMIZED))
        radius_anim.setEndValue(float(self._BORDER_RADIUS_NORMAL))
        radius_anim.setDuration(self._RESTORE_ANIM_DURATION)
        # InOutCubic for radius: smooth rounding that accelerates in the
        # middle of the animation when the window is at its smallest
        # (during the overshoot), giving a pleasing "pop into shape" feel.
        radius_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # ── Parallel group ────────────────────────────────────────────
        group = QParallelAnimationGroup(self)
        group.addAnimation(geo_anim)
        group.addAnimation(opacity_anim)
        group.addAnimation(radius_anim)

        geo_anim.finished.connect(self._lock_size)
        group.finished.connect(self._on_restore_anim_finished)

        self._maximize_anim_group = group
        group.start()

    # ── Animation cleanup & state transitions ─────────────────────────────

    def _stop_maximize_anim_group(self):
        """Safely stop and clean up the current maximize/restore animation
        group.  Called before starting a new animation to prevent two
        groups from fighting over the geometry property."""

        if self._maximize_anim_group is not None:
            if self._maximize_anim_group.state() == QParallelAnimationGroup.State.Running:
                self._maximize_anim_group.stop()
            self._maximize_anim_group.deleteLater()
            self._maximize_anim_group = None

    def _on_maximize_anim_finished(self):
        """Callback when the maximize animation completes.
        Flips the state flag and updates the button icon so the visual
        feedback is in sync with the actual window state."""

        self._is_animating = False
        self.is_maximized = True
        self.main_widget.setProperty("class", "window-background-layer-maximized")
        self.main_widget.style().unpolish(self.main_widget)
        self.main_widget.style().polish(self.main_widget)

        self.close_button.setProperty('class', 'close-button-maximized')
        self.close_button.style().unpolish(self.close_button)
        self.close_button.style().polish(self.close_button)
        #self.background_layer.update()

        self.maximize_button.setIcon(QIcon(":/icons/double-square.svg"))
        
        # Ensure opacity and border radius are at their final values
        # (defensive: guards against floating-point drift in animations)
        self.setWindowOpacity(1.0)
        self._border_radius = float(self._BORDER_RADIUS_MAXIMIZED)
        self.update()

        # Clean up the animation group
        if self._maximize_anim_group is not None:
            self._maximize_anim_group.deleteLater()
            self._maximize_anim_group = None

    def _on_restore_anim_finished(self):
        """Callback when the restore animation completes.
        Flips the state flag and updates the button icon so the visual
        feedback is in sync with the actual window state."""

        self._is_animating = False
        self.is_maximized = False
        self.main_widget.setProperty("class", "window-background-layer")
        self.main_widget.style().unpolish(self.main_widget)
        self.main_widget.style().polish(self.main_widget)

        self.close_button.setProperty('class', 'close-button')
        self.close_button.style().unpolish(self.close_button)
        self.close_button.style().polish(self.close_button)

        self.maximize_button.setIcon(QIcon(":/icons/square.svg"))

        # Ensure opacity and border radius are at their final values
        self.setWindowOpacity(1.0)
        self._border_radius = float(self._BORDER_RADIUS_NORMAL)
        self.update()

        # Clean up the animation group
        if self._maximize_anim_group is not None:
            self._maximize_anim_group.deleteLater()
            self._maximize_anim_group = None

    # ─── Instant restore for titlebar drag ────────────────────────────────
    # When the user drags a maximized window by the titlebar the expected
    # behaviour (matching Windows / macOS / KDE) is an instant snap back to
    # the restored geometry — NOT a slow animation.  The window should
    # appear at the restored size immediately so the user can continue
    # dragging without waiting.

    def _instant_restore_for_drag(self, global_mouse_pos):
        """Instantly restore the window from maximized to its original
        geometry and reposition it so the mouse cursor stays on the
        titlebar at a proportional horizontal position.  No animation."""

        # Stop any running animation
        self._stop_maximize_anim_group()
        self._is_animating = False

        # Unlock and snap to the original geometry
        self._unlock_size()
        restored = QRect(self.original_geometry)
        self.setGeometry(restored)

        # Position the window so the cursor lands at the same proportional
        # X offset on the titlebar (mimics Windows "drag out of maximize").
        proportional_x = int(restored.width() * 0.5)
        self._drag_start_position = global_mouse_pos - self.frameGeometry().topLeft()
        self._drag_start_position.setX(proportional_x)

        # Update state and icon immediately (no animation to wait for)
        self.is_maximized = False
        self.maximize_button.setIcon(QIcon(get_icon('square')))
        self._border_radius = float(self._BORDER_RADIUS_NORMAL)
        self.setWindowOpacity(1.0)
        self.update()

        # Re-lock after the next event-loop iteration so the geometry
        # change has time to settle.
        QTimer.singleShot(0, self._lock_size)

    # ─── Fade-in animation ────────────────────────────────────────────────────

    def animate_fadeIn(self):
        # Unlock size so the slide-in geometry animation can move the window
        self._unlock_size()

        # Animation for opacity (fade-in effect)
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(500)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Animation for geometry (slide-in effect from the top)
        start_rect = QRect(self.x(), self.y() - 50, self.width(), self.height())
        end_rect = self.geometry()
        self.geometry_animation = QPropertyAnimation(self, b"geometry")
        self.geometry_animation.setDuration(500)
        self.geometry_animation.setStartValue(start_rect)
        self.geometry_animation.setEndValue(end_rect)
        self.geometry_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Re-lock the window size after the slide-in finishes
        self._connect_lock_after_animation(self.geometry_animation)

        # Start both animations
        self.opacity_animation.start()
        self.geometry_animation.start()

    # ─── Page / style helpers ─────────────────────────────────────────────────

    def add_page(self, page_widget: QWidget):
        self.stacked_widget.add_page(page_widget)
        
        self.back_button.setVisible(self.stacked_widget.count()>1)

        self.forward_button.setVisible(self.stacked_widget.count()>1)

    def apply_style(self, style_sheet):
        self.setStyleSheet(style_sheet)

    def load_style(self, file_name='default'):
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                style = file.read()
                self.setStyleSheet(style)
                return style
        else:
            print(f"Stylesheet not found: {file_name}")
            return None

    # ─── Edge/corner resizing (manual, replaces QSizeGrip) ────────────────────

    def _get_resize_direction(self, pos):
        """Determine which edge/corner the cursor is near."""
        m = self.RESIZE_MARGIN
        w, h = self.width(), self.height()

        on_left = pos.x() < m
        on_right = pos.x() > w - m
        on_top = pos.y() < m
        on_bottom = pos.y() > h - m

        if on_top and on_left:
            return 'top_left'
        if on_top and on_right:
            return 'top_right'
        if on_bottom and on_left:
            return 'bottom_left'
        if on_bottom and on_right:
            return 'bottom_right'
        if on_left:
            return 'left'
        if on_right:
            return 'right'
        if on_top:
            return 'top'
        if on_bottom:
            return 'bottom'
        return None

    def _cursor_for_direction(self, direction):
        """Return the appropriate cursor shape for a resize direction."""
        cursors = {
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'top_left': Qt.CursorShape.SizeFDiagCursor,
            'bottom_right': Qt.CursorShape.SizeFDiagCursor,
            'top_right': Qt.CursorShape.SizeBDiagCursor,
            'bottom_left': Qt.CursorShape.SizeBDiagCursor,
        }
        return cursors.get(direction, Qt.CursorShape.ArrowCursor)

    def _do_resize(self, global_pos):
        """Perform the actual resize based on the stored direction and delta.

        Uses CLAMPING instead of conditional-skip so that when the window
        reaches its minimum size the edges stay at the clamped position
        instead of jumping back to the pre-resize geometry.  This fixes the
        bug where the window would snap back to its original size when the
        user dragged an edge to the minimum constraint.

        How it works:
          - Every frame, we compute the *desired* new edge position from
            the start geometry + total mouse delta.
          - We then clamp that desired position so the resulting width or
            height never goes below the minimum.
          - setGeometry() is called with the clamped geometry, which keeps
            the edge pinned at the minimum boundary even as the mouse
            continues moving past it.
        """
        delta = global_pos - self._resize_start_pos
        start = self._resize_start_geo

        # Begin with the start geometry; we will overwrite only the edges
        # that the user is dragging.
        new_geo = QRect(start)

        if 'left' in self._resize_dir:
            # Desired new left edge based on total mouse displacement
            desired_left = start.left() + delta.x()
            # The left edge cannot move so far right that the width drops
            # below the minimum — clamp it at that boundary.
            max_left = start.right() - self.MIN_WINDOW_WIDTH + 1
            new_geo.setLeft(min(desired_left, max_left))

        if 'right' in self._resize_dir:
            # Desired new right edge based on total mouse displacement
            desired_right = start.right() + delta.x()
            # The right edge cannot move so far left that the width drops
            # below the minimum — clamp it at that boundary.
            min_right = start.left() + self.MIN_WINDOW_WIDTH - 1
            new_geo.setRight(max(desired_right, min_right))

        if 'top' in self._resize_dir:
            # Desired new top edge based on total mouse displacement
            desired_top = start.top() + delta.y()
            # The top edge cannot move so far down that the height drops
            # below the minimum — clamp it at that boundary.
            max_top = start.bottom() - self.MIN_WINDOW_HEIGHT + 1
            new_geo.setTop(min(desired_top, max_top))

        if 'bottom' in self._resize_dir:
            # Desired new bottom edge based on total mouse displacement
            desired_bottom = start.bottom() + delta.y()
            # The bottom edge cannot move so far up that the height drops
            # below the minimum — clamp it at that boundary.
            min_bottom = start.top() + self.MIN_WINDOW_HEIGHT - 1
            new_geo.setBottom(max(desired_bottom, min_bottom))

        self.setGeometry(new_geo)
        # Force the layout to reflow immediately so the stacked_widget
        # expands/contracts to fill the new window size.
        self.main_widget.layout().activate()

    # ─── Qt event overrides ───────────────────────────────────────────────────

    def showEvent(self, event):
        # Animate the window only when it's shown for the first time
        if self.first_show:
            self.first_show = False
            self.animate_fadeIn()
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = int(self._border_radius)
        rect = self.rect()

        # ── Window background with animated rounded corners ────────────
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        # Use the window's palette background instead of hard-coded white
        bg_color = self.palette().window().color()
        painter.fillPath(path, QBrush(bg_color))

        # ── Subtle inner glow border ──────────────────────────────────
        # A thin, semi-transparent white line drawn just inside the
        # rounded-rect edge gives the window a "glass card" appearance
        # when in normal (non-maximized) mode.  The border fades out
        # proportionally as the window maximizes (radius → 0) so there
        # is no visible border artifact when the window is full-screen.
        if radius > 0:
            # Border opacity scales with border_radius so it disappears
            # smoothly during the maximize animation.
            glow_alpha = int(40 * (radius / self._BORDER_RADIUS_NORMAL))
            inner_rect = rect.adjusted(1, 1, -1, -1)
            inner_radius = max(radius - 1, 0)
            painter.setPen(QPen(QColor(255, 255, 255, glow_alpha), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(inner_rect, inner_radius, inner_radius)

    def eventFilter(self, obj, event):
        """Detect clicks outside panels to auto-close them.
        Also manages the cursor shape for edge/corner resizing by intercepting
        ALL mouse-move events (including those over child widgets)."""

        # ─── Cursor management ────────────────────────────────────────
        # Handle hover cursor for edge/corner resizing.
        # This MUST be in the event filter (not mouseMoveEvent) because
        # mouseMoveEvent only fires when the mouse is over the window's
        # own area — not over child widgets.  Without the event filter
        # the resize cursor would get "stuck" or appear over child
        # widgets that inherit the parent's cursor.
        if event.type() == QEvent.Type.MouseMove and not event.buttons():
            if not self.is_maximized and self.isVisible():
                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)
                if self.rect().contains(local_pos):
                    direction = self._get_resize_direction(local_pos)
                    if direction:
                        self.setCursor(self._cursor_for_direction(direction))
                    else:
                        self.unsetCursor()
                else:
                    self.unsetCursor()
            else:
                self.unsetCursor()

        # ─── Auto-close panels on outside click ───────────────────────
        if event.type() == QEvent.Type.MouseButtonPress:
            # Skip if the click target is one of our control buttons
            if isinstance(obj, QPushButton) and obj in (
                self.toggle_button, self.pin_button,
                self.settings_button, self.maximize_button,
                self.minimize_button, self.close_button,
            ):
                return super().eventFilter(obj, event)

            global_pos = event.globalPos() if hasattr(event, 'globalPos') else event.globalPosition().toPoint()
            local_pos = self.mapFromGlobal(global_pos)

            # Auto-close right panel if click is outside it
            if self.right_panel and (self.right_panel.width() > 0 and not self.right_panel.geometry().contains(local_pos)):
                self.toggle_frame(self.right_panel, 0)

            # Auto-close left panel in overlay mode if click is outside it
            if self.overlay and self.expanded:
                if not self.left_panel.geometry().contains(local_pos):
                    self.animate_content(self.left_panel, self.stacked_widget)

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if cursor is near an edge/corner for resizing
            direction = self._get_resize_direction(event.position().toPoint())
            if direction and not self.is_maximized:
                # Unlock so the edge-drag can change the window size
                self._unlock_size()
                self._resizing = True
                self._resize_dir = direction
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                # Lock the resize cursor for the entire drag operation
                self.setCursor(self._cursor_for_direction(direction))
                event.accept()
                return

            # Titlebar drag
            self._drag_start_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = event.globalPosition().toPoint().y() - self.frameGeometry().y()

        if pos < self.titlebar_height:
            self.toggle_maximize_restore()
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._resizing:
                self._do_resize(event.globalPosition().toPoint())
                event.accept()
                return
            elif self._drag_start_position:
                # When dragging a maximized window by the titlebar, snap
                # instantly to the restored geometry instead of playing the
                # slow restore animation.  This matches the behaviour of
                # native window managers (Windows / macOS / KDE) where the
                # user expects to "pull" the window out of maximized state
                # and start dragging immediately.
                if self.is_maximized:
                    self._instant_restore_for_drag(event.globalPosition().toPoint())
                geo = self.titlebar.geometry()
                if self._drag_start_position.y() < geo.bottomRight().y():
                    self.move(event.globalPosition().toPoint() - self._drag_start_position)
                event.accept()
                return
        # NOTE: cursor management for hover (no button pressed) is handled
        # in eventFilter, NOT here.  mouseMoveEvent only fires when the
        # mouse is over the window's own area — child widgets consume the
        # events.  The eventFilter catches ALL mouse-move events so the
        # resize cursor is always shown/hidden correctly.

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._resizing:
                self._resizing = False
                self._resize_dir = None
                # Re-lock the window to its new size now that the user
                # has finished dragging the edge/corner
                self._lock_size()
                # Clear the resize cursor — the eventFilter will set the
                # correct cursor on the next hover move
                self.unsetCursor()
            self._drag_start_position = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        """Reset the cursor when the mouse leaves the window entirely."""
        self.unsetCursor()
        super().leaveEvent(event)
