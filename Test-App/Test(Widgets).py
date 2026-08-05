
import os
import random
import sys
from pathlib import Path
# Add the parent package directory to sys.path
# (the inner PySideUI/ which is the Python package root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from widgets.src.PySideAbdhUI.Widgets import Window, utils
from widgets.src.PySideAbdhUI.Widgets.Notify import PopupNotifier
from widgets.src.PySideAbdhUI.Widgets.Widgets import RingProgress, SearchBox, Separator, StackedWidget

# PySide6 modules
from PySide6.QtCore import QTimer, Qt,Signal
from PySide6.QtGui import QIcon, QFontDatabase, QColor
from PySide6.QtWidgets import (QApplication, QFileDialog, QFontComboBox, QMenu, QProgressBar,
                               QPushButton, QMessageBox, QLabel, QGridLayout, QTabWidget,
                               QComboBox, QRadioButton, QHBoxLayout, QSlider, QGroupBox, QCheckBox,
                               QVBoxLayout, QWidget,  QColorDialog, QScrollArea, QLineEdit)


icon_path ='F:\\Projects\\Python\\icons\\svg\\'
theme = utils.ThemeManager()


class SearchOptionsPanel(QWidget):
    """
    Custom popup panel for search options.
    Emits search_requested with a dict of all current settings
    and closes the parent popup.
    """

    search_requested = Signal(dict)   # emitted when the Search button is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Search in group ---
        search_in_group = QGroupBox("Search in:")
        
        search_in_layout = QHBoxLayout(search_in_group)
        search_in_layout.setContentsMargins(0,0,0,0)
        self.chk_data_id = QCheckBox("data Id")
        self.chk_resources = QCheckBox("resources")
        self.chk_data_contents = QCheckBox("data-contents")

        search_in_layout.addWidget(self.chk_data_id)
        search_in_layout.addWidget(self.chk_resources)
        search_in_layout.addWidget(self.chk_data_contents)

        # --- Formal options group ---
        options_group = QGroupBox("Options:")
        options_layout = QHBoxLayout(options_group)
        options_layout.setContentsMargins(0,0,0,0)
        self.chk_case_sensitive = QCheckBox("Case sensitive")
        self.chk_whole_word = QCheckBox("Whole word")
        self.chk_regex = QCheckBox("Regular expression")

        options_layout.addWidget(self.chk_case_sensitive)
        options_layout.addWidget(self.chk_whole_word)
        options_layout.addWidget(self.chk_regex)

        # --- Search button ---
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._on_search_clicked)

        # --- Main layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(search_in_group)
        main_layout.addWidget(options_group)
        main_layout.addWidget(self.search_btn)

    def _on_search_clicked(self):
        """Emit search options and close the popup menu."""
        options = {
            "data_id": self.chk_data_id.isChecked(),
            "resources": self.chk_resources.isChecked(),
            "data_contents": self.chk_data_contents.isChecked(),
            "case_sensitive": self.chk_case_sensitive.isChecked(),
            "whole_word": self.chk_whole_word.isChecked(),
            "regex": self.chk_regex.isChecked(),
        }
        self.search_requested.emit(options)

        # Close the parent popup (menu) if it exists
        popup = self.window()
        if isinstance(popup, QMenu):
            popup.close()

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

                # Picker button
                button = QPushButton("🎨")
                button.setProperty('class', 'mini')
                button.setFixedWidth(32)

                # Color preview
                preview = QLabel()
                preview.setFixedSize(34, 34)
                preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #888888;")
                button.clicked.connect(self.make_picker(editor, preview))

                # Add to layout
                grid_layout.addWidget(label, row, order + 0,alignment=Qt.AlignmentFlag.AlignRight)
                grid_layout.addWidget(editor, row, order + 1)
                grid_layout.addWidget(button, row, order + 2)
                grid_layout.addWidget(preview, row, order + 3)
                

                # Description
                desc_label = QLabel(description)
                desc_label.setStyleSheet("color: gray; font-size: 10px;")
                grid_layout.addWidget(desc_label, row, order + 4)

                if order == 0: order = 5
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

app = QApplication(sys.argv)

theme_editor = ThemeEditor()

class CLI:

    def __init__(self):

        ##self.window = Window.AbdhWindow()
        #.window.setContentsMargins(20,20,20,20)
        theme.apply_theme(QApplication.instance(),theme.get_current_theme_name())
        
    # Creates a v panel on the right edge of the mian window
    # This panel is used to settings porpose

    def create_left_pane(self):
        
        left_item = QPushButton('  Theme Editor')
        left_item.setIcon(QIcon(f'{icon_path}palette.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.load_theme_editor(s))
        
        self.load_theme_editor(left_item)

        # Init left pane
        left_item = QPushButton('  Window properties')
        left_item.setIcon(QIcon(f'{icon_path}pencil-ruler.svg'))
        left_item.setCheckable(True)
        left_item.setChecked(False)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _, s= left_item:self.load_window_properties_page(s))
        
        left_item = QPushButton('  Widgets')
        left_item.setIcon(QIcon(f'{icon_path}shapes.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.setup_tabwidgets(s))

        left_item = QPushButton('  Navigation')
        left_item.setIcon(QIcon(f'{icon_path}layout-panel-left.svg'))
        left_item.setCheckable(True)
        left_item.setProperty('class','MenuItem')
        self.window.add_left_panel_item(left_item)
        left_item.clicked.connect(lambda _,s= left_item:self.load_stacked_page(s))

        # stretch end of panel to keep items on top,
        # we can use 'add_left_panel_item' method after 
        # this line to keep required item on bottom
        self.window.left_panel_layout.addStretch(1)

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

        github = QLabel('\n https://github.com/abdhmohammadi/')
        self.window.add_right_panel_item(github)
        github.setProperty('class','hyperlink')          


    def on_theme_switch(self,sender:QComboBox):

        theme_name = sender.currentText()
        theme.apply_theme(QApplication.instance(),theme_name)


    def setup_tabwidgets(self, sender:QPushButton):

        self.uncheck_items(self.window.left_panel_layout)

        if sender: sender.setChecked(True)
        w = QWidget()
        layout = QVBoxLayout(w)
        self.window.add_page(w)
        header_label = QLabel('QTabWidget with customized qss stylesheet')
        header_label.setProperty('class','heading1')
        # set 10 column span as default
        layout.addWidget(header_label)
        # -- Create tab widget --
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        #self.setCentralWidget(self.tabs)
        
        # -- Tab 2: Labels with random colored texts --
        tab2 = QWidget()
        self.setup_tab2(tab2)
        self.tabs.addTab(tab2, "Colors")

        
        # -- Tab 1: Ring progress & controls --
        tab1 = QWidget()
        self.setup_tab1(tab1)
        self.tabs.addTab(tab1, "Customized widgets")       

        # -- Tab 3: Misc interactive widgets --
        tab3 = QWidget()
        self.setup_tab3(tab3)
        self.tabs.addTab(tab3, "Python Widgets")

        self.tabs.setCurrentIndex(0)

    # ---------- Tab 1: Ring progress ----------
    def setup_tab1(self, parent):

        layout = QGridLayout(parent)
        layout.addWidget(QLabel('Animated SearchBox'),0,0)
        # Add whatever you need to the popup menu
        search = SearchBox(expanded_width=260)
        options_panel = SearchOptionsPanel()
        # Connect the panel's signal to your search logic
        def handle_search(options: dict):
            print("Search options:", options)

        options_panel.search_requested.connect(handle_search)
        
        # Attach the panel to the popup
        search.setPopupPanel(options_panel)

        search.popupMenu().addAction("Settings")
        search.popupMenu().addSeparator()
        search.popupMenu().addAction("About")

        layout.addWidget(search,1,0)

        # Start/stop simulation button
        self.timer = QTimer()
        self.timer.timeout.connect(self.increment_progress)

        self.btn_toggle = QPushButton("Start Progress")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.toggled.connect(self.toggle_progress)
        layout.addWidget(self.btn_toggle,0,1)
        
        # Progress bar (standard)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress,1,1)

        # Change ring color button
        btn_color = QPushButton("Random Ring Color")
        btn_color.clicked.connect(lambda: self.ring.setRingColor(
            utils.random_contrasting_hex(QColor("#FFFFFF"), theme="light")))
        
        layout.addWidget(btn_color,0,2)

        self.ring = RingProgress()
        self.ring.setValue(60)
        layout.addWidget(self.ring,1,2,3,1 , alignment=Qt.AlignCenter)

        layout.addWidget(QLabel('Slider:'),2,0)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(60)
        slider.valueChanged.connect(self.ring.setValue)
        layout.addWidget(slider,2,1)

        layout.addWidget(QLabel(),3,0)
        # Keep label in sync        
        layout.setRowStretch(layout.rowCount(),2)

    # ---------- Tab 2: Random colored labels ----------
    def setup_tab2(self, parent: QWidget):
        vlayout = QVBoxLayout(parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        self.color_labels = []
        
        for i in range(15):
            lbl = QLabel()#f"Label {i+1}\ncolor")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)   # center text inside the label
            
            h = random.randint(50, 500)
            lbl.setFixedHeight(h)
            lbl.setFixedWidth(50)
            lbl.setText(str(lbl.height()))
            layout.addWidget(lbl)
            # This is the key line: anchor the widget to the bottom of its layout cell
            layout.setAlignment(lbl, Qt.AlignmentFlag.AlignBottom)
            self.color_labels.append(lbl)

        # Assign initial random colors that contrast with the window background
        #bg = 'auto' #self.tabs.palette().color(self.tabs.backgroundRole()).name()
        self.refresh_label_values()

        vlayout.addLayout(layout)
        vlayout.addWidget(Separator(stroke=3))
        # Button to re-randomize all labels
        btn = QPushButton("Randomize")
        btn.clicked.connect(self.refresh_label_values)
        vlayout.addWidget(btn)
        vlayout.setAlignment(btn, Qt.AlignmentFlag.AlignBottom)  # button also bottom-aligned

    def refresh_label_values(self):
        """Set each label's text color and background to a random contrasting pair."""
        bg = self.tabs.palette().color(self.tabs.backgroundRole()).name()
        for lbl in self.color_labels:
            fg = utils.random_contrasting_hex(bg)          # text color that pops
            bg2 = utils.random_contrasting_hex(fg)         # background that pops on the text
            
            lbl.setFixedHeight(random.randint(50, 500))
            lbl.setStyleSheet(
                f"color: {fg}; background-color: {bg2};"
                "padding: 0px; border-top-left-radius: 4px; border-bottom-left-radius: 0px;border-top-right-radius: 4px; border-bottom-right-radius: 0px; font-weight: bold; font-size: 12px;"
            )

    # ---------- Tab 3: Extra widgets ----------
    def setup_tab3(self, parent):
        layout = QVBoxLayout(parent)

        # Text input with placeholder
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Type something...")
        layout.addWidget(self.line_edit)

        # Combobox
        combo = QComboBox()
        combo.addItems(["Option 1", "Option 2", "Option 3"])
        combo.currentTextChanged.connect(lambda t: print("Selected:", t))
        layout.addWidget(combo)

        # A label that mirrors the line edit content
        self.mirror_label = QLabel()
        self.mirror_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.mirror_label)
        self.line_edit.textChanged.connect(self.mirror_label.setText)

        layout.addStretch()

    def toggle_progress(self, checked):
        if checked:
            self.timer.start(50)   # update every 50 ms
            self.btn_toggle.setText("Stop Progress")
        else:
            self.timer.stop()
            self.btn_toggle.setText("Start Progress")

    def increment_progress(self):
        val = self.progress.value() + 1
        if val > 100:
            val = 0
        self.progress.setValue(val)


    def on_open_package(self):
        
        filepath, _ = QFileDialog.getOpenFileName(None, 'Open package','','Text(*.txt)')
        
        if not filepath: return
        
        with open(filepath, mode='r',encoding='utf-8') as f:  block = f.read()
        
        #styles, content = unpack_block(block)

        #doc_editor.copy_content(content, styles)
            
    def on_save_package(self):
        
        #full_html = doc_editor.getFullHtmlAsync()
        #styles , content = extract_editor_parts(full_html)

        #block = f'<BLOCK>\n{styles}\n<CONTENT>\n{content}\n</CONTENT></BLOCK>'

        #filepath, _ = QFileDialog.getSaveFileName(None, 'Save Package', '','Text(*.txt)')

        #with open(filepath, mode='w',encoding='utf-8') as f: f.write(block)
        pass

    def setGlobalFont(self, fontCombo:QFontComboBox): 
        #doc_editor.applyGlobalValue('font-family',fontCombo.currentFont().family())
        pass
    def create_doc_editor_Toolbar(self, vlayout:QVBoxLayout, editor):
        
        hlayout = QHBoxLayout()
        hlayout.setSpacing(5)

        btn = QPushButton('~bg')
        btn.setProperty('class','mini')
        #btn.setIcon(QIcon(f'{icon_path}sheet.svg'))
        btn.clicked.connect(editor.remove_background)
        hlayout.addWidget(btn)

        btn = QPushButton('bg')
        btn.setProperty('class','mini')
        #btn.setIcon(QIcon(f'{icon_path}sheet.svg'))
        btn.clicked.connect(editor.reset_background)
        hlayout.addWidget(btn)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}folder-open-dot.svg'))
        
        hlayout.addWidget(btn)

        file_menu = QMenu(btn)
        btn.setMenu(file_menu) 
        for name, slot in [('New',self._on_new_doc),
                           ('Save Package', self.on_save_package),
                           ('Open package', self.on_open_package),
                           ("Open File", lambda: editor.LoadFileDialog('Open File','', dialog_type='open')),
                           ("Save File", lambda: editor.LoadFileDialog('Save File','', dialog_type='save')),
                           ("Save Portable HTML", editor.saveAsPortableHtml),
                           ("Extract as Images", editor.extractAsImages)]:
        
            file_menu.addAction(name, slot)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}text-initial.svg'))
        text_menu = QMenu(btn)
        btn.setMenu(text_menu)
        hlayout.addWidget(btn)   

        for name, slot in [
            ("Bold", lambda : editor.applyTextStyle('Bold')), # or editor.setBold(italic: bool)
            ("Italic", lambda: editor.applyTextStyle('Italic')),
            ("Underline", lambda: editor.applyTextStyle('Underline')),
            ("Strike", lambda: editor.applyTextStyle('Strike')),
            ('Text Color', editor.chooseTextColor),
            ('Highlight',editor.chooseBackgroundColor)
        ]:
            text_menu.addAction(name, slot)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}sigma.svg'))
        btn.clicked.connect(editor.insertMathDialog)
        hlayout.addWidget(btn)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}sheet.svg'))
        btn.clicked.connect(editor.insertTableDialog)
        hlayout.addWidget(btn)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}image-plus.svg'))
        btn.clicked.connect(editor.insertImage)
        hlayout.addWidget(btn)
       
        for align in ("left", "center", "right", "justify"):
            btn = QPushButton()
            btn.setProperty('class','mini')
            btn.setIcon(QIcon(f'{icon_path}{align}.svg'))
            # Use *args to swallow any arguments the signal sends
            btn.clicked.connect(lambda *args, a=align: editor.setAlignment(a))

            hlayout.addWidget(btn)
                
        btn = QPushButton()
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}pilcrow-left.svg'))
        # Use *args to swallow any arguments the signal sends
        btn.clicked.connect(lambda : editor.setParagraphDirection(True))

        hlayout.addWidget(btn)
        
        btn = QPushButton()
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}pilcrow-right.svg'))
        # Use *args to swallow any arguments the signal sends
        btn.clicked.connect(lambda : editor.setParagraphDirection(False))

        hlayout.addWidget(btn)

        btn = QPushButton()
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}square-dashed.svg'))

        btn.clicked.connect(editor.showMarginDialog)
        hlayout.addWidget(btn)

        # Zoom Out
        btn = QPushButton("-/+")
        btn.setProperty('class','mini')
        menu = QMenu(btn)
        btn.setMenu(menu)
        #zoom_out_action.clicked.connect(editor.zoomOut)
        hlayout.addWidget(btn)

        menu.addAction('Zoom In',editor.zoomIn)
        menu.addAction('Zoom Out', editor.zoomOut)
        menu.addAction('Fit',editor.fitPage)
        # Zoom percentage combo
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setFixedWidth(80)
        self.zoom_combo.currentTextChanged.connect(editor.on_zoom_changed)
        hlayout.addWidget(self.zoom_combo)

        fontCombo = QFontComboBox()
        fontCombo.setFixedWidth(100)
        fontCombo.setFontFilters(QFontComboBox.FontFilter.ScalableFonts)
        fontCombo.currentFontChanged.connect(lambda f: editor.setFontFamily(f.family()))
        hlayout.addWidget(fontCombo)
        
        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}file-text.svg'))

        page_menu = QMenu(btn)
        btn.setMenu(page_menu) 
        
        for name, slot in [('Apply Font', lambda f=fontCombo: self.setGlobalFont(f)),
                           ('Right direction', lambda: editor.applyGlobalValue('dir', 'rtl', False, False)),
                           ('Left direction', lambda: editor.applyGlobalValue('dir', 'ltr', False, False)),
                           ('ReadOnly', lambda: editor.applyGlobalValue("contenteditable", "false", False, False)),
                           ('Editable', lambda: editor.applyGlobalValue("contenteditable", "true", False, False)),
                           ('Lock document', lambda: editor.lock_document(True)),
                           ('Unlock document', lambda: editor.lock_document(False))]:
            
            page_menu.addAction(name, slot)
        
        hlayout.addWidget(btn)

        
        font_sz_edit = QLineEdit('12')

        font_sz_edit.setFixedWidth(40)
        font_sz_edit.textEdited.connect(lambda sz=font_sz_edit: editor.setFontSize(sz))
        hlayout.addWidget(font_sz_edit)        
        
        vlayout.addLayout(hlayout)
        self.pageCombo = QComboBox()
        self.pageCombo.setFixedWidth(100)
        self.pageCombo.addItems(["A4", "Letter", "B5", "Edu-Item"])
        self.pageCombo.currentTextChanged.connect(editor.setPageSize)
        hlayout.addWidget(self.pageCombo)


        hlayout.addStretch(1)
        #hlayout.addWidget(SearchBox())

    def load_theme_editor(self, sender:QPushButton):

        self.uncheck_items(self.window.left_panel_layout)
        
        sender.setChecked(True)
        
        if not os.path.exists(theme.color_rules):
            QMessageBox.warning(self.window,'Error','Color rules not found')
            return 
            
        self.window.add_page(theme_editor)


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
        
        #settings_list = [('family',selected_text),('size',12)]
        # Create a dictionary with the list elements as key-value pairs under 'connection'
        #settings = {"font": dict(settings_list)}
        #settings_manager.write(settings)

        #self.app.setStyleSheet(st.stylesheet)


    def Run(self):

        # Create the main customized UI window
        self.window = Window.AbdhWindow()

        self.window.initUI(app_title= 'PySideAbdhUI - Widgets navigatior', direction= Qt.LayoutDirection.LeftToRight)
            
        self.create_settings_pane()
        self.create_left_pane()


        self.window.show()
        
        PopupNotifier.Notify(self.window,"Wellcome!", "📚 PySideAbdhUI is ready.", 'bottom-right')#, 
    
        sys.exit(app.exec())

cli = CLI()

cli.Run()

# INSTALL wheel:
# Run to BIULD: python setup.py sdist bdist_wheel

# RUN to INSTALL: cd 'F:\Projects\Python\Teaching-assistant-project\TeacherAssistant'; .\env\Scripts\python.exe -m pip install 'F:\Projects\Python\PySideAbdhUI\dist\PySideAbdhUI-1.7.4.11-py3-none-any.whl'
