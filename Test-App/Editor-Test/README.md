# Editor Test Driver

A PySide6 application that shows the Editor widget and runs an
automated test suite against it.

## Philosophy

- **Non-destructive**: the editor content is NOT cleared between
  tests unless the test is specifically testing a clear/reset
  function. Tests APPEND content at the end and scroll to it.
- **Long content**: documents use realistic, multi-paragraph
  content — 300-paragraph pagination tests, 60-row tables,
  multi-section rich documents.
- **Live observation**: after each action, the editor scrolls
  (smoothly) to the new content so you can watch the test happen.

## Running

From the `Editor_0.5.1_fixed` directory:

```
python tests/main.py
```

## What you see

The window is split horizontally:
- **Left**: the Editor widget (live, editable)
- **Right**: test panel with:
  - "Start testing" button
  - Progress bar (`completed / total`)
  - Summary line (Passed / Failed / Total)
  - Dark console log with color-coded PASS/FAIL entries
  - Final result banner (green/orange/red) with percentage

As tests run, the editor on the left fills with content:
1. A rich startup document (title, intro, table, math, list, 15 filler paragraphs)
2. Math formulas (block + inline) appended at the cursor
3. Tables inserted and edited (add row, add column)
4. A 300-paragraph document for pagination testing
5. A 60-row table for split-attribute testing
6. Save/reload round-trip verification
7. Bold formatting on appended paragraphs
8. Half-space (ZWNJ) insertion

Each test scrolls the new content into view so you can watch the
editor handle it in real time.

## Test categories

| Category   | Tests                                                        |
|------------|--------------------------------------------------------------|
| Boot       | Editor initializes, JS reports ready                         |
| Document   | Load rich doc, clear+reload, load_blocks                     |
| Math       | Block/inline insertion, round-trip via load_blocks          |
| Table      | Insert, add_row, add_column, fragment merge                 |
| Pagination | 300-paragraph multi-page, table split + attributes          |
| Save/Load  | HTML save/reload round-trip                                  |
| Export     | export_blocks_async, get_content_html                       |
| Mode       | Page mode switch (paged <-> continuous)                     |
| Format     | Bold on appended paragraph                                   |
| Settings   | set_page_margin, set_background_color (restored after)     |
| Special    | insert_half_space (ZWNJ)                                    |

21 tests total.

## Files

| File                | Purpose                                           |
|---------------------|---------------------------------------------------|
| `tests/main.py`     | Main window with Editor + side panel              |
| `tests/test_runner.py` | Test harness: 21 tests + EditorTestRunner class |
| `tests/__init__.py` | Package marker                                    |
