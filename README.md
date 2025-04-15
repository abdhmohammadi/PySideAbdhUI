
# PySideAbdhUI

**PySideAbdhUI** is a clean, reusable, and highly customizable UI component package built with [PySide6](https://doc.qt.io/qtforpython/). It is ideal for building professional and elegant desktop applications, especially those needing consistent styles, structured windows, enhanced widgets, and notification systems.

---

## 🔧 Features

- 📦 **Modular Widgets**: Custom widgets like `StackedWidget`, `Notify`, `StyledTableWidget`, and more.
- 🎨 **Theming Support**: Includes bundled QSS (Qt Style Sheet) themes that are easy to apply.
- 🧠 **Utilities Included**: Helpful UI utilities such as style loaders, path resolution, and notifications.
- 📁 **Bundled Resources**: Icons (`.svg`) and styles (`.qss`) included and auto-detected even when bundled via PyInstaller.
- 🛠️ **Ready for Production**: Easily embeddable in other applications, and compatible with PyInstaller and custom build scripts.

---

## 📦 Installation

You can install this package **locally** using pip:

```bash
pip install path	o\PySideAbdhUI
```

For example:

```bash
pip install F:\Projects\Python\PySideAbdhUI
```

Alternatively, install in editable mode (recommended for development):

```bash
pip install -e F:\Projects\Python\PySideAbdhUI
```
```bash
pip install git+https://github.com/abdhmohammadi/PySideAbdhUI.git
```

> ✅ This method allows the package to be used across **any Python IDE**, without needing to build a wheel (`.whl`) file.

---

## 🧪 Test Your Installation

To test whether the package is correctly installed:

```bash
python
>>> from PySideAbdhUI import Notify
>>> Notify.Info("Test notification works!")
```

Or run a bundled test file (if provided):

```bash
python test.py
```

---

## 🗂️ Package Structure

Your package is structured like this:

```
PySideAbdhUI/
├── PySideAbdhUI/
│   ├── __init__.py              # Core module entry
│   ├── Widgets.py               # Custom UI widgets
│   ├── Window.py                # Custom main window manager
│   ├── StyleManagers.py         # QSS stylesheet loader
│   ├── TableWidget.py           # Extended QTableWidget
│   ├── Notify.py                # Notification system
│   ├── utils.py                 # Utility functions
│   └── resources/
│       ├── icons/
│       │   └── svg/             # Icon SVGs
│       └── styles/              # .qss stylesheets
├── test-images/                 # Screenshots for documentation
│   ├── table-preview.png
│   ├── notification-preview.png
│   └── mainwindow-preview.png
├── LICENSE                      # MIT License
├── README.md                    # This file
├── setup.py                     # Install configuration
└── MANIFEST.in                  # Resource inclusion rules
```

---

## 🖼️ Visual Preview

Here’s how the components look in a typical application:

### 🔹 Styled Table Widget

A fully styled, responsive QTableWidget with alternate row colors and header formatting.

![Styled Table](test-images/table-preview.png)

---

### 🔹 Notification System

Non-blocking, animated popups for success, error, info, or warning messages.

![Notification](test-images/notification-preview.png)

---

### 🔹 Custom Main Window with Styled Titlebar

A modern, frameless main window supporting drag, drop, theme application, and stacked widgets.

![Main Window](test-images/mainwindow-preview.png)

---

## 🚀 Example Usage

Here’s a quick Python example showing how to use PySideAbdhUI components in your app:

```python
from PySideAbdhUI import Notify, load_stylesheet
from PySide6.QtWidgets import QApplication

app = QApplication([])

# Load and apply custom style
app.setStyleSheet(load_stylesheet("dark"))

# Show a sample notification
Notify.Success("Project loaded successfully!")

app.exec()
```

---

## ✅ Requirements

- Python ≥ 3.8
- PySide6

Install PySide6 if not available:

```bash
pip install PySide6
```

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for full terms.

---

## 🤝 Contributing

Pull requests, issues, and feature suggestions are always welcome. You can:

- Fork the project
- Submit a PR
- Report bugs or request features

> Developed with ❤️ by [Your Name or Team Name]

---

## 📢 Tips for Distribution

To use this package in PyInstaller or freeze it with your own application:

- Use `collect_submodules("PySideAbdhUI")` and `collect_data_files("PySideAbdhUI")` in your `.spec` file
- The `get_resource_path()` function ensures the package detects bundled resources correctly

---

Enjoy building with **PySideAbdhUI**!
