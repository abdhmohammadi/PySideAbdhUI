

import os

from PySide6.QtWidgets import (QSizePolicy, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QGridLayout, QPushButton, QLabel, QFrame, QSizeGrip)

from PySide6.QtCore import Qt,QPropertyAnimation, QParallelAnimationGroup, QEasingCurve,QRect,QSize,QPoint,QEvent
from PySide6.QtGui import QPainter, QBrush, QColor, QPixmap,QPainterPath,QMouseEvent,QIcon

from .Widgets import StackedWidget
# Use a relative import from the utils module:
from .utils import get_icon

############################# Customized QMainWindow ################################
# Layout of the windwow: QGridLayout 2x3
# Titlebar:         [0,0]-[0,2],  (stretched in 3 columns)
# Window content :  [1,1]
# Left menu panel:  [0-1,0],      (stretched into 2 rows)
# Right menu panel: [0-1,2],      (stretched into 2 rows)

#####################################################################################

class AbdhWindow(QMainWindow):

    control_button_size = QSize(40,32)
    logo_size = QSize(32,32)
    drag_start_position = QPoint(0,0)
    pane_width = 250
    pane_min_width = 48
    titlebar_height = 42
    # Pined  : The left panel sets to column 0 and is able to open/close
    #          just in this column and auto-close is disabled.
    # Unpined: The left panel sets to column 0 with column-span = 2. it is
    #          able to auto-close.
    overlay  = False
    expanded = True
    def __init__(self):
        
        super().__init__()
        # Track if the window is opening for the first time and used to fade-in animation at start
        self.first_show = True  

        # configuration of the window with start position and size
        # First we hide normal border of the window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint| Qt.WindowType.Window)
        # Enable translucent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)  
        # To start the window in center of screen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Calculate the window dimensions based on the golden ratio
        window_width = int(screen_width * 1.618*0.5)
        window_height = int(screen_height *1.618* 0.5)
        self.resize(window_width, window_height)

        # Center the window on the screen
        x = int((screen_width - window_width)/2)
        y = int((screen_height-window_height)/2)
        
        self.move(x,y*0.70)
        
        self.initalized = False

    def initUI(self,app_title:str='PySideAbdhUI Application', 
               style_sheet=None, title_logo_path=None, 
               direction=Qt.LayoutDirection.LeftToRight):
        
        if style_sheet: self.setStyleSheet(style_sheet)

        self.setWindowTitle(app_title)

        # Main widget and layout
        self.main_widget = QWidget(self)
        self.main_widget.setLayoutDirection(direction)

        self.main_widget.setContentsMargins(0,0,0,0)
        self.setCentralWidget(self.main_widget)
        # 3x3 Grid
        self.main_layout = QGridLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Left panel, location -->[0,0], stretched in 2 rows
        self.left_panel = QFrame(self)
        
        # Uses object name property to correspond the named stylesheet in qss file
        self.left_panel.setObjectName('LeftPaneFrame')
        self.left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_panel.setFixedWidth(self.pane_width)
        self.left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.left_panel_layout = QVBoxLayout(self.left_panel)
        # Content margin for leftpanel:
        # If we set the left margin to a larger value, the mouse 
        # effect will appear equally large inside the panel. 
        self.left_panel_layout.setContentsMargins(0,self.titlebar_height, 0,5)
        self.left_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        #Right panel, location -->[0,2], stretched in 3 rows
        self.right_panel = QFrame(self)
        # Uses object name property to correspond the named stylesheet in qss file
        self.right_panel.setObjectName('RightPaneFrame')
        self.right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.right_panel.setMinimumWidth(0)   # Start with zero width
        self.right_panel.setMaximumWidth(0)   # Also limit max width when collapsed

        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.setSpacing(5)
        self.right_panel_layout.setContentsMargins(10, self.titlebar_height, 10, 10)
        self.right_panel_layout.addStretch(1)
        
        # Toggle button for left menu
        top_commands_layout = QHBoxLayout()
        self.toggle_button = QPushButton("")
        self.toggle_button.setProperty('class','grouped_mini')
        self.toggle_button.setIcon(QIcon(get_icon('menu')))
        self.toggle_button.setMinimumWidth(self.pane_min_width)

        top_commands_layout.addWidget(self.toggle_button)

        top_commands_layout.addStretch()

        self.pin_button = QPushButton("", self)
        self.pin_button.setProperty('class','grouped_mini')
        self.pin_button.setIcon(QIcon(get_icon('pin')))
        self.pin_button.clicked.connect(self.toggle_overlay)
    
        top_commands_layout.addWidget(self.pin_button)

        self.left_panel_layout.addLayout(top_commands_layout)
        
        # Stacked widget for pages
        self.stacked_widget = StackedWidget()
        self.stacked_widget.setContentsMargins(0,0,0,0)
        self.stacked_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Set an object name for the parent widget
        #self.stacked_widget.setObjectName("parentWidget")
        #self.stacked_widget.setStyleSheet('background-color:brown;border: 2px solid black;')
        self.toggle_button.clicked.connect(lambda _, frame= self.left_panel, stack= self.stacked_widget: self.animate_content(frame, stack))

        # Custom title bar
        self.titlebar = self.__create_titlebar(self.windowTitle(), title_logo_path)

        self.main_layout.addWidget(self.stacked_widget, 1, 1,1,2)
        self.main_layout.addWidget(self.right_panel, 0, 2,2,1)
        self.main_layout.addWidget(self.left_panel, 0, 0, 2, 1, Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addWidget(self.titlebar, 0, 0, 1, 3)
        
        # Add QSizeGrip to corners and edges
        self.size_grips = []
        self.add_edge_size_grip()
        self.add_size_grip(0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)      # Top-left corner
        self.add_size_grip(0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)     # Top-right corner
        self.add_size_grip(1, 2, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)  # Bottom-right corner
        self.add_size_grip(1, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)   # Bottom-left corner
        # Enable window resizing from sides
        self.setMouseTracking(True)
        self.resizing = False
        self.resize_direction = None

        self.is_maximized = False                 # Track the current state of the window
        self.original_geometry = self.geometry()  # Store the original geometry
        self.animation = QPropertyAnimation(self, b"geometry")  # Single animation object
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)  # Smooth easing curve
        self.animation.setDuration(175)           # 175ms duration for smoothness
        
        self.initalized = True
        # Install global event filter to detect clicks anywhere
        QApplication.instance().installEventFilter(self)

    def switch_settings_button(self, on= True): self.settings_button.setVisible(on)
    
    def switch_navigations(self, on = True):
        self.back_button.setVisible(on)
        self.forward_button.setVisible(on)

    def toggle_overlay(self):

        self.overlay = not self.overlay
        self.expanded = not self.overlay
        if self.overlay:
            # In overlay stat left and stacked panels are located in column 0.
            # In this stat left panel colsed automatically when mouse clicked out of it.
            # removeing from column 0
            self.main_layout.removeWidget(self.left_panel)
            self.left_panel.setFixedWidth(self.pane_min_width)
            # Placeing into column 0 with column span 2.
            self.main_layout.addWidget(self.left_panel,0, 0, 2, 2, Qt.AlignmentFlag.AlignLeft)
            # Keeping the left margin equal to the width of the left panel
            self.stacked_widget.setContentsMargins(self.pane_min_width,0,0,0)
            #self.stacked_widget.move(self.pane_min_width,0)#,self.stacked_widget.width(),self.stacked_widget.height())
            
        else:
            
            # removeng left panel from column 1
            self.main_layout.removeWidget(self.left_panel)
            # replaceing left panel into column 0
            self.main_layout.addWidget(self.left_panel, 0, 0, 2, 1, Qt.AlignmentFlag.AlignLeft)
            #self.stacked_widget.resize(self.stacked_widget.width() - self.pane_width, self.stacked_widget.height())
            # resetting left margin to zero
            self.stacked_widget.setContentsMargins(0,0,0,0)    

        self.pin_button.setVisible(self.expanded)
    
    def animate_content(self, frame:QFrame, stack:StackedWidget):
        
        if self.overlay: self.toggle_frame(frame, self.pane_min_width)

        else:
            start_width = frame.width()
            end_width = self.pane_min_width if self.expanded else self.pane_width
            width_diff = end_width - start_width

            # Frame animation
            frame_anim = QPropertyAnimation(frame, b"minimumWidth")
            frame_anim.setStartValue(start_width)
            frame_anim.setEndValue(end_width)
            frame_anim.setDuration(400)
            frame_anim.setEasingCurve(QEasingCurve.InOutQuad)
            
            # Stack animation
            stack_width = stack.width()
            
            stack_anim = QPropertyAnimation(stack, b"minimumWidth")
            stack_anim.setStartValue(stack_width)
            stack_anim.setEndValue(stack_width - width_diff)
            stack_anim.setDuration(400)
            stack_anim.setEasingCurve(QEasingCurve.InOutQuad)

            # Parallel animation
            self.anim_group = QParallelAnimationGroup()
            self.anim_group.addAnimation(frame_anim)
            self.anim_group.addAnimation(stack_anim)

            # Delete animation after it's finished
            self.anim_group.finished.connect(self.anim_group.deleteLater)

            self.anim_group.start()

        self.expanded = not self.expanded

        self.pin_button.setVisible(self.expanded)
        
    def open_settings(self): self.toggle_frame(self.right_panel,0)

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

    def show(self):
        try:
            assert self.initalized,'PySideAbdhWindow has not initalized yet!\n Call window.initUI befor show()'
            super().show()  # Call the original show() method from QMainWindow
        except Exception as e:
            print(e)


    def __create_titlebar(self,title_text,title_logo):

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # Logo icon
        self.logo_label = QLabel()
        self.logo_label.setStyleSheet('border-radius:0px;padding: 0px;background-color:transparent; margin:8px 10px 4px 8px;')
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        layout.setAlignment(self.logo_label,Qt.AlignmentFlag.AlignTop)
        
        layout.addWidget(self.logo_label)        
        
        if os.path.exists(title_logo):
            
            pixmap = QPixmap(title_logo).scaled(self.logo_size,
                                                Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)

        # Navigation buttons
        self.back_button = QPushButton('')
    
        self.back_button.setToolTip('Navigation back')
        self.back_button.setProperty('class','grouped_mini')
        
        self.back_button.setIcon(QIcon(get_icon('arrow-left')))
        self.back_button.clicked.connect(self.stacked_widget.go_back)
        layout.addWidget(self.back_button)
        layout.setAlignment(self.back_button,Qt.AlignmentFlag.AlignTop)
        
        self.forward_button = QPushButton('')
        self.forward_button.setProperty('class','grouped_mini')
        self.forward_button.setIcon(QIcon(get_icon('arrow-right')))
        self.forward_button.clicked.connect(self.stacked_widget.go_next)
        layout.addWidget(self.forward_button)
        layout.setAlignment(self.forward_button,Qt.AlignmentFlag.AlignTop)
        # Title label
        self.title_label = QLabel("PySideAbdhUI | Window")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setContentsMargins(4, 4, 0, 0) 
        self.title_label.setText(title_text)
        self.title_label.setProperty('class','caption')
        layout.addWidget(self.title_label)
        layout.setAlignment(self.title_label,Qt.AlignmentFlag.AlignTop)
        # Spacer to push buttons to the right
        layout.addStretch()

        # Settings button
        self.settings_button = QPushButton("", self)
        self.settings_button.setProperty('class','grouped_mini')
        self.settings_button.setToolTip('Setting')
        self.settings_button.setIcon(QIcon(get_icon('settings')))
        self.settings_button.clicked.connect(lambda _, sender= self.right_panel, min_width=0: self.toggle_frame(sender,min_width))
        layout.addWidget(self.settings_button)
        layout.setAlignment(self.settings_button,Qt.AlignmentFlag.AlignTop)
        # Minimize button
        self.minimize_button = QPushButton("")
        self.minimize_button.setProperty('class','grouped_mini')
        self.minimize_button.setIcon(QIcon(get_icon('minus')))
        self.minimize_button.clicked.connect(self.showMinimized)
        layout.addWidget(self.minimize_button)
        layout.setAlignment(self.minimize_button,Qt.AlignmentFlag.AlignTop)

        # Maximize/Restore button
        self.maximize_button = QPushButton("")
        self.maximize_button.setProperty('class','grouped_mini')
        self.maximize_button.setIcon(QIcon(get_icon('square')))
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)
        layout.addWidget(self.maximize_button)
        layout.setAlignment(self.maximize_button,Qt.AlignmentFlag.AlignTop)
        # Close button
        self.close_button = QPushButton('', self)
        self.close_button.setProperty('class','closebutton')
        self.close_button.setIcon(QIcon(get_icon('x')))
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)
        layout.setAlignment(self.close_button,Qt.AlignmentFlag.AlignTop)

        titlebar = QWidget()
        titlebar.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        # Uses object name property to correspond the named stylesheet in qss file
        titlebar.setObjectName('Titlebar')
        titlebar.setFixedHeight(self.titlebar_height)
        titlebar.setLayout(layout)

        return titlebar


    def set_direction(self,direction:Qt.LayoutDirection=Qt.LayoutDirection.LeftToRight): self.stacked_widget.setLayoutDirection(direction)


    def update_navigation_buttons(self, can_go_back, can_go_forward):
        
        self.back_button.setVisible(can_go_back)
        self.forward_button.setVisible(can_go_forward)


    def add_right_panel_item(self,item:QWidget): 
        self.right_panel_layout.insertWidget(self.right_panel_layout.count()-1, item)
        

    def add_left_panel_item(self,item:QWidget): self.left_panel_layout.addWidget(item)


    def toggle_maximize_restore(self):
        
        if self.is_maximized:
            self.animate_restore()
            self.maximize_button.setIcon(QIcon(get_icon('square')))            
        else:
            self.animate_maximize()
            self.maximize_button.setIcon(QIcon(get_icon('double-square')))
        
        self.is_maximized = not self.is_maximized


    def animate_maximize(self):
        # Stop any ongoing animation
        if self.animation.state() == QPropertyAnimation.State.Running: self.animation.stop()

        # Get the available screen geometry (excluding taskbar)
        screen_geometry = QApplication.primaryScreen().availableGeometry()

        # Store the original geometry before maximizing
        geo = self.geometry()

        if geo.width() >= screen_geometry.width(): 
            diff = geo.width() - screen_geometry.width()
            geo.setWidth(geo.width() - diff - 10 )

        if geo.height() >= screen_geometry.height():
            diff = geo.height() - screen_geometry.height()
            geo.setHeight(geo.height() - diff - 10)

        if geo.left()<0: geo.setLeft(5)

        if geo.top()<0: geo.setTop(5)
        
        if geo.bottom()>= screen_geometry.bottom():
            geo.setBottom(screen_geometry.bottom() - 5)

        if geo.right()>= screen_geometry.right():
            geo.setRight(screen_geometry.right() - 5)

        self.original_geometry = geo

        # Set up the animation to expand to full screen
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(screen_geometry)

        # Start the animation
        self.animation.start()


    def animate_restore(self):
        # Stop any ongoing animation
        if self.animation.state() == QPropertyAnimation.State.Running: self.animation.stop()

        # Set up the animation to shrink to the original size
        self.animation.setStartValue(self.geometry())
        
        self.animation.setEndValue(self.original_geometry)

        # Start the animation
        self.animation.start()
       
        
    # fade-in effect animation
    def animate_fadeIn(self):
        # Animation for opacity (fade-in effect)
        self.opacity_effect = self.graphicsEffect()
        if not self.opacity_effect:
            self.opacity_effect = self.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(500)  # 500ms duration
        self.opacity_animation.setStartValue(0.0)  # Start fully transparent
        self.opacity_animation.setEndValue(1.0)  # End fully opaque
        self.opacity_animation.setEasingCurve(QEasingCurve.OutQuad)

        # Animation for geometry (slide-in effect from the top)
        start_rect = QRect(self.x(), self.y() - 50, self.width(), self.height())  # Start 50px above
        end_rect = self.geometry()  # End at the original position
        self.geometry_animation = QPropertyAnimation(self, b"geometry")
        self.geometry_animation.setDuration(500)  # 500ms duration
        self.geometry_animation.setStartValue(start_rect)
        self.geometry_animation.setEndValue(end_rect)
        self.geometry_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Start both animations
        self.opacity_animation.start()
        self.geometry_animation.start()


    def add_page(self, page_widget:QWidget): self.stacked_widget.add_page(page_widget)


    def apply_style(self,style_sheet): self.setStyleSheet(style_sheet)

    def load_style(self,file_name ='default'):
    
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        else:
            print(f"Stylesheet not found: {file_name}")
            return ""


    def add_size_grip(self, row, col, alignment):
        size_grip = QSizeGrip(self)
        size_grip.setFixedSize(10, 10)
        size_grip.setStyleSheet("QSizeGrip { background: none; border: none; }")
        self.size_grips.append(size_grip)
        self.main_layout.addWidget(size_grip, row, col, alignment=alignment)
    

    def add_edge_size_grip(self):
        # Left edge
        size_grip = QSizeGrip(self)
        size_grip.setCursor(Qt.CursorShape.SizeHorCursor)
        size_grip.setFixedWidth(10)
        size_grip.setStyleSheet("QSizeGrip { background: none; border: none; }")
        self.size_grips.append(size_grip)
        # Set the size policy to make button2 stretch
        size_grip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(size_grip,0,0,2,1)
        # Right edge
        size_grip = QSizeGrip(self)
        size_grip.setCursor(Qt.CursorShape.SizeHorCursor)
        size_grip.setFixedWidth(10)
        size_grip.setStyleSheet("QSizeGrip { background: none; border: none; }")
        self.size_grips.append(size_grip)
        # Set the size policy to make button2 stretch
        size_grip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(size_grip,0,2,2,1)

        # Top edge
        size_grip = QSizeGrip(self)
        size_grip.setCursor(Qt.CursorShape.SizeVerCursor)
        size_grip.setFixedHeight(10)
        size_grip.setStyleSheet("QSizeGrip { background: none; border: none; }")
        self.size_grips.append(size_grip)
        # Set the size policy to make button2 stretch
        size_grip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(size_grip,0,0,1,3, Qt.AlignmentFlag.AlignTop)
        # Bottom edge
        size_grip = QSizeGrip(self)
        size_grip.setCursor(Qt.CursorShape.SizeVerCursor)
        size_grip.setFixedHeight(10)
        size_grip.setStyleSheet("QSizeGrip { background: none; border: none; }")
        self.size_grips.append(size_grip)
        # Set the size policy to make button2 stretch
        size_grip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(size_grip,1,0,1,3, Qt.AlignmentFlag.AlignBottom)

    
    def showEvent(self, event):
        # Animate the window only when it's shown for the first time
        if self.first_show:
            self.first_show = False
            self.animate_fadeIn()

        super().showEvent(event)
        

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 8, 8)
        painter.fillPath(path, QBrush(QColor(255, 255, 255)))
    
    
    def eventFilter(self, obj, event):
        # Detect clicks anywhere in the application to close the frame.
        if event.type() == QEvent.Type.MouseButtonPress:
            # Check if click is outside the frame
            if self.right_panel.width()>0 and not self.right_panel.geometry().contains(self.mapFromGlobal(event.globalPos())):
                self.toggle_frame(self.right_panel,0)  # Collapse the right pane

            if self.overlay and self.expanded:
                if not self.left_panel.geometry().contains(self.mapFromGlobal(event.globalPos())):
                    
                    self.animate_content(self.left_panel, self.stacked_widget)  # Collapse the left pane

        
        return super().eventFilter(obj, event)  # Continue normal event processing



    def mousePressEvent(self, event:QMouseEvent):

        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos  = event.globalPosition().toPoint().y() - self.frameGeometry().y()

        if pos<self.titlebar_height: self.toggle_maximize_restore()
        # Call the base class implementation (optional)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event:QMouseEvent):

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.resizing:
                self.resize_window(event)
            else:
                if self.drag_start_position:
                    self.move(event.globalPosition().toPoint() - self.drag_start_position)
            event.accept()

        super().mouseMoveEvent(event)

# End Window