from pathlib import Path
import sys
import os

from PySide6.QtWidgets import (QApplication, QComboBox, QFontComboBox, QHBoxLayout, QLabel, 
                               QMenu, QPushButton, QVBoxLayout, QWidget)
from PySide6.QtGui import QFont, QIcon, QKeySequence, Qt


#print(str(Path(__file__).resolve().parent.parent))
# Add the parent package directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from editor.src.PySideAbdhUI.Editor.editor import Editor
from editor.src.PySideAbdhUI.Editor.core.document import Document
from editor.src.PySideAbdhUI.Editor.core.paragraph import Paragraph
from editor.src.PySideAbdhUI.Editor import (__version__ as editor_version, 
                                            __document_version__ as document_version,
                                            find_katex_version)

from widgets.src.PySideAbdhUI.Widgets import Window
from widgets.src.PySideAbdhUI.Widgets.Notify import PopupNotifier
from widgets.src.PySideAbdhUI.Widgets.Widgets import SearchBox
from widgets.src.PySideAbdhUI.Widgets import __version__ as ui_version



def setup_test_document():

    doc = Document()

    # ---------------------------------------------------------
    # 80 paragraphs
    # ---------------------------------------------------------

    lorem = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ")

    for i in range(2):

        html = f"""<p><b>Paragraph {i+1}</b><br>{lorem * 4}</p>"""

        doc.append(Paragraph(html=html))

    #doc.append(Image(src="C:/Users/AbdhM/Pictures/Screenshots/Screenshot 2026-06-30 180229.png", width="400"))

    return doc

b0 = [
    "<div class=\"block\" data-id=\"9a939fab3d1645b5bd7705448dc7800b\" data-type=\"Paragraph\">\n        <p dir=\"rtl\"><font face=\"Vazirmatn FD\">فرض کنید تابع خطی f از نقطه&nbsp;</font><span class=\"math-inline\" data-math-id=\"ff35fc206bfc4c6ba98cbc1863246ac3\" title=\"db-click to edit\" data-formula=\"(1,2)\" contenteditable=\"false\" dir=\"ltr\"><span dir=\"ltr\" contenteditable=\"false\" title=\"Double click to Edit\"><span class=\"katex\"><span class=\"katex-mathml\"><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><semantics><mrow><mo stretchy=\"false\">(</mo><mn>1</mn><mo separator=\"true\">,</mo><mn>2</mn><mo stretchy=\"false\">)</mo></mrow><annotation encoding=\"application/x-tex\">(1,2)</annotation></semantics></math></span><span class=\"katex-html\" aria-hidden=\"true\"><span class=\"base\"><span class=\"strut\" style=\"height: 1em; vertical-align: -0.25em;\"></span><span class=\"mopen\">(</span><span class=\"mord\">1</span><span class=\"mpunct\">,</span><span class=\"mspace\" style=\"margin-right: 0.1667em;\"></span><span class=\"mord\">2</span><span class=\"mclose\">)</span></span></span></span></span></span><font face=\"Vazirmatn FD\"> بگذرد و محور عمودی را در نقطه&nbsp;</font><span class=\"math-inline\" data-math-id=\"bf67628528684d9fb486495cfa5c49fa\" title=\"db-click to edit\" data-formula=\"-1\" contenteditable=\"false\" dir=\"ltr\"><span dir=\"ltr\" contenteditable=\"false\" title=\"Double click to Edit\"><span class=\"katex\"><span class=\"katex-mathml\"><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><semantics><mrow><mo>−</mo><mn>1</mn></mrow><annotation encoding=\"application/x-tex\">-1</annotation></semantics></math></span><span class=\"katex-html\" aria-hidden=\"true\"><span class=\"base\"><span class=\"strut\" style=\"height: 0.7278em; vertical-align: -0.0833em;\"></span><span class=\"mord\">−</span><span class=\"mord\">1</span></span></span></span></span></span><font face=\"Vazirmatn FD\"> قطع کند:</font></p><p dir=\"rtl\"></p><ul><li dir=\"rtl\" style=\"text-align: right; \"><font face=\"Vazirmatn FD\">الف) نمودار آن را رسم کنید.</font></li><li dir=\"rtl\" style=\"text-align: right; \"><font face=\"Vazirmatn FD\">ب&nbsp; ) ضابطه\u200cی تابع را بدست آورید</font>.</li></ul><p dir=\"rtl\"></p>\n        </div>"
  ]

def setup__list():

    global_actions = """
        <div class="global-actions">
            <button id="selectAll" contenteditable="false">Select All</button>
            <button id="showAllAnswers" contenteditable="false">Show All Answers</button>
            <div class="status-text" id="selectionStatus" contenteditable="false">#QUESTIONS#</div>
        </div>"""

    block_actions = """
        <div class="actions">
            <div class="block-meta">#HEADER#</div>
            <input type="checkbox" class="select-cb" title="Select this question">
            
            <button class="toggle-btn" type="button" contenteditable="false">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M6 9l6 6 6-6"/>
                </svg>
            </button>
        </div>"""

    custom_css = """
        .block-meta
        {
            opacity: 0.5; 
            margin:18px 20px 0px 20px; 
            font-size:8pt; 
            align-self:baseline;
        }
        .global-actions 
        {
            display:flex; 
            gap:10px; 
            padding:10px; 
            margin-bottom: 32px;
            border-bottom: 2px solid #4f46e5;
            box-shadow:0 4px 12px rgba(0,0,0,0.06);
            user-select: none;
        }
        .global-actions button 
        {
            font-weight:600;
            padding:10px 18px;
            border:none; 
            background:#003d66;
            border-radius: 100px;
            width:200px;
            cursor:pointer; 
            color:whitesmoke;
        }
        .status-text 
        { 
            margin: auto 10px auto auto;
            font-size:0.9rem; 
            color:#64748b; 
            text-align:center; 
            font-style: italic;
        }
        
        .toggle-btn 
        {
            margin: 5px;
            opacity: 0.40;
            background-color: transparent;
            border:none;
            cursor:pointer;
            user-select:none;
        }
        .select-cb 
        {
            width:14px; 
            height:14px; 
            margin: 15px;
            cursor:pointer; 
            accent-color:#4f46e5; 
            justify-self: center;
            margin-inline-start: auto;
        }
        .actions
        {
            direction: inherit;
            display: flex;
            justify-self: stretch; 
            justify-content:end;
            vertical-align: bottom;
            margin-top: 0px;
            margin-bottom: 0px;
            padding-bottom: 0px;
            border-bottom:1px #1717165c solid;
            align-items: flex-end;
        }
        .no-answer
        {
            margin-top:0px;
            padding-top:0px;
            text-transform: uppercase;
            text-decoration: underline; 
            opacity: 0.40; text-align: center;
            font-size:18pt;
            font-weight:600;
        }
    """

    custom_script = """
        var statusText = null;
        var select_all = false;
        var show_all_answers = false;
        const all_questions = 0; 
        function updateSelectionStatus() 
        {
            const selected = document.querySelectorAll(".select-cb:checked").length;

            statusText.textContent = `${selected} question${selected === 1 ? "" : "s"} selected of ${all_questions}`;
        }
        function setSelected(checkbox, selected) 
        {
            const actions = checkbox.closest(".actions");
            const question = actions.previousElementSibling.querySelector(".block");
            const answer = actions.nextElementSibling.querySelector(".block");
            
            checkbox.checked = selected;

            const value = selected ? "true" : "false";

            question.setAttribute("question-selected", value);
            answer.setAttribute("answer-selected", value);
        }
function openAnswer(answer)
{
    if (answer.dataset.open === "true")
        return;

    answer.dataset.open = "true";

    // Start from current height (0 when closed)
    answer.style.height = answer.offsetHeight + "px";

    requestAnimationFrame(() =>
    {
        answer.style.height = answer.scrollHeight + "px";
    });

    answer.addEventListener("transitionend", function handler(e)
    {
        if (e.propertyName !== "height") return;

        answer.style.height = "auto";
        answer.removeEventListener("transitionend", handler);
    });
}

function closeAnswer(answer)
{
    if (answer.dataset.open === "false")
        return;

    answer.dataset.open = "false";

    // If currently auto, freeze its current height first
    answer.style.height = answer.scrollHeight + "px";

    requestAnimationFrame(() =>
    {
        answer.style.height = "0px";
    });
}
        
        document.addEventListener("DOMContentLoaded", () => 
        {
            statusText = document.getElementById("selectionStatus");
            
            document.getElementById("selectAll").addEventListener("click", () => {

                document.querySelectorAll(".select-cb").forEach(cb => 
                {
                    setSelected(cb, !select_all);
                });
                select_all = !select_all;
                document.getElementById("selectAll").textContent = !select_all? "Select all" : "Clear all" ;
                updateSelectionStatus();

            });
 document.getElementById("showAllAnswers").addEventListener("click", () =>
{
    document.querySelectorAll(".actions").forEach(actions =>
{
    const answer = actions.nextElementSibling.querySelector(".block");

    if (!answer) return;

    if (!show_all_answers)
        openAnswer(answer);
    else
        closeAnswer(answer);
});

    show_all_answers = !show_all_answers;
    document.getElementById("showAllAnswers").textContent = show_all_answers ? "Hide answers" : "Show all answers";

});
            /*          
            document.getElementById("showAllAnswers").addEventListener("click", () => {

               document.querySelectorAll(".actions").forEach(actions => 
                {
                
                    if(!show_all_answers)
                    {
                        openAnswer(actions.nextElementSibling);
                    }
                    else
                    {
                        closeAnswer(actions.nextElementSibling);
                    }
                });
                show_all_answers = !show_all_answers;

            });
*/
            // -----------------------------
            // Initialize every quiz item
            // -----------------------------
            document.querySelectorAll(".actions").forEach(actions => {

                const question = actions.previousElementSibling.querySelector(".block");
                const answer = actions.nextElementSibling.querySelector(".block");

                const checkbox = actions.querySelector(".select-cb");
                const toggle = actions.querySelector(".toggle-btn");

                if (!question || !answer || !checkbox || !toggle)  return;

                // Initial attributes
                question.setAttribute("question-selected", "false");
                answer.setAttribute("answer-selected", "false");
                answer.dataset.open = "false";

                // Prepare animation
                answer.style.overflow = "hidden";
                answer.style.height = "0px";
                answer.style.transition = "height 300ms ease";

                // -----------------------------
                // Checkbox
                // -----------------------------
                checkbox.addEventListener("change", () => {

                    const value = checkbox.checked ? "true" : "false";

                    question.setAttribute("question-selected", value);
                    answer.setAttribute("answer-selected", value);

                    updateSelectionStatus();

                });

                // -----------------------------
                // Toggle Answer
                // -----------------------------
                toggle.addEventListener("click", () => {

                    if (answer.dataset.open === "true") closeAnswer(answer);
                    else openAnswer(answer);

                });
            });

        });
        """

    b1 = """
        <!-- Group 1 of child elements -->
        <!-- Child 1 -->
        <div class="block" data-type="Paragraph">
            <p>Content of the Question 1</p>
        </div>
        <!-- Child 2 -->
        <div class="block" data-type="Paragraph">
            <p>Content contiues ...</p>
        </div>
        <!-- Continue childs -->
            <!-- Child N -->
        <div class="block" data-type="Paragraph">
            <p>Last block</p>
        </div>
        <!-- End of group 1 -->
        """
    
    ans1 = """
        <!-- Group 2 of child elements -->
        <!-- Child 1 -->
        <div class="block" data-type="Paragraph">
            <p>First Answer for question 1</p>
        </div>
        <!-- Child 2 -->
        <div class="block" data-type="Paragraph">
            <p>Second answer for quesion 1</p>
        </div>
        <!-- Continue childs -->
            <!-- Child M -->
        <div class="block" data-type="Paragraph">
            <p>Last block</p>
        </div>
        """
    
    b2 ="""
        <!-- Group 1 of child elements -->
        <!-- Child 1 -->
        <div class="block" data-type="Paragraph">
            <p>Content of the Question 1</p>
        </div>
        <!-- Child 2 -->
        <div class="block" data-type="Paragraph">
            <p>Content contiues ...</p>
        </div>
        <!-- Continue childs -->
            <!-- Child N -->
        <div class="block" data-type="Paragraph">
            <p>Last block</p>
        </div>
        <!-- End of group 1 -->
        """
    
    ans2 ="""  
        <!-- Group 2 of child elements -->
        <!-- Child 1 -->
        <div class="block" data-type="Paragraph">
            <p>Content of the Answer for question 1</p>
        </div>
        <!-- Child 2 -->
        <div class="block" data-type="Paragraph">
            <p>Content contiues ...</p>
        </div>
        <!-- Continue childs -->
            <!-- Child M -->
        <div class="block" data-type="Paragraph">
            <p>Last block</p>
        </div>
        """
    
    b3="""
        <!-- Group 1 of child elements -->
        <!-- Child 1 -->
        <div class="block" data-type="Paragraph">
            <p>Content of the Question 1</p>
        </div>
        <!-- Child 2 -->
        <div class="block" data-type="Paragraph">
            <p>Content contiues ...</p>
        </div>
        <!-- Continue childs -->
            <!-- Child N -->
        <div class="block" data-type="Paragraph">
            <p>Last block</p>
        </div>
        <!-- End of group 1 -->
        """
    
    ans3 ="""
        <!-- Group 2 of child elements -->
        <!-- Child 1 -->
        <div class="block" data-type="Paragraph">
            <p>Content of the Answer for question 1</p>
        </div>
        <!-- Child 2 -->
        <div class="block" data-type="Paragraph">
            <p>Content contiues ...</p>
        </div>
        <!-- Continue childs -->
            <!-- Child M -->
        <div class="block" data-type="Paragraph">
            <p>Last block</p>
        </div>
    """
    
    blocks =[global_actions]

    qs = [(b1,ans1),(b2,ans2),(b3,ans3),(b1,ans1),(b2,ans2),(b3,ans3),(b1,ans1),(b2,ans2),(b3,ans3), (b1,ans1),(b2,ans2),(b3,ans3), (b1,ans1),(b2,ans2),(b3,ans3)]
    
    for q,ans in qs:

        block = f"<section>{q}</section>{block_actions}<section>{ans}</sction>"
        
        blocks.append(block)

    return blocks, custom_css, custom_script

icon_path ='F:\\Projects\\Python\\icons\\svg\\'

class EditorWindow(Window.AbdhWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Editor")
        self.add_right_panel_item(QLabel(f'UI Version: {ui_version}\n' \
                                         f'Editor Version: {editor_version}\n' \
                                         f'Document Version: {document_version}\n' \
                                         f"Math Engine: KaTeX {find_katex_version()} MIT"),True)
        
        gitgub_page = 'https://abdhmohammadi.github.io'
        ui_repo     = 'https://github.com/abdhmohammadi/pysydeabdhui/editor'

        github = QLabel(f'<a href="{gitgub_page}">Home page</a><br>' \
                        f'<a href="{ui_repo}">GitHub for UI</a>', 
                        openExternalLinks=True, 
                        textInteractionFlags= Qt.TextInteractionFlag.LinksAccessibleByMouse)
        
        github.setProperty('class','hyperlink')

        self.add_right_panel_item(github,True)

        katex_updates_label = QLabel('<a href="https://github.com/KaTeX/KaTeX/releases">KaTeX Updates</a>')      
        katex_updates_label.setTextFormat(Qt.TextFormat.RichText)
        katex_updates_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        katex_updates_label.setOpenExternalLinks(True)
        self.add_right_panel_item(katex_updates_label,True)
        central = QWidget()
        vlayout = QVBoxLayout(central)
        self.add_page(central)

        # Create the editor.
        self.editor = Editor(self)

        self.create_doc_editor_Toolbar(vlayout,self.editor)
        vlayout.addWidget(self.editor)

    def on_load_string(self):
        # Has the error
        # js: Uncaught TypeError: Cannot read properties of null (reading 'addEventListener')
        blocks, css, script = setup__list()
        html_string = f'<head>\n<style>{css}</style>\n<script>{script}</script></head><body>\n{"\n".join(blocks)}</body>'
        self.editor.load_html_string(html_string= html_string, 
                                     allow_scripts=True, 
                                     preserve_block_class=True)

    def on_load_blocks(self):
        blocks, css, script = setup__list()
        self.editor.load_blocks(blocks,
                                custom_css=css, custom_scripts= script, 
                                allow_scripts=True, preserve_block_class= True)
    
    def print_document(self):
        # Default: ONE QPrintPreviewDialog, no Microsoft dialog
        self.editor.print_document(callback=lambda ok: print("printed" if ok else "cancelled"))

    def create_doc_editor_Toolbar(self, vlayout:QVBoxLayout, editor:Editor):
        
        hlayout = QHBoxLayout()
        hlayout.setSpacing(1)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}menu.svg'))
        
        hlayout.addWidget(btn)

        file_menu = QMenu(btn)
        btn.setMenu(file_menu) 
        for name, slot,key in [
                            ('New', editor.clear_document, QKeySequence.StandardKey.New),
                            ("Open HTML File",lambda: self.editor.load_html_file(allow_scripts=True), QKeySequence.StandardKey.Open),
                            ("Open Text File", self.editor.open_text_file,""),
                            ("Save HTML File", self.editor.save_html_file, QKeySequence.StandardKey.Save),
                            ('Save as PDF', self.editor.save_pdf_async,""),
                            ("Export as image", editor.export_as_images, ""),
                            ("Print ...", self.print_document, "Ctrl+P"),
                            ("Load Blocks", self.on_load_blocks, ""),
                            ("Load string", self.on_load_string,""),
                            ]:
        
            file_menu.addAction(name, slot,key)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}image-plus.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Insert image')
        btn.clicked.connect(self.editor.insert_image)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}sheet.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Insert Table')
        btn.clicked.connect(self.editor.insert_table)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}sigma.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Insert formula')
        btn.clicked.connect(self.editor.insert_formula)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}bold.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Bold')
        btn.clicked.connect(self.editor.format_bold)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}italic.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Italic')
        btn.clicked.connect(self.editor.format_italic)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}underline.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Underline')
        btn.clicked.connect(self.editor.format_underline)
        hlayout.addWidget(btn)

        
        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}highlighter.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Highlight')
        btn.clicked.connect(self.editor.pick_highlight_color)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}text-color.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Text color')
        btn.clicked.connect(self.editor.pick_text_color)
        hlayout.addWidget(btn)

        btn = QPushButton('')
        btn.setProperty('class','mini')
        btn.setIcon(QIcon(f'{icon_path}text-initial.svg'))
        text_menu = QMenu(btn)
        btn.setMenu(text_menu)
        hlayout.addWidget(btn)   
        
        for name, slot in [
            ("Strikethrough", self.editor.format_strikethrough),
            ("Superscript ", self.editor.format_superscript),
            ("Subscript", self.editor.format_subscript),
            ("Indent", self.editor.format_indent),
            ("Outdent", self.editor.format_outdent)
        ]:
            text_menu.addAction(name, slot)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}text-left.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Align left')
        btn.clicked.connect(self.editor.format_align_left)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}text-center.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Align center')
        btn.clicked.connect(self.editor.format_align_center)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}text-right.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Align right')
        btn.clicked.connect(self.editor.format_align_right)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}text-justify.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Justify')
        btn.clicked.connect(self.editor.format_align_justify)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}bullets.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Unordered list(creates bullets)')
        btn.clicked.connect(self.editor.format_unordered_list)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}list-ordered.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Ordered list(numbered)')
        btn.clicked.connect(self.editor.format_ordered_list)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}ltr.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Left to Right text direction')
        btn.clicked.connect(lambda: self.editor.set_page_direction("ltr"))
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}rtl.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Right to Left text direction')
        btn.clicked.connect(lambda: self.editor.set_page_direction('rtl'))
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}line-spacing.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Line and paragraph spacing')
        mnu = QMenu(btn)
        btn.setMenu(mnu)
        spaces = [0.25 * i for i in range(1,13)]
        for i in spaces:
            mnu.addAction(str(i), lambda: self.editor.format_line_height(str(i)))

        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}leter-spacing.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Leter spacing')
        mnu = QMenu(btn)
        btn.setMenu(mnu)
        spaces = [round(0.1 * i,1) for i in range(1,11)]
        for i in spaces:
            mnu.addAction(str(i), lambda: self.editor.format_letter_spacing(f'{i}px'))

        hlayout.addWidget(btn)
        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}scan.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('change page margin')
        btn.clicked.connect(self.editor.showMarginDialog)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}paintbrush.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('change background color')
        btn.clicked.connect(self.editor.pick_background_color)
        hlayout.addWidget(btn)

        btn = QPushButton("")
        btn.setIcon(QIcon(f'{icon_path}page-break.svg'))
        btn.setProperty('class', 'mini')
        btn.setToolTip('Toggle page-break/continuos')
        btn.clicked.connect(self.editor.switch_page_mode)
        hlayout.addWidget(btn)

        # Font size dropdown
        font_size = QComboBox()
        font_size.setToolTip("Font size")
        font_size.addItems(["8","9","10","11","12","14","16","18","20","22","24","26","28","30","36","48","72"])
        font_size.setCurrentText("12")
        font_size.currentTextChanged.connect(lambda v: self.editor.format_font_size(v))
        hlayout.addWidget(font_size)

        fontCombo = QFontComboBox()
        fontCombo.setFixedWidth(100)
        fontCombo.setFontFilters(QFontComboBox.FontFilter.AllFonts)
        fontCombo.setCurrentFont(QFont("Arial",12))  # default font
        fontCombo.setToolTip('System installed fonts')
        fontCombo.currentFontChanged.connect(lambda f: self.editor.format_font_family(f.family()))
        hlayout.addWidget(fontCombo)
        """
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

        self.pageCombo = QComboBox()
        self.pageCombo.setFixedWidth(100)
        self.pageCombo.addItems(["A4", "Letter", "B5", "Edu-Item"])
        self.pageCombo.currentTextChanged.connect(editor.setPageSize)
        hlayout.addWidget(self.pageCombo)
"""
        vlayout.addLayout(hlayout)
        hlayout.addStretch(1)
        hlayout.addWidget(SearchBox())
        btn = QPushButton("")
        btn.setIcon(QIcon(f"{icon_path}lightbulb.svg"))
        btn.setProperty('class', 'mini')
        btn.setToolTip('LaTeX typing help')
        btn.clicked.connect(lambda _, sender=btn: self.open_LaTeX_helpe_popup(sender))
        hlayout.addWidget(btn)
 
    def on_open_file(self):
        self.editor.load_html_file(allow_scripts=True, preserve_block_class=True)

    def open_LaTeX_helpe_popup(self, sender:QPushButton):

        hlp = os.path.join('F:\\Projects\\Python\\PySideAbdhUI\\PySideAbdhUI\\Editor\\resources\\KaTeX', 'LaTeX-Typing.html')
        
        if  not os.path.exists(hlp):
            PopupNotifier.Notify(self,'', "LaTeX typeing help has not installed.")
            return

        #with open(hlp, 'r',encoding='utf-8') as f: html = f.read()
        widget = QWidget(sender)
        widget.setMinimumWidth(800)
        vl = QVBoxLayout(widget)
        vl.setContentsMargins(1,1,1,1)
        widget.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        view = Editor()
        #view.setMaximumWidth(800)
        view.open_html_file(hlp, True)

        vl.addWidget(view)

        r = sender.rect()
        p = r.bottomLeft()
        p.setX(p.x() - view.width())
        point = sender.mapToGlobal(p)
        widget.move(point)
        widget.show()


if __name__ == "__main__":
    """Entry point for the ``abdh-editor`` GUI script."""

    app = QApplication(sys.argv)

    window = EditorWindow()
    window.show()
    sys.exit(app.exec())
