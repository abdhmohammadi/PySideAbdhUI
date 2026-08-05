"""
Utility functions for PySideAbdhUI.
"""

# ========================================================================
# Resource Handling Utility
# ========================================================================
# This function can be used to access packaged resources like SVGs and QSS files
# regardless of where the package is installed.
#
# It first attempts to use importlib.resources (available in Python 3.7+),
# and, if needed, falls back to pkg_resources.
#
# Usage Example:
#
#     from PySideAbdhUI import get_resource_path
#     icon_path = get_resource_path("PySideAbdhUI.resources.icons.svg", "myicon.svg")
#     print(icon_path)
#
# Adjust the package path argument according to where your resources are
# located inside the package.
import random
import re
import json
import importlib.resources
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, Qt
_PARENT_PACKAGE_ = "PySideAbdhUI.Widgets"
def get_resource_path(package: str, resource: str, ext ='') -> Path:
    """
    Retrieve the full path to the specified resource located within the given package.
    
    Args:
        package (str): The package relative to which the resource is located.
                       For example: "PySideAbdhUI.resources.icons.svg" or
                       "PySideAbdhUI.resources.styles".
        resource (str): The filename of the resource (e.g., "icon.svg" or "style.qss").
    
    Returns:
        Path: The full filesystem path to the resource.
    
    Raises:
        RuntimeError: If the resource cannot be located.
    """
    # Try to use importlib.resources (Python 3.7+)
    try:
        if not ext or ext =='':
            segments = package.split('.')
            ext = segments[len(segments)-1]

        with importlib.resources.path(f'{_PARENT_PACKAGE_}.{package}', f'{resource}.{ext}') as res_path:
            return res_path
        
    except Exception as e:
    
        raise RuntimeError(f"Unable to locate the resource '{resource}' in package '{package}'.") from e

def get_icon(name:str, package:str='resources.icons.svg', ext = 'svg'):
    
    return get_resource_path(package, name,ext).as_posix()

def get_styles_template(package:str='resources.styles'):
    
    return get_resource_path(package,'qss-template','qss').as_posix()

def get_color_palettes(package:str='resources.styles'):
    
    return get_resource_path(package, 'color-palettes','json').as_posix()



class ThemeManager:
    
    def __init__(self):
        
        color_rules = get_color_palettes()
        template =  get_styles_template()
        # color-rules.json
        # Path: json file for color pallete of the theme
        self.color_rules = color_rules

        self.template_path = template

        self.data = self.load()

    def load(self):
        with open(self.color_rules, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            return data

        # If color-palletes.json not found.   
        return {"active-theme": "", "themes": {}}

    def save(self):
        with open(self.color_rules, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)
            f.close()

    def get_current_theme_name(self): return self.data.get("active-theme", "")
    
    def get_current_font(self)->tuple:
        ff = self.data.get("font-family")
        sz = self.data.get("font-size")
    
        return(ff or "system",sz or 12)
    
    def set_direction(self, direction:Qt.LayoutDirection= Qt.LayoutDirection.LeftToRight):
        self.data['direction'] = 'ltr' if direction == Qt.LayoutDirection.LeftToRight else 'rtl'
        self.save()

    def get_direction(self)->Qt.LayoutDirection:
        
        if self.data.get('direction') == "ltr":
            return Qt.LayoutDirection.LeftToRight
        
        return Qt.LayoutDirection.RightToLeft
    
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

    def get_all_themes(self): return list(self.data.get("themes", {}).keys())

    def apply_theme(self,app: QApplication, theme_name='default-dark'):

        self.switch_theme(theme_name)

        theme = self.get_current_theme()

        try:
            with open(self.template_path, "r", encoding="utf-8") as f: qss = f.read()
    
            # Replace placeholders using theme values
            for category, rules in theme.items():
                for role_name, rule_info in rules.items():
                    placeholder = f"--{role_name}--"
                    color = rule_info.get("color", "")
                    qss = qss.replace(placeholder, color)
        
            # Apply stylesheet to app
            app.setStyleSheet(qss)

        except Exception as e:
            print(f"[ERROR]: Failed to read QSS template: {e}")
        

    def add_property_to_widget(self, widget_name: str, property_name: str, property_value: str):
        """
            Add or update a property for a specific widget in the stylesheet.

        Args:
            widget_name (str): The name of the widget (e.g., "QPushButton").
            property_name (str): The name of the property (e.g., "font-family").
            property_value (str): The value of the property (e.g., "'Arial'").
        """

        with open(self.template_path,'r',encoding="utf-8") as f: qss = f.read()

        # Create the new property string
        new_property = f"{property_name}: {property_value};"

        # Check if the widget already has a stylesheet definition
        widget_pattern = re.compile(rf'{widget_name}\s*{{[^}}]*}}')
        match = widget_pattern.search(qss)
        if match:
            # Extract the existing stylesheet block for the widget
            widget_style = match.group(0)

            # Check if the property already exists in the widget's stylesheet
            property_pattern = re.compile(rf'{property_name}\s*:\s*[^;]+;')
            property_match = property_pattern.search(widget_style)
            
            if property_match:
                # If the property exists, update its value
                updated_style = widget_style.replace(property_match.group(0), new_property)
                qss = qss.replace(widget_style, updated_style)
    
                print('Property updated:',property_match)

                #logger.info(f"Updated property '{property_name}' to '{property_value}' for widget '{widget_name}'.")
            else:
                # If the property does not exist, append it to the widget's stylesheet
                updated_style = widget_style.rstrip('}') + f"\n    {new_property}\n}}"
                qss = qss.replace(widget_style, updated_style)
                #logger.info(f"Added property '{property_name}: {property_value}' to widget '{widget_name}'.")
                print('Property added:',property_match)

            # Update sylesheet template
            with open(self.template_path, 'w',encoding="utf-8") as f:
                f.write(qss)
                f.close()

            #self.apply_theme(QApplication.instance(), self.get_current_theme_name())


    def update_qss_font(self, font_size: int, font_family: str):
        """
        Modify a .qss file so that the global font rule (* { ... }) uses the given
        size and family. Other rules are left untouched.
        
        Special widgets that have a font set via setFont() will keep their manual
        font automatically because QWidget::font overrides the stylesheet.
        """
        self.data['font-family']= font_family
        self.data['font-size']=font_size
        self.save()
        with open(self.template_path,'r',encoding="utf-8") as f: raw = f.read()

        # Pattern to match the whole global * { ... } block
        global_rule_pattern = re.compile(
            r'(\*\s*\{)'          # opening of the * rule
            r'([^}]+?)'           # contents (non-greedy to avoid eating following rules)
            r'(\})',              # closing brace
            re.DOTALL
        )

        font_size  =  12 if font_size<=0 else font_size
        
        def replace_global_rule(match):
            """Inside the * { ... } block, replace font-size and font-family."""
            opening = match.group(1)
            body = match.group(2)
            closing = match.group(3)

            # Replace existing font-size / font-family declarations
            body = re.sub(r'font-size\s*:\s*[^;]+;', f'font-size: {font_size}pt;', body)
            body = re.sub(r'font-family\s*:\s*[^;]+;', f'font-family: "{font_family}";', body)

            # If they were missing, append them
            if 'font-size' not in body:
                body += f' font-size: {font_size}pt;'
            if 'font-family' not in body:
                body += f' font-family: "{font_family}";'

            return f'{opening}{body}{closing}'

        new_qss, count = global_rule_pattern.subn(replace_global_rule, raw)

        if count == 0:
            # No global * rule found → add one at the very beginning
            new_rule = f"* {{\n    font-size: {font_size}pt;\n    font-family: \"{font_family}\";\n}}\n"
            
            new_qss = new_rule + raw
      
        # Write back only if something changed (avoid unnecessary I/O)
        if new_qss != raw:
            with open(self.template_path, 'w',encoding="utf-8") as f: f.write(new_qss)

# ---------- Random contrasting hex color utility (light/dark aware) ----------
def random_contrasting_hex(background: QColor | str,
                           theme: str = "auto",
                           min_contrast: float = 4.5) -> str:
    """
    Returns a random hex color that is readable on the given background
    and is **never extremely bright** (no white, and generally darker).
    """
    if isinstance(background, str):
        bg = QColor(background)
    else:
        bg = QColor(background)

    def luminance(color: QColor) -> float:
        def linearize(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = linearize(color.redF() * 255), linearize(color.greenF() * 255), linearize(color.blueF() * 255)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast_ratio(l1, l2):
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    bg_lum = luminance(bg)

    if theme == "auto":
        need_light = bg_lum < 0.5
    else:
        need_light = (theme == "dark")

    max_attempts = 1000
    for _ in range(max_attempts):
        h = random.uniform(0, 360)
        s = random.uniform(0.4, 1.0)   # higher minimum saturation → bolder colors

        if need_light:
            # Light foreground – but darker than before (max 0.7)
            l = random.uniform(0.4, 0.7)
        else:
            # Dark foreground – deeper darks (max 0.35)
            l = random.uniform(0.1, 0.35)

        color = QColor.fromHslF(h / 360, s, l)

        # Reject white and very bright colours (lightness > 85%)
        if color.name() == "#ffffff" or color.lightnessF() > 0.85:
            continue

        color_lum = luminance(color)
        if contrast_ratio(bg_lum, color_lum) >= min_contrast:
            return color.name()

    # Darker fallbacks instead of pure white / black
    if need_light:
        return "#C8C8C8"   # dark grey, still readable on black
    else:
        return "#1A1A1A"   # very dark grey, almost black

# ========================================================================
# Additional Package Initialization or Configuration
# ========================================================================
# If necessary, add additional initialization code here (e.g., configuration
# settings, logging setup, or registering plugins).

# End