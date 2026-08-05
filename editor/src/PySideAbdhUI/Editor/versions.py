# Editor.versions.py

# #########################################################################################
# HOW TO BUILD:
# From package root F:\Projects\Python\PySideAbdhUI
# Run from console>> python -m build --no-isolation .\editor
#
# HOW TO INSTALL:
#
# Editable install(for development)
# python -m pip install -e .\editor
# distribute on host apps: In your host app run:
# Run from console>> pip install 'F:\Projects\Python\PySideAbdhUI\editor\dist\pysideabdhui_editor-0.5.2-py3-none-any.whl'
# HOW TO REMOVE:
# In your host app run:
# Run from console>> pip uninstall PysideAbdhUI.Editor
# #########################################################################################

__version__ = "0.5.2"              # Verion of the package
__document_version__ = "0.1.2"     # Version of the html document structure(base.html)

from pathlib import Path
import re

def find_katex_version():
    resource = Path(__file__).resolve().parent / "resources"
    
    text = (resource / "katex/katex.min.js").read_text(encoding="utf-8", errors="ignore")
                                       
    patterns = [r'\bversion\b\s*:\s*["\']([^"\']+)["\']',                         #  version:"0.16.9" 
                r'["\']version["\']\s*:\s*["\']([^"\']+)["\']',                   # "version":"0.16.9" or 'version':'0.16.9'
                r'\bversion\b\s*[:=]\s*`([^`]+)`',                                #  version=`0.16.9`
                r'\bversion\b\s*[:=]\s*([0-9]+(?:\.[0-9]+)+(?:[-A-Za-z0-9.]*)?)', #  version=0.16.9 (unquoted)
               ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        
        if m: return m.group(1) if m else "Not avilable"
    
    return "Not avilable"
