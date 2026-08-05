"""
HTML document loader.

Pipeline 1 (file/string → editor):
  1. Extract CSS from <style> tags
  2. Extract scripts from <script> tags
  3. Extract abdh-document <meta>
  4. Extract <body> content
     - If .page-content divs exist → extract & concatenate their content
     - Otherwise → use raw body HTML
  5. Strip :root and body CSS rules (editor owns these)
  6. Rename CSS classes that conflict with editor's preserved classes
  7. Split body HTML into blocks (one block per top-level tag)
  8. Build Document with metadata

Pipeline 2 (blocks → editor):
  Starts at step 5 — CSS/scripts are provided directly,
  blocks are already created from the html_list.
"""

import html as _html
import base64
import re
from html.parser import HTMLParser
from pathlib import Path

from .document import Document, ScriptEntry
from .image import Image
from .math import MathBlock
from .paragraph import Paragraph
from .table import Table

# Be carefull, all keywords in this data is used by Regex("re" library)
_META = f'<meta name="abdh-document" content="version=0.1.0; page-system=multi-page">'

# ---------------------------------------------------------
# Image path → data URL conversion
# ---------------------------------------------------------

_MIME_BY_EXT = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".svg":  "image/svg+xml",
    ".webp": "image/webp",
    ".bmp":  "image/bmp",
}


def _file_to_data_url(path) -> str:
    """
    Convert an image file to a base64 data URL.

    Returns a string like:
        "data:image/png;base64,iVBORw0KGgo..."

    Returns empty string if the file doesn't exist or can't be read.
    """
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return ""
        ext = p.suffix.lower()
        mime = _MIME_BY_EXT.get(ext, "image/png")
        data = p.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except (OSError, ValueError):
        return ""


# Editor's preserved CSS classes — renamed in loaded documents
# to avoid style conflicts with the editor's own style.css.
_PRESERVED_CLASSES = frozenset({"table-drag-handle",
    "page", "page-content", "block", "math-block", "page-number", "loading-overlay","loading-overlay.visible",
    "measure-stage", "pages-wrapper", "editor","loading-container", "loading-spinner",
    "loading-text", "editor.continuous-mode", "block.image-block-selected", "image-resize-handles",
    "img-handle", "img-handle-nw", "img-handle-ne", "img-handle-sw", "img-handle-se", "block.image-dragging",
    "block.table-dragging", "image-drop-indicator", "block-drop-indicator", "context-menu", "context-menu-item",
    "context-menu-shortcut", "context-menu-separator", "context-menu-section-label", "context-menu-item.has-submenu",
    "context-submenu", "math-inline", "math-editing"
})

# Block-level elements that become individual Block instances.
# These are the "well-known" content tags that the editor recognizes
# by name and can render specially (e.g. tables get split by rows).
#
# NOTE: Container tags (div, section, article, etc.) are NOT in this
# set — they are handled as "generic" blocks that preserve their
# entire inner HTML verbatim. See _CONTAINER_TAGS below.
_BLOCK_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "ul", "ol", "table",
})

# Container elements — also become individual blocks, but their
# inner HTML is preserved verbatim (we don't try to split them by
# recognized sub-tags). They are still first-level blocks.
#
# Rule: Any tag at the first level of body HTML becomes a block.
# The block's content is the tag's full HTML (including children,
# attributes, classes — nothing is lost).
_CONTAINERS_THAT_BECOME_BLOCKS = frozenset({
    "div", "section", "article", "main",
    "header", "footer", "nav", "aside", "figure",
    "span",  # spans can also be first-level (e.g. math-inline)
})

# Void (self-closing) elements
_VOID_TAGS = frozenset({
    "img", "br", "hr", "input", "meta", "link", "area",
    "base", "col", "embed", "param", "source", "track", "wbr",
})

# Tags whose content should be skipped entirely during body parsing
_SKIP_TAGS = frozenset({
    "script", "style", "head", "title", "meta", "link", "noscript",
})


class _ImgAttrParser(HTMLParser):
    """Extract attributes from the first <img> tag."""
    def __init__(self):
        super().__init__()
        self.attrs = {}
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img" and not self.attrs:
            self.attrs = dict(attrs)


# ---------------------------------------------------------
# Escaping helpers
# ---------------------------------------------------------

def _escape_attr(value):
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def _escape_text(text):
    return _html.escape(text, quote=False)


# ---------------------------------------------------------
# CSS body-rule stripping (rule 3)
# ---------------------------------------------------------

_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)


def _remove_css_rule(key:str,css: str) -> str:
    """
    Remove CSS rules whose selector list includes 'body'.
    Handles comma-separated selectors by keeping the non-body ones.
    """
    if not css: return ""

    def replacer(match):
        selector_list = match.group(1)
        declarations = match.group(2)
        selectors = [s.strip() for s in selector_list.split(",")]
        
        kept = [s for s in selectors if not re.match(rf"^{key}(?:[.:#\[<\s]|$)", s)]

        if not kept: return ""

        return ", ".join(kept) + " {" + declarations + "}"

    return _CSS_RULE_RE.sub(replacer, css)


# CSS class renaming (rule 2/4 conflict avoidance)
def _rename_classes_in_css(css: str, prefix: str = "usr-", skip_block: bool = False):
    # Rename .page → .usr-page etc. in CSS selectors.
    renamed = []
    for cls in _PRESERVED_CLASSES:

        if skip_block and cls == "block": continue
        
        if "." + cls in css: 
            css = css.replace("." + cls, "." + prefix + cls)
            renamed.append(cls)

    return css, renamed


def _rename_classes_in_html(html_str: str, classes:list, prefix: str = "usr-", skip_block: bool = False) -> str:
    
    # Rename class="page" → class="usr-page" etc. in HTML.
    def replacer(match):
        classes_ = match.group(1).split()
        renamed = []
        for c in classes_:
            if c in classes:
                if skip_block and c == "block":
                    renamed.append(c)  # keep as-is
                else:
                    renamed.append(prefix + c)
            else:
                renamed.append(c)

        return 'class="' + " ".join(renamed) + '"'

    return re.sub(r'class="([^"]*)"', replacer, html_str)


# ---------------------------------------------------------
# Head metadata extraction (regex-based)
# ---------------------------------------------------------
def _extract_all_styles(html_str: str) -> str:
    """Extract CSS from all <style> tags in the document."""
    # List of all tags with <style ...
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html_str, re.DOTALL | re.IGNORECASE)

    return "\n".join(styles)


def _extract_inline_scripts(html_str: str) -> list:
    """Extract ScriptEntry list from all <script> tags."""
    scripts = []
    
    for match in re.finditer(r"<script([^>]*)>(.*?)</script>", html_str, re.DOTALL | re.IGNORECASE):
        attrs_str = match.group(1)
        inline = match.group(2)
        src_match = re.search(r'src="([^"]*)"', attrs_str)
        
        if src_match:
            pass#scripts.append(ScriptEntry(src=src_match.group(1)))
        elif inline.strip():
            scripts.append(ScriptEntry(inline=inline))
    
    return scripts


def _extract_abdh_meta(html_str: str):
    # Extract version and page_system from abdh-document meta tag."""
    match = re.search(r'<meta\s+[^>]*name="abdh-document"[^>]*content="([^"]*)"', html_str, re.IGNORECASE)
    
    if not match: return None, None
    
    content = match.group(1)
    version = None
    page_system = None
    
    for part in content.split(";"):
        part = part.strip()
        
        if "=" not in part: continue
        
        key, _, value = part.partition("=")
        key = key.strip().lower()
        value = value.strip()
        
        if key == "version": version = value
        elif key == "page-system": page_system = value

    return version, page_system


# ---------------------------------------------------------
# Body extraction (regex + parser-based)
# ---------------------------------------------------------

class _PageContentExtractor(HTMLParser):
    """
    Find ALL <div class="page-content"> elements and extract their
    inner HTML. Handles multiple .page-content divs (e.g. multi-page
    saved documents) and arbitrary nesting depth.

    The editor saves documents with this structure:
        <div id="editor">
          <div class="pages-wrapper">
            <div class="page" data-page="0">
              <div class="page-content"> ... blocks ... </div>
            </div>
            <div class="page" data-page="1">
              <div class="page-content"> ... blocks ... </div>
            </div>
          </div>
        </div>

    This extractor pulls out the content of EVERY .page-content div
    and concatenates them, so the block extractor sees a flat stream
    of top-level tags regardless of how many pages were saved.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []      # one string per .page-content div
        self._depth = 0          # >0 when inside a .page-content div
        self._buffer = []        # accumulates inner HTML

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        element_class = attrs_dict.get("class", "")
        class_tokens = element_class.split() if element_class else []

        if self._depth > 0:
            # Already inside .page-content — capture everything
            self._buffer.append(self._reconstruct_tag(tag, attrs))
            if tag not in _VOID_TAGS:
                self._depth += 1
        elif tag == "div" and "page-content" in class_tokens:
            # Entering a .page-content div — start capturing (skip the
            # .page-content div itself, only capture its children)
            self._depth = 1
            self._buffer = []

    def handle_startendtag(self, tag, attrs):
        if self._depth > 0:
            self._buffer.append(self._reconstruct_tag(tag, attrs))

    def handle_endtag(self, tag):
        if self._depth > 0:
            if tag in _VOID_TAGS:
                return
            self._depth -= 1
            if self._depth == 0:
                # End of .page-content div — flush buffer
                self.fragments.append("".join(self._buffer))
                self._buffer = []
            else:
                self._buffer.append(f"</{tag}>")

    def handle_data(self, data):
        if self._depth > 0:
            self._buffer.append(data)

    def _reconstruct_tag(self, tag, attrs):
        parts = [tag]
        for k, v in attrs:
            if v is None:
                parts.append(k)
            else:
                parts.append(f'{k}="{_escape_attr(v)}"')
        return "<" + " ".join(parts) + ">"

    def get_content(self):
        """Return concatenated content of all .page-content divs,
        or None if none were found."""
        if self.fragments:
            return "\n".join(self.fragments)
        return None


def _extract_body(html_str: str) -> str:
    """
    Extract body content from an HTML document.

    Pipeline:
      1. Get content between <body> and </body>
      2. Strip editor structural elements (#loading-overlay, #context-menu)
      3. If .page-content divs exist → extract & concatenate their content
         Otherwise → use the body HTML as-is

    The .page-content extraction uses a proper HTML parser
    (_PageContentExtractor) to handle arbitrary nesting depth and
    multiple .page-content divs (e.g. multi-page saved documents).
    """
    match = re.search(
        r"<body[^>]*>(.*?)</body>", html_str, re.DOTALL | re.IGNORECASE
    )
    if match:
        body = match.group(1)
    else:
        # No <body> tag — strip <head> and return the rest
        body = re.sub(
            r"<head[^>]*>.*?</head>", "", html_str,
            flags=re.DOTALL | re.IGNORECASE,
        )
        body = re.sub(r"</?html[^>]*>", "", body, flags=re.IGNORECASE)

    # Strip editor structural elements if present (saved by editor)
    # Remove #loading-overlay (has nested divs)
    body = re.sub(
        r'<div\s+id="loading-overlay"[^>]*>.*?</div>\s*</div>\s*</div>',
        '', body, flags=re.DOTALL | re.IGNORECASE
    )
    # Remove #context-menu
    body = re.sub(
        r'<div\s+id="context-menu"[^>]*>.*?</div>',
        '', body, flags=re.DOTALL | re.IGNORECASE
    )

    # ── Extract .page-content (handles multiple divs + nesting) ──
    extractor = _PageContentExtractor()
    try:
        extractor.feed(body)
        extractor.close()
    except Exception:
        pass

    page_content = extractor.get_content()
    if page_content:
        return page_content

    # No .page-content found — return body as-is
    return body


# ---------------------------------------------------------
# Math formula detection and extraction
# ---------------------------------------------------------
# Detects LaTeX formulas in paragraphs using common delimiters:
#   Block-level: $$ ... $$ or \[ ... \]
#   Inline: $ ... $ or \( ... \)
# Creates Math blocks for formulas and splits paragraphs as needed.

def _extract_formulas_from_html(html_str: str) -> list:
    """
    Extract all math formulas from HTML content.
    
    Returns list of dicts: {
        'formula': str,     # The formula content
        'is_inline': bool,  # True for inline ($...$), False for block ($$...$$)
        'start': int,       # Position in html_str
        'end': int,         # Position in html_str
        'delimiter': str,   # The delimiter used ($$, $, \\[, \\()
    }
    """
    formulas = []
    i = 0
    html_len = len(html_str)
    
    while i < html_len:
        # Check for block-level delimiters first
        if i < html_len - 1 and html_str[i:i+2] == "$$":
            # Block formula: $$ ... $$
            end = html_str.find("$$", i + 2)
            if end != -1:
                formulas.append({
                    'formula': html_str[i+2:end],
                    'is_inline': False,
                    'start': i,
                    'end': end + 2,
                    'delimiter': '$$',
                })
                i = end + 2
                continue
        
        if i < html_len - 1 and html_str[i:i+2] == "\\[":
            # Block formula: \[ ... \]
            end = html_str.find("\\]", i + 2)
            if end != -1:
                formulas.append({
                    'formula': html_str[i+2:end],
                    'is_inline': False,
                    'start': i,
                    'end': end + 2,
                    'delimiter': '\\[',
                })
                i = end + 2
                continue
        
        if html_str[i] == "$":
            # Check it's not part of $$ (already handled above)
            if i + 1 < html_len and html_str[i+1] == "$":
                i += 1
                continue
            
            # Inline formula: $ ... $
            # Only match if not preceded or followed by whitespace (to avoid false positives)
            end = html_str.find("$", i + 1)
            if end != -1:
                # Avoid matching $...$ across HTML tags or in attributes
                segment = html_str[i+1:end]
                if "$" not in segment and "<" not in segment:
                    formulas.append({
                        'formula': segment,
                        'is_inline': True,
                        'start': i,
                        'end': end + 1,
                        'delimiter': '$',
                    })
                    i = end + 1
                    continue
        
        if i < html_len - 1 and html_str[i:i+2] == "\\(":
            # Inline formula: \( ... \)
            end = html_str.find("\\)", i + 2)
            if end != -1:
                formulas.append({
                    'formula': html_str[i+2:end],
                    'is_inline': True,
                    'start': i,
                    'end': end + 2,
                    'delimiter': '\\(',
                })
                i = end + 2
                continue
        
        i += 1
    
    return formulas


def _convert_formula_paragraph(paragraph: Paragraph) -> list:
    """
    Check if a Paragraph contains math formulas.
    If so, split it into multiple blocks (Paragraph and MathBlock).
    Returns list of blocks.
    """
    html_content = paragraph.html
    
    formulas = _extract_formulas_from_html(html_content)
    
    if not formulas:
        return [paragraph]
    
    blocks = []
    last_end = 0
    
    for formula_info in formulas:
        start = formula_info['start']
        end = formula_info['end']
        
        # Add text before formula if any
        if start > last_end:
            before = html_content[last_end:start]
            # Wrap in paragraph if not empty
            if before.strip():
                blocks.append(Paragraph(html=f"<p>{before}</p>", id=paragraph.id))
        
        # Add Math block
        blocks.append(MathBlock(
            content=formula_info['formula'],
            is_inline=formula_info['is_inline'],
            id=f"{paragraph.id}_math"  # Generate related ID
        ))
        
        last_end = end
    
    # Add remaining text after last formula
    if last_end < len(html_content):
        after = html_content[last_end:]
        if after.strip():
            blocks.append(Paragraph(html=f"<p>{after}</p>", id=paragraph.id))
    
    return blocks if blocks else [paragraph]


def _process_math_blocks(blocks: list) -> list:
    """
    Post-process blocks to extract math formulas from paragraphs.
    Replaces Paragraph blocks containing formulas with mixed blocks.
    """
    result = []
    for block in blocks:
        if isinstance(block, Paragraph):
            result.extend(_convert_formula_paragraph(block))
        else:
            result.append(block)
    return result


class _BlockExtractor(HTMLParser):
    """
    Walks body HTML and emits ONE block per top-level tag.

    RULES (per the editor's block model):
      1. Any tag at the first level of body HTML becomes a block.
         This includes container tags (div, section, article, ...)
         as well as content tags (p, h1, ul, table, ...).
      2. A block's HTML is the tag's FULL verbatim HTML, including
         all children, attributes, classes, ids — nothing is lost.
         We NEVER descend into containers and we NEVER wrap children
         in <p>. The editor's pagination handles overflow by
         splitting at runtime; the loader does not split.
      3. If a tag is already a `<div class="block" data-id="..."
         data-type="...">` (i.e. previously saved by the editor),
         preserve its data-id and data-type instead of generating
         new ones. The class name "block" is the editor's own
         marker — treat it as structural, not user-styling.
      4. <img> at the top level becomes an Image block.
      5. Tags inside <script>, <style>, #loading-overlay,
         #context-menu, .page-content are skipped (those are
         editor chrome, not document content).
      6. Loose text at the top level (not inside any tag) is
         wrapped in <p>...</p> and becomes a Paragraph block.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        # When capturing a top-level tag, holds:
        #   [tag, buffer, depth, attrs_dict, existing_id, existing_type]
        # `depth` counts nested instances of the same tag so we know
        # which </tag> closes the top-level one.
        # `existing_id` / `existing_type` are set when the tag is
        # already an editor block div (preserved verbatim).
        self._capture = None
        self._skip_depth = 0   # >0 when inside script/style/etc.

    # ───────────────────────────────────────────────────────
    # Start tags
    # ───────────────────────────────────────────────────────
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return

        attrs_dict = dict(attrs)
        element_id = attrs_dict.get("id", "")
        element_class = attrs_dict.get("class", "")

        # Skip editor structural elements entirely
        if element_id in ("loading-overlay", "context-menu") or \
           "page-content" in element_class:
            self._skip_depth += 1
            return

        # If we're already capturing a top-level tag, this tag is
        # nested inside it — append its raw HTML to the buffer and
        # bump depth if it matches the captured tag (so we know
        # which </tag> closes the top-level element).
        if self._capture is not None:
            self._capture[1].append(self._reconstruct_tag(tag, attrs))
            if tag == self._capture[0] and tag not in _VOID_TAGS:
                self._capture[2] += 1
            return

        # ── Top-level tag → start capturing ──
        # Every top-level tag (including div/section/article/etc.)
        # becomes a block. We do NOT descend into containers.

        # Check if this is already an editor block div
        # (preserved data-id and data-type)
        existing_id = ""
        existing_type = ""
        # tag in ["div", "section", "all containers"]
        if "block" in element_class.split():# and tag == "div":
            existing_id = attrs_dict.get("data-id", "")
            existing_type = attrs_dict.get("data-type", "")

        # Void tags (img, hr, etc.) — emit immediately, no closing tag
        if tag in _VOID_TAGS:
            if tag == "img":
                self._emit_image(attrs)
            else:
                # Other void tags (hr, br, input, ...) become a
                # Paragraph block with their raw HTML.
                raw = self._reconstruct_tag(tag, attrs)
                self.blocks.append(Paragraph(
                    html=raw,
                    id=existing_id or None,
                ))
                if existing_id:
                    self.blocks[-1].id = existing_id
            return

        # Start capturing a non-void top-level tag
        self._capture = [
            tag,
            [self._reconstruct_tag(tag, attrs)],
            0,            # depth (nested same-tag count)
            attrs_dict,
            existing_id,
            existing_type,
        ]

    def handle_startendtag(self, tag, attrs):
        """Self-closing tag like <img /> or <br/>."""
        tag = tag.lower()
        if self._skip_depth > 0:
            return

        # If we're inside a captured block, just append the raw tag.
        if self._capture is not None:
            self._capture[1].append(self._reconstruct_tag(tag, attrs))
            return

        # Top-level self-closing tag
        attrs_dict = dict(attrs)
        if tag == "img":
            self._emit_image(attrs)
        else:
            raw = self._reconstruct_tag(tag, attrs)
            self.blocks.append(Paragraph(html=raw))

    # ───────────────────────────────────────────────────────
    # End tags
    # ───────────────────────────────────────────────────────
    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in _VOID_TAGS:
            return  # void tags don't have end tags
        if self._capture is None:
            return  # stray end tag, ignore

        # Append the closing tag to the buffer
        self._capture[1].append(f"</{tag}>")

        # If this closes the top-level captured tag, emit the block
        if tag == self._capture[0]:
            if self._capture[2] == 0:
                self._emit_block()
            else:
                self._capture[2] -= 1

    # ───────────────────────────────────────────────────────
    # Text data
    # ───────────────────────────────────────────────────────
    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._capture is not None:
            # Inside a captured block — preserve text verbatim
            self._capture[1].append(data)
        elif data.strip():
            # Loose top-level text → wrap in <p> and emit as Paragraph
            self.blocks.append(Paragraph(
                html=f"<p>{_escape_text(data.strip())}</p>"
            ))

    # ───────────────────────────────────────────────────────
    # Helpers
    # ───────────────────────────────────────────────────────
    def _reconstruct_tag(self, tag, attrs):
        parts = [tag]
        for k, v in attrs:
            if v is None:
                parts.append(k)
            else:
                parts.append(f'{k}="{_escape_attr(v)}"')
        return "<" + " ".join(parts) + ">"

    def _emit_block(self):
        """Emit the captured tag as a Block."""
        tag, buffer, _, attrs_dict, existing_id, existing_type = self._capture
        html_str = "".join(buffer)
        self._capture = None

        # If this was already an editor block (data-id + data-type
        # set), preserve those. Otherwise dispatch by tag/content.

        # Image block (data-type="Image")
        if existing_type == "Image":
            # The inner <img> is what matters — parse it
            img = self._parse_inner_image(html_str)
            if img is not None:
                img.id = existing_id or img.id
                img.outer_html = html_str  # preserve full structure
                self.blocks.append(img)
                return
            # Fallback: treat as Paragraph with the full HTML
            p = Paragraph(html=html_str)
            if existing_id: p.id = existing_id
            self.blocks.append(p)
            return

        # Math block (data-type="Math")
        if existing_type == "Math":
            math = self._parse_inner_math(html_str)
            if math is not None:
                math.id = existing_id or math.id
                math.outer_html = html_str
                self.blocks.append(math)
                return
            p = Paragraph(html=html_str)
            if existing_id: p.id = existing_id
            self.blocks.append(p)
            return

        # Table block (data-type="Table" or tag is <table>)
        if existing_type == "Table" or tag == "table":
            t = Table(html=html_str)
            if existing_id: t.id = existing_id
            t.outer_html = html_str if existing_type == "Table" else ""
            self.blocks.append(t)
            return

        # Already-typed block we don't recognize (e.g. RawBlock from
        # a previous save) → preserve as Paragraph with outer_html
        if existing_type and existing_type not in (
            "Paragraph", "Image", "Math", "Table"
        ):
            from .block import RawBlock
            rb = RawBlock(raw_type=existing_type, html=html_str)
            if existing_id: rb.id = existing_id
            rb.outer_html = html_str
            self.blocks.append(rb)
            return

        # Default: Paragraph with full verbatim HTML
        # (handles p, h1-h6, ul, ol, blockquote, pre, div, section,
        #  article, and any other tag — all preserve their content)
        p = Paragraph(html=html_str)
        if existing_id: p.id = existing_id
        # If this was an editor block, preserve outer_html so the
        # renderer outputs it verbatim (no re-wrapping).
        if existing_type == "Paragraph":
            p.outer_html = html_str
        self.blocks.append(p)

    def _emit_image(self, attrs):
        """Emit a top-level <img> as an Image block."""
        attr_dict = dict(attrs)
        src = attr_dict.get("src", "")

        # Convert local file paths to base64 data URLs so images
        # are embedded in the document and don't break if the file
        # is moved or deleted.
        if src and not src.startswith(
            ("data:", "http://", "https://", "blob:")
        ):
            converted = _file_to_data_url(src)
            if converted:
                src = converted

        self.blocks.append(Image(
            src=src,
            alt=attr_dict.get("alt", ""),
            width=attr_dict.get("width", ""),
            height=attr_dict.get("height", ""),
            img_style=attr_dict.get("style", ""),
        ))

    def _parse_inner_image(self, html_str):
        """Extract an Image block from a <div class='block'> wrapper."""
        parser = _ImgAttrParser()
        try:
            parser.feed(html_str)
        except Exception:
            return None
        if not parser.attrs:
            return None
        src = parser.attrs.get("src", "")
        if src and not src.startswith(
            ("data:", "http://", "https://", "blob:")
        ):
            converted = _file_to_data_url(src)
            if converted:
                src = converted
        return Image(
            src=src,
            alt=parser.attrs.get("alt", ""),
            width=parser.attrs.get("width", ""),
            height=parser.attrs.get("height", ""),
            img_style=parser.attrs.get("style", ""),
        )

    def _parse_inner_math(self, html_str):
        """Extract a MathBlock from a <div class='math-block'> wrapper."""
        import re as _re
        is_inline = "math-inline" in html_str
        match = _re.search(r'data-formula="([^"]*)"', html_str)
        if not match:
            return None
        formula = match.group(1).replace("&quot;", '"')
        return MathBlock(content=formula, is_inline=is_inline)


# NOTE: The previous _BlockExtractor (which only captured _BLOCK_TAGS and
# descended into <div> containers) has been removed. It could not recognise
# editor-saved wrappers like <div class="block" data-type="Math">, so on
# reload the rendered KaTeX HTML inside .math-block was flattened into
# dozens of stray <p> paragraphs and the MathBlock was lost.
# _BlockExtractor0 above already handles this correctly (it captures ANY
# top-level tag as a block and dispatches on data-type), so it has been
# promoted to be the canonical _BlockExtractor.

# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def html_file_to_document(path, allow_scripts: bool = False) -> Document:
    """Load an HTML file and return a Document."""
    path = Path(path)

    html_text = path.read_text(encoding="utf-8-sig")

    return html_string_to_document(html_text, allow_scripts=allow_scripts)


# ---------------------------------------------------------
# Smart HTML-tags-to-blocks parser
# ---------------------------------------------------------

def _get_root_tag_name(html_str):
    """Return the tag name of the single root element, or None."""
    s = html_str.strip()
    # Find the first opening tag
    m = re.match(r'<(\w+)', s)
    if not m:
        return None
    tag = m.group(1).lower()
    return tag

def _count_top_level_tags(html_str):
    """
    Count how many top-level elements exist in the HTML string.
    Returns (count, first_tag_name).

    A "top-level element" is one that is not nested inside any other
    element. Void tags (img, hr, etc.) inside a parent element are
    NOT top-level — they belong to their parent.
    """
    s = html_str.strip()
    if not s:
        return (0, None)

    depth = 0
    count = 0
    first_tag = None
    i = 0
    while i < len(s):
        if s[i] == '<':
            if i + 1 < len(s) and s[i+1] == '/':
                depth -= 1
            elif i + 1 < len(s) and s[i+1] == '!':
                pass  # comment or doctype
            else:
                m = re.match(r'<(\w+)', s[i:])
                if m:
                    tag = m.group(1).lower()
                    if tag in _VOID_TAGS:
                        # Void tag — only top-level if depth == 0
                        if depth == 0:
                            count += 1
                            if first_tag is None:
                                first_tag = tag
                    else:
                        depth += 1
                        if depth == 1:
                            count += 1
                            if first_tag is None:
                                first_tag = tag
        i += 1

    return (count, first_tag)

def _parse_single_tag_to_block(html_str):
    """
    Parse a single-root HTML string into a Block.

    Used by Pipeline 2 (load_blocks) — each item in the html_list
    is treated as one block. The full HTML is preserved verbatim
    so no attributes, classes, or children are lost.

    Detection order:
      1. Existing editor block <div class="block" data-id="..."
         data-type="..."> → preserve id, type, and outer_html
      2. <img> → Image
      3. <table> → Table
      4. <span class="math-inline"> or <div class="math-block"> → MathBlock
      5. Everything else → Paragraph (full HTML preserved)
    """
    s = html_str.strip()
    tag = _get_root_tag_name(s)

    # Extract ONLY the root tag's attributes
    root_tag_match = re.match(r'<\w+([^>]*)>', s)
    root_attrs = root_tag_match.group(1) if root_tag_match else ""

    # ── 1. Existing editor block (data-id + data-type set) ──
    # The user passed in an already-structured block — preserve it.
    has_block_class = 'class="block"' in root_attrs or \
                      "class='block'" in root_attrs or \
                      'class="block ' in root_attrs or \
                      "class='block " in root_attrs
    if has_block_class and tag == "div":
        id_match = re.search(r'data-id="([^"]*)"', root_attrs)
        type_match = re.search(r'data-type="([^"]*)"', root_attrs)
        existing_id = id_match.group(1) if id_match else ""
        existing_type = type_match.group(1) if type_match else ""

        if existing_type == "Image":
            # Parse inner <img>
            parser = _ImgAttrParser()
            try: parser.feed(s)
            except Exception: pass
            src = parser.attrs.get("src", "")
            if src and not src.startswith(("data:", "http://", "https://", "blob:")):
                converted = _file_to_data_url(src)
                if converted: src = converted
            img = Image(
                src=src,
                alt=parser.attrs.get("alt", ""),
                width=parser.attrs.get("width", ""),
                height=parser.attrs.get("height", ""),
                img_style=parser.attrs.get("style", ""),
            )
            if existing_id: img.id = existing_id
            img.outer_html = s
            return img

        if existing_type == "Math":
            is_inline = "math-inline" in s
            formula_match = re.search(r'data-formula="([^"]*)"', s)
            formula = formula_match.group(1).replace("&quot;", '"') if formula_match else ""
            math = MathBlock(content=formula, is_inline=is_inline)
            if existing_id: math.id = existing_id
            math.outer_html = s
            return math

        if existing_type == "Table":
            t = Table(html=s)
            if existing_id: t.id = existing_id
            t.outer_html = s
            return t

        if existing_type and existing_type not in (
            "Paragraph", "Image", "Math", "Table"
        ):
            from .block import RawBlock
            rb = RawBlock(raw_type=existing_type, html=s)
            if existing_id: rb.id = existing_id
            rb.outer_html = s
            return rb

        # Paragraph with preserved id + outer_html
        p = Paragraph(html=s)
        if existing_id: p.id = existing_id
        p.outer_html = s
        return p

    # ── 2. Top-level <img> ──
    if tag == "img":
        parser = _ImgAttrParser()
        try:
            parser.feed(s)
        except Exception:
            pass
        src = parser.attrs.get("src", "")
        if src and not src.startswith(("data:", "http://", "https://", "blob:")):
            converted = _file_to_data_url(src)
            if converted:
                src = converted
        return Image(
            src=src,
            alt=parser.attrs.get("alt", ""),
            width=parser.attrs.get("width", ""),
            height=parser.attrs.get("height", ""),
            img_style=parser.attrs.get("style", ""),
        )

    # ── 3. Top-level <table> ──
    if tag == "table":
        return Table(html=s)

    # ── 4. Math blocks (by class on root tag) ──
    if 'class="math-block"' in root_attrs or "class='math-block'" in root_attrs:
        match = re.search(r'data-formula="([^"]*)"', root_attrs)
        formula = match.group(1).replace("&quot;", '"') if match else ""
        return MathBlock(content=formula, is_inline=False)

    if 'class="math-inline"' in root_attrs or "class='math-inline'" in root_attrs:
        match = re.search(r'data-formula="([^"]*)"', root_attrs)
        formula = match.group(1).replace("&quot;", '"') if match else ""
        return MathBlock(content=formula, is_inline=True)

    # ── 5. Default: Paragraph with full verbatim HTML ──
    # Preserves p, h1-h6, ul, ol, blockquote, pre, div, section,
    # article, and any other tag — full content, no re-wrapping.
    return Paragraph(html=s)

def html_tags_to_document(html_list:list[str], custom_css="", custom_scripts=None,
                          allow_scripts=False, preserve_block_class=False) -> Document:
    """
    Pipeline 2 entry point — create a Document from pre-made HTML blocks.

    Starts at the 'create document' step of Pipeline 1:
      - CSS is provided directly (strip :root and body rules)
      - Scripts are provided directly
      - Blocks are created from the html_list (one block per top-level tag)
    """

    # Process CSS — strip :root and body rules, then rename conflicting classes
    processed_css = _remove_css_rule("body", custom_css or "")
    processed_css = _remove_css_rule(":root", processed_css)

    processed_css, renamed = _rename_classes_in_css(processed_css, skip_block=preserve_block_class)
    doc = Document()

    for item in (html_list or []):

        if not isinstance(item, str): continue
        
        item = item.strip()
        
        if not item: continue

        # Rename preserved CSS classes in the HTML
        item = _rename_classes_in_html(item, renamed, skip_block= preserve_block_class)

        count, first_tag = _count_top_level_tags(item)

        if count == 1:
            # Single root tag — parse directly
            block = _parse_single_tag_to_block(item)
            doc.append(block)
        elif count > 1:
            # Multiple top-level tags — wrap in <div>
            wrapped = f"<div>{item}</div>"
            doc.append(Paragraph(html=wrapped))
        else:
            # Plain text or void element — wrap in <p>
            doc.append(Paragraph(html=f"<p>{item}</p>"))

    doc.metadata.custom_css = processed_css
    # Process scripts
    doc.metadata.scripts = []
    doc.metadata.allow_scripts = allow_scripts

    if custom_scripts:
        if isinstance(custom_scripts, str):
            doc.metadata.scripts.append(ScriptEntry(inline=custom_scripts))
        elif isinstance(custom_scripts, list):
            for entry in custom_scripts:
                if isinstance(entry, dict):
                    doc.metadata.scripts.append(ScriptEntry(
                        src=entry.get("src", ""),
                        inline=entry.get("inline", "")
                    ))
                elif isinstance(entry, ScriptEntry):
                    doc.metadata.scripts.append(entry)

    return doc

def html_string_to_document(html_str: str, allow_scripts: bool = False, preserve_block_class= True) -> Document:
    """
    Pipeline 1 entry point — create a Document from a full HTML string.

    Steps:
      1. Extract abdh-document <meta>
      2. Extract CSS from <style> tags, strip :root and body rules
      3. Extract inline scripts
      4. Extract body content (from .page-content divs if present)
      5. Rename conflicting CSS classes
      6. Split body into blocks (one block per top-level tag)
      7. Extract math formulas from paragraphs
      8. Build Document with metadata
    """

    version, page_system = _extract_abdh_meta(html_str)
    
    # The preserved styles is linked by <link id="preserved-style" rel="stylesheet" href="style.css">
    # Therefore all results of this query is user styles, this ecures for external files while user opens.
    # NOTE: returned "raw_css" does not has <style ...> tag
    raw_css = _extract_all_styles(html_str)
    # Strip :root and body rules — the editor owns these selectors
    custom_css = _remove_css_rule("body", raw_css)
    custom_css = _remove_css_rule(":root", custom_css)
    # All rules scaned for duplication and renamed if exists duplicated name with built-in rules.
    custom_css, renamed = _rename_classes_in_css(css= custom_css, skip_block= preserve_block_class)

    # The built-in scripts is linked by <script src="script.js"></script>, thus all results of this
    # query are external scripts.
    custom_scripts = _extract_inline_scripts(html_str)

    # Body extraction + class renaming
    body_html = _extract_body(html_str)
    
    body_html = _rename_classes_in_html(html_str=body_html,classes= renamed, skip_block= preserve_block_class)
    # Split into blocks
    parser = _BlockExtractor()
    parser.feed(body_html)
    parser.close()

    # Extract math formulas from paragraphs
    blocks = _process_math_blocks(parser.blocks)

    # Build document
    doc = Document()
    for block in blocks: doc.append(block)

    doc.metadata.custom_css = custom_css
    doc.metadata.scripts = custom_scripts
    doc.metadata.allow_scripts = allow_scripts

    if version: doc.metadata.version = version
    if page_system: doc.metadata.page_system = page_system
    
    return doc
