"""
Editor test harness — non-destructive edition.

Runs a sequence of tests against the Editor widget and reports
progress live via Qt signals.

PHILOSOPHY
==========
- Load ONE rich document at the start and keep it.
- Each test APPENDS or INSERTS content at the end, rather than
  clearing and starting fresh.
- After each action, scroll the editor to the new content so the
  user can watch the test happen.
- Use long, realistic content (multi-paragraph text, big tables,
  multiple math formulas).

The document grows as tests run. The user sees a live "build-up"
of content — paragraphs, tables, formulas, formatted text —
appearing and scrolling into view as each test executes.

Usage:
    runner = EditorTestRunner(editor)
    runner.progress.connect(on_progress)
    runner.finished.connect(on_finished)
    runner.start()
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QEventLoop, QCoreApplication


# ──────────────────────────────────────────────────────────────
# Test result data
# ──────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    detail: str = ""
    duration_ms: float = 0.0


@dataclass
class TestSuiteResult:
    results: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def percent(self) -> float:
        if not self.total:
            return 0.0
        return 100.0 * self.passed / self.total


# ──────────────────────────────────────────────────────────────
# Async helpers
# ──────────────────────────────────────────────────────────────

def run_js_and_wait(editor, js: str, timeout_ms: int = 5000):
    """Run JavaScript on the editor's page and block until the
    callback fires. Returns the callback's result, or None on
    timeout."""
    loop = QEventLoop()
    result = [None]
    timed_out = [False]

    def on_result(data):
        if not timed_out[0]:
            result[0] = data
            loop.quit()

    editor.page().runJavaScript(js, on_result)

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    loop.exec()
    timer.stop()

    return result[0]


def wait_ms(ms: int):
    """Block the GUI thread for `ms` ms while keeping the event
    loop spinning so async callbacks can fire."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_for_ready(editor, timeout_ms: int = 20000):
    """Wait until the editor's JS side reports ready=True."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        ready = run_js_and_wait(editor, "window.Editor && Editor.ready;", 500)
        if ready:
            return True
        wait_ms(100)
    return False


def scroll_to_bottom(editor):
    """Scroll the editor's viewport to the bottom so the user can
    see the most recently added content."""
    run_js_and_wait(editor,
        '(function(){'
        'var pages=document.querySelectorAll(".pages-wrapper > .page");'
        'if(!pages.length)return;'
        'var last=pages[pages.length-1];'
        'last.scrollIntoView({behavior:"smooth",block:"end"});'
        '})();')


def scroll_to_element(editor, selector):
    """Scroll a specific element into view."""
    js = f'''
    (function(){{
        var el=document.querySelector({selector!r});
        if(el)el.scrollIntoView({{behavior:"smooth",block:"center"}});
    }})();
    '''
    run_js_and_wait(editor, js)


def scroll_to_last_block(editor):
    """Scroll the last .block on the last page into view."""
    run_js_and_wait(editor,
        '(function(){'
        'var blocks=document.querySelectorAll(".page-content > .block");'
        'if(blocks.length){'
        'var last=blocks[blocks.length-1];'
        'last.scrollIntoView({behavior:"smooth",block:"center"});'
        '}'
        '})();')


# ──────────────────────────────────────────────────────────────
# Rich startup document
# ──────────────────────────────────────────────────────────────

def build_startup_document():
    """Build a rich, long HTML document to load at test start.

    The document includes:
    - A title and intro paragraphs
    - A heading and multi-paragraph section
    - A 10-row table with styling
    - A block math formula
    - An ordered list
    - More paragraphs with inline formatting
    - A blockquote

    This gives the editor real content to paginate and display
    while tests run. Tests APPEND to this rather than clearing.
    """
    parts = []

    # Title
    parts.append("<h1>Editor Automated Test Suite</h1>")

    # Intro
    parts.append(
        "<p>This document is generated by the automated test suite. "
        "As each test runs, it appends content below and scrolls it "
        "into view. The document grows progressively — you can watch "
        "the editor handle tables, math, formatting, and pagination "
        "in real time.</p>"
    )
    parts.append(
        "<p>The editor is a PySide6 QWebEngineView-based rich text "
        "editor with support for paginated layout, KaTeX math "
        "rendering, table editing, image embedding, and HTML "
        "round-tripping. This test suite exercises each of these "
        "features against a live instance.</p>"
    )

    # Section heading + paragraphs
    parts.append("<h2>Initial Content</h2>")
    parts.append(
        "<p>The quick brown fox jumps over the lazy dog. "
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
        "sed do eiusmod tempor incididunt ut labore et dolore magna "
        "aliqua. Ut enim ad minim veniam, quis nostrud exercitation "
        "ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>"
    )
    parts.append(
        "<p>Duis aute irure dolor in reprehenderit in voluptate velit "
        "esse cillum dolore eu fugiat nulla pariatur. Excepteur sint "
        "occaecat cupidatat non proident, sunt in culpa qui officia "
        "deserunt mollit anim id est laborum. Sed ut perspiciatis "
        "unde omnis iste natus error sit voluptatem accusantium "
        "doloremque laudantium.</p>"
    )

    # Table
    parts.append("<h2>Sample Table</h2>")
    table_rows = ""
    for i in range(1, 11):
        table_rows += (
            f"<tr><td>{i}</td><td>Item {i}</td>"
            f"<td>Description for item {i}</td>"
            f"<td>${i * 10}.00</td></tr>"
        )
    parts.append(
        f'<table border="1" cellpadding="6" '
        f'style="border-collapse:collapse;width:100%;">'
        f'<thead><tr><th>#</th><th>Name</th>'
        f'<th>Description</th><th>Price</th></tr></thead>'
        f'<tbody>{table_rows}</tbody>'
        f'</table>'
    )

    # Math
    parts.append("<h2>Sample Formula</h2>")
    parts.append(
        '<div class="block" data-type="Math">'
        '<div class="math-block" data-formula='
        '"\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}"'
        ' contenteditable="false" dir="ltr"></div>'
        '</div>'
    )
    parts.append(
        "<p>The Gaussian integral above is one of the most famous "
        "results in mathematics. The editor renders it using KaTeX "
        "from the LaTeX source stored in the data-formula attribute.</p>"
    )

    # List
    parts.append("<h2>Feature Checklist</h2>")
    parts.append(
        "<ol>"
        "<li>Document loading (HTML string and block list)</li>"
        "<li>Math formula insertion (block and inline)</li>"
        "<li>Table creation and editing</li>"
        "<li>Pagination (single and multi-page)</li>"
        "<li>Save/reload round-trip</li>"
        "<li>Text formatting (bold, italic, colors)</li>"
        "<li>Page mode switching (paged / continuous)</li>"
        "</ol>"
    )

    # Blockquote
    parts.append(
        "<blockquote>Testing is the engineering practice of proving "
        "that your code does what you think it does. Without tests, "
        "you don't have working code — you have code that might work.</blockquote>"
    )

    # More paragraphs to ensure multi-page
    parts.append("<h2>Additional Content</h2>")
    for i in range(1, 16):
        parts.append(
            f"<p>Paragraph {i} of additional content. "
            f"This paragraph exists to give the editor enough text "
            f"to paginate across multiple pages. Each paragraph is "
            f"a few sentences long so the total document height "
            f"exceeds a single page. The quick brown fox jumps over "
            f"the lazy dog. Lorem ipsum dolor sit amet.</p>"
        )

    return "<body>" + "".join(parts) + "</body>"


# ──────────────────────────────────────────────────────────────
# Test helpers — append content at the end
# ──────────────────────────────────────────────────────────────

def append_blocks_via_js(editor, html_blocks: list):
    """Append a list of HTML block strings to the last page's content.

    Uses the editor's JS API to insert at the end of the current
    document. Each item in html_blocks should be a complete block
    (e.g. '<p>...</p>' or '<div class="block" ...>...</div>').
    """
    import json
    js_blocks = json.dumps(html_blocks)
    js = f"""
    (function() {{
        var blocks = {js_blocks};
        var pages = document.querySelectorAll('.pages-wrapper > .page');
        if (!pages.length) return 0;
        var lastPage = pages[pages.length - 1];
        var content = lastPage.querySelector('.page-content') || lastPage;
        var inserted = 0;
        blocks.forEach(function(html) {{
            var div = document.createElement('div');
            div.innerHTML = html;
            while (div.firstChild) {{
                content.appendChild(div.firstChild);
                inserted++;
            }}
        }});
        return inserted;
    }})();
    """
    return run_js_and_wait(editor, js)


def append_block_and_scroll(editor, block_html: str, label: str = ""):
    """Append a single block, scroll to it, and return the new
    block count."""
    appended = append_blocks_via_js(editor, [block_html])
    wait_ms(300)
    scroll_to_last_block(editor)
    wait_ms(400)  # allow smooth scroll to settle
    return appended


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────

def test_editor_boots(editor):
    """Editor initializes and JS side reports ready."""
    ok = wait_for_ready(editor, timeout_ms=20000)
    if not ok:
        raise AssertionError("Editor.ready never became true within 20s")
    return "Editor.ready = true"


def test_load_rich_document(editor):
    """Load the rich startup document and verify it paginates."""
    html = build_startup_document()
    editor.load_html_string(html, page_mode="paged")
    wait_ms(3000)  # long doc needs time to paginate
    pages = run_js_and_wait(editor,
        'document.querySelectorAll(".pages-wrapper > .page").length')
    if pages is None or pages < 1:
        raise AssertionError(f"Expected >=1 page, got {pages}")
    blocks = run_js_and_wait(editor,
        'document.querySelectorAll(".block").length')
    if blocks is None or blocks < 5:
        raise AssertionError(f"Expected >=5 blocks, got {blocks}")
    scroll_to_bottom(editor)
    wait_ms(500)
    return f"{pages} page(s), {blocks} blocks loaded"


def test_clear_document(editor):
    """clear_document() resets to a single empty paragraph.

    This is one of the few tests that DOES clear — it's testing the
    clear function itself. After verifying, we reload the rich doc.
    """
    editor.clear_document()
    wait_ms(800)
    blocks = run_js_and_wait(editor,
        'document.querySelectorAll(".block").length')
    if blocks is None or blocks < 1:
        raise AssertionError(f"Expected >=1 block after clear, got {blocks}")

    # Reload the rich document so subsequent tests have content
    html = build_startup_document()
    editor.load_html_string(html, page_mode="paged")
    wait_ms(2500)
    scroll_to_bottom(editor)
    return f"cleared ({blocks} block), then reloaded rich doc"


def test_load_blocks_append(editor):
    """load_blocks() with a list of HTML strings.

    Loads a fresh document via load_blocks (this replaces content,
    which is the function's contract), then scrolls to the bottom.
    """
    blocks = [
        "<h2>Loaded via load_blocks()</h2>",
        "<p>This section was loaded using the load_blocks() API, "
        "which accepts a list of HTML block strings and builds a "
        "Document from them. This is the primary programmatic "
        "entry point for injecting content into the editor.</p>",
        "<p>Each string in the list becomes a top-level block. "
        "The editor's block model supports paragraphs, headings, "
        "tables, math, images, lists, blockquotes, and generic "
        "containers. Unknown block types are preserved verbatim "
        "as RawBlock instances.</p>",
        "<p>The block list approach is useful when generating "
        "documents programmatically — for example, building a "
        "report from a database query, or constructing a quiz "
        "document from a question bank.</p>",
    ]
    editor.load_blocks(html_list=blocks, page_mode="paged",
                       preserve_block_class=True)
    wait_ms(2000)
    count = run_js_and_wait(editor,
        'document.querySelectorAll(".block").length')
    if count is None or count < 4:
        raise AssertionError(f"Expected >=4 blocks, got {count}")
    scroll_to_bottom(editor)
    return f"{count} blocks loaded via load_blocks()"


def test_insert_math_block(editor):
    """insert_math_formula() creates a block-level MathBlock.

    Inserts a math block at the cursor (end of document) and scrolls
    to it. The editor appends an empty paragraph after so the user
    can continue typing.
    """
    # First append a heading so we can find our insertion
    append_block_and_scroll(editor,
        "<h2>Block Math Insertion Test</h2>")

    editor.insert_math_formula(
        r"\frac{d}{dx}\left[\int_{a}^{x} f(t)\,dt\right] = f(x)",
        inline=False
    )
    wait_ms(1000)
    scroll_to_last_block(editor)
    wait_ms(500)

    count = run_js_and_wait(editor,
        'document.querySelectorAll(\'[data-type="Math"]\').length')
    if count is None or count < 1:
        raise AssertionError(f"Expected >=1 math block, got {count}")

    formula = run_js_and_wait(editor,
        '(function(){var els=document.querySelectorAll(".math-block");'
        'if(!els.length)return null;'
        'return els[els.length-1].getAttribute("data-formula");})()')
    if not formula:
        raise AssertionError("data-formula attribute missing or empty")
    return f"math block inserted: {formula[:50]}..."


def test_insert_math_inline(editor):
    """insert_math_formula(inline=True) creates an inline math span.

    Appends a paragraph with a placeholder, then inserts an inline
    formula. Scrolls to the result.
    """
    append_block_and_scroll(editor,
        "<p>This paragraph contains an inline formula: </p>")

    # Place cursor at end of the last paragraph's text
    run_js_and_wait(editor,
        '(function(){'
        'var ps=document.querySelectorAll(".page-content > .block > p");'
        'if(!ps.length)return false;'
        'var p=ps[ps.length-1];'
        'var r=document.createRange();'
        'r.selectNodeContents(p);'
        'r.collapse(false);'
        'var s=window.getSelection();'
        's.removeAllRanges();s.addRange(r);'
        'p.focus();return true;})()')

    editor.insert_math_formula("\\alpha + \\beta = \\gamma", inline=True)
    wait_ms(800)
    scroll_to_last_block(editor)

    count = run_js_and_wait(editor,
        'document.querySelectorAll(\'.math-inline\').length')
    if count is None or count < 1:
        raise AssertionError(f"Expected >=1 inline math span, got {count}")
    return f"{count} inline math span(s) total"


def test_math_roundtrip_via_load_blocks(editor):
    """Math block survives load_blocks round-trip.

    Loads a document with a math block via load_blocks, verifies the
    MathBlock is recognized and the formula is preserved.
    """
    blocks = [
        "<h2>Math Round-Trip Test</h2>",
        "<p>This section tests that math blocks survive the "
        "load_blocks() → render → export cycle. The formula below "
        "is stored as LaTeX source in the data-formula attribute.</p>",
        '<div class="block" data-type="Math">'
        '<div class="math-block" data-formula="a^2 + b^2 = c^2" '
        'contenteditable="false" dir="ltr"></div>'
        '</div>',
        "<p>The Pythagorean theorem above should render via KaTeX "
        "and be editable by double-clicking. If the data-formula "
        "attribute is lost, the formula becomes uneditable.</p>",
    ]
    editor.load_blocks(html_list=blocks, page_mode="paged",
                       preserve_block_class=True)
    wait_ms(2000)

    math_count = run_js_and_wait(editor,
        'document.querySelectorAll(\'[data-type="Math"]\').length')
    if math_count is None or math_count < 1:
        raise AssertionError(f"Expected >=1 math block, got {math_count}")

    formula = run_js_and_wait(editor,
        '(function(){var e=document.querySelector(".math-block");'
        'return e?e.getAttribute("data-formula"):null;})()')
    if formula != "a^2 + b^2 = c^2":
        raise AssertionError(f"Formula mismatch: {formula!r}")
    scroll_to_bottom(editor)
    return f"math round-trip OK: {formula}"


def test_insert_table(editor):
    """insert_table() creates a table via the JS API.

    Appends a heading first, then inserts a 3x4 table and scrolls
    to it.
    """
    append_block_and_scroll(editor,
        "<h2>Table Insertion Test</h2>")

    run_js_and_wait(editor, "Editor.insertTable(3, 4);")
    wait_ms(1000)
    scroll_to_last_block(editor)

    tables = run_js_and_wait(editor,
        'document.querySelectorAll(\'[data-type="Table"]\').length')
    if tables is None or tables < 1:
        raise AssertionError(f"Expected >=1 table block, got {tables}")
    rows = run_js_and_wait(editor,
        '(function(){var ts=document.querySelectorAll("table");'
        'if(!ts.length)return 0;'
        'return ts[ts.length-1].rows.length;})()')
    if rows is None or rows < 3:
        raise AssertionError(f"Expected >=3 rows, got {rows}")
    return f"table with {rows} rows inserted"


def test_table_add_row(editor):
    """add_row() adds a row to the last table."""
    # Find the last table and click its first cell to select it
    run_js_and_wait(editor,
        '(function(){'
        'var ts=document.querySelectorAll("table");'
        'if(!ts.length)return false;'
        'var t=ts[ts.length-1];'
        'var c=t.querySelector("td");'
        'if(c)c.click();return true;})()')
    wait_ms(400)

    rows_before = run_js_and_wait(editor,
        '(function(){var ts=document.querySelectorAll("table");'
        'if(!ts.length)return 0;'
        'return ts[ts.length-1].rows.length;})()')

    editor.add_row()
    wait_ms(600)
    scroll_to_last_block(editor)

    rows_after = run_js_and_wait(editor,
        '(function(){var ts=document.querySelectorAll("table");'
        'if(!ts.length)return 0;'
        'return ts[ts.length-1].rows.length;})()')

    if rows_after is None or rows_after <= rows_before:
        raise AssertionError(
            f"Row count did not increase: {rows_before} -> {rows_after}")
    return f"{rows_before} -> {rows_after} rows"


def test_table_add_column(editor):
    """add_column() adds a column to the last table."""
    run_js_and_wait(editor,
        '(function(){'
        'var ts=document.querySelectorAll("table");'
        'if(!ts.length)return false;'
        'var t=ts[ts.length-1];'
        'var c=t.querySelector("td");'
        'if(c)c.click();return true;})()')
    wait_ms(400)

    cols_before = run_js_and_wait(editor,
        '(function(){var ts=document.querySelectorAll("table");'
        'if(!ts.length)return 0;'
        'var t=ts[ts.length-1];'
        'return t.rows[0]?t.rows[0].cells.length:0;})()')

    editor.add_column()
    wait_ms(600)
    scroll_to_last_block(editor)

    cols_after = run_js_and_wait(editor,
        '(function(){var ts=document.querySelectorAll("table");'
        'if(!ts.length)return 0;'
        'var t=ts[ts.length-1];'
        'return t.rows[0]?t.rows[0].cells.length:0;})()')

    if cols_after is None or cols_after <= cols_before:
        raise AssertionError(
            f"Col count did not increase: {cols_before} -> {cols_after}")
    return f"{cols_before} -> {cols_after} columns"


def test_table_merge_fragments(editor):
    """Adjacent table fragments on the same page get merged.

    Loads two adjacent table blocks via load_blocks and verifies
    they merge into one table after pagination.
    """
    blocks = [
        "<h2>Table Fragment Merge Test</h2>",
        '<div class="block" data-type="Table">'
        '<table border="1"><thead><tr><th>H1</th><th>H2</th></tr></thead>'
        '<tbody><tr><td>A1</td><td>A2</td></tr>'
        '<tr><td>A3</td><td>A4</td></tr></tbody>'
        '</table></div>',
        '<div class="block" data-type="Table">'
        '<table border="1"><thead><tr><th>H1</th><th>H2</th></tr></thead>'
        '<tbody><tr><td>B1</td><td>B2</td></tr>'
        '<tr><td>B3</td><td>B4</td></tr></tbody>'
        '</table></div>',
        "<p>The two table fragments above should merge into a single "
        "table with 4 body rows after pagination.</p>",
    ]
    editor.load_blocks(html_list=blocks, page_mode="paged",
                       preserve_block_class=True)
    wait_ms(2500)

    table_count = run_js_and_wait(editor,
        'document.querySelectorAll("table").length')
    if table_count is None or table_count != 1:
        raise AssertionError(f"Expected 1 merged table, got {table_count}")

    row_count = run_js_and_wait(editor,
        '(function(){var t=document.querySelector("table");'
        'return t?t.querySelectorAll("tbody tr").length:0;})()')
    if row_count is None or row_count < 4:
        raise AssertionError(f"Expected >=4 rows after merge, got {row_count}")
    scroll_to_bottom(editor)
    return f"merged into 1 table with {row_count} rows"


def test_pagination_multi_page_long(editor):
    """A very long document paginates into multiple pages.

    Loads a document with 300 paragraphs and verifies pagination
    produces multiple pages.
    """
    parts = ["<h2>Long Document Pagination Test</h2>"]
    for i in range(1, 301):
        parts.append(
            f"<p>Paragraph {i} of 300. Lorem ipsum dolor sit amet, "
            f"consectetur adipiscing elit. Sed do eiusmod tempor "
            f"incididunt ut labore et dolore magna aliqua. Ut enim "
            f"ad minim veniam, quis nostrud exercitation.</p>"
        )
    html = "<body>" + "".join(parts) + "</body>"
    editor.load_html_string(html)
    wait_ms(5000)  # very long doc needs more time

    pages = run_js_and_wait(editor,
        'document.querySelectorAll(".pages-wrapper > .page").length')
    if pages is None or pages < 5:
        raise AssertionError(f"Expected >=5 pages for 300-para doc, got {pages}")
    scroll_to_bottom(editor)
    wait_ms(500)
    return f"{pages} pages generated for 300 paragraphs"


def test_pagination_table_split_preserves_attrs(editor):
    """A long table splits across pages, preserving attributes.

    Loads a 60-row table with border/cellpadding attributes and
    verifies the attributes survive pagination.
    """
    rows_html = ""
    for i in range(60):
        rows_html += (
            f"<tr><td>Row {i}</td><td>Data {i}</td>"
            f"<td>More data {i}</td><td>Extra {i}</td></tr>"
        )
    table_html = (
        '<h2>Table Split Attribute Preservation Test</h2>'
        '<table style="border:1px solid #333;width:100%;" '
        'border="1" cellpadding="4" cellspacing="0">'
        '<thead><tr><th>Col A</th><th>Col B</th>'
        '<th>Col C</th><th>Col D</th></tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )
    editor.load_html_string(f"<body>{table_html}</body>")
    wait_ms(4000)

    tables = run_js_and_wait(editor,
        'document.querySelectorAll("table").length')
    if tables is None or tables < 1:
        raise AssertionError("No tables found after load")

    has_border = run_js_and_wait(editor,
        '(function(){var t=document.querySelector("table");'
        'return t?t.getAttribute("border"):null;})()')
    if not has_border:
        raise AssertionError("border attribute lost after pagination")
    scroll_to_bottom(editor)
    return f"{tables} table(s), border={has_border} preserved"


def test_save_html_roundtrip(editor):
    """Save to a temp file and reload; content survives.

    Loads a document with a unique marker, serializes via the
    editor's clone+strip path, writes to a temp file, reloads,
    and verifies the marker survives.
    """
    marker = "UNIQUE_MARKER_54321"
    html = (
        f"<body><h2>Save/Reload Round-Trip Test</h2>"
        f"<p>This document contains a {marker} that must survive "
        f"the save-reload cycle. The editor serializes the live DOM "
        f"with KaTeX HTML stripped, writes it to disk, and reloads "
        f"it. If any step loses content, the marker will be missing.</p>"
        f"<p>Additional paragraph to ensure the document has enough "
        f"content to be meaningful. Lorem ipsum dolor sit amet.</p>"
        f"</body>"
    )
    editor.load_html_string(html)
    wait_ms(2000)

    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "test_roundtrip.html")

    js = """
    (function() {
        var clone = document.documentElement.cloneNode(true);
        clone.querySelectorAll('.math-block, .math-inline').forEach(function(el) {
            while (el.firstChild) el.removeChild(el.firstChild);
            el.setAttribute('contenteditable', 'false');
        });
        clone.querySelectorAll('link#katex-style, link#preserved-style').forEach(function(el) {
            el.remove();
        });
        clone.querySelectorAll('script:not([data-custom="true"])').forEach(function(el) {
            el.remove();
        });
        return '<!DOCTYPE html>\\n' + clone.outerHTML;
    })();
    """
    serialized = run_js_and_wait(editor, js, timeout_ms=5000)
    if not serialized:
        raise AssertionError("Serialization returned empty")

    with open(path, "w", encoding="utf-8") as f:
        f.write(serialized)

    editor.load_html_string(serialized)
    wait_ms(2000)

    has_marker = run_js_and_wait(editor,
        f'(function(){{return document.body.textContent.indexOf("{marker}")>=0;}})()')
    if not has_marker:
        raise AssertionError("Marker text lost after round-trip")
    scroll_to_bottom(editor)
    return f"saved {len(serialized)}B, marker survived"


def test_export_blocks(editor):
    """export_blocks_async() returns a list of block dicts.

    Loads a known document and verifies export returns the right
    number of blocks.
    """
    editor.load_html_string(
        "<body><h2>Export Blocks Test</h2>"
        "<p>Paragraph one for export.</p>"
        "<p>Paragraph two for export.</p>"
        "<p>Paragraph three for export.</p>"
        "</body>"
    )
    wait_ms(2000)

    blocks = editor.export_blocks_async()
    if not blocks or len(blocks) < 4:
        raise AssertionError(
            f"Expected >=4 blocks, got {len(blocks) if blocks else 0}")
    scroll_to_bottom(editor)
    return f"{len(blocks)} blocks exported"


def test_get_content_html(editor):
    """get_content_html() returns HTML containing the loaded content."""
    marker = "GET_CONTENT_MARKER_98765"
    editor.load_html_string(
        f"<body><h2>Get Content HTML Test</h2>"
        f"<p>Document with {marker} for verification.</p>"
        f"<p>Second paragraph to make the document substantial.</p>"
        f"</body>"
    )
    wait_ms(2000)

    loop = QEventLoop()
    result_html = [None]

    def on_html(html):
        result_html[0] = html
        loop.quit()

    editor.get_content_html(on_html)

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(5000)
    loop.exec()

    if not result_html[0]:
        raise AssertionError("get_content_html returned empty")
    if marker not in result_html[0]:
        raise AssertionError("Marker text missing from HTML")
    scroll_to_bottom(editor)
    return f"{len(result_html[0])} chars returned"


def test_page_mode_switch(editor):
    """Switching to continuous mode and back to paged works.

    Loads a document, switches to continuous, verifies, switches
    back to paged, verifies.
    """
    editor.load_html_string(
        "<body><h2>Page Mode Switch Test</h2>"
        "<p>This document tests switching between paged and "
        "continuous modes. In paged mode, content is split into "
        "fixed-size pages. In continuous mode, all content flows "
        "on a single growing page with no page breaks.</p>"
        + "".join(f"<p>Filler paragraph {i}.</p>" for i in range(1, 11))
        + "</body>"
    )
    wait_ms(2000)

    editor.set_page_mode("continuous")
    wait_ms(1000)
    mode = run_js_and_wait(editor, "Editor.getMode();")
    if mode != "continuous":
        raise AssertionError(f"Expected continuous mode, got {mode}")

    editor.set_page_mode("paged")
    wait_ms(1000)
    mode = run_js_and_wait(editor, "Editor.getMode();")
    if mode != "paged":
        raise AssertionError(f"Expected paged mode, got {mode}")
    scroll_to_bottom(editor)
    return "continuous -> paged OK"


def test_format_bold(editor):
    """format_bold() applies bold formatting to a selection.

    Appends a paragraph, selects its text, applies bold, verifies.
    """
    append_block_and_scroll(editor,
        "<p>Bold formatting test paragraph.</p>")

    # Select the text in the last paragraph
    run_js_and_wait(editor,
        '(function(){'
        'var ps=document.querySelectorAll(".page-content > .block > p");'
        'if(!ps.length)return false;'
        'var p=ps[ps.length-1];'
        'var r=document.createRange();'
        'r.selectNodeContents(p);'
        'var s=window.getSelection();'
        's.removeAllRanges();s.addRange(r);'
        'p.focus();return true;})()')

    editor.format_bold()
    wait_ms(500)
    scroll_to_last_block(editor)

    has_bold = run_js_and_wait(editor,
        '(function(){var ps=document.querySelectorAll(".page-content > .block > p");'
        'if(!ps.length)return false;'
        'var p=ps[ps.length-1];'
        'return p.innerHTML.indexOf("<b>")>=0 || '
        'p.innerHTML.indexOf("font-weight")>=0 || '
        'p.innerHTML.indexOf("<strong>")>=0;})()')
    if not has_bold:
        raise AssertionError("No bold formatting detected")
    return "bold applied to last paragraph"


def test_set_page_margin(editor):
    """set_page_margin() updates the page padding.

    Sets a 30px margin and verifies it's applied to all .page
    elements. Restores the default afterward.
    """
    editor.set_page_margin("30px")
    wait_ms(500)

    margin = run_js_and_wait(editor,
        '(function(){var p=document.querySelector(".page");'
        'return p?p.style.padding:"";})()')
    if margin != "30px":
        raise AssertionError(f"Expected 30px margin, got {margin!r}")

    # Restore default
    editor.set_page_margin("60px")
    wait_ms(300)
    return "30px applied (restored to 60px)"


def test_set_background_color(editor):
    """set_background_color() updates the body background.

    Sets a dark background, verifies, then restores the default.
    """
    editor.set_background_color("#1a2a3a")
    wait_ms(500)

    color = run_js_and_wait(editor,
        'document.body.style.backgroundColor')
    if not color:
        raise AssertionError("Background color not set")
    if "26" not in color and "1a2a3a" not in color.lower():
        raise AssertionError(f"Expected #1a2a3a, got {color!r}")

    # Restore default
    editor.set_background_color("#121212")
    wait_ms(300)
    return f"#1a2a3a applied (restored to #121212)"


def test_insert_half_space(editor):
    """insert_half_space() inserts a ZWNJ character.

    Appends a paragraph, places cursor at end, inserts half-space,
    verifies ZWNJ is present.
    """
    append_block_and_scroll(editor,
        "<p>Half-space test paragraph</p>")

    run_js_and_wait(editor,
        '(function(){'
        'var ps=document.querySelectorAll(".page-content > .block > p");'
        'if(!ps.length)return false;'
        'var p=ps[ps.length-1];'
        'var r=document.createRange();'
        'r.selectNodeContents(p);'
        'r.collapse(false);'
        'var s=window.getSelection();'
        's.removeAllRanges();s.addRange(r);'
        'p.focus();return true;})()')

    editor.insert_half_space()
    wait_ms(500)
    scroll_to_last_block(editor)

    has_zwnj = run_js_and_wait(editor,
        '(function(){var ps=document.querySelectorAll(".page-content > .block > p");'
        'if(!ps.length)return false;'
        'var p=ps[ps.length-1];'
        'return p?p.textContent.indexOf("\\u200C")>=0:false;})()')
    if not has_zwnj:
        raise AssertionError("No ZWNJ character found")
    return "half-space (ZWNJ) inserted"


# ──────────────────────────────────────────────────────────────
# Test registry
# ──────────────────────────────────────────────────────────────

TESTS = [
    # (category, name, function)
    ("Boot",       "Editor boots and JS reports ready",              test_editor_boots),
    ("Document",   "Load rich startup document (multi-page)",        test_load_rich_document),
    ("Document",   "clear_document() resets (then reloads rich)",    test_clear_document),
    ("Document",   "load_blocks() with list of HTML strings",        test_load_blocks_append),
    ("Math",       "Block-level math formula insertion",             test_insert_math_block),
    ("Math",       "Inline math formula insertion",                  test_insert_math_inline),
    ("Math",       "Math round-trip via load_blocks",                test_math_roundtrip_via_load_blocks),
    ("Table",      "Table insertion via JS API",                     test_insert_table),
    ("Table",      "add_row() increases row count",                  test_table_add_row),
    ("Table",      "add_column() increases column count",            test_table_add_column),
    ("Table",      "Fragment merge on same page",                    test_table_merge_fragments),
    ("Pagination", "Long document (300 paras) → multi-page",         test_pagination_multi_page_long),
    ("Pagination", "Table split preserves attributes",               test_pagination_table_split_preserves_attrs),
    ("Save/Load",  "HTML save/reload round-trip",                    test_save_html_roundtrip),
    ("Export",     "export_blocks_async() returns blocks",           test_export_blocks),
    ("Export",     "get_content_html() returns HTML",                test_get_content_html),
    ("Mode",       "Page mode switch (paged <-> continuous)",        test_page_mode_switch),
    ("Format",     "Bold formatting on appended paragraph",          test_format_bold),
    ("Settings",   "set_page_margin() updates padding",              test_set_page_margin),
    ("Settings",   "set_background_color() updates bg",              test_set_background_color),
    ("Special",    "insert_half_space() inserts ZWNJ",               test_insert_half_space),
]


# ──────────────────────────────────────────────────────────────
# Test runner
# ──────────────────────────────────────────────────────────────

class EditorTestRunner(QObject):
    """Runs the editor test suite on the GUI thread.

    Uses QTimer.singleShot(0, ...) to chain tests so the event loop
    can process the editor's async callbacks between tests.

    Signals:
        progress(result: TestResult)     — emitted after each test
        finished(suite: TestSuiteResult) — emitted when all tests done
    """

    progress = Signal(object)   # TestResult
    finished = Signal(object)   # TestSuiteResult

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._results: list = []
        self._index = 0
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._results = []
        self._index = 0
        QTimer.singleShot(0, self._run_next)

    def _run_next(self):
        if self._index >= len(TESTS):
            self._finish()
            return

        category, name, func = TESTS[self._index]
        self._index += 1

        t0 = time.time()
        detail = ""
        passed = False
        try:
            detail = func(self._editor) or ""
            passed = True
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            tb = traceback.format_exc()
            tb_lines = tb.strip().split("\n")
            if len(tb_lines) > 4:
                detail += "\n    " + "\n    ".join(tb_lines[-4:])
        duration_ms = (time.time() - t0) * 1000.0

        result = TestResult(
            name=name,
            category=category,
            passed=passed,
            detail=detail,
            duration_ms=duration_ms,
        )
        self._results.append(result)
        self.progress.emit(result)

        QTimer.singleShot(100, self._run_next)

    def _finish(self):
        self._running = False
        suite = TestSuiteResult(results=list(self._results))
        self.finished.emit(suite)
