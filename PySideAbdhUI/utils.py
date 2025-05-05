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
import os
import re
import json
import importlib.resources
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox

def get_resource_path(package: str, resource: str, ext ='svg') -> Path:
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
        if not ext:
            segments = package.split('.')
            ext = segments[len(segments)-1]

        with importlib.resources.path(package, f'{resource}.{ext}') as res_path:
            return res_path
        
    except Exception as e:
    
        raise RuntimeError(f"Unable to locate the resource '{resource}' in package '{package}'.") from e

def get_icon(name:str, package:str='PySideAbdhUI.resources.icons.svg', ext = 'svg'):
    
    return get_resource_path(package, name,ext).as_posix()

def get_styles_template(package:str='PySideAbdhUI.resources.styles'):
    
    return get_resource_path(package,'qss-template','qss').as_posix()

def get_color_roles(package:str='PySideAbdhUI.resources.styles'):
    
    return get_resource_path(package, 'color-roles','json').as_posix()


class ThemeManager:
    
    def __init__(self):
        
        color_roles = get_color_roles()
        template =  get_styles_template()
        
        self.color_roles = color_roles

        self.template_path = template
        self.data = self.load()

    def load(self):
        with open(self.color_roles, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            f.close()
            return data
            
        return {"active-theme": "", "themes": {}}

    def save(self):
        with open(self.color_roles, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)
            f.close()

    def get_current_theme_name(self): return self.data.get("active-theme", "")

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
            with open(self.template_path, "r", encoding="utf-8") as f: 
                qss = f.read()
                f.close()
    
            # Replace placeholders using theme values
            for category, roles in theme.items():
                for role_name, role_info in roles.items():
                    placeholder = f"--{role_name}--"
                    color = role_info.get("color", "")
                    qss = qss.replace(placeholder, color)
        
            # Apply stylesheet to app
            app.setStyleSheet(qss)
        except Exception as e:
            print(f"[ERROR] Failed to read QSS template: {e}")
            return

    def add_property_to_widget(self, widget_name: str, property_name: str, property_value: str):
        """
            Add or update a property for a specific widget in the stylesheet.

        Args:
            widget_name (str): The name of the widget (e.g., "QPushButton").
            property_name (str): The name of the property (e.g., "font-family").
            property_value (str): The value of the property (e.g., "'Arial'").
        """
        with open(self.template_path,'r',encoding="utf-8") as f: 
            qss = f.read()
            f.close()

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

                #logger.info(f"Updated property '{property_name}' to '{property_value}' for widget '{widget_name}'.")
            else:
                # If the property does not exist, append it to the widget's stylesheet
                updated_style = widget_style.rstrip('}') + f"\n    {new_property}\n}}"
                qss = qss.replace(widget_style, updated_style)
                #logger.info(f"Added property '{property_name}: {property_value}' to widget '{widget_name}'.")
            
            # Update sylesheet template
            with open(self.template_path, 'w',encoding="utf-8") as f:
                f.write(qss)
                f.close()

            #self.apply_theme(QApplication.instance(), self.get_current_theme_name())

# ========================================================================
# Additional Package Initialization or Configuration
# ========================================================================
# If necessary, add additional initialization code here (e.g., configuration
# settings, logging setup, or registering plugins).

# End