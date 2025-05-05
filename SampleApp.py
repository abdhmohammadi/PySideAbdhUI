"""
This app is a model based application, in development of the app 
"""
import json
import sys, os
import PySideAbdhUI
from PySideAbdhUI import Window, StackedWidget, utils
from PySideAbdhUI.Notify import PopupNotifier

# PySide6 modules
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFontDatabase, QColor
from PySide6.QtWidgets import (QApplication, QPushButton, QMessageBox, QLabel, QGridLayout,
                               QComboBox, QRadioButton, QHBoxLayout, QVBoxLayout, QWidget,
                               QColorDialog, QScrollArea, QLineEdit)


theme = utils.ThemeManager()

class ThemeEditor(QWidget):
    def __init__(self):
        
        super().__init__()

        self.inputs = {}

        hlayout = QHBoxLayout()
        hlayout.setSpacing(3)

        content_widget = QWidget()
        self.grid_layout = QGridLayout(content_widget)
        self.grid_layout.setSpacing(3)

        title_lbl = QLabel('THEME EDITOR')
        title_lbl.setProperty('class', 'heading2')
        hlayout.addWidget(title_lbl)
        hlayout.addStretch(1)

        self.theme_selector = QComboBox()
        self.theme_selector.addItems(theme.get_all_themes())
        self.theme_selector.setCurrentText(theme.get_current_theme_name())
        self.theme_selector.currentTextChanged.connect(self.on_theme_switch)
        hlayout.addWidget(QLabel('Theme:'))
        hlayout.addWidget(self.theme_selector)

        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.addLayout(hlayout)
        layout.addWidget(QLabel("<hr>"))  # Simple separator for now

        self.build_theme_ui(self.grid_layout)

        scroll = QScrollArea(self)
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        theme.apply_theme(QApplication.instance(),theme.get_current_theme_name())

    def build_theme_ui(self, grid_layout: QGridLayout):
        self.inputs = {}  # Reset inputs dict on rebuild
        current_theme = theme.get_current_theme()
        row = 1

        for category, colors in current_theme.items():
            category_label = QLabel(f"<u><b>{category}</b></u>")
            category_label.setProperty('class', 'subtitle')
            grid_layout.addWidget(category_label, row, 0, 1, 1, Qt.AlignmentFlag.AlignLeft)
            row += 1

            order = 0
            for color_key, color_info in colors.items():
                if not isinstance(color_info, dict):
                    print(f"Invalid color_info for {color_key}, skipping.")
                    continue

                color_hex = color_info.get("color", "#000000")
                description = color_info.get("description", "")
                color_key = str(color_key)
                color_hex = str(color_hex)
                description = str(description)

                # Color label
                label = QLabel(color_key)

                # Editable color field
                editor = QLineEdit(color_hex)
                editor.setObjectName(color_key)
                editor.setFixedWidth(120)
                self.inputs[color_key] = editor

                # Color preview
                preview = QLabel()
                preview.setFixedSize(27, 27)
                preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #888888;")

                # Picker button
                button = QPushButton("🎨")
                button.setProperty('class', 'mini')
                button.setFixedWidth(24)
                button.clicked.connect(self.make_picker(editor, preview))

                # Add to layout
                grid_layout.addWidget(label, row, order + 0,alignment=Qt.AlignmentFlag.AlignRight)
                grid_layout.addWidget(editor, row, order + 1)
                grid_layout.addWidget(preview, row, order + 2)
                grid_layout.addWidget(button, row, order + 3)

                # Description
                desc_label = QLabel(description)
                desc_label.setStyleSheet("color: gray; font-size: 10px;")
                grid_layout.addWidget(desc_label, row, order + 4)

                if order == 0:
                    order = 5
                else:
                    order = 0
                    row += 1

            row += 1

        grid_layout.setRowStretch(grid_layout.rowCount(), 1)

    def make_picker(self, edit, preview_label):
        def pick_color():
            initial = QColor(edit.text())
            color = QColorDialog.getColor(initial)
            if color.isValid():
                hex_color = color.name()
                edit.setText(hex_color)
                preview_label.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")
        return pick_color


    def on_theme_switch(self, theme_name):

        if theme.switch_theme(theme_name):
            self.clear_layout(self.grid_layout)
            self.build_theme_ui(self.grid_layout)
            self.theme_selector.setCurrentText(theme_name)

            theme.apply_theme(QApplication.instance(),theme_name)


    def clear_layout(self, layout:QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        QApplication.processEvents()

class CLI:

    def __init__(self):

        self.app = QApplication(sys.argv)

        self.window = Window.AbdhWindow()
 
    # Creates a vertical panel on the right edge of the mian window
    # This panel is used to settings porpose
    def create_settings_pane(self):

        # Global Font in the application domain 
        fonts = QFontDatabase.families()

        combo2 = QComboBox()
        combo2.setPlaceholderText("Select font")
        combo2.addItems(fonts)
        combo2.setCurrentText('Times New Roman')

        self.window.add_right_panel_item(combo2)
        # Changes the application font, this change affects all objects in the application
        combo2.currentIndexChanged.connect(lambda _,sender=combo2:self.on_font_changed(sender))

        # Page direction options: It is provided Left-to-Right
        # The direction is applied on the mantent of main frame, and titlebar,
        # left panel and right panel are not affected currently.
        hlayout = QHBoxLayout()
        #direction = settings_manager.find_value('direction')
        radio1 = QRadioButton('Right to Left')
        radio1.clicked.connect(lambda _, d=Qt.LayoutDirection.RightToLeft: self.toggle_direction(d))
        radio1.setChecked(False)
        hlayout.addWidget(radio1)

        radio2 = QRadioButton('Left to Right')
        radio2.setChecked(True)
        radio2.clicked.connect(lambda _, d= Qt.LayoutDirection.LeftToRight: self.toggle_direction(d))

        hlayout.addWidget(radio2)
        self.window.set_direction(Qt.LayoutDirection.LeftToRight)
        w = QWidget()
        w.setLayout(hlayout)
        self.window.add_right_panel_item(w)

        # There are a number of custom styles can be applied to the UI.
        # Changing it will affects all UI objects of the application.
        theme_selector = QComboBox()
        theme_selector.addItems(theme.get_all_themes())
        theme_selector.setCurrentText(theme.get_current_theme_name())
        theme_selector.currentTextChanged.connect(lambda _, sender=theme_selector:self.on_theme_switch(sender=sender))
        self.window.add_right_panel_item(theme_selector)

        github = QLabel('\n https://github.com/abdhmohammadi/')
        self.window.add_right_panel_item(github)
        github.setProperty('class','hyperlink')          


    def on_theme_switch(self,sender:QComboBox):

        theme_name = sender.currentText()
        theme.apply_theme(QApplication.instance(),theme_name)


    def create_left_pane(self):
        left_item = QPushButton('Theme Editor')
        left_item.setIcon(QIcon('F:\\Projects\\Python\\icons\\shapes.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.load_theme_editor(s))
        self.load_theme_editor(left_item)

        # Init left pane
        left_item = QPushButton('Window properties')
        left_item.setIcon(QIcon('F:\\Projects\\Python\\icons\\shapes.svg'))
        left_item.setCheckable(True)
        left_item.setChecked(False)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _, s= left_item:self.load_window_properties_page(s))
        
        left_item = QPushButton('Navigation')
        left_item.setIcon(QIcon('F:\\Projects\\Python\\icons\\shapes.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.load_stacked_page(s))

        self.window.left_panel_layout.addStretch(1)


    def load_theme_editor(self, sender:QPushButton):
        self.uncheck_items(self.window.left_panel_layout)
        sender.setChecked(True)
        
        if not os.path.exists(theme.color_roles):
            QMessageBox.warning(self.window,'Error','Color roles not found')
            return 
                    
        editor = ThemeEditor()
            
        self.window.add_page(editor)
        

    def uncheck_items(self,grid_layout:QVBoxLayout):
        
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            if type(item.widget()) is QPushButton:
                item.widget().setChecked(False)


    def toggle_direction(self, direction:Qt.LayoutDirection): self.window.set_direction(direction)
        

    def load_stacked_page(self, sender:QPushButton): 
        
        self.uncheck_items(self.window.left_panel_layout)

        if sender: sender.setChecked(True)

        w = QWidget()
        grid_layout = QGridLayout(w)
        grid_layout.setColumnStretch(2,1)
        self.window.add_page(w)
        
        lbl = QLabel('STACKED PAGES')
        lbl.setWordWrap(True)
        lbl.setProperty('class', 'title')
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,0,0,alignment=Qt.AlignmentFlag.AlignTop)

        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s += '<b>StackedWidget:</b> is one of advanced widgets that plays important rule as a container of other objects. this widget has powered by adding slide animation feature.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,1,0,1,3,alignment=Qt.AlignmentFlag.AlignTop)

        grid = QGridLayout()
        grid_layout.addLayout(grid,2,0, alignment=Qt.AlignmentFlag.AlignTop)

        lbl = QLabel('Stacked Widget')
        lbl.setProperty('class','title')
        grid.addWidget(lbl,0,2)

        stack = StackedWidget()
        stack.setStyleSheet('border:1px solid #88888866; border-radius:8px;padding:5px')
        grid_layout.addWidget(stack,3,0,1,3)

        lbl = QLabel('       Page 1')
        lbl.setStyleSheet('border:none; background-color: brown;color:#ffffff;font-size:72pt;text-align: center;')        
        stack.add_page(lbl)

        lbl= QLabel('        Page 2')
        lbl.setStyleSheet('border:none; background-color: green;color:#ffffff;font-size:72pt;text-align: center;')  
        stack.add_page(lbl)

        lbl= QLabel('Page 3')
        lbl.setStyleSheet('border:none; background-color: lightblue;color:#000000;font-size:72pt;text-align: center;')  
        stack.add_page(lbl)
        
        btn = QPushButton('')
        btn.setProperty('class','grouped_min')
        btn.setIcon(QIcon(PySideAbdhUI.utils.get_icon('arrow-left')))
        btn.clicked.connect(stack.go_back)
        grid.addWidget(btn,0,0)
        
        btn = QPushButton('')
        btn.setProperty('class','grouped_min')
        btn.setIcon(QIcon(PySideAbdhUI.utils.get_icon('arrow-right')))
        btn.clicked.connect(stack.go_next)
        grid.addWidget(btn,0,1)

        grid_layout.setRowStretch(3,1)


    def load_window_properties_page(self, sender:QPushButton): 
        
        self.uncheck_items(self.window.left_panel_layout)
        
        if sender: sender.setChecked(True)
        
        w = QWidget()
        grid_layout = QGridLayout(w)
        grid_layout.setColumnStretch(0,4)
        grid_layout.setColumnStretch(1,1)
        self.window.add_page(w)
        
        s = '<b>Important features of the main window:</b>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setProperty('class', 'title')
        lbl.setTextFormat(Qt.TextFormat.RichText)
        
        grid_layout.addWidget(lbl,0,0,alignment=Qt.AlignmentFlag.AlignTop)

        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s +=  '• In the top-right, next to the control keys, there is a settings menu ⚙️. By clicking on it, a panel opens. '
        s += 'In it, the settings are located within the PySideAbdhUI page. The user can also set his application settings there. '
        s += 'if you want can hide settings button by <b>\'switch_settings_button(False)\'</b></div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        #lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,2,0,alignment=Qt.AlignmentFlag.AlignTop)

        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s += '• The left panel is the main menu container for accessing the user\'s application components. '
        s += 'This section is supported by two function. One is for opening and closing the panel and the other '
        s += 'is for switching its overlay state. On the left panel click on ☰ to expand or close the panel, '
        s += 'click on the 📌 to toggle ovelay property</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        #lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,3,0,alignment=Qt.AlignmentFlag.AlignTop)
        
        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s += '• Navigation keys ⬅️ ➡️ and the application logo are available in the title bar. These keys can be hidden with <b>\'switch_navigations(False)\'</b>. '
        s += 'You can also use ss to place a custom logo in the left corner of the title bar.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        #lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,4,0,alignment=Qt.AlignmentFlag.AlignTop)

        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s += '• You can also use the existing notification system to provide appropriate notifications to the user. '
        s += 'This system is available throughout the package. You can easily enable this using <b>PopupNotifier.Notify(...)</b>.'
        s += 'Try now using \'Test Notification\' button.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        #lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,5,0,alignment=Qt.AlignmentFlag.AlignTop)

        right_panel = QVBoxLayout()

        button = QPushButton('Open Settings')
        button.clicked.connect(self.window.open_settings)
        right_panel.addWidget(button)

        button = QPushButton('Test notification')
        button.clicked.connect(lambda:PopupNotifier.Notify(self.window, message='👋 Hi, This is the PySideAbdhUI notification feature.',position='top-right'))
        right_panel.addWidget(button)


        right_panel.addStretch()
        grid_layout.addLayout(right_panel,0,1,2,1)

        grid_layout.setRowStretch(6,1)

    
    def on_font_changed(self,sender:QComboBox):
        # Get the text of the selected item 
        selected_text = sender.itemText(sender.currentIndex())
        
        #st.add_property_to_widget('QWidget','font-family',selected_text)
        #st.add_property_to_widget('QWidget','font-size',12)
        
        settings_list = [('family',selected_text),('size',12)]
        # Create a dictionary with the list elements as key-value pairs under 'connection'
        #settings = {"font": dict(settings_list)}
        #settings_manager.write(settings)

        #self.app.setStyleSheet(st.stylesheet)


    def Run(self):
        root = os.path.dirname(__file__)
        icon = PySideAbdhUI.get_icon(package='PySideAbdhUI.resources.png',name='app-icon',ext='png')
        # Our custom ICON is available in application_path + "/resources/icons/
        self.app.setWindowIcon(QIcon(icon))
        # Create the main customized UI window
        self.window = Window.AbdhWindow()

        self.window.initUI(app_title= 'PySideAbdhUI - Application test | ' + PySideAbdhUI.__version__, 
                           title_logo_path= icon, direction= Qt.LayoutDirection.LeftToRight)
    
        
        self.create_settings_pane()
        self.create_left_pane()

        self.window.show()
        
        PopupNotifier.Notify(self.window,"Wellcome!", "📚 PySideAbdhUI is ready.", 'bottom-right')#, 
    
        sys.exit(self.app.exec())

cli = CLI()

cli.Run()