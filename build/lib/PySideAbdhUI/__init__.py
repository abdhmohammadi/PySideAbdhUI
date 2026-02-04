"""
PySideAbdhUI Package Initialization

This package provides a collection of PySide6 components with bundled resources,
such as icons and styles, that are easily accessible after installation.
"""

__version__ = "1.0.7"

# Import primary submodules so that they are available when the package is imported.
from .CardGridView import *
from .Notify import *
from .StyleManagers import *
from .TableWidget import *
from .utils import *
from .Widgets import *
from .Window import *

# You can add additional initialization code or configuration if needed.