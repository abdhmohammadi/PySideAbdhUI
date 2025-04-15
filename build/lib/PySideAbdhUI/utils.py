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

# ========================================================================
# Additional Package Initialization or Configuration
# ========================================================================
# If necessary, add additional initialization code here (e.g., configuration
# settings, logging setup, or registering plugins).

# End