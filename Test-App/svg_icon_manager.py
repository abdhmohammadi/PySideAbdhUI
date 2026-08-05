#!/usr/bin/env python3
"""
SVG Icon Manager — PySide6 desktop app to manage a folder of SVG icons.

Features
--------
1) Display icons in an auto-sized grid (N rows x 8 columns, N = ceil(count / 8)).
2) Live search/filter by filename substring.
3) Pick a color -> override both `fill` and `stroke` on every element of the SVG.
4) Slider to change the thumbnail display size (the SVG file is NOT modified).
5) Click an icon to open a large preview with its own zoom slider.
6) Batch recolor: apply the picked color to all filtered icons at once.
7) Save modified copies: prompt for a destination folder on every save
   (originals are never overwritten).
8) Export visible icons to PNG at a chosen resolution.

Usage
-----
    pip install -r requirements.txt
    python svg_icon_manager.py [path/to/icon/folder]

Author: Super Z
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStatusBar,
    QTableWidgetItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from widgets.src.PySideAbdhUI.Widgets.Window import AbdhWindow

# ---------------------------------------------------------------------------
# SVG color manipulation
# ---------------------------------------------------------------------------

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# Every SVG/CSS property whose value is a single <color>.
# Reference: https://www.w3.org/TR/SVG2/painting.html + CSS Color spec.
COLOR_PROPERTIES = {
    "fill",
    "stroke",
    "stop-color",
    "color",
    "flood-color",
    "lighting-color",
    "solid-color",
    "background-color",
    "border-color",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "outline-color",
    "text-decoration-color",
    "caret-color",
    "accent-color",
}

# Same properties when they appear as XML attributes (kebab-case as-is).
COLOR_ATTRIBUTES = COLOR_PROPERTIES

# Named CSS colors that should be replaced. `currentColor` and `inherit`/
# `unset`/`revert` are left untouched because they reference context.
NAMED_COLORS = {
    "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure", "beige",
    "bisque", "black", "blanchedalmond", "blue", "blueviolet", "brown",
    "burlywood", "cadetblue", "chartreuse", "chocolate", "coral",
    "cornflowerblue", "cornsilk", "crimson", "cyan", "darkblue", "darkcyan",
    "darkgoldenrod", "darkgray", "darkgreen", "darkgrey", "darkkhaki",
    "darkmagenta", "darkolivegreen", "darkorange", "darkorchid", "darkred",
    "darksalmon", "darkseagreen", "darkslateblue", "darkslategray",
    "darkslategrey", "darkturquoise", "darkviolet", "deeppink", "deepskyblue",
    "dimgray", "dimgrey", "dodgerblue", "firebrick", "floralwhite",
    "forestgreen", "fuchsia", "gainsboro", "ghostwhite", "gold", "goldenrod",
    "gray", "green", "greenyellow", "grey", "honeydew", "hotpink",
    "indianred", "indigo", "ivory", "khaki", "lavender", "lavenderblush",
    "lawngreen", "lemonchiffon", "lightblue", "lightcoral", "lightcyan",
    "lightgoldenrodyellow", "lightgray", "lightgreen", "lightgrey",
    "lightpink", "lightsalmon", "lightseagreen", "lightskyblue",
    "lightslategray", "lightslategrey", "lightsteelblue", "lightyellow",
    "lime", "limegreen", " linen", "maroon", "mediumaquamarine",
    "mediumblue", "mediumorchid", "mediumpurple", "mediumseagreen",
    "mediumslateblue", "mediumspringgreen", "mediumturquoise",
    "mediumvioletred", "midnightblue", "mintcream", "mistyrose", "moccasin",
    "navajowhite", "navy", "oldlace", "olive", "olivedrab", "orange",
    "orangered", "orchid", "palegoldenrod", "palegreen", "paleturquoise",
    "palevioletred", "papayawhip", "peachpuff", "peru", "pink", "plum",
    "powderblue", "purple", "rebeccapurple", "red", "rosybrown", "royalblue",
    "saddlebrown", "salmon", "sandybrown", "seagreen", "seashell", "sienna",
    "silver", "skyblue", "slateblue", "slategray", "slategrey", "snow",
    "springgreen", "steelblue", "tan", "teal", "thistle", "tomato",
    "turquoise", "violet", "wheat", "white", "whitesmoke", "yellow",
    "yellowgreen", "transparent",
}

# Tokens that should NOT be replaced (they reference context, not a color).
COLOR_KEYWORDS_KEEP = {"currentcolor", "inherit", "initial", "unset", "revert"}


def _is_hex_color(value: str) -> bool:
    v = value.strip().lstrip("#")
    return v != "" and all(c in "0123456789abcdefABCDEF" for c in v) and len(v) in (3, 4, 6, 8)


def _is_rgb_function(value: str) -> bool:
    """Match rgb()/rgba()/hsl()/hsla() functional notations (including legacy space-separated)."""
    v = value.strip().lower()
    for fn in ("rgb(", "rgba(", "hsl(", "hsla("):
        if v.startswith(fn) and v.endswith(")"):
            return True
    return False


def _is_named_color(value: str) -> bool:
    v = value.strip().lower()
    return v in NAMED_COLORS


def _is_color_value(value: str) -> bool:
    """Return True if `value` looks like a color we can replace."""
    v = value.strip().lower()
    if not v or v in COLOR_KEYWORDS_KEEP:
        return False
    if v.startswith("#"):
        return _is_hex_color(v)
    if _is_rgb_function(v):
        return True
    if v in NAMED_COLORS:
        return True
    return False


def _replace_color_value(value: str, new_color: str) -> str:
    """If `value` is a recognizable color, return `new_color`; otherwise return `value` unchanged."""
    if _is_color_value(value):
        return new_color
    return value


# ----- inline `style="..."` rewriting -------------------------------------


def _rewrite_inline_style(style: str, new_color: str) -> str:
    """Rewrite every color property in an inline `style` string."""
    new_parts: list[str] = []
    for part in style.split(";"):
        if ":" not in part:
            if part.strip():
                new_parts.append(part.strip())
            continue
        prop, _, val = part.partition(":")
        prop_clean = prop.strip().lower()
        val_clean = val.strip()
        if prop_clean in COLOR_PROPERTIES:
            new_parts.append(f"{prop_clean}: {new_color}")
        else:
            new_parts.append(f"{prop_clean}: {val_clean}")
    return "; ".join(new_parts)


# ----- `<style>` block CSS rewriting --------------------------------------


def _rewrite_css_text(css: str, new_color: str) -> str:
    """Rewrite color declarations inside a CSS stylesheet string.

    Preserves selectors, at-rules (`@media`, `@import`), braces, and comments.
    Only property values that are colors are replaced; everything else is left
    verbatim.
    """
    if not css:
        return css

    out: list[str] = []
    i = 0
    n = len(css)

    while i < n:
        ch = css[i]

        # Comment: /* ... */ — copy verbatim.
        if ch == "/" and i + 1 < n and css[i + 1] == "*":
            end = css.find("*/", i + 2)
            if end == -1:
                out.append(css[i:])
                break
            out.append(css[i:end + 2])
            i = end + 2
            continue

        # String literal: " ... " or ' ... ' — copy verbatim (e.g. content: "x").
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                if css[i] == "\\" and i + 1 < n:
                    out.append(css[i:i + 2])
                    i += 2
                    continue
                if css[i] == quote:
                    out.append(css[i])
                    i += 1
                    break
                out.append(css[i])
                i += 1
            continue

        # Property declaration: only rewrite inside `prop: value;` pairs.
        # We detect a colon that is NOT inside parentheses and NOT inside braces.
        if ch == ":":
            # Walk back to find the property name.
            j = len(out) - 1
            while j >= 0 and out[j] in " \t\r\n":
                j -= 1
            k = j
            while k >= 0 and (out[k].isalnum() or out[k] in "-_"):
                k -= 1
            prop_name = "".join(out[k + 1:j + 1]).lower()

            if prop_name in COLOR_PROPERTIES:
                # Find end of value: next `;` or `}` at top level.
                end = i + 1
                depth = 0
                while end < n:
                    c = css[end]
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth = max(0, depth - 1)
                    elif c in ";}" and depth == 0:
                        break
                    end += 1
                value = css[i + 1:end].strip()
                # Strip trailing `!important` etc.
                important = ""
                if "!" in value:
                    value, _, important = value.partition("!")
                    important = "!" + important
                    value = value.strip()
                # Replace if value is a recognizable color.
                if _is_color_value(value):
                    replacement = new_color + ((" " + important) if important else "")
                else:
                    replacement = value + ((" " + important) if important else "")
                # Replace property name + value in `out` (drop name) then emit `prop: new_value`.
                del out[k + 1:]
                out.append(f"{prop_name}: {replacement}")
                i = end
                continue

        out.append(ch)
        i += 1

    return "".join(out)


# ----- main entry point ---------------------------------------------------


# Default properties that get overridden when the user just clicks "Apply".
DEFAULT_PROPERTIES = frozenset({"fill", "stroke", "stop-color", "color"})


def _is_url_ref(value: str) -> bool:
    """True if value is `url(#...)` paint-server reference."""
    return value.strip().lower().startswith("url(")


def modify_svg_colors(
    svg_str: str,
    color: str,
    properties: Optional[set[str]] = None,
    preserve_currentcolor: bool = True,
    preserve_url_refs: bool = False,
) -> str:
    """Override every color in an SVG with `color`.

    Parameters
    ----------
    svg_str : str
        Input SVG markup.
    color : str
        Replacement color (any CSS color syntax — typically `#rrggbb`).
    properties : set[str], optional
        Which color properties to override. Defaults to
        ``{fill, stroke, stop-color, color}``. Use the full
        ``COLOR_PROPERTIES`` set to override every known color property.
    preserve_currentcolor : bool, default True
        If True, elements whose current color value is the literal
        ``currentColor`` keyword are left untouched (so they still
        inherit context at render time). Set False to force-override.
    preserve_url_refs : bool, default False
        If True, ``fill="url(#gradient)"`` / ``stroke="url(#pattern)"``
        references are preserved. If False (default), they are replaced
        with the new color.

    The function is idempotent on the original string and tolerant of
    malformed SVG: on parse failure it returns the input unchanged.
    """
    if properties is None:
        properties = set(DEFAULT_PROPERTIES)

    try:
        ET.register_namespace("", SVG_NS)
        ET.register_namespace("xlink", XLINK_NS)
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        return svg_str

    for elem in root.iter():
        tag = elem.tag.rpartition("}")[2] if "}" in elem.tag else elem.tag

        # 1) Presentation attributes — replace any existing color attribute
        #    that the user wants to touch.
        for attr in list(elem.attrib.keys()):
            attr_local = attr.rpartition("}")[2] if "}" in attr else attr
            if attr_local not in properties:
                continue
            current = elem.get(attr)
            if current is None:
                continue
            v = current.strip().lower()
            if v in COLOR_KEYWORDS_KEEP and preserve_currentcolor:
                continue
            if _is_url_ref(current) and preserve_url_refs:
                continue
            if _is_color_value(current) or v in COLOR_KEYWORDS_KEEP or _is_url_ref(current):
                # Force-set even for `none`/`currentColor`/`url()` (unless
                # preservation flagged above), so the new color wins.
                elem.set(attr, color)

        # 2) Inline `style="..."`.
        style = elem.get("style")
        if style:
            elem.set("style", _rewrite_inline_style_filtered(style, color, properties, preserve_currentcolor))

        # 3) Gradient stop-color attribute.
        if tag == "stop" and "stop-color" in properties:
            current = elem.get("stop-color")
            if current is None or not (preserve_currentcolor and current.strip().lower() in COLOR_KEYWORDS_KEEP):
                elem.set("stop-color", color)

        # 4) `<style>` element text — full CSS rewrite.
        if tag == "style" and elem.text:
            elem.text = _rewrite_css_text_filtered(elem.text, color, properties, preserve_currentcolor)

    return ET.tostring(root, encoding="unicode")


def _rewrite_inline_style_filtered(
    style: str, new_color: str, properties: set[str], preserve_currentcolor: bool
) -> str:
    """Rewrite only color properties listed in `properties`."""
    new_parts: list[str] = []
    for part in style.split(";"):
        if ":" not in part:
            if part.strip():
                new_parts.append(part.strip())
            continue
        prop, _, val = part.partition(":")
        prop_clean = prop.strip().lower()
        val_clean = val.strip()
        if prop_clean in properties and prop_clean in COLOR_PROPERTIES:
            v_lower = val_clean.lower()
            if v_lower in COLOR_KEYWORDS_KEEP and preserve_currentcolor:
                new_parts.append(f"{prop_clean}: {val_clean}")
            elif _is_url_ref(val_clean):
                # Inline style url() ref — keep as-is (rare in practice).
                new_parts.append(f"{prop_clean}: {val_clean}")
            else:
                new_parts.append(f"{prop_clean}: {new_color}")
        else:
            new_parts.append(f"{prop_clean}: {val_clean}")
    return "; ".join(new_parts)


def _rewrite_css_text_filtered(
    css: str, new_color: str, properties: set[str], preserve_currentcolor: bool
) -> str:
    """Same as `_rewrite_css_text` but only touches properties in `properties`."""
    if not css:
        return css

    out: list[str] = []
    i = 0
    n = len(css)

    while i < n:
        ch = css[i]

        if ch == "/" and i + 1 < n and css[i + 1] == "*":
            end = css.find("*/", i + 2)
            if end == -1:
                out.append(css[i:])
                break
            out.append(css[i:end + 2])
            i = end + 2
            continue

        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                if css[i] == "\\" and i + 1 < n:
                    out.append(css[i:i + 2])
                    i += 2
                    continue
                if css[i] == quote:
                    out.append(css[i])
                    i += 1
                    break
                out.append(css[i])
                i += 1
            continue

        if ch == ":":
            j = len(out) - 1
            while j >= 0 and out[j] in " \t\r\n":
                j -= 1
            k = j
            while k >= 0 and (out[k].isalnum() or out[k] in "-_"):
                k -= 1
            prop_name = "".join(out[k + 1:j + 1]).lower()

            if prop_name in properties and prop_name in COLOR_PROPERTIES:
                end = i + 1
                depth = 0
                while end < n:
                    c = css[end]
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth = max(0, depth - 1)
                    elif c in ";}" and depth == 0:
                        break
                    end += 1
                value = css[i + 1:end].strip()
                important = ""
                if "!" in value:
                    value, _, important = value.partition("!")
                    important = "!" + important
                    value = value.strip()

                v_lower = value.lower()
                if v_lower in COLOR_KEYWORDS_KEEP and preserve_currentcolor:
                    replacement = value + ((" " + important) if important else "")
                elif _is_url_ref(value):
                    replacement = value + ((" " + important) if important else "")
                elif _is_color_value(value):
                    replacement = new_color + ((" " + important) if important else "")
                else:
                    replacement = value + ((" " + important) if important else "")

                del out[k + 1:]
                out.append(f"{prop_name}: {replacement}")
                i = end
                continue

        out.append(ch)
        i += 1

    return "".join(out)


# ---------------------------------------------------------------------------
# Extra color tools: extract, find-replace, stroke-width, opacity
# ---------------------------------------------------------------------------


def extract_colors(svg_str: str) -> dict[str, int]:
    """Return a {color_value: occurrence_count} map of every color found.

    Scans presentation attributes, inline styles, `<style>` blocks, and
    gradient stop-colors. Colors are returned in their original textual
    form (e.g. `#ff0000`, `rgb(255,0,0)`, `red`). `currentColor`,
    `inherit`, `initial`, `unset`, `revert`, `none`, and `url(#...)`
    references are excluded.
    """
    counts: dict[str, int] = {}

    def bump(value: str) -> None:
        v = value.strip()
        if not v:
            return
        if v.lower() in COLOR_KEYWORDS_KEEP or v.lower() == "none":
            return
        if _is_url_ref(v):
            return
        if _is_color_value(v):
            counts[v] = counts.get(v, 0) + 1

    try:
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        return counts

    for elem in root.iter():
        tag = elem.tag.rpartition("}")[2] if "}" in elem.tag else elem.tag

        for attr, value in elem.attrib.items():
            attr_local = attr.rpartition("}")[2] if "}" in attr else attr
            if attr_local in COLOR_ATTRIBUTES:
                bump(value)

        style = elem.get("style")
        if style:
            for part in style.split(";"):
                if ":" not in part:
                    continue
                prop, _, val = part.partition(":")
                if prop.strip().lower() in COLOR_PROPERTIES:
                    bump(val)

        if tag == "style" and elem.text:
            for m in re.finditer(r"[\w-]+\s*:\s*([^;{}]+)", elem.text):
                # We don't know the prop name here without more parsing;
                # check if the value looks like a color.
                val = m.group(1).strip()
                # Heuristic: only count if it really is a color.
                if _is_color_value(val):
                    bump(val)

    return counts


def find_replace_color(svg_str: str, old: str, new: str) -> str:
    """Replace every occurrence of `old` color with `new` color throughout.

    Both arguments should be color values in any CSS syntax. The function
    matches case-insensitively on the trimmed value (so `#FF0000` and
    `#ff0000` are treated as the same color).
    """
    if not old or not new:
        return svg_str

    try:
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        return svg_str

    old_norm = old.strip().lower()
    new_val = new.strip()

    def maybe_replace(value: str) -> str:
        if value.strip().lower() == old_norm:
            return new_val
        return value

    for elem in root.iter():
        tag = elem.tag.rpartition("}")[2] if "}" in elem.tag else elem.tag

        for attr in list(elem.attrib.keys()):
            attr_local = attr.rpartition("}")[2] if "}" in attr else attr
            if attr_local in COLOR_ATTRIBUTES:
                current = elem.get(attr)
                if current is not None:
                    elem.set(attr, maybe_replace(current))

        style = elem.get("style")
        if style:
            new_parts: list[str] = []
            for part in style.split(";"):
                if ":" not in part:
                    if part.strip():
                        new_parts.append(part.strip())
                    continue
                prop, _, val = part.partition(":")
                prop_clean = prop.strip().lower()
                val_clean = val.strip()
                if prop_clean in COLOR_PROPERTIES:
                    val_clean = maybe_replace(val_clean)
                new_parts.append(f"{prop_clean}: {val_clean}")
            elem.set("style", "; ".join(new_parts))

        if tag == "style" and elem.text:
            # Token-based replace inside CSS — only swap whole color tokens.
            def repl(m: re.Match) -> str:
                if m.group(0).strip().lower() == old_norm:
                    return new_val
                return m.group(0)

            # Match common color token shapes.
            elem.text = re.sub(
                r"#[0-9a-fA-F]{3,8}|rgb\([^)]*\)|rgba\([^)]*\)|hsl\([^)]*\)|hsla\([^)]*\)|[a-zA-Z]+",
                repl,
                elem.text,
            )

    return ET.tostring(root, encoding="unicode")


def set_stroke_width(svg_str: str, width: float) -> str:
    """Set `stroke-width` on every element that has a stroke."""
    try:
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        return svg_str

    width_str = str(width)
    for elem in root.iter():
        # Set as attribute on every drawable element; harmless if no stroke.
        elem.set("stroke-width", width_str)
        # Also override inline style if present.
        style = elem.get("style")
        if style:
            new_parts: list[str] = []
            found = False
            for part in style.split(";"):
                if ":" not in part:
                    if part.strip():
                        new_parts.append(part.strip())
                    continue
                prop, _, val = part.partition(":")
                if prop.strip().lower() == "stroke-width":
                    new_parts.append(f"stroke-width: {width_str}")
                    found = True
                else:
                    new_parts.append(f"{prop.strip().lower()}: {val.strip()}")
            if not found:
                new_parts.append(f"stroke-width: {width_str}")
            elem.set("style", "; ".join(new_parts))

    return ET.tostring(root, encoding="unicode")


def set_opacity(svg_str: str, opacity: float, target: str = "both") -> str:
    """Set fill-opacity and/or stroke-opacity on every element.

    `target` is one of `"fill"`, `"stroke"`, or `"both"`. `opacity` is
    clamped to [0.0, 1.0].
    """
    opacity = max(0.0, min(1.0, float(opacity)))
    opacity_str = f"{opacity:.3f}".rstrip("0").rstrip(".")
    if opacity_str == "":
        opacity_str = "0"

    try:
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        return svg_str

    targets = []
    if target in ("fill", "both"):
        targets.append("fill-opacity")
    if target in ("stroke", "both"):
        targets.append("stroke-opacity")

    for elem in root.iter():
        for t in targets:
            elem.set(t, opacity_str)
        style = elem.get("style")
        if style:
            new_parts: list[str] = []
            found = {t: False for t in targets}
            for part in style.split(";"):
                if ":" not in part:
                    if part.strip():
                        new_parts.append(part.strip())
                    continue
                prop, _, val = part.partition(":")
                prop_clean = prop.strip().lower()
                if prop_clean in targets:
                    new_parts.append(f"{prop_clean}: {opacity_str}")
                    found[prop_clean] = True
                else:
                    new_parts.append(f"{prop_clean}: {val.strip()}")
            for t in targets:
                if not found[t]:
                    new_parts.append(f"{t}: {opacity_str}")
            elem.set("style", "; ".join(new_parts))

    return ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------------------
# SVG -> QPixmap rendering
# ---------------------------------------------------------------------------


def render_svg_to_pixmap(svg_str: str, size: int) -> QPixmap:
    """Render an SVG string into a square QPixmap of the given pixel size."""
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    if not renderer.isValid():
        pm = QPixmap(size, size)
        pm.fill(QColor("#dddddd"))
        return pm
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    return pm


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class IconItem:
    path: str
    filename: str
    original_svg: str
    current_svg: str
    modified: bool = False


# ---------------------------------------------------------------------------
# Icon cell widget (one tile in the grid)
# ---------------------------------------------------------------------------


class IconCell(QFrame):
    clicked = Signal(object)  # emits the IconItem

    NORMAL_STYLE = "QFrame { border: 1px solid #ccc; background: #ffffff; }"
    HOVER_STYLE = "QFrame { border: 2px solid #4a90e2; background: #f0f7ff; }"
    SELECTED_STYLE = "QFrame { border: 2px solid #2c7be5; background: #e3f2fd; }"
    MODIFIED_STYLE = "QFrame { border: 2px solid #f39c12; background: #fff8e1; }"
    SELECTED_MODIFIED_STYLE = "QFrame { border: 2px solid #d35400; background: #fff3cd; }"

    def __init__(self, item: IconItem, thumb_size: int, parent=None):
        super().__init__(parent)
        self.item = item
        self.thumb_size = thumb_size
        self.is_selected = False

        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setFixedSize(thumb_size, thumb_size)
        layout.addWidget(self.thumb_label, alignment=Qt.AlignCenter)

        self.name_label = QLabel(item.filename)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-size: 10px; color: #555;")
        self.name_label.setMaximumWidth(thumb_size + 24)
        layout.addWidget(self.name_label)

        self.setFixedSize(thumb_size + 28, thumb_size + 56)
        self._refresh_style()
        self.update_thumbnail()

    # ---- styling ---------------------------------------------------------

    def _refresh_style(self) -> None:
        if self.is_selected and self.item.modified:
            self.setStyleSheet(self.SELECTED_MODIFIED_STYLE)
        elif self.is_selected:
            self.setStyleSheet(self.SELECTED_STYLE)
        elif self.item.modified:
            self.setStyleSheet(self.MODIFIED_STYLE)
        else:
            self.setStyleSheet(self.NORMAL_STYLE)

    def set_selected(self, value: bool) -> None:
        self.is_selected = value
        self._refresh_style()

    def enterEvent(self, event):
        if not self.is_selected:
            self.setStyleSheet(self.HOVER_STYLE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._refresh_style()
        super().leaveEvent(event)

    # ---- thumbnail -------------------------------------------------------

    def update_thumbnail(self) -> None:
        pm = render_svg_to_pixmap(self.item.current_svg, self.thumb_size)
        self.thumb_label.setPixmap(pm)
        self._refresh_style()

    def set_thumb_size(self, size: int) -> None:
        self.thumb_size = size
        self.thumb_label.setFixedSize(size, size)
        self.name_label.setMaximumWidth(size + 24)
        self.setFixedSize(size + 28, size + 56)
        self.update_thumbnail()

    # ---- interaction -----------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.item)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Preview dialog (large view with zoom slider)
# ---------------------------------------------------------------------------


class PreviewDialog(QWidget):
    def __init__(self, item: IconItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(f"Preview — {item.filename}")
        self.setWindowFlags(Qt.Window)
        self.resize(420, 520)

        layout = QVBoxLayout(self)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(320, 320)
        self.preview_label.setStyleSheet("background: #fafafa; border: 1px solid #ddd;")
        layout.addWidget(self.preview_label)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Preview size:"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(64, 512)
        self.size_slider.setValue(256)
        self.size_slider.valueChanged.connect(self._update_preview)
        size_row.addWidget(self.size_slider, 1)
        self.size_value_label = QLabel("256 px")
        self.size_value_label.setMinimumWidth(60)
        size_row.addWidget(self.size_value_label)
        layout.addLayout(size_row)

        info = QLabel(f"File: {item.path}")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info)

        status = QLabel(
            "Modified" if item.modified else "Original (unmodified)"
        )
        status.setStyleSheet(
            "color: #f39c12; font-weight: bold;" if item.modified
            else "color: #888;"
        )
        layout.addWidget(status)

        self._update_preview(self.size_slider.value())

    def _update_preview(self, size: int) -> None:
        self.size_value_label.setText(f"{size} px")
        pm = render_svg_to_pixmap(self.item.current_svg, size)
        self.preview_label.setPixmap(pm)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class IconManagerWindow(AbdhWindow):
    GRID_COLUMNS = 8

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG Icon Manager")
        self.resize(1024, 720)

        self.items: list[IconItem] = []
        self.filtered_items: list[IconItem] = []
        self.cells: list[IconCell] = []
        self.selected_item: Optional[IconItem] = None
        self.current_thumb_size: int = 64
        self.current_color: Optional[str] = None
        self.recent_colors: list[str] = []
        self.selected_properties: set[str] = set(DEFAULT_PROPERTIES)
        self.preserve_currentcolor: bool = True
        self.preserve_url_refs: bool = False

        self._build_menu()
        self._build_ui()

    # ---- menu bar --------------------------------------------------------

    def _build_menu(self) -> None:
        #menubar = self.menuBar()

        #file_menu = menubar.addMenu("&File")
        btn = QPushButton("Open Folder…", self)
        #btn.setIcon(QIcon(":icons/book-text.svg"))
        btn.setShortcut("Ctrl+O")
        btn.clicked.connect(self.open_folder)
        self.add_left_panel_item(btn)

        save_action = QPushButton("Save Modified Copies To…", self)
        save_action.setShortcut("Ctrl+S")
        save_action.clicked.connect(self.save_copies)
        self.add_left_panel_item(save_action)

        export_action = QPushButton("Export Visible to PNG…", self)
        export_action.setShortcut("Ctrl+E")
        export_action.clicked.connect(self.export_png)
        self.add_left_panel_item(export_action)

        quit_action = QPushButton("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.clicked.connect(self.close)
        self.add_left_panel_item(quit_action)

    # ---- main UI ---------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.add_page(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ----- sidebar (wider to fit the new tool sections) -----
        content_scroll = QScrollArea()
        content_scroll.setFixedWidth(350)
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        main_layout.addWidget(content_scroll)

        sidebar = QWidget()
        content_scroll.setWidget(sidebar)
        
        #sidebar.setFixedWidth(800)
        sb = QVBoxLayout(sidebar)
        
        sb.setContentsMargins(0, 0, 8, 0)
        sb.setSpacing(4)

        # ===== Search =====
        sb.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by filename…")
        self.search_edit.textChanged.connect(self.refresh_grid)
        sb.addWidget(self.search_edit)

        # ===== Color picker =====
        color_group = QGroupBox("Icon Color")
        cg = QVBoxLayout(color_group)
        color_row = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(44, 30)
        self.color_preview.setStyleSheet("background: #000000; border: 1px solid #999;")
        color_row.addWidget(self.color_preview)
        self.pick_color_btn = QPushButton("Pick…")
        self.pick_color_btn.clicked.connect(self.pick_color)
        color_row.addWidget(self.pick_color_btn)
        color_row.addStretch(1)
        cg.addLayout(color_row)

        # Quick swatches (recent colors)
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(4)
        self.swatch_buttons: list[QPushButton] = []
        for _ in range(8):
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setEnabled(False)
            btn.setStyleSheet("background: #ddd; border: 1px solid #999;")
            btn.clicked.connect(self._make_swatch_handler(btn))
            swatch_row.addWidget(btn)
            self.swatch_buttons.append(btn)
        swatch_row.addStretch(1)
        cg.addLayout(swatch_row)

        self.apply_selected_btn = QPushButton("Apply to Selected")
        self.apply_selected_btn.setToolTip("Apply the picked color to the currently selected icon.")
        self.apply_selected_btn.clicked.connect(self.apply_color_to_selected)
        self.apply_selected_btn.setEnabled(False)
        cg.addWidget(self.apply_selected_btn)

        self.apply_all_btn = QPushButton("Apply to All (filtered)")
        self.apply_all_btn.setToolTip("Apply the picked color to every icon currently visible in the grid.")
        self.apply_all_btn.clicked.connect(self.apply_color_to_all)
        self.apply_all_btn.setEnabled(False)
        cg.addWidget(self.apply_all_btn)

        sb.addWidget(color_group)

        # ===== Properties to modify (checkboxes) =====
        prop_group = QGroupBox("Properties to Modify")
        pg = QVBoxLayout(prop_group)
        pg.setSpacing(2)
        self.prop_checks: dict[str, QCheckBox] = {}
        for prop in ("fill", "stroke", "stop-color", "color", "all-others"):
            cb = QCheckBox(prop)
            if prop == "all-others":
                # "all-others" is checked when every non-default color property is selected.
                initially_checked = bool(
                    self.selected_properties >= (COLOR_PROPERTIES - DEFAULT_PROPERTIES)
                )
            else:
                initially_checked = prop in self.selected_properties
            cb.setChecked(initially_checked)
            cb.stateChanged.connect(self._on_property_toggled)
            pg.addWidget(cb)
            self.prop_checks[prop] = cb
        sb.addWidget(prop_group)

        # ===== Preservation toggles =====
        preserve_group = QGroupBox("Preserve")
        prg = QVBoxLayout(preserve_group)
        prg.setSpacing(2)
        self.preserve_currentcolor_cb = QCheckBox("currentColor keyword")
        self.preserve_currentcolor_cb.setChecked(True)
        self.preserve_currentcolor_cb.stateChanged.connect(self._on_preserve_toggled)
        prg.addWidget(self.preserve_currentcolor_cb)

        self.preserve_url_cb = QCheckBox("url(#…) gradient/pattern refs")
        self.preserve_url_cb.setChecked(False)
        self.preserve_url_cb.stateChanged.connect(self._on_preserve_toggled)
        prg.addWidget(self.preserve_url_cb)
        sb.addWidget(preserve_group)

        # ===== Thumbnail size =====
        size_group = QGroupBox("Thumbnail Size")
        sgl = QVBoxLayout(size_group)
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(32, 160)
        self.size_slider.setValue(64)
        self.size_slider.valueChanged.connect(self.on_thumb_size_changed)
        sgl.addWidget(self.size_slider)
        self.size_value_label = QLabel("64 px")
        self.size_value_label.setMinimumWidth(60)
        sgl.addWidget(self.size_value_label)
        sb.addWidget(size_group)

        # ===== Tools =====
        tools_group = QGroupBox("Color Tools")
        tl = QVBoxLayout(tools_group)
        tl.setSpacing(4)
        self.extract_btn = QPushButton("Extract Colors…")
        self.extract_btn.setToolTip("Scan all icons and list every unique color found.")
        self.extract_btn.clicked.connect(self.extract_colors_dialog)
        tl.addWidget(self.extract_btn)

        self.find_replace_btn = QPushButton("Find & Replace Color…")
        self.find_replace_btn.setToolTip("Replace one specific color with another across all icons.")
        self.find_replace_btn.clicked.connect(self.find_replace_dialog)
        tl.addWidget(self.find_replace_btn)

        self.stroke_btn = QPushButton("Set Stroke Width…")
        self.stroke_btn.setToolTip("Change stroke-width on all visible icons.")
        self.stroke_btn.clicked.connect(self.stroke_width_dialog)
        tl.addWidget(self.stroke_btn)

        self.opacity_btn = QPushButton("Set Opacity…")
        self.opacity_btn.setToolTip("Set fill-opacity and/or stroke-opacity on all visible icons.")
        self.opacity_btn.clicked.connect(self.opacity_dialog)
        tl.addWidget(self.opacity_btn)

        self.reset_btn = QPushButton("Reset Modified Icons")
        self.reset_btn.setToolTip("Revert all modified icons back to their original SVG.")
        self.reset_btn.clicked.connect(self.reset_modifications)
        tl.addWidget(self.reset_btn)

        sb.addWidget(tools_group)

        # ===== Stats =====
        self.stats_label = QLabel("No folder loaded.")
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet("color: #666; font-size: 11px;")
        sb.addWidget(self.stats_label)

        sb.addStretch(1)

        # ===== Save / export =====
        self.save_btn = QPushButton("Save Modified Copies To…")
        self.save_btn.clicked.connect(self.save_copies)
        sb.addWidget(self.save_btn)

        self.export_btn = QPushButton("Export Visible to PNG…")
        self.export_btn.clicked.connect(self.export_png)
        sb.addWidget(self.export_btn)

        # ----- grid area -----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self.scroll_ = QScrollArea()
        self.scroll_.setWidgetResizable(True)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_.setWidget(self.grid_container)
        right_layout.addWidget(self.scroll_)

        main_layout.addWidget(right, 1)

        #self.setStatusBar(QStatusBar())

    # ---- property / preserve toggles ------------------------------------

    def _on_property_toggled(self) -> None:
        """Rebuild self.selected_properties from the checkbox states."""
        selected = set()
        if self.prop_checks["fill"].isChecked():
            selected.add("fill")
        if self.prop_checks["stroke"].isChecked():
            selected.add("stroke")
        if self.prop_checks["stop-color"].isChecked():
            selected.add("stop-color")
        if self.prop_checks["color"].isChecked():
            selected.add("color")
        if self.prop_checks["all-others"].isChecked():
            # Everything else: flood-color, lighting-color, background-color, etc.
            selected |= (COLOR_PROPERTIES - {"fill", "stroke", "stop-color", "color"})
        self.selected_properties = selected

    def _on_preserve_toggled(self) -> None:
        self.preserve_currentcolor = self.preserve_currentcolor_cb.isChecked()
        self.preserve_url_refs = self.preserve_url_cb.isChecked()

    # ---- quick swatches --------------------------------------------------

    def _make_swatch_handler(self, btn: QPushButton):
        def handler():
            color = btn.property("color")
            if color:
                self.current_color = color
                self.color_preview.setStyleSheet(
                    f"background: {color}; border: 1px solid #999;"
                )
                self.apply_selected_btn.setEnabled(self.selected_item is not None)
                self.apply_all_btn.setEnabled(bool(self.filtered_items))
                self.statusBar().showMessage(f"Color: {color}", 3000)
        return handler

    def _add_recent_color(self, color: str) -> None:
        if not color:
            return
        if color in self.recent_colors:
            self.recent_colors.remove(color)
        self.recent_colors.insert(0, color)
        self.recent_colors = self.recent_colors[:8]
        for i, btn in enumerate(self.swatch_buttons):
            if i < len(self.recent_colors):
                c = self.recent_colors[i]
                btn.setEnabled(True)
                btn.setStyleSheet(f"background: {c}; border: 1px solid #999;")
                btn.setProperty("color", c)
                btn.setToolTip(c)
            else:
                btn.setEnabled(False)
                btn.setStyleSheet("background: #ddd; border: 1px solid #999;")
                btn.setProperty("color", None)
                btn.setToolTip("")

    # ---- thumbnail size --------------------------------------------------

    def on_thumb_size_changed(self, value: int) -> None:
        self.current_thumb_size = value
        self.size_value_label.setText(f"{value} px")
        for cell in self.cells:
            cell.set_thumb_size(value)

    # ---- color picker ----------------------------------------------------

    def pick_color(self) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color.name()
            self.color_preview.setStyleSheet(
                f"background: {self.current_color}; border: 1px solid #999;"
            )
            self._add_recent_color(self.current_color)
            self.apply_selected_btn.setEnabled(self.selected_item is not None)
            self.apply_all_btn.setEnabled(bool(self.filtered_items))
            self.statusBar().showMessage(f"Color: {self.current_color}", 3000)

    # ---- folder loading --------------------------------------------------

    def open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open SVG Icon Folder")
        if not folder:
            return
        self.load_folder(folder)

    def load_folder(self, folder: str) -> None:
        self.items.clear()
        try:
            entries = sorted(os.listdir(folder))
        except OSError as exc:
            QMessageBox.critical(self, "Open Folder", f"Cannot read folder:\n{exc}")
            return

        for fname in entries:
            fpath = os.path.join(folder, fname)
            if not (fname.lower().endswith(".svg") and os.path.isfile(fpath)):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as fp:
                    svg = fp.read()
            except OSError as exc:
                print(f"[skip] Failed to read {fpath}: {exc}", file=sys.stderr)
                continue
            self.items.append(
                IconItem(
                    path=fpath,
                    filename=fname,
                    original_svg=svg,
                    current_svg=svg,
                )
            )

        self.selected_item = None
        self.stats_label.setText(f"Folder: {folder}\nIcons: {len(self.items)}")
        self.statusBar().showMessage(
            f"Loaded {len(self.items)} icons from {folder}", 5000
        )
        self.refresh_grid()

    # ---- grid rendering --------------------------------------------------

    def refresh_grid(self) -> None:
        # Clear existing cells.
        for cell in self.cells:
            cell.setParent(None)
            cell.deleteLater()
        self.cells.clear()

        query = self.search_edit.text().strip().lower()
        self.filtered_items = [
            it for it in self.items
            if not query or query in it.filename.lower()
        ]

        for i, item in enumerate(self.filtered_items):
            cell = IconCell(item, self.current_thumb_size)
            cell.clicked.connect(self.on_cell_clicked)
            if item is self.selected_item:
                cell.set_selected(True)
            r, c = divmod(i, self.GRID_COLUMNS)
            self.grid_layout.addWidget(cell, r, c)
            self.cells.append(cell)

        self.statusBar().showMessage(
            f"Showing {len(self.filtered_items)} / {len(self.items)} icons", 3000
        )
        self.apply_all_btn.setEnabled(
            bool(self.filtered_items) and self.current_color is not None
        )

    # ---- selection & preview --------------------------------------------

    def on_cell_clicked(self, item: IconItem) -> None:
        self.selected_item = item
        for cell in self.cells:
            cell.set_selected(cell.item is item)
        self.apply_selected_btn.setEnabled(self.current_color is not None)
        dlg = PreviewDialog(item, self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.show()

    # ---- color application ----------------------------------------------

    def apply_color_to_selected(self) -> None:
        if not self.selected_item or not self.current_color:
            return
        self._apply_color([self.selected_item])

    def apply_color_to_all(self) -> None:
        if not self.current_color:
            return
        self._apply_color(list(self.filtered_items))

    def _apply_color(self, items: list[IconItem]) -> None:
        if not items or not self.current_color:
            return
        if not self.selected_properties:
            QMessageBox.warning(
                self,
                "No Properties Selected",
                "No color properties are checked in 'Properties to Modify'. "
                "Select at least one (fill, stroke, stop-color, …) before applying.",
            )
            return
        for it in items:
            it.current_svg = modify_svg_colors(
                it.current_svg,
                self.current_color,
                properties=set(self.selected_properties),
                preserve_currentcolor=self.preserve_currentcolor,
                preserve_url_refs=self.preserve_url_refs,
            )
            it.modified = True
        for cell in self.cells:
            if cell.item in items:
                cell.update_thumbnail()
        self.statusBar().showMessage(
            f"Applied color {self.current_color} to {len(items)} icon(s) "
            f"(props: {', '.join(sorted(self.selected_properties)) or 'none'}).",
            4000,
        )

    # ---- extract colors dialog ------------------------------------------

    def extract_colors_dialog(self) -> None:
        if not self.items:
            QMessageBox.information(self, "Extract Colors", "No icons loaded.")
            return

        # Aggregate colors across all icons.
        all_colors: dict[str, int] = {}
        per_icon_counts: dict[str, dict[str, int]] = {}
        for it in self.items:
            counts = extract_colors(it.current_svg)
            per_icon_counts[it.filename] = counts
            for color, n in counts.items():
                all_colors[color] = all_colors.get(color, 0) + n

        if not all_colors:
            QMessageBox.information(
                self, "Extract Colors", "No recognized colors found in any icon."
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Extract Colors — {len(all_colors)} unique colors in {len(self.items)} icon(s)")
        dlg.resize(640, 520)
        layout = QVBoxLayout(dlg)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Color", "Hex / Value", "Occurrences"])
        table.setRowCount(len(all_colors))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)

        for row, (color, n) in enumerate(
            sorted(all_colors.items(), key=lambda kv: -kv[1])
        ):
            swatch_item = QTableWidgetItem("")
            # Use the color value as background; if invalid, leave grey.
            try:
                swatch_item.setBackground(QColor(color))
            except Exception:
                pass
            table.setItem(row, 0, swatch_item)
            table.setItem(row, 1, QTableWidgetItem(color))
            table.setItem(row, 2, QTableWidgetItem(str(n)))

        table.setColumnWidth(0, 80)
        table.setColumnWidth(1, 220)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)

        info = QLabel(
            "Click a row to load that color into the picker. "
            "Close the dialog when done."
        )
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info)

        def on_cell_clicked(row, _col):
            color_item = table.item(row, 1)
            if color_item:
                self.current_color = color_item.text()
                self.color_preview.setStyleSheet(
                    f"background: {self.current_color}; border: 1px solid #999;"
                )
                self._add_recent_color(self.current_color)
                self.apply_selected_btn.setEnabled(self.selected_item is not None)
                self.apply_all_btn.setEnabled(bool(self.filtered_items))
                self.statusBar().showMessage(
                    f"Loaded color {self.current_color} from extracted list.", 3000
                )

        table.cellClicked.connect(on_cell_clicked)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec()

    # ---- find & replace color dialog ------------------------------------

    def find_replace_dialog(self) -> None:
        if not self.filtered_items:
            QMessageBox.information(self, "Find & Replace", "No icons to operate on.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Find & Replace Color")
        dlg.resize(520, 280)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Old color (find):"))
        old_edit = QLineEdit()
        old_edit.setPlaceholderText("e.g. #ff0000 or red or rgb(255,0,0)")
        layout.addWidget(old_edit)

        old_pick_btn = QPushButton("Pick old color…")
        layout.addWidget(old_pick_btn)

        layout.addWidget(QLabel("New color (replace with):"))
        new_edit = QLineEdit()
        new_edit.setPlaceholderText("e.g. #00ccff")
        layout.addWidget(new_edit)

        new_pick_btn = QPushButton("Pick new color…")
        layout.addWidget(new_pick_btn)

        scope_group = QGroupBox("Scope")
        sgl = QVBoxLayout(scope_group)
        scope_selected = QRadioButton("Selected icon only")
        scope_filtered = QRadioButton("All visible (filtered) icons")
        scope_filtered.setChecked(True)
        sgl.addWidget(scope_selected)
        sgl.addWidget(scope_filtered)
        layout.addWidget(scope_group)

        def pick_into(line: QLineEdit) -> None:
            c = QColorDialog.getColor()
            if c.isValid():
                line.setText(c.name())

        old_pick_btn.clicked.connect(lambda: pick_into(old_edit))
        new_pick_btn.clicked.connect(lambda: pick_into(new_edit))

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Close
        )
        btn_box.button(QDialogButtonBox.Apply).clicked.connect(
            lambda: self._do_find_replace(
                old_edit.text().strip(),
                new_edit.text().strip(),
                scope_selected.isChecked(),
            )
        )
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec()

    def _do_find_replace(
        self, old: str, new: str, scope_selected: bool
    ) -> None:
        if not old or not new:
            QMessageBox.warning(self, "Find & Replace", "Both colors are required.")
            return
        if scope_selected:
            if not self.selected_item:
                QMessageBox.warning(self, "Find & Replace", "No icon is selected.")
                return
            targets = [self.selected_item]
        else:
            targets = list(self.filtered_items)

        for it in targets:
            it.current_svg = find_replace_color(it.current_svg, old, new)
            it.modified = True
        for cell in self.cells:
            if cell.item in targets:
                cell.update_thumbnail()
        self.statusBar().showMessage(
            f"Replaced '{old}' with '{new}' in {len(targets)} icon(s).", 4000
        )

    # ---- stroke width dialog --------------------------------------------

    def stroke_width_dialog(self) -> None:
        if not self.filtered_items:
            QMessageBox.information(self, "Stroke Width", "No icons to operate on.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Set Stroke Width")
        dlg.resize(420, 200)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Stroke width (px):"))
        spin = QSpinBox()
        spin.setRange(0, 32)
        spin.setValue(2)
        spin.setSingleStep(1)
        layout.addWidget(spin)

        scope_group = QGroupBox("Scope")
        sgl = QVBoxLayout(scope_group)
        scope_selected = QRadioButton("Selected icon only")
        scope_filtered = QRadioButton("All visible (filtered) icons")
        scope_filtered.setChecked(True)
        sgl.addWidget(scope_selected)
        sgl.addWidget(scope_filtered)
        layout.addWidget(scope_group)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Close
        )
        btn_box.button(QDialogButtonBox.Apply).clicked.connect(
            lambda: self._do_stroke_width(
                spin.value(), scope_selected.isChecked(), dlg
            )
        )
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec()

    def _do_stroke_width(
        self, width: int, scope_selected: bool, dlg: QDialog
    ) -> None:
        if scope_selected:
            if not self.selected_item:
                QMessageBox.warning(self, "Stroke Width", "No icon is selected.")
                return
            targets = [self.selected_item]
        else:
            targets = list(self.filtered_items)

        for it in targets:
            it.current_svg = set_stroke_width(it.current_svg, float(width))
            it.modified = True
        for cell in self.cells:
            if cell.item in targets:
                cell.update_thumbnail()
        self.statusBar().showMessage(
            f"Set stroke-width={width} on {len(targets)} icon(s).", 4000
        )
        dlg.accept()

    # ---- opacity dialog -------------------------------------------------

    def opacity_dialog(self) -> None:
        if not self.filtered_items:
            QMessageBox.information(self, "Opacity", "No icons to operate on.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Set Opacity")
        dlg.resize(420, 280)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Opacity (0.0 – 1.0):"))
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(100)
        spin.setSuffix("%")
        layout.addWidget(spin)

        target_group = QGroupBox("Target")
        tgl = QVBoxLayout(target_group)
        t_fill = QRadioButton("Fill opacity")
        t_stroke = QRadioButton("Stroke opacity")
        t_both = QRadioButton("Both")
        t_both.setChecked(True)
        tgl.addWidget(t_fill)
        tgl.addWidget(t_stroke)
        tgl.addWidget(t_both)
        layout.addWidget(target_group)

        scope_group = QGroupBox("Scope")
        sgl = QVBoxLayout(scope_group)
        scope_selected = QRadioButton("Selected icon only")
        scope_filtered = QRadioButton("All visible (filtered) icons")
        scope_filtered.setChecked(True)
        sgl.addWidget(scope_selected)
        sgl.addWidget(scope_filtered)
        layout.addWidget(scope_group)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Close
        )

        def do_apply():
            opacity = spin.value() / 100.0
            target = "fill" if t_fill.isChecked() else (
                "stroke" if t_stroke.isChecked() else "both"
            )
            self._do_opacity(
                opacity, target, scope_selected.isChecked(), dlg
            )

        btn_box.button(QDialogButtonBox.Apply).clicked.connect(do_apply)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec()

    def _do_opacity(
        self, opacity: float, target: str, scope_selected: bool, dlg: QDialog
    ) -> None:
        if scope_selected:
            if not self.selected_item:
                QMessageBox.warning(self, "Opacity", "No icon is selected.")
                return
            targets = [self.selected_item]
        else:
            targets = list(self.filtered_items)

        for it in targets:
            it.current_svg = set_opacity(it.current_svg, opacity, target)
            it.modified = True
        for cell in self.cells:
            if cell.item in targets:
                cell.update_thumbnail()
        self.statusBar().showMessage(
            f"Set {target} opacity={opacity:.2f} on {len(targets)} icon(s).", 4000
        )
        dlg.accept()

    # ---- reset modifications --------------------------------------------

    def reset_modifications(self) -> None:
        if not self.items:
            return
        modified = [it for it in self.items if it.modified]
        if not modified:
            QMessageBox.information(self, "Reset", "Nothing to reset.")
            return
        reply = QMessageBox.question(
            self,
            "Reset Modifications",
            f"Revert {len(modified)} modified icon(s) back to their original SVG?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        for it in modified:
            it.current_svg = it.original_svg
            it.modified = False
        for cell in self.cells:
            if cell.item in modified:
                cell.update_thumbnail()
        self.statusBar().showMessage(f"Reset {len(modified)} icon(s).", 3000)

    # ---- save modified copies -------------------------------------------

    def save_copies(self) -> None:
        if not self.items:
            QMessageBox.information(self, "Save Copies", "No icons loaded.")
            return
        modified = [it for it in self.items if it.modified]
        if not modified:
            QMessageBox.information(
                self, "Save Copies", "No icons have been modified yet."
            )
            return

        dest = QFileDialog.getExistingDirectory(
            self, "Choose destination folder for modified copies"
        )
        if not dest:
            return

        saved = 0
        errors: list[str] = []
        for it in modified:
            out_path = os.path.join(dest, it.filename)
            try:
                with open(out_path, "w", encoding="utf-8") as fp:
                    fp.write(it.current_svg)
                saved += 1
            except OSError as exc:
                errors.append(f"{it.filename}: {exc}")

        msg = f"Saved {saved} modified icon(s) to:\n{dest}"
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "Save Copies", msg)
        self.statusBar().showMessage(f"Saved {saved} copies to {dest}", 5000)

    # ---- PNG export -----------------------------------------------------

    def export_png(self) -> None:
        if not self.filtered_items:
            QMessageBox.information(self, "Export PNG", "No icons to export.")
            return

        dest = QFileDialog.getExistingDirectory(
            self, "Choose destination folder for PNGs"
        )
        if not dest:
            return

        size, ok = QInputDialog.getInt(
            self, "PNG Size", "Output PNG size (px):", 128, 16, 1024, 16
        )
        if not ok:
            return

        exported = 0
        errors: list[str] = []
        for it in self.filtered_items:
            base = os.path.splitext(it.filename)[0]
            out_path = os.path.join(dest, base + ".png")
            pm = render_svg_to_pixmap(it.current_svg, size)
            if pm.save(out_path, "PNG"):
                exported += 1
            else:
                errors.append(it.filename)

        msg = f"Exported {exported} PNG(s) at {size}x{size}px to:\n{dest}"
        if errors:
            msg += "\n\nFailed:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "Export PNG", msg)
        self.statusBar().showMessage(
            f"Exported {exported} PNGs to {dest}", 5000
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    path_ = "F:\\Projects\\Python\\icons\\svg"
    app = QApplication()
    window = IconManagerWindow()
    if len(path_) > 1 and os.path.isdir(path_): window.load_folder(path_)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()