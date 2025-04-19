"""
This app is a model based application, in development of the app 
"""

import sys, os
import PySideAbdhUI
from PySideAbdhUI import Window
from PySideAbdhUI.StyleManagers import QtStyleSheetManager
from PySideAbdhUI.Notify import PopupNotifier

# PySide6 modules
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFontDatabase
from PySide6.QtWidgets import (QApplication, QPushButton, QMessageBox, QFileDialog, QLabel, QGridLayout,
                               QComboBox, QRadioButton, QHBoxLayout, QVBoxLayout, QWidget)

st =  QtStyleSheetManager()

lbl_style = """QLabel 
{
    background-color: transparent; /* Transparent so it blends with parent */
    font-size: 16px;               /* Adjust as needed */
    font-weight: normal;           /* Options: normal, bold */
    padding: 4px;                  /* Some spacing around the text */
    border-bottom:2px solid #888888;                  
}
"""
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
        left_item.setObjectName('MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(self.load_window_properties_page)
        self.load_window_properties_page(left_item)
        
        """self.window.add_left_panel_item(left_item)
        
        left_item = QPushButton('Learning resource Editor')
        left_item.setIcon(QIcon(root + '\\notebook-pen.svg'))
        left_item.setCheckable(True)
        left_item.setObjectName('MenuItem')
        left_item.clicked.connect(lambda _, sender=left_item: self.load_EduResourceEditor(sender))
        
        self.window.add_left_panel_item(left_item)

        left_item = QPushButton('Resource collection')
        left_item.setIcon(QIcon(root + '\\library.svg'))
        left_item.setCheckable(True)
        left_item.setObjectName('MenuItem')
        left_item.clicked.connect(lambda _, sender=left_item: self.load_EduResourcesViewer(sender))
        
        self.window.add_left_panel_item(left_item)

        left_item = QPushButton('Database maintenance')
        left_item.setIcon(QIcon(root + '\\database-zap.svg'))
        left_item.setCheckable(True)
        left_item.setObjectName('MenuItem')
        left_item.clicked.connect(lambda _, sender= left_item: self.load_db_maintenance_page(sender))
        """
        self.window.left_panel_layout.addStretch(1)
        

    def uncheck_items(self,layout:QVBoxLayout):
        
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if type(item.widget()) is QPushButton:
                item.widget().setChecked(False)

    def toggle_direction(self, direction:Qt.LayoutDirection): self.window.set_direction(direction)
        
    def load_EduResourceEditor(self, sender:QPushButton): 
        
        self.uncheck_items(self.window.left_panel_layout)
        #self.window.add_page(Pages.EducationalResourceEditor())
        sender.setChecked(True)

    def load_window_properties_page(self, sender:QPushButton): 
        
        #self.uncheck_items(self.window.left_panel_layout)
        
        w = QWidget()
        layout = QGridLayout(w)
        layout.setColumnStretch(0,4)
        layout.setColumnStretch(1,1)
        self.window.add_page(w)
        
        s =  '<div style="line-height: 200%; font-size: 20px;">'
        s += '<b>Important features of the main window:</b></div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setProperty('class', 'title')
        lbl.setTextFormat(Qt.TextFormat.RichText)
        
        layout.addWidget(lbl,0,0,alignment=Qt.AlignmentFlag.AlignTop)

        s =  '<div style="line-height: 200%; font-size: 16px;">'
        s += '• <b>Important features of the main window:</b><br>'
        s += 'The main window has a built-in function to apply custom themes. '
        s += 'You can also use <b>StyleManagers.QtStyleSheetManager</b> '
        s += 'To change the theme of the application. Practice now by clicking <b>"Change Style"</b> button from right panel of this page.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        
        layout.addWidget(lbl,1,0,alignment=Qt.AlignmentFlag.AlignTop)
        
        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 200%; font-size: 16px;">'
        s +=  '• In the top-right, next to the control keys, there is a settings menu ⚙️. By clicking on it, a panel opens. '
        s += 'In it, the settings are located within the PySideAbdhUI page. The user can also set his application settings there. '
        s += 'if you want can hide settings button by <b>\'switch_settings_button(False)\'</b></div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl,2,0,alignment=Qt.AlignmentFlag.AlignTop)

        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 200%; font-size: 16px;">'
        s += '• The left panel is the main menu container for accessing the user\'s application components. '
        s += 'This section is supported by two function. One is for opening and closing the panel and the other '
        s += 'is for switching its overlay state. On the left panel click on ☰ to expand or close the panel, '
        s += 'click on the 📌 to toggle ovelay property</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl,3,0,alignment=Qt.AlignmentFlag.AlignTop)
        
        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 200%; font-size: 16px;">'
        s += '• Navigation keys ⬅️ ➡️ and the application logo are available in the title bar. These keys can be hidden with <b>\'switch_navigations(False)\'</b>. '
        s += 'You can also use ss to place a custom logo in the left corner of the title bar.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl,4,0,alignment=Qt.AlignmentFlag.AlignTop)

        # ------------------------------------------------------------ #
        s =  '<div style="line-height: 200%; font-size: 16px;">'
        s += '• You can also use the existing notification system to provide appropriate notifications to the user. '
        s += 'This system is available throughout the package. You can easily enable this using <b>PopupNotifier.Notify(...)</b>.'
        s += 'Try now using \'Test Notification\' button.</div>'
        lbl = QLabel(s)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(lbl_style)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl,5,0,alignment=Qt.AlignmentFlag.AlignTop)

        right_panel = QVBoxLayout()
        button = QPushButton('Change Style')
        button.clicked.connect(self.apply_style)
        right_panel.addWidget(button)

        button = QPushButton('Open Settings')
        button.clicked.connect(self.window.open_settings)
        right_panel.addWidget(button)

        button = QPushButton('Test notification')
        button.clicked.connect(lambda:PopupNotifier.Notify(self.window, message='👋 Hi, This is the PySideAbdhUI notification feature.'))
        right_panel.addWidget(button)


        right_panel.addStretch()
        layout.addLayout(right_panel,0,1,2,1)

        layout.setRowStretch(6,1)
        if sender: sender.setChecked(True)

    
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

        style_path = "PySideAbdhUI\\resources\\styles\\default-light.qss"
        # Using QtStyleSheetManager to manage custom styles
        st.load_stylesheet(style_path)
    
        check, value = st.check_accent_color_placeholder()
                    
        if check: st.replace_placeholder(value)
        # Apply stylesheet on the application
        self.app.setStyleSheet(st.stylesheet)
        
        # Our custom ICON is available in application_path + "/resources/icons/
        self.app.setWindowIcon(QIcon('PySideAbdhUI\\resources\\png\\app-icon.png'))
        # Create the main customized UI window
        self.window = Window.AbdhWindow()

        self.window.initUI(app_title= 'PySideAbdhUI - Application test | ' + PySideAbdhUI.__version__, 
                           title_logo_path=  "PySideAbdhUI\\resources\\png\\app-icon.png",
                           direction= Qt.LayoutDirection.LeftToRight)
    
        
        self.create_settings_pane()
        self.create_left_pane()

        self.window.show()
        
        PopupNotifier.Notify(self.window,"Wellcome!", "📚 PySideAbdhUI is ready.", 'bottom-right')#, 
    
        sys.exit(self.app.exec())

cli = CLI()

cli.Run()