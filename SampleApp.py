"""
This app is a model based application, in development of the app 
"""
import json
import sys, os
import PySideAbdhUI
from PySideAbdhUI import Window, StackedWidget, Separator
from PySideAbdhUI.StyleManagers import QtStyleSheetManager
from PySideAbdhUI.Notify import PopupNotifier

# PySide6 modules
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFontDatabase, QColor
from PySide6.QtWidgets import (QApplication, QPushButton, QMessageBox, QFileDialog, QLabel, QGridLayout,
                               QComboBox, QRadioButton, QHBoxLayout, QVBoxLayout, QWidget,
                               QColorDialog, QScrollArea, QFormLayout, QLineEdit)

st =  QtStyleSheetManager()

lbl_style = """QLabel 
{
    background-color: transparent; /* Transparent so it blends with parent */
    font-size: 16px;               /* Adjust as needed */
    font-weight: normal;           /* Options: normal, bold */
    padding: 4px;                  /* Some spacing around the text */
    border-bottom:1px solid #88888866;                  
}
"""


class ThemeManager:
    def __init__(self, json_path):
        self.json_path = json_path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.json_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading theme JSON: {e}")
            return {"active-theme": "", "themes": {}}

    def save(self):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def get_current_theme_name(self):
        return self.data.get("active-theme", "")

    def get_current_theme(self):
        name = self.get_current_theme_name()
        return self.data.get("themes", {}).get(name, {})

    def switch_theme(self, new_theme_name):
        if new_theme_name in self.data.get("themes", {}):
            self.data["active-theme"] = new_theme_name
            self.save()
            return True
        return False

    def get_color(self, role_category, role_name):
        theme = self.get_current_theme()
        return theme.get(role_category, {}).get(role_name, {}).get("color")

    def get_all_themes(self):
        return list(self.data.get("themes", {}).keys())


class ThemeEditor(QWidget):
    def __init__(self, theme_json_path):
        super().__init__()
        self.theme_manager = ThemeManager(theme_json_path)
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
        self.theme_selector.addItems(self.theme_manager.get_all_themes())
        self.theme_selector.setCurrentText(self.theme_manager.get_current_theme_name())
        self.theme_selector.currentTextChanged.connect(self.on_theme_switch)
        hlayout.addWidget(QLabel('Theme:'))
        hlayout.addWidget(self.theme_selector)

        generate_btn = QPushButton("💾 Generate QSS")
        generate_btn.clicked.connect(self.generate_qss)
        hlayout.addWidget(generate_btn)

        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.addLayout(hlayout)
        layout.addWidget(QLabel("<hr>"))  # Simple separator for now

        self.build_theme_ui(self.grid_layout)

        scroll = QScrollArea(self)
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

    def build_theme_ui(self, grid_layout: QGridLayout):
        self.inputs = {}  # Reset inputs dict on rebuild
        theme = self.theme_manager.get_current_theme()
        row = 1

        for category, colors in theme.items():
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
                self.inputs[color_key] = editor

                # Color preview
                preview = QLabel()
                preview.setFixedSize(24, 24)
                preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #888;")

                # Picker button
                button = QPushButton("🎨")
                button.setProperty('class', 'mini')
                button.clicked.connect(self.make_picker(editor, preview))

                # Add to layout
                grid_layout.addWidget(label, row, order + 0)
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
        if self.theme_manager.switch_theme(theme_name):
            self.clear_layout(self.grid_layout)
            self.build_theme_ui(self.grid_layout)
            # self.theme_selector.setCurrentText(theme_name)  # Don't set again here!

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        QApplication.processEvents()

    def generate_qss(self):
        qss = ""
        for key, input_field in self.inputs.items():
            qss += f"* {{ --{key}: {input_field.text()}; }}\n"

        file_path, _ = QFileDialog.getSaveFileName(self, "Save QSS File", "theme.qss", "QSS Files (*.qss)")
        if file_path:
            with open(file_path, "w") as f:
                f.write(qss)

class CLI:

    def __init__(self):

        self.app = QApplication(sys.argv)

        self.window = Window.AbdhWindow()

    def apply_style(self):
        # default style sheets location is in the: '/resourrces/styles/<folder with style name>'
        # this folder contains two qss file named classes.qss and global.qss
        # global.qss stylishes the widgets generally and classes.qss was defined for spicial effects
        # When a style is selected, the app creates a qss file in the 'LOCALAPPDATA' with file name
        # '<folder with style name>.qss' then merges these files, writes  all in the created file.
        # the uses this style file to appy effects.
        dialog = QFileDialog(self.window,directory = '/resources/styles')
        dialog.setOption(QFileDialog.Option.ShowDirsOnly)
        #dialog.setFileMode(QFileDialog.FileMode.Directory)
       
        if not dialog.exec() == QFileDialog.DialogCode.Accepted: return
        
        fileName = dialog.selectedFiles()

        if fileName:
            st.load_stylesheet(fileName[0])

            self.app.setStyleSheet(st.stylesheet)

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
        btn = QPushButton(text='CHANGE STYLE')
        self.window.add_right_panel_item(btn)
        #btn.setObjectName('MenuItem')
        btn.clicked.connect(self.apply_style)

        github = QLabel('\n https://github.com/abdhmohammadi/')
        self.window.add_right_panel_item(github)
        github.setProperty('class','hyperlink')          


    def create_left_pane(self):
        # Init left pane
        left_item = QPushButton('Window properties')
        left_item.setIcon(QIcon('F:\\Projects\\Python\\icons\\shapes.svg'))
        left_item.setCheckable(True)
        left_item.setChecked(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _, s= left_item:self.load_window_properties_page(s))
        self.load_window_properties_page(left_item)
        
        left_item = QPushButton('Widgets')
        left_item.setIcon(QIcon('F:\\Projects\\Python\\icons\\shapes.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.load_widgets_page(s))

        left_item = QPushButton('Theme Editor')
        left_item.setIcon(QIcon('F:\\Projects\\Python\\icons\\shapes.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.load_theme_editor(s))

        self.window.left_panel_layout.addStretch(1)
        
    def load_theme_editor(self, sender:QPushButton):
        self.uncheck_items(self.window.left_panel_layout)
        sender.setChecked(True)

        color_roles_path ="PySideAbdhUI/resources/styles/color-roles.json"
        
        if not os.path.exists(color_roles_path):
            QMessageBox.warning(self.window,'Error','Color roles not found')
            return 
        
        #with open(color_roles_path, "r") as f:
            
        #    theme_json =  json.load(f)
            
        editor = ThemeEditor(color_roles_path)
            
        self.window.add_page(editor)
        

    def uncheck_items(self,grid_layout:QVBoxLayout):
        
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            if type(item.widget()) is QPushButton:
                item.widget().setChecked(False)

    def toggle_direction(self, direction:Qt.LayoutDirection): self.window.set_direction(direction)
        

    def load_widgets_page(self, sender:QPushButton): 
        
        self.uncheck_items(self.window.left_panel_layout)

        if sender: sender.setChecked(True)

        w = QWidget()
        grid_layout = QGridLayout(w)
        grid_layout.setColumnStretch(2,1)
        self.window.add_page(w)
        
        lbl = QLabel('WIDGETS')
        lbl.setWordWrap(True)
        lbl.setProperty('class', 'title')
        lbl.setTextFormat(Qt.TextFormat.RichText)
        grid_layout.addWidget(lbl,0,0,alignment=Qt.AlignmentFlag.AlignTop)

        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s += '<b>StackedWidget:</b> is one of advanced widgets that plays imporant rule as a container of other objects.</div>'
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
        
        btn = QPushButton('<')
        btn.setProperty('class','grouped_min')
        btn.clicked.connect(stack.go_back)
        grid.addWidget(btn,0,0)
        
        btn = QPushButton('>')
        btn.setProperty('class','grouped_min')
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

        s =  '<div style="line-height: 100%; font-size: 16px;">'
        s += 'The main window has a built-in function to apply custom themes. '
        s += 'You can also use <b>StyleManagers.QtStyleSheetManager</b> '
        s += 'To change the theme of the application. Practice now by clicking <b>"Change Style"</b> button from right panel of this page.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        #lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        
        grid_layout.addWidget(lbl,1,0,alignment=Qt.AlignmentFlag.AlignTop)
        
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
        button = QPushButton('Change Style')
        button.clicked.connect(self.apply_style)
        right_panel.addWidget(button)

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
        
        st.add_property_to_widget('QWidget','font-family',selected_text)
        st.add_property_to_widget('QWidget','font-size',12)
        
        settings_list = [('family',selected_text),('size',12)]
        # Create a dictionary with the list elements as key-value pairs under 'connection'
        #settings = {"font": dict(settings_list)}
        #settings_manager.write(settings)

        self.app.setStyleSheet(st.stylesheet)



    def Run(self):
        root = os.path.dirname(__file__) 
        style_path = "C:\\Users\\AbdhM\\AppData\\Local\\Abdh\\TeacherAssistant\\default-dark.qss" #root + "\\PySideAbdhUI\\resources\\styles\\default-dark.qss"
        # Using QtStyleSheetManager to manage custom styles
        st.load_stylesheet(style_path)
    
        check, value = st.check_accent_color_placeholder()
                    
        if check: st.replace_placeholder(value)
        # Apply stylesheet on the application
        self.app.setStyleSheet(st.stylesheet)
        
        # Our custom ICON is available in application_path + "/resources/icons/
        self.app.setWindowIcon(QIcon(root + '\\PySideAbdhUI\\resources\\png\\app-icon.png'))
        # Create the main customized UI window
        self.window = Window.AbdhWindow()

        self.window.initUI(app_title= 'PySideAbdhUI - Application test | ' + PySideAbdhUI.__version__, 
                           title_logo_path= root + "\\PySideAbdhUI\\resources\\png\\app-icon.png",
                           direction= Qt.LayoutDirection.LeftToRight)
    
        
        self.create_settings_pane()
        self.create_left_pane()

        self.window.show()
        
        PopupNotifier.Notify(self.window,"Wellcome!", "📚 PySideAbdhUI is ready.", 'bottom-right')#, 
    
        sys.exit(self.app.exec())

cli = CLI()

cli.Run()