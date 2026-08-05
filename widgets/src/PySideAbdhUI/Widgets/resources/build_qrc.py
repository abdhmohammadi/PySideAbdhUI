# How to congig, compile and use icons?
# 1. Specify icons to use, in the following I set it by "ICON_FILE_NAMES"
#    this list is only name and extension of icons, next determine location 
#    of these icons in the directory of "ICON_FOLDER".
# 2. Build QRC file: it is a xml file format.
#    following code generates my QRC file. I named the output as "icons.qrc".
#    this file has been created in "QRC_FILE_OUTPUT"
# 3. COMPILE QRC RESOURCES ( in my task this is icons.qrc), the complile operation
#    generates *.py file, this is the reference to icons and is used by "import"
#    keyword, this reference must imported one time befer any usage of the icons
#    the best loaction to import is __init__.py, main.py and similar entry points.
#    the rcc.exe is used to compile the qrc file, it has to run:
#    CONSOLE>> rcc.exe --generator python path-to \icons.qrc -o path-to-output\icons_rc.py
#    In my project I need to run: F:\Projects\Python\PySideAbdhUI\env\Lib\site-packages\PySide6\rcc.exe --generator python F:\Projects\Python\PySideAbdhUI\widgets\src\PySideAbdhUI\Widgets\resources\icons_rc.qrc -o F:\Projects\Python\PySideAbdhUI\widgets\src\PySideAbdhUI\Widgets\resources\icons_rc.py
# 4. Ready to use: go to entry poit of the project and import icons_rc.py


import os

# Configuration
ICON_FOLDER = "F:\\Projects\\Python\\icons\\svg"  # folder to scan
QRC_FILE_OUTPUT = "F:\\Projects\\Python\\PySideAbdhUI\\widgets\\src\\PySideAbdhUI\\Widgets\\resources\\icons_rc.qrc"  # output QRC file
PREFIX = "/icons"  # resource prefix in Qt

# pair of file name and extention,
# extention is used as parent folder name too.
ICON_FILE_NAMES =[
     ("check","svg"),
             ("chevron-down","svg"),
             ("chevron-up","svg"),
             ("arrow-left","svg"),
             ("arrow-right","svg"),
             ("double-square","svg"),
             ("menu","svg"),
             ("minus","svg"),
             ("pin","svg"),
             ("search","svg"),
             ("settings","svg"),
             ("square","svg"),
             ("x","svg"),
             ("v-ellipsis","svg")
             ]
# Supported extensions
def scan_folder():
    """Recursively scan folder for supported files."""
    files = []
        
    for pair in ICON_FILE_NAMES:
        name = pair[0]+"."+pair[1]
        # store relative path for QRC
        root = ICON_FOLDER + "\\"
        rel_path = os.path.relpath(os.path.join(root, name), os.path.dirname(QRC_FILE_OUTPUT))
        files.append(rel_path.replace("\\", "/"))  # use forward slashes for QRC
    
    return files

def create_qrc(files, prefix, output_file):
    """Create a .qrc XML file from a list of files."""
    elements =""
    for f in files:
        name = str(f).split("/").pop()

        # SAMPLE: <file alias="check.svg">../../../../../../icons/svg/check.svg</file>
        s = f"\t\t<file alias=\"{name}\">{f}</file>\n"
        elements = elements + s
        
    rcc = f"<?xml version=\"1.0\" ?>\n<RCC>\n\t<qresource prefix=\"{prefix}\">\n{elements}\n\t</qresource>\n</RCC>" 


    with open(output_file, "w", encoding="utf-8") as f: f.write(rcc)

    print(f"\n\n\nQRC file generated: {output_file}\n\nNext step: compile it using rcc.exe\n\n")

if __name__ == "__main__":

    files = scan_folder()

    create_qrc(files, PREFIX, QRC_FILE_OUTPUT)
