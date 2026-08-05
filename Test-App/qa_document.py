"""
Q&A Document Integration — Data-Side Design

DESIGN PHILOSOPHY
=================
The editor is NOT modified. We design the data to fit the editor's
existing contract so the same HTML+CSS+JS works both in the editor
and in a standalone browser.

THE EDITOR'S CONTRACT (relevant pieces)
=======================================
1. isUnsplitableBlock(block) returns true if:
   - data-type is "Image" or "Math", OR
   - the block contains ZERO of these tags:
     p, h1, h2, h3, h4, h5, h6, ul, ol, table, blockquote, pre,
     div, section, article, li, tr

   A splittable block gets split across pages on overflow, which
   would break our question/actions/answer sibling structure.

2. User scripts are injected via Editor.addScript(null, inline),
   which creates <script data-custom="true"> in <head> with
   textContent = the JS source. The script runs synchronously
   on injection. After injection, Editor.fireContentLoaded()
   dispatches a synthetic DOMContentLoaded event.

3. The editor's refresh() path calls setDocument(), which rebuilds
   .pages-wrapper via innerHTML. Direct event listeners on
   elements are LOST when this happens. Event delegation on
   document survives.

OUR DATA-SIDE DESIGN
====================
To make question-groups unsplittable WITHOUT modifying the editor,
we use <span> elements styled as display:block instead of <div> /
<section>. <span> is NOT in the editor's "content elements" list,
so a block whose only children are <span>s is naturally unsplittable.

This works identically in browsers — <span style="display:block">
is valid CSS and renders as a block-level element.

The JS uses event delegation on document, so it survives the
editor's setDocument() rebuilds. It also listens for DOMContentLoaded
(with a readyState fallback), so it works whether the script is:
  - loaded via <script> in a browser (DOMContentLoaded fires naturally)
  - injected by the editor's addScript + fireContentLoaded
  - injected by the editor's _build_full_html (script in <head>,
    runs after body is parsed)

USAGE
=====
    from examples.qa_document import build_qa_blocks, CUSTOM_CSS, CUSTOM_SCRIPT

    blocks = build_qa_blocks(qa_pairs)

    editor.load_blocks(
        html_list=blocks,
        page_mode="paged",
        custom_css=CUSTOM_CSS,
        custom_scripts=CUSTOM_SCRIPT,
        allow_scripts=True,           # REQUIRED — enables script injection
        preserve_block_class=True,    # REQUIRED — blocks use class="block"
    )

For browser standalone, build a full HTML file:
    from examples.qa_document import build_standalone_html
    html = build_standalone_html(qa_pairs)
    open("qa.html", "w", encoding="utf-8").write(html)
"""

# ============================================================
# CSS (raw — no <style> wrapper; load_blocks expects raw CSS)
# ============================================================
# All structural elements use <span> styled as display:block.
# This is the KEY design choice: <span> is not in the editor's
# "content elements" list, so a block containing only <span>s
# is naturally unsplittable — no editor modification needed.

CUSTOM_CSS = """
/* ── Question group container ──
   Uses <span> not <div> so the editor treats the block as
   unsplittable (see isUnsplitableBlock in script.js).
   display:block makes it render as a block-level element. */
.qa-group
{
    display: block;
    border: 1px solid #ddd;
    border-radius: 8px;
    margin-bottom: 14px;
    overflow: hidden;
}

/* ── Question, Answer, Actions ──
   All <span> display:block — same rationale. */
.qa-question
{
    display: block;
    flow-root: display;  /* CSS alias, ignored if unsupported */
}
.qa-answer
{
    display: block;
    border: 0.5px solid #4c45d09d;
    border-radius: 8px;
    margin: 5px 0px;
    /* Initial hidden state — prevents FOUC before JS runs.
       JS overrides these inline when opening/closing. */
    overflow: hidden;
    height: 0;
    transition: height 300ms ease, padding 300ms ease;
}
.qa-actions
{
    display: flex;
    justify-content: end;
    align-items: center;
    gap: 16px;
    margin-top: 8px;
    padding: 0 8px;
}

/* ── Global actions header ── */
.global-actions
{
    display: flex;
    gap: 10px;
    padding: 10px;
    margin-bottom: 32px;
    border-bottom: 2px solid #4f46e5;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    user-select: none;
}
.global-actions button
{
    font-weight: 600;
    padding: 10px 18px;
    border: none;
    background: #003d66;
    border-radius: 100px;
    width: 200px;
    cursor: pointer;
    color: whitesmoke;
}
.status-text
{
    margin: auto 10px auto auto;
    font-size: 0.9rem;
    color: #64748b;
    text-align: center;
    font-style: italic;
}

/* ── Per-question actions ── */
.block-meta
{
    opacity: 0.5;
    font-size: 8pt;
    align-self: baseline;
    cursor: not-allowed;
}
.toggle-btn
{
    opacity: 0.75;
    background-color: transparent;
    border: none;
    cursor: pointer;
    user-select: none;
}
.select-cb
{
    width: 14px;
    height: 14px;
    cursor: pointer;
    accent-color: #4f46e5;
    margin-inline-start: auto;
}
.no-answer
{
    margin-top: 0px;
    padding: 8px;
    text-transform: uppercase;
    text-decoration: underline;
    opacity: 0.75;
    color: #64748bb3;
    text-align: center;
    font-size: 10pt;
    font-weight: 600;
    letter-spacing: 6px;
}
"""


# ============================================================
# JS (raw — no <script> wrapper; load_blocks expects raw JS)
# ============================================================
# Key design choices:
# 1. IIFE wrapper — no global namespace pollution
# 2. Event delegation on document — survives editor setDocument()
#    rebuilds (which clone the DOM and lose direct listeners)
# 3. DOMContentLoaded + readyState fallback — works for:
#    - browser <script> in <head> (waits for DOMContentLoaded)
#    - browser <script> at end of <body> (readyState already 'interactive')
#    - editor addScript() injection (synthetic DOMContentLoaded fired)
# 4. data-initialized flag on .qa-actions — idempotent re-init
#    after editor re-pagination moves elements around

CUSTOM_SCRIPT = """
(function() {
    "use strict";

    var statusText = null;
    var select_all = false;
    var show_all_answers = false;

    // ── Status ──────────────────────────────────────────
    function updateSelectionStatus()
    {
        if (!statusText) statusText = document.getElementById("selectionStatus");
        if (!statusText) return;
        var selected = document.querySelectorAll(".select-cb:checked").length;
        var total = document.querySelectorAll(".select-cb").length;
        statusText.textContent = selected + " question" + (selected === 1 ? "" : "s") +
                                 " selected of " + total;
    }

    // ── Selection ───────────────────────────────────────
    function setSelected(checkbox, selected)
    {
        var actions = checkbox.closest(".qa-actions");
        if (!actions) return;
        var question = actions.previousElementSibling;
        var answer = actions.nextElementSibling;
        checkbox.checked = selected;
        var value = selected ? "true" : "false";
        if (question) question.setAttribute("question-selected", value);
        if (answer) answer.setAttribute("answer-selected", value);
    }

    // ── Open / Close ────────────────────────────────────
    function openAnswer(answer)
    {
        if (!answer || answer.dataset.open === "true") return;
        answer.dataset.open = "true";
        answer.style.padding = "16px";
        answer.style.display = "block";
        answer.style.overflow = "hidden";
        answer.style.height = "0px";
        answer.offsetHeight;  // force reflow
        answer.style.height = answer.scrollHeight + "px";
        function handler(e)
        {
            if (e.propertyName !== "height") return;
            answer.style.height = "auto";
            answer.removeEventListener("transitionend", handler);
        }
        answer.addEventListener("transitionend", handler);
    }

    function closeAnswer(answer)
    {
        if (!answer || answer.dataset.open === "false") return;
        answer.dataset.open = "false";
        answer.style.padding = "0px";
        answer.style.height = answer.scrollHeight + "px";
        answer.offsetHeight;  // force reflow
        answer.style.height = "0px";
    }

    // ── Initialize ──────────────────────────────────────
    // Idempotent: uses data-initialized flag so re-init after
    // editor re-pagination doesn't double-bind or reset state.
    function initAnswers()
    {
        document.querySelectorAll(".qa-actions").forEach(function(actions)
        {
            if (actions.dataset.initialized === "true") return;

            var question = actions.previousElementSibling;
            var answer = actions.nextElementSibling;
            var checkbox = actions.querySelector(".select-cb");
            var toggle = actions.querySelector(".toggle-btn");

            if (!question || !answer || !checkbox || !toggle)
            {
                console.warn("QA init: missing siblings", {question: !!question, answer: !!answer, checkbox: !!checkbox, toggle: !!toggle});
                return;
            }

            actions.dataset.initialized = "true";
            question.setAttribute("question-selected", "false");
            answer.setAttribute("answer-selected", "false");
            answer.dataset.open = "false";
            answer.style.overflow = "hidden";
            answer.style.height = "0px";
            answer.style.transition = "height 300ms ease";
        });
        updateSelectionStatus();
    }

    // ── Event delegation on document ────────────────────
    // Survives editor setDocument() which rebuilds the DOM.
    // Direct listeners on elements would be lost.

    // Prevent caret placement inside buttons when the page is
    // contenteditable=true (editor context).
    document.addEventListener("mousedown", function(e)
    {
        if (e.target.tagName === "BUTTON" &&
            e.target.closest(".qa-actions, .global-actions"))
        {
            e.preventDefault();
        }
    });

    document.addEventListener("click", function(e)
    {
        // Toggle answer button
        var toggle = e.target.closest(".toggle-btn");
        if (toggle)
        {
            var actions = toggle.closest(".qa-actions");
            if (actions)
            {
                var answer = actions.nextElementSibling;
                if (answer)
                {
                    if (answer.dataset.open === "true") closeAnswer(answer);
                    else openAnswer(answer);
                }
            }
            return;
        }

        // Select All / Clear All
        var selectAllBtn = e.target.closest("#selectAll");
        if (selectAllBtn)
        {
            document.querySelectorAll(".select-cb").forEach(function(cb)
            {
                setSelected(cb, !select_all);
            });
            select_all = !select_all;
            selectAllBtn.textContent = select_all ? "Clear All" : "Select All";
            updateSelectionStatus();
            return;
        }

        // Show All / Hide All Answers
        var showAllBtn = e.target.closest("#showAllAnswers");
        if (showAllBtn)
        {
            document.querySelectorAll(".qa-actions").forEach(function(actions)
            {
                var answer = actions.nextElementSibling;
                if (!answer) return;
                if (show_all_answers) closeAnswer(answer);
                else openAnswer(answer);
            });
            show_all_answers = !show_all_answers;
            showAllBtn.textContent = show_all_answers ? "Hide All Answers" : "Show All Answers";
            return;
        }
    });

    document.addEventListener("change", function(e)
    {
        if (e.target.classList && e.target.classList.contains("select-cb"))
        {
            var cb = e.target;
            var actions = cb.closest(".qa-actions");
            if (actions)
            {
                var question = actions.previousElementSibling;
                var answer = actions.nextElementSibling;
                var value = cb.checked ? "true" : "false";
                if (question) question.setAttribute("question-selected", value);
                if (answer) answer.setAttribute("answer-selected", value);
            }
            updateSelectionStatus();
        }
    });

    // ── Boot ────────────────────────────────────────────
    // Works in three contexts:
    // 1. Browser <script> in <head>: readyState is "loading",
    //    wait for DOMContentLoaded.
    // 2. Browser <script> at end of <body>: readyState is
    //    "interactive", init immediately.
    // 3. Editor addScript() injection: script runs synchronously
    //    after body is parsed (readyState "interactive"), AND
    //    Editor.fireContentLoaded() dispatches DOMContentLoaded
    //    afterward. The readyState check handles the immediate
    //    case; the DOMContentLoaded listener is a no-op if init
    //    already ran (data-initialized flag).
    function boot()
    {
        initAnswers();
    }

    if (document.readyState === "loading")
    {
        document.addEventListener("DOMContentLoaded", boot);
    }
    else
    {
        boot();
    }
})();
"""


# ============================================================
# Block templates
# ============================================================
# CRITICAL: all structural elements use <span>, not <div>/<section>.
# The editor's isUnsplitableBlock() treats a block as splittable if
# it contains any of: p, h1-h6, ul, ol, table, blockquote, pre,
# div, section, article, li, tr. <span> is NOT in that list, so a
# block whose children are all <span>s is naturally unsplittable.
#
# This means question-groups stay together across page breaks
# without any editor modification. The CSS gives every <span>
# display:block (or display:flex) so they render as block-level.

HEADER_ACTIONS = """
<span class="global-actions" contenteditable="false">
    <button id="selectAll" contenteditable="false">Select All</button>
    <button id="showAllAnswers" contenteditable="false">Show All Answers</button>
    <span class="status-text" id="selectionStatus" contenteditable="false">--QUESTIONS--</span>
</span>
"""

BLOCK_ACTIONS = """
<span class="qa-actions" contenteditable="false">
    <span class="block-meta" title="Id | Learning material source | score" contenteditable="false">301 | Calculus / Derivatives | 0.0</span>
    <input type="checkbox" class="select-cb" title="Select this question" contenteditable="false">
    <button class="toggle-btn" type="button" contenteditable="false">
        <span style="display: flex;gap: 10px;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
            <span style="padding-top: 4px; opacity:0.5;font-size:8pt;font-weight:600;">ANSWER (NOT AVILABLE)</span>
        </span>
    </button>
</span>
"""


# ============================================================
# Block builders
# ============================================================

def build_qa_block(question_html, answer_html):
    """
    Build a single question-group block for the editor.

    The question_html and answer_html should be pre-rendered HTML
    strings. They will be placed inside <span class="qa-question">
    and <span class="qa-answer"> wrappers.

    IMPORTANT: if question_html or answer_html contains <p>, <div>,
    <section>, etc., the editor's isUnsplitableBlock() will see
    those tags and treat the block as splittable. To keep the group
    unsplittable, use only inline tags (<span>, <b>, <i>, <sup>,
    <sub>, <br>) inside question_html and answer_html, OR wrap
    them in <span style="display:block">.

    For rich text content (multiple paragraphs, lists, etc.), wrap
    each paragraph in its own <span class="qa-line"> with
    display:block in CSS.
    """
    group_inner = ('<span class="qa-question">' + question_html + '</span>'
                    + BLOCK_ACTIONS + 
                   '<span class="qa-answer">' + answer_html + '</span>')
    # The .block wrapper is the editor's structural marker.
    # data-type="QuestionGroup" is preserved by the loader (only
    # "Image" and "Math" are special-cased), so it round-trips
    # through save/reload unchanged.
    return ('<div class="block" data-type="QuestionGroup">' + group_inner + '</div>')


def build_qa_blocks(questions_and_answers):
    """
    Build a list of HTML block strings for the editor.

    Each item in questions_and_answers is a (question_html, answer_html)
    tuple. Returns a list of block HTML strings suitable for
    editor.load_blocks(html_list=...).

    The first block is the global-actions header; subsequent blocks
    are question-groups.
    """
    blocks = []

    # Header block (global actions)
    blocks.append('<div class="block" data-type="GlobalActions">' + HEADER_ACTIONS + '</div>')

    # Question groups
    for question_html, answer_html in questions_and_answers:
        blocks.append(build_qa_block(question_html, answer_html))

    return blocks


# ============================================================
# Standalone browser HTML builder
# ============================================================

def build_standalone_html(questions_and_answers, title="Q&A Document"):
    """
    Build a complete HTML document for standalone browser viewing.

    The same CSS and JS work in both the editor and a browser —
    no conditional logic needed. The <style> and <script> tags here
    are stripped by load_blocks() when loading into the editor
    (which expects raw CSS/JS), so this function is for browser
    output only.
    """
    blocks = build_qa_blocks(questions_and_answers)
    body_content = "\n".join(blocks)

    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
{css}
    </style>
</head>
<body>
{body}
    <script>
{js}
    </script>
</body>
</html>
""".format(
        title=title,
        css=CUSTOM_CSS,
        body=body_content,
        js=CUSTOM_SCRIPT,
    )


# ============================================================
# Verification
# ============================================================

if __name__ == "__main__":
    import re

    # Sample data — note: inline tags only inside question/answer
    qa_pairs = [
        ("What is the derivative of x<sup>2</sup>?", "The derivative of x<sup>2</sup> is 2x."),
        ("What is the integral of 2x dx?",
         "The integral of 2x dx is x<sup>2</sup> + C."),
        ("State the chain rule.",
         "If f(g(x)), then f'(g(x)) &middot; g'(x)."),
    ]

    # ── Verify editor blocks ──
    blocks = build_qa_blocks(qa_pairs)

    print("Generated {} editor blocks:".format(len(blocks)))

    for i, b in enumerate(blocks):
        m = re.search(r'data-type="([^"]*)"', b)
        dtype = m.group(1) if m else "?"
        # Check that NO <div>, <section>, <p>, etc. appear inside
        # (those would make the block splittable)
        has_block_tag = bool(re.search(
            r'<(?:div|section|p|h[1-6]|ul|ol|table|blockquote|pre|article|li|tr)\b',
            b.split('>', 1)[1]  # skip the .block wrapper itself
        ))
        print("  [{}] type={} splittable_risk={} size={}B".format(
            i, dtype, "YES" if has_block_tag else "no", len(b)))

    # ── Verify standalone HTML ──
    standalone = build_standalone_html(qa_pairs, title="Calculus Q&A")
    
    print("\nStandalone HTML: {} bytes".format(len(standalone)))
    print("  Has <!DOCTYPE html>: {}".format(standalone.startswith("<!DOCTYPE html>")))
    print("  Has <style>: {}".format("<style>" in standalone))
    print("  Has <script>: {}".format("<script>" in standalone))

    # ── Verify CSS/JS are clean for load_blocks ──
    # The JS contains comments that mention "<script>" (explaining
    # how the script is loaded). Strip JS comments before checking
    # for actual <script> tag usage.
    import re as _re
    css_tag = _re.search(r'<style\b', CUSTOM_CSS)
    assert not css_tag, "CSS must not have <style> wrapper"

    # Strip // line comments and /* */ block comments from JS
    js_no_comments = _re.sub(r'/\*.*?\*/', '', CUSTOM_SCRIPT, flags=_re.DOTALL)
    js_no_comments = _re.sub(r'//.*$', '', js_no_comments, flags=_re.MULTILINE)
    js_tag = _re.search(r'<script\b', js_no_comments)
    assert not js_tag, "JS must not have <script> wrapper (found outside comments: {})".format(
        js_tag.group(0) if js_tag else "")
    print("\nCSS and JS are clean for load_blocks().")

    # ── Verify no block tags inside question-groups ──
    # (the .block wrapper itself is a <div>, but that's the editor's
    # structural marker, not content)
    for i, b in enumerate(blocks[1:], 1):  # skip header
        inner = b.split('>', 1)[1]  # everything after first <div class="block"...>
        inner = inner.rsplit('</div>', 1)[0]  # strip closing wrapper
        block_tags = re.findall(
            r'<(div|section|p|h[1-6]|ul|ol|table|blockquote|pre|article|li|tr)\b',
            inner
        )
        if block_tags:
            print("  WARNING: block [{}] contains block-level tags: {}".format(i, set(block_tags)))
            print("    These would make the block splittable in the editor.")
        else:
            print("  Block [{}] OK: only inline tags inside (unsplittable)".format(i))

    # ── Write standalone HTML for browser testing ──
    import os
    out_path = os.path.join(os.path.dirname(__file__), "qa_standalone.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(standalone)
    print("\nStandalone HTML written to: {}".format(out_path))
    print("Open it in a browser to verify the JS works outside the editor.")
