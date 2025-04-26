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

import importlib.resources
from pathlib import Path
import os
import json
from PySide6.QtWidgets import QApplication

def get_resource_path(package: str, resource: str) -> Path:
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
    # First, try to use importlib.resources (Python 3.7+)
    try:
        with importlib.resources.path(package, resource) as res_path:
            return res_path
    except Exception:
        # Fallback using pkg_resources for older environments
        try:
            from pkg_resources import resource_filename
            # Convert the dot-separated package name to the file system path
            package_path = os.path.join(*package.split("."))
            full_path = resource_filename("PySideAbdhUI", os.path.join(package_path, resource))
            return Path(full_path)
        except Exception as e:
            raise RuntimeError(
                f"Unable to locate the resource '{resource}' in package '{package}'."
            ) from e

def get_icon(name:str, package:str='PySideAbdhUI.resources.icons.svg'):
    return get_resource_path(package, f'{name}.svg').as_posix()

def get_stylesheet(name:str,package:str='PySideAbdhUI.resources.styles'):
    return get_resource_path(package, f'{name}.qss').as_posix()

def get_styles_template(package:str='PySideAbdhUI.resources.styles'):
    return get_resource_path(package,'qss-template.qss').as_posix()

def get_color_roles(package:str='PySideAbdhUI.resources.styles'):
    return get_resource_path(package, 'color-roles.json').as_posix()


class ThemeManager:
    
    def __init__(self):
        
        color_roles = get_color_roles()
        template =  get_styles_template()

        if not os.path.exists(color_roles) or not os.path.exists(template):
            print('Error: color roles or theme template not exist in the path.')
            return
        
        self.color_roles = color_roles

        self.template = template
        self.data = self._load()

    def _load(self):
        try:
            with open(self.color_roles, "r", encoding="utf-8-sig") as f:
                return json.load(f)
            
        except Exception as e:
            print(f"Error loading theme JSON: {e}")
            return {"active-theme": "", "themes": {}}

    def save(self):

        with open(self.color_roles, "w", encoding="utf-8") as f: json.dump(self.data, f, indent=4)

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

    def apply_theme(self,app: QApplication,theme_name='default-dark'):

        self.switch_theme(theme_name)
        theme = self.get_current_theme()

        try:
            with open(self.template, "r", encoding="utf-8") as f: qss = f.read()
    
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
# ========================================================================
# Additional Package Initialization or Configuration
# ========================================================================
# If necessary, add additional initialization code here (e.g., configuration
# settings, logging setup, or registering plugins).

# End