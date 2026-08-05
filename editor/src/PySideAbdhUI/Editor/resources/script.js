
"use strict";
    var bridge = null;      //Python bridge                
    var changeTimer = null;
    var editable = false;
    var activeMathEditElement = null;
    var mathEditGlobalHandlersAttached = false;

    function collectPageGeometry()
    {
        var pages = document.querySelectorAll('.page');
        if (!pages.length) return JSON.stringify([]);

        var wrapper = document.querySelector('.pages-wrapper');
        var wrapperOffset = wrapper ? wrapper.offsetTop : 0;

        var result = [];
        pages.forEach(function(p, i) {
            result.push({
                index: i + 1,
                scrollY: p.offsetTop - wrapperOffset,
                width: p.offsetWidth,
                height: p.offsetHeight
            });
        });
        return JSON.stringify(result);
    }
    function _removeGlobalMathEditHandlers()
    {
        if (!mathEditGlobalHandlersAttached) return;
        document.removeEventListener('keydown', _onGlobalMathEditKeydown, true);
        document.removeEventListener('keypress', _onGlobalMathEditKeypress, true);
        document.removeEventListener('beforeinput', _onGlobalMathEditBeforeInput, true);
        mathEditGlobalHandlersAttached = false;
    }

    function generateId()
    {
        if (window.crypto && crypto.randomUUID) 
        {
            return crypto.randomUUID().replace(/-/g, "");
        }
        
        return Math.random().toString(16).slice(2) + Date.now().toString(16);
    }

    function _encodeHtmlAttr(value)
    {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function _insertHtmlAtCursor(html)
    {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) {
            var page = document.querySelector('.page');
            if (!page) return;
            var content = getPageContent(page);
            if (!content) return;
            content.insertAdjacentHTML('beforeend', html);
            return;
        }

        var range = sel.getRangeAt(0);
        var fragment = range.createContextualFragment(html);
        range.deleteContents();
        range.insertNode(fragment);

        sel.removeAllRanges();
        var newRange = document.createRange();
        var lastNode = fragment.lastChild || fragment.firstChild;
        if (lastNode) {
            newRange.setStartAfter(lastNode);
            newRange.collapse(true);
            sel.addRange(newRange);
        }
    }

    function _insertBlockAtCursor(html)
    {
        var sel = window.getSelection();
        var block = null;

        // Try the current selection first
        if (sel && sel.rangeCount) {
            var range = sel.getRangeAt(0);
            var container = range.startContainer;
            if (container.nodeType === Node.TEXT_NODE) {
                container = container.parentElement;
            }
            if (container && container.closest) {
                block = container.closest('.block');
            }
        }

        // Try document.activeElement — the currently focused element
        // inside the editor. This catches cases where the selection
        // is gone but the page still has focus.
        if (!block) {
            var active = document.activeElement;
            if (active && active.closest) {
                block = active.closest('.block');
                if (block && !block.hasAttribute('data-id')) {
                    block = null;
                }
            }
        }

        // Fall back to the last focused block by data-id.
        // We look it up by selector (not by DOM reference) because
        // setDocument() may have rebuilt the DOM, making old
        // element references stale.
        if (!block && lastFocusedBlockId) {
            block = document.querySelector(
                '.block[data-id="' + CSS.escape(lastFocusedBlockId) + '"]'
            );
        }

        if (!block) {
            // Ultimate fallback: end of first page
            var page = document.querySelector('.page');
            if (page) {
                var content = getPageContent(page);
                if (content) {
                    content.insertAdjacentHTML('beforeend', html);
                    return;
                }
            }
            return;
        }

        block.insertAdjacentHTML('afterend', html);
    }

    function _extractFormulaFromKaTeX(katexEl) 
    {
        if (!katexEl) return null;
        var annotation = katexEl.querySelector('annotation[encoding="application/x-tex"]');
        if (annotation) {
            return annotation.textContent || annotation.innerText || null;
        }
        return null;
    }

    function _wrapKaTeXElement(katexEl) {
        if (!katexEl) return null;
        var formula = _extractFormulaFromKaTeX(katexEl);
        if (!formula) return null;

        var isDisplay = katexEl.classList.contains('katex-display');
        var wrapper = document.createElement(isDisplay ? 'div' : 'span');
        wrapper.className = isDisplay ? 'math-block' : 'math-inline';
        wrapper.setAttribute('data-math-id', generateId());
        wrapper.setAttribute('data-formula', formula);
        wrapper.setAttribute('contenteditable', 'false');

        var parent = katexEl.parentElement;
        if (parent) {
            parent.insertBefore(wrapper, katexEl);
        }
        wrapper.appendChild(katexEl);
        return wrapper;
    }

    // ── Wrap all un-wrapped KaTeX elements ──────────────────
    // After pasting from external sources (web pages, other
    // editors), the pasted HTML may contain KaTeX-rendered spans
    // (<span class="katex">) that are NOT inside a .math-block /
    // .math-inline wrapper. These render visually but can't be
    // edited by double-clicking (because _findMathElement looks
    // for .math-block / .math-inline / data-math-id).
    //
    // This function finds all such un-wrapped KaTeX elements and
    // wraps them using _wrapKaTeXElement, extracting the LaTeX
    // source from the <annotation> tag that KaTeX always includes.
    // After wrapping, the formulas become editable.
    //
    // Called after paste operations and after renderMathFormulas().
    function _wrapUnwrappedKaTeX()
    {
        // Find all .katex elements that are NOT inside a
        // .math-block or .math-inline wrapper.
        var allKatex = document.querySelectorAll('.katex');
        allKatex.forEach(function(katexEl) {
            // Skip if already inside a wrapper
            if (katexEl.closest('.math-block, .math-inline')) return;

            // Skip .katex-display's parent .katex (the inner one)
            // — we want to wrap the .katex-display, not the inner
            if (katexEl.classList.contains('katex-display')) return;
            // But if the parent is .katex-display, we should wrap
            // the .katex-display, not this inner .katex
            if (katexEl.parentElement &&
                katexEl.parentElement.classList.contains('katex-display')) {
                // Will be handled when we process the .katex-display
                return;
            }

            // Check if this .katex has an annotation (LaTeX source)
            var formula = _extractFormulaFromKaTeX(katexEl);
            if (!formula) return;

            // Determine if it's display-mode (inside .katex-display)
            var isDisplay = false;
            var checkParent = katexEl.parentElement;
            while (checkParent) {
                if (checkParent.classList &&
                    checkParent.classList.contains('katex-display')) {
                    isDisplay = true;
                    break;
                }
                checkParent = checkParent.parentElement;
            }

            // Wrap the .katex (or its .katex-display parent) 
            var elementToWrap = isDisplay ?
                (katexEl.closest('.katex-display') || katexEl) : katexEl;

            // Check again if already wrapped (might have been wrapped
            // by a previous iteration)
            if (elementToWrap.closest('.math-block, .math-inline')) return;

            _wrapKaTeXElement(elementToWrap);
        });
    }

    function _findMathElement(node)
    {
        if (!node) return null;
        
        while (node && node.nodeType === Node.TEXT_NODE) 
        {
            node = node.parentElement;
        }

        var current = node;
        while (current) {
            if (current.classList && (current.classList.contains('math-block') || current.classList.contains('math-inline'))) {
                return current;
            }
            if (current.nodeType === Node.ELEMENT_NODE && current.hasAttribute && current.hasAttribute('data-math-id')) {
                return current;
            }
            current = current.parentElement;
        }

        current = node;
        while (current) {
            if (current.classList && current.classList.contains('katex')) {
                return _wrapKaTeXElement(current);
            }
            current = current.parentElement;
        }

        return null;
    }

    function _reportMathSelection(element)
    {
        if (!bridge || !element) return;

        var mathId = element.getAttribute('data-math-id') || element.getAttribute('data-id') || '';

        bridge.reportSelection({
            type: 'Math',
            id: mathId,
            formula: element.getAttribute('data-formula') || '',
            inline: element.classList.contains('math-inline')
        });
    }

    function insertMathFormula(formula, isInline)
    {
        if (!formula) return;

        var encoded = _encodeHtmlAttr(formula);
        var mathId = generateId();

        if (isInline)
        {
            var html = '<span class="math-inline" data-math-id="' + mathId + '" title="db-click to edit" ' +
                       'data-formula="' + encoded + '" contenteditable="false" dir="ltr"></span>';
            _insertHtmlAtCursor(html);
        }
        else
        {
            var html = '<div class="block" data-type="Math">'
                     + '<div class="math-block" data-math-id="' + mathId + '" title="db-click to edit" '
                     +'data-formula="' + encoded + '" contenteditable="false" dir="ltr"></div>'
                     + '</div>';
                
            _insertBlockAtCursor(html);

            // ── Ensure there's a paragraph after the block math ──
            // A block math is contenteditable="false", so the user
            // can't place the cursor inside it. If it's the last
            // block on the page (or the only block), pressing Enter
            // or trying to continue typing after it would be
            // impossible — there's nowhere for the cursor to go.
            //
            // Fix: find the just-inserted math block, check if it
            // has a next sibling that's an editable block. If not,
            // insert an empty paragraph block after it and move
            // the cursor there. This gives the user somewhere to
            // continue typing.
            var mathBlock = document.querySelector(
                '.block[data-type="Math"] .math-block[data-math-id="' + mathId + '"]'
            );
            if (mathBlock) {
                var mathWrapper = mathBlock.closest('.block');
                var parentContent = mathWrapper.parentElement;
                var nextSibling = mathWrapper.nextElementSibling;

                // Check if there's already an editable block after
                var hasEditableNext = false;
                if (nextSibling && nextSibling.classList &&
                    nextSibling.classList.contains('block') &&
                    nextSibling.getAttribute('data-type') !== 'Math' &&
                    nextSibling.getAttribute('data-type') !== 'Image') {
                    hasEditableNext = true;
                }

                if (!hasEditableNext) {
                    // Insert an empty paragraph block after the math
                    var paraBlock = document.createElement('div');
                    paraBlock.className = 'block';
                    paraBlock.setAttribute('data-id', generateId());
                    paraBlock.setAttribute('data-type', 'Paragraph');
                    var p = document.createElement('p');
                    p.innerHTML = '<br>';
                    paraBlock.appendChild(p);
                    parentContent.insertBefore(paraBlock, mathWrapper.nextSibling);

                    // Move cursor into the new paragraph
                    _placeCursorAtStart(p);
                }
            }
        }

        renderMathFormulas();
        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    // Place the cursor at the start of the given element.
    // Used after inserting a block math + empty paragraph to move
    // the cursor into the new paragraph so the user can continue typing.
    function _placeCursorAtStart(el)
    {
        if (!el) return;
        var range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(true);  // collapse to start
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    }

    function updateMathFormula(id, formula, isInline)
    {
        if (!id || !formula) return;

        var target = document.querySelector('[data-math-id="' + id + '"]') || document.querySelector('[data-id="' + id + '"]');
        if (!target) return;

        var encoded = _encodeHtmlAttr(formula);
        var mathEl = target.classList.contains('math-block') || target.classList.contains('math-inline')
            ? target
            : target.querySelector('.math-block, .math-inline');

        if (!mathEl) {
            return;
        }

        if (isInline) {
            if (!mathEl.classList.contains('math-inline')) {
                var wrapper = document.createElement('span');
                wrapper.className = 'math-inline';
                wrapper.setAttribute('data-math-id', id);
                wrapper.setAttribute('data-formula', encoded);
                wrapper.setAttribute('contenteditable', 'false');
                target.parentNode.replaceChild(wrapper, target);
                mathEl = wrapper;
            } else {
                mathEl.setAttribute('data-formula', encoded);
            }
        } else {
            if (!mathEl.classList.contains('math-block')) {
                var wrapper = document.createElement('div');
                wrapper.className = 'math-block';
                wrapper.setAttribute('data-math-id', id);
                wrapper.setAttribute('data-formula', encoded);
                wrapper.setAttribute('contenteditable', 'false');
                if (mathEl.parentNode) {
                    mathEl.parentNode.replaceChild(wrapper, mathEl);
                }
                mathEl = wrapper;
            } else {
                mathEl.setAttribute('data-formula', encoded);
            }
        }

        renderMathFormulas();
        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function _setCaretToEnd(element)
    {
        var range = document.createRange();
        range.selectNodeContents(element);
        range.collapse(false);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    }

    function _onMathEditBlur(event)
    {
        _endMathEdit(event.currentTarget);
    }

    function _onMathEditBeforeInput(event)
    {
        if (event.inputType === 'insertParagraph') {
            event.preventDefault();
            _endMathEdit(activeMathEditElement || event.currentTarget);
            return;
        }
    }

    function _onMathEditKeydown(event)
    {
        if ((event.key === 'Enter' || event.keyCode === 13) && !event.shiftKey) {
            event.preventDefault();
            event.stopImmediatePropagation();
            _endMathEdit(activeMathEditElement || event.currentTarget);
            return;
        }
        if (event.key === 'Escape' || event.keyCode === 27) {
            event.preventDefault();
            event.stopImmediatePropagation();
            _cancelMathEdit(activeMathEditElement || event.currentTarget);
            return;
        }
    }

    function _onGlobalMathEditBeforeInput(event)
    {
        if (!activeMathEditElement) return;
        if (event.inputType === 'insertParagraph') {
            event.preventDefault();
            _endMathEdit(activeMathEditElement);
            return;
        }
    }

    function _onGlobalMathEditKeydown(event)
    {
        if (!activeMathEditElement) return;
        if ((event.key === 'Enter' || event.keyCode === 13) && !event.shiftKey) {
            event.preventDefault();
            event.stopImmediatePropagation();
            _endMathEdit(activeMathEditElement);
            return;
        }
        if (event.key === 'Escape' || event.keyCode === 27) {
            event.preventDefault();
            event.stopImmediatePropagation();
            _cancelMathEdit(activeMathEditElement);
            return;
        }
    }

    function _onGlobalMathEditKeypress(event)
    {
        if (!activeMathEditElement) return;
        if (event.key === 'Enter' || event.keyCode === 13) {
            event.preventDefault();
            event.stopImmediatePropagation();
            _endMathEdit(activeMathEditElement);
            return;
        }
    }

    function _beginMathEdit(element)
    {
        if (!element || element.getAttribute('data-editing') === 'true') return;

        var formula = element.getAttribute('data-formula') || '';
        element.setAttribute('data-editing', 'true');
        element.setAttribute('contenteditable', 'true');
        element.setAttribute('tabindex', '-1');
        element.setAttribute('spellcheck', 'false');
        element.classList.add('math-editing');
        element.innerText = formula;
        element.focus();
        _setCaretToEnd(element);
        element.addEventListener('blur', _onMathEditBlur);
        element.addEventListener('keydown', _onMathEditKeydown, true);
        element.addEventListener('keypress', _onMathEditKeydown, true);
        element.addEventListener('beforeinput', _onMathEditBeforeInput, true);

        activeMathEditElement = element;
        if (!mathEditGlobalHandlersAttached) {
            document.addEventListener('keydown', _onGlobalMathEditKeydown, true);
            document.addEventListener('keypress', _onGlobalMathEditKeypress, true);
            document.addEventListener('beforeinput', _onGlobalMathEditBeforeInput, true);
            mathEditGlobalHandlersAttached = true;
        }
    }

    function _endMathEdit(element)
    {
        if (!element || element.getAttribute('data-editing') !== 'true') return;

        var formula = element.innerText.trim();
        element.removeEventListener('blur', _onMathEditBlur);
        element.removeEventListener('keydown', _onMathEditKeydown, true);
        element.removeEventListener('keypress', _onMathEditKeydown, true);
        element.removeEventListener('beforeinput', _onMathEditBeforeInput, true);
        element.removeAttribute('data-editing');
        element.removeAttribute('contenteditable');
        element.removeAttribute('tabindex');
        element.removeAttribute('spellcheck');
        element.classList.remove('math-editing');
        element.setAttribute('data-formula', formula);
        activeMathEditElement = null;
        _removeGlobalMathEditHandlers();
        renderMathFormulas();
        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function _cancelMathEdit(element)
    {
        if (!element || element.getAttribute('data-editing') !== 'true') return;

        element.removeEventListener('blur', _onMathEditBlur);
        element.removeEventListener('keydown', _onMathEditKeydown, true);
        element.removeEventListener('keypress', _onMathEditKeydown, true);
        element.removeEventListener('beforeinput', _onMathEditBeforeInput, true);
        element.removeAttribute('data-editing');
        element.removeAttribute('contenteditable');
        element.removeAttribute('tabindex');
        element.removeAttribute('spellcheck');
        element.classList.remove('math-editing');
        activeMathEditElement = null;
        _removeGlobalMathEditHandlers();
        renderMathFormulas();
    }

    function scheduleContentChanged() 
    {
        if (!bridge || !editable) return;
        
        if (changeTimer) clearTimeout(changeTimer);
        
        changeTimer = setTimeout(function () 
        {
            bridge.notifyContentChanged();
        }, 250);
    }

    function connectBridge() 
    {
        if (typeof QWebChannel === "undefined" || typeof qt === "undefined") 
        {
            setTimeout(connectBridge, 50);
            return;
        }

        new QWebChannel(qt.webChannelTransport, function (channel) 
        {
            bridge = channel.objects.bridge;
            window.Editor.ready = true;
        });
    }

    function getPageContent(page) 
    {
        return page.querySelector(".page-content") || page;
    }

    function isUnsplitableBlock(block)
    {
        var dataType = block.getAttribute("data-type");
        // Image and Math blocks are always unsplitable — they are
        // "single tags" that cannot be meaningfully divided.
        if (dataType === "Image" || dataType === "Math") return true;

        // Also treat blocks whose ONLY content is void/single elements
        // (img, hr, svg, etc.) as unsplitable — there's nothing to split.
        var contentElements = block.querySelectorAll(
            "p, h1, h2, h3, h4, h5, h6, ul, ol, table, blockquote, pre, " +
            "div, section, article, li, tr"
        );
        if (!contentElements.length) return true;

        return false;
    }

/* ******** Table *********/

    // Currently selected table state. Set by clicking on a table;
    // cleared by clicking elsewhere or by removeRow/removeColumn/
    // deleteTable operations.
    var selectedTable = null;
    var selectedCell = null;
    var selectedRowIdx = -1;
    var selectedColIdx = -1;

    // Resize drag state. Activated by mousedown near a cell's right
    // (column) or bottom (row) edge.
    var resizeMode = null;          // 'col' | 'row' | null
    var resizeCol = null;           // <col> being resized
    var resizeRow = null;           // <tr> being resized
    var resizeStartX = 0;
    var resizeStartY = 0;
    var resizeStartWidth = 0;
    var resizeStartHeight = 0;
    var tableHandlersAttached = false;

    var RESIZE_EDGE = 6;            // pixels from cell border that triggers resize
    var MIN_COL_WIDTH = 20;
    var MIN_ROW_HEIGHT = 20;

    function _findTableElement(node)
    {
        if (!node) return null;
        while (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        while (node) {
            if (node.tagName === 'TABLE') return node;
            node = node.parentElement;
        }
        return null;
    }

    function _findCellElement(node)
    {
        if (!node) return null;
        while (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        while (node) {
            if (node.tagName === 'TD' || node.tagName === 'TH') return node;
            node = node.parentElement;
        }
        return null;
    }

    function _ensureColgroup(table)
    {
        if (!table) return null;
        var cols = table.rows[0] ? table.rows[0].cells.length : 0;
        if (cols === 0) return null;

        var colgroup = table.querySelector('colgroup');
        if (!colgroup) {
            colgroup = document.createElement('colgroup');
            for (var i = 0; i < cols; i++) {
                colgroup.appendChild(document.createElement('col'));
            }
            // colgroup must be the first child of <table>
            table.insertBefore(colgroup, table.firstChild);
        } else {
            // Sync col count with actual cell count
            while (colgroup.children.length < cols) {
                colgroup.appendChild(document.createElement('col'));
            }
            while (colgroup.children.length > cols) {
                colgroup.removeChild(colgroup.lastChild);
            }
        }
        return colgroup;
    }

    function _clearTableSelection()
    {
        if (selectedTable) {
            selectedTable.classList.remove('table-selected');
            var block = selectedTable.closest('.block');
            if (block) {
                block.classList.remove('table-block-selected');
                var handle = block.querySelector('.table-drag-handle');
                if (handle) handle.remove();
            }
            selectedTable = null;
        }
        if (selectedCell) {
            selectedCell.classList.remove('cell-selected');
            selectedCell = null;
        }
        selectedRowIdx = -1;
        selectedColIdx = -1;
    }

    function _selectTable(table, cell)
    {
        _clearTableSelection();
        if (!table) return;

        selectedTable = table;
        table.classList.add('table-selected');

        var block = table.closest('.block');
        if (block) 
        {
            block.classList.add('table-block-selected');

            // Add drag handle for moving the table to a new position.
            // We use a dedicated handle instead of making the <table>
            // draggable because that would conflict with text editing
            // inside cells.
            if (!block.querySelector('.table-drag-handle')) 
            {
                var handle = document.createElement('div');
                handle.contentEditable = "false";
                handle.className = 'table-drag-handle';
                handle.setAttribute('draggable', 'true');
                handle.innerHTML = '&#10021;';//'&#9776;';  // ☰ grip icon
                handle.title = 'Drag to move table';
                var tb = block.querySelector('table');
                var r = tb.getBoundingClientRect();
                var x = r.left;
                var y =  r.top;
                // size of handle is 18x18, thus we use -9 to adjust
                // display location
                handle.style.left = String(parseInt(x) - 9) + "px";
                handle.style.top = String(parseInt(y)-9) + "px";
                handle.style.position = "fixed"; 
                               
                block.appendChild(handle);
            }
        }

        if (cell) {
            selectedCell = cell;
            cell.classList.add('cell-selected');
            selectedColIdx = cell.cellIndex;

            // Row index within tbody (header rows are tracked
            // separately via thead, but for our purposes we use
            // the row index within its parent section).
            var row = cell.parentElement;
            selectedRowIdx = row.sectionRowIndex;

            // Report selection to Python
            if (bridge) {
                bridge.reportSelection({
                    type: 'Table',
                    tableId: block ? block.getAttribute('data-id') : '',
                    row: selectedRowIdx,
                    col: selectedColIdx,
                    rows: table.rows.length,
                    cols: row.cells.length,
                    inHeader: row.parentElement.tagName === 'THEAD'
                });
            }
        }
    }

    function _attachTableHandlers()
    {
        if (tableHandlersAttached) return;
        tableHandlersAttached = true;

        var root = document.getElementById('editor');
        if (!root) return;

        // Click → select table / cell / image. Use mousedown so we
        // capture the click before contenteditable does.
        root.addEventListener('mousedown', function (e) {
            // ── Track the block at click position ──
            // This is the most reliable way to know where the user
            // is working — fires on every click, no throttling.
            var clickBlock = e.target.closest ? e.target.closest('.block') : null;
            if (clickBlock && clickBlock.hasAttribute('data-id')) {
                lastFocusedBlockId = clickBlock.getAttribute('data-id');
            }

            // ── Image resize handle? ──
            var handleEl = e.target.closest ? e.target.closest('.img-handle') : null;
            if (handleEl && selectedImage) {
                e.preventDefault();
                var handle = handleEl.getAttribute('data-handle');
                _beginImageResize(handle, e.clientX, e.clientY);
                return;
            }

            // ── Table drag handle? ──
            // Must check BEFORE the "clear selection" branch below,
            // otherwise mousedown on the handle clears the table
            // selection and removes the handle before dragstart fires.
            var tableDragHandle = e.target.closest ? e.target.closest('.table-drag-handle') : null;
            if (tableDragHandle) {
                // Don't preventDefault — let HTML5 dragstart fire
                return;
            }

            // ── Image click? ──
            var img = _findImageElement(e.target);
            if (img) {
                // Only select if the image is inside a block (not the
                // measure-stage or other off-screen element).
                var block = img.closest('.block');
                if (block) {
                    _selectImage(img);
                    // Don't preventDefault for plain clicks — allow
                    // drag-and-drop to start naturally from the img
                    return;
                }
            }

            // ── Table cell click? ──
            var cell = _findCellElement(e.target);

            if (cell) {
                var table = _findTableElement(cell);
                if (table) {
                    // Clear any image selection first
                    _clearImageSelection();

                    // Check for resize handle first
                    var rect = cell.getBoundingClientRect();
                    var onRightEdge = Math.abs(e.clientX - rect.right) < RESIZE_EDGE;
                    var onBottomEdge = Math.abs(e.clientY - rect.bottom) < RESIZE_EDGE;

                    if (onRightEdge) {
                        e.preventDefault();
                        _beginColResize(table, cell, e.clientX);
                        return;
                    }
                    if (onBottomEdge) {
                        e.preventDefault();
                        _beginRowResize(cell, e.clientY);
                        return;
                    }

                    // Plain click → select
                    _selectTable(table, cell);
                    // Don't preventDefault — let caret placement happen
                    return;
                }
            }

            // Click outside any table/image → clear selections
            if (selectedTable && !_findTableElement(e.target)) {
                _clearTableSelection();
            }
            if (selectedImageBlock && !_findImageElement(e.target)) {
                _clearImageSelection();
            }
            if (!selectedTable && !selectedImage && bridge) {
                bridge.reportSelection({ type: 'None' });
            }
        });

        // Mousemove — update cursor near edges, or drag-resize
        document.addEventListener('mousemove', function (e) {
            // ── Image resize ──
            if (imageResizeMode && selectedImage) {
                var dx = e.clientX - imageResizeStartX;
                var dy = e.clientY - imageResizeStartY;
                var newW, newH;

                if (imageResizeMode === 'se') {
                    newW = Math.max(IMAGE_MIN_SIZE, imageResizeStartWidth + dx);
                    newH = Math.max(IMAGE_MIN_SIZE, imageResizeStartHeight + dy);
                } else if (imageResizeMode === 'nw') {
                    newW = Math.max(IMAGE_MIN_SIZE, imageResizeStartWidth - dx);
                    newH = Math.max(IMAGE_MIN_SIZE, imageResizeStartHeight - dy);
                } else if (imageResizeMode === 'ne') {
                    newW = Math.max(IMAGE_MIN_SIZE, imageResizeStartWidth + dx);
                    newH = Math.max(IMAGE_MIN_SIZE, imageResizeStartHeight - dy);
                } else if (imageResizeMode === 'sw') {
                    newW = Math.max(IMAGE_MIN_SIZE, imageResizeStartWidth - dx);
                    newH = Math.max(IMAGE_MIN_SIZE, imageResizeStartHeight + dy);
                }

                // Hold Shift to maintain aspect ratio
                if (e.shiftKey && imageResizeStartHeight > 0) {
                    var aspect = imageResizeStartWidth / imageResizeStartHeight;
                    newH = newW / aspect;
                }

                selectedImage.style.width = Math.round(newW) + 'px';
                selectedImage.style.height = Math.round(newH) + 'px';
                selectedImage.setAttribute('width', Math.round(newW));
                selectedImage.setAttribute('height', Math.round(newH));
                return;
            }

            // ── Table column/row resize ──
            if (resizeMode === 'col' && resizeCol) {
                var delta = e.clientX - resizeStartX;
                var newWidth = Math.max(MIN_COL_WIDTH, resizeStartWidth + delta);
                resizeCol.style.width = newWidth + 'px';
                return;
            }
            if (resizeMode === 'row' && resizeRow) {
                var dY = e.clientY - resizeStartY;
                var newHeight = Math.max(MIN_ROW_HEIGHT, resizeStartHeight + dY);
                resizeRow.style.height = newHeight + 'px';
                return;
            }

            // Update cursor on hover for table cells
            var cell = _findCellElement(e.target);
            if (cell && editable) {
                var rect = cell.getBoundingClientRect();
                if (Math.abs(e.clientX - rect.right) < RESIZE_EDGE) {
                    document.body.style.cursor = 'col-resize';
                } else if (Math.abs(e.clientY - rect.bottom) < RESIZE_EDGE) {
                    document.body.style.cursor = 'row-resize';
                } else {
                    document.body.style.cursor = '';
                }
            } else if (document.body.style.cursor === 'col-resize' ||
                       document.body.style.cursor === 'row-resize') {
                document.body.style.cursor = '';
            }
        });

        // Mouseup — finalize resize
        document.addEventListener('mouseup', function (e) {
            if (imageResizeMode) {
                imageResizeMode = null;
                document.body.style.cursor = '';
                if (bridge && typeof bridge.notifyContentChanged === 'function') {
                    bridge.notifyContentChanged();
                }
            }
            if (resizeMode) {
                if (bridge && typeof bridge.notifyContentChanged === 'function') {
                    bridge.notifyContentChanged();
                }
                resizeMode = null;
                resizeCol = null;
                resizeRow = null;
                document.body.style.cursor = '';
            }
        });

        // Keyup — track block position for arrow key navigation.
        // This ensures lastFocusedBlockId stays current when the
        // user moves the cursor with keyboard, not just mouse.
        root.addEventListener('keyup', function (e) {
            _trackFocusedBlock();
        });
    }

    function _beginColResize(table, cell, clientX)
    {
        _ensureColgroup(table);
        var colgroup = table.querySelector('colgroup');
        var colIdx = cell.cellIndex;
        var col = colgroup ? colgroup.children[colIdx] : null;
        if (!col) return;

        var rect = cell.getBoundingClientRect();
        var currentWidth = col.style.width
            ? parseInt(col.style.width, 10)
            : Math.round(rect.width);

        resizeMode = 'col';
        resizeCol = col;
        resizeStartX = clientX;
        resizeStartWidth = currentWidth;
        document.body.style.cursor = 'col-resize';
    }

    function _beginRowResize(cell, clientY)
    {
        var row = cell.parentElement;
        var rect = row.getBoundingClientRect();
        var currentHeight = row.style.height
            ? parseInt(row.style.height, 10)
            : Math.round(rect.height);

        resizeMode = 'row';
        resizeRow = row;
        resizeStartY = clientY;
        resizeStartHeight = currentHeight;
        document.body.style.cursor = 'row-resize';
    }

    // ---------------------------------------------------------
    // Public table operations (called from Python via runJavaScript)
    // ---------------------------------------------------------

    function insertTable(rows, cols)
    {
        rows = Math.max(1, parseInt(rows, 10) || 3);
        cols = Math.max(1, parseInt(cols, 10) || 3);

        // Default column width — gives new tables a reasonable starting
        // size. With CSS width: fit-content, without this the table would
        // shrink to just the header text width. Users can resize columns
        // by dragging cell borders.
        var DEFAULT_COL_WIDTH = 120;

        var blockId = generateId();
        var html = '<div class="block" data-type="Table" data-id="' + blockId + '">'
                 + '<table>'
                 + '<colgroup>';
        for (var c = 0; c < cols; c++) {
            html += '<col style="width:' + DEFAULT_COL_WIDTH + 'px">';
        }
        html += '</colgroup>'
                 + '<thead><tr>';
        for (var k = 0; k < cols; k++) html += '<th>Header ' + (k + 1) + '</th>';
        html += '</tr></thead>'
                 + '<tbody>';
        for (var r = 0; r < rows; r++) {
            html += '<tr>';
            for (var k = 0; k < cols; k++) html += '<td><br></td>';
            html += '</tr>';
        }
        html += '</tbody></table></div>';

        _insertBlockAtCursor(html);

        // Select the newly inserted table's first cell so subsequent
        // addRow/addColumn calls have a target.
        var block = document.querySelector('.block[data-id="' + blockId + '"]');
        if (block) 
        {
            console.warn('float:', block.style.float);
            var firstCell = block.querySelector('td, th');
            if (firstCell) _selectTable(block.querySelector('table'), firstCell);
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function deleteTable()
    {
        if (!selectedTable) return;
        var block = selectedTable.closest('.block');
        _clearTableSelection();
        if (block && block.parentElement) block.remove();
        if (bridge) bridge.reportSelection({ type: 'None' });
        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function addRow()
    {
        if (!selectedTable) return;

        var tbody = selectedTable.tBodies && selectedTable.tBodies[0];
        if (!tbody) {
            tbody = document.createElement('tbody');
            selectedTable.appendChild(tbody);
        }

        var cols = selectedTable.rows[0] ? selectedTable.rows[0].cells.length : 1;
        var newRow = document.createElement('tr');
        for (var i = 0; i < cols; i++) 
        {   
            var td = document.createElement('td');
            td.innerHTML = "<br>";
            newRow.appendChild(td);//document.createElement('td'));
        }

        // Insert after the currently-selected row (if it's in tbody)
        var inserted = false;
        if (selectedRowIdx >= 0 && selectedRowIdx < tbody.rows.length) 
        {
            var currentRow = tbody.rows[selectedRowIdx];
            if (currentRow.nextSibling) 
            {
                tbody.insertBefore(newRow, currentRow.nextSibling);
            } 
            else 
            {
                tbody.appendChild(newRow);
            }
            inserted = true;
        }
        if (!inserted) tbody.appendChild(newRow);

        // Move selection to the first cell of the new row
        _selectTable(selectedTable, newRow.cells[0]);

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function addColumn()
    {
        if (!selectedTable) return;

        _ensureColgroup(selectedTable);
        var colgroup = selectedTable.querySelector('colgroup');
        if (!colgroup) return;

        var newCol = document.createElement('col');

        // Insert <col> after the currently-selected column
        var insertIdx = (selectedColIdx >= 0) ? selectedColIdx + 1 : colgroup.children.length;
        if (insertIdx < colgroup.children.length) 
        {
            colgroup.insertBefore(newCol, colgroup.children[insertIdx]);
        } else {
            colgroup.appendChild(newCol);
        }

        // Insert a new cell at the same index in every row
        for (var r = 0; r < selectedTable.rows.length; r++) 
        {
            var row = selectedTable.rows[r];
            var isHeader = row.parentElement.tagName === 'THEAD';
            var newCell = document.createElement(isHeader ? 'th' : 'td');
            
            newCell.innerHTML = isHeader ? "New Header" : "<br>";
            
            if (insertIdx < row.cells.length) row.insertBefore(newCell, row.cells[insertIdx]);
            
            else row.appendChild(newCell);
        
        }

        // Select the new column's cell in the current row
        var currentRow = null;
        if (selectedRowIdx >= 0) {
            var tbody = selectedTable.tBodies && selectedTable.tBodies[0];
            if (tbody && selectedRowIdx < tbody.rows.length) {
                currentRow = tbody.rows[selectedRowIdx];
            }
        }
        if (!currentRow && selectedTable.rows.length > 0) {
            currentRow = selectedTable.rows[0];
        }
        if (currentRow && insertIdx < currentRow.cells.length) {
            _selectTable(selectedTable, currentRow.cells[insertIdx]);
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function removeRow()
    {
        if (!selectedTable || selectedRowIdx < 0) return;

        var tbody = selectedTable.tBodies && selectedTable.tBodies[0];
        if (!tbody || tbody.rows.length <= 1) return;  // keep ≥ 1 row

        if (selectedRowIdx < tbody.rows.length) {
            tbody.rows[selectedRowIdx].remove();
        }

        // Re-select the row that took its place (or the last row)
        var newIdx = Math.min(selectedRowIdx, tbody.rows.length - 1);
        _clearTableSelection();
        if (newIdx >= 0 && tbody.rows[newIdx] && tbody.rows[newIdx].cells[0]) {
            _selectTable(selectedTable, tbody.rows[newIdx].cells[0]);
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function removeColumn()
    {
        if (!selectedTable || selectedColIdx < 0) return;

        var firstRow = selectedTable.rows[0];
        if (!firstRow || firstRow.cells.length <= 1) return;  // keep ≥ 1 col

        // Remove <col>
        var colgroup = selectedTable.querySelector('colgroup');
        if (colgroup && selectedColIdx < colgroup.children.length) {
            colgroup.children[selectedColIdx].remove();
        }

        // Remove cell at selectedColIdx in every row
        for (var r = 0; r < selectedTable.rows.length; r++) {
            var row = selectedTable.rows[r];
            if (selectedColIdx < row.cells.length) {
                row.cells[selectedColIdx].remove();
            }
        }

        // Re-select the column that took its place
        var newIdx = Math.min(selectedColIdx, (selectedTable.rows[0] ? selectedTable.rows[0].cells.length - 1 : 0));
        _clearTableSelection();
        if (newIdx >= 0) {
            var tbody = selectedTable.tBodies && selectedTable.tBodies[0];
            var targetRow = (tbody && tbody.rows[0]) || selectedTable.rows[0];
            if (targetRow && targetRow.cells[newIdx]) {
                _selectTable(selectedTable, targetRow.cells[newIdx]);
            }
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

/* ******** Image *********/

    // Selected image state. Set by clicking on an <img>; cleared by
    // clicking elsewhere or by deleteImage().
    var selectedImage = null;           // the <img> element
    var selectedImageBlock = null;      // the .block containing it

    // Resize drag state. Activated by mousedown on a corner handle.
    var imageResizeMode = null;         // 'nw'|'ne'|'sw'|'se' | null
    var imageResizeStartX = 0;
    var imageResizeStartY = 0;
    var imageResizeStartWidth = 0;
    var imageResizeStartHeight = 0;
    var imageDragHandlersAttached = false;

    var IMAGE_MIN_SIZE = 20;

    function _findImageElement(node)
    {
        if (!node) return null;
        while (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        while (node) {
            if (node.tagName === 'IMG') return node;
            node = node.parentElement;
        }
        return null;
    }

    function _clearImageSelection()
    {
        if (selectedImageBlock) {
            selectedImageBlock.classList.remove('image-block-selected');
            var handles = selectedImageBlock.querySelector('.image-resize-handles');
            if (handles) handles.remove();
        }
        selectedImage = null;
        selectedImageBlock = null;
    }

    function _selectImage(img)
    {
        _clearImageSelection();
        _clearTableSelection();

        var block = img.closest('.block');
        if (!block) return;

        selectedImage = img;
        selectedImageBlock = block;
        block.classList.add('image-block-selected');

        // Add 4 corner resize handles
        var handles = document.createElement('div');
        handles.className = 'image-resize-handles';
        handles.innerHTML =
              '<div class="img-handle img-handle-nw" data-handle="nw"></div>'
            + '<div class="img-handle img-handle-ne" data-handle="ne"></div>'
            + '<div class="img-handle img-handle-sw" data-handle="sw"></div>'
            + '<div class="img-handle img-handle-se" data-handle="se"></div>';
        block.appendChild(handles);

        // Make the image draggable for move operations
        img.setAttribute('draggable', 'true');

        if (bridge) {
            bridge.reportSelection({
                type: 'Image',
                imageId: block.getAttribute('data-id'),
                src: img.getAttribute('src') || '',
                width: img.getAttribute('width') || '',
                height: img.getAttribute('height') || '',
                naturalWidth: img.naturalWidth || 0,
                naturalHeight: img.naturalHeight || 0
            });
        }
    }

    function _addImageHandles(block)
    {
        if (block.querySelector('.image-resize-handles')) return;
        var handles = document.createElement('div');
        handles.className = 'image-resize-handles';
        handles.innerHTML =
              '<div class="img-handle img-handle-nw" data-handle="nw"></div>'
            + '<div class="img-handle img-handle-ne" data-handle="ne"></div>'
            + '<div class="img-handle img-handle-sw" data-handle="sw"></div>'
            + '<div class="img-handle img-handle-se" data-handle="se"></div>';
        block.appendChild(handles);
    }

    function _beginImageResize(handle, clientX, clientY)
    {
        if (!selectedImage) return;

        var rect = selectedImage.getBoundingClientRect();
        imageResizeMode = handle;
        imageResizeStartX = clientX;
        imageResizeStartY = clientY;
        imageResizeStartWidth = rect.width;
        imageResizeStartHeight = rect.height;
        document.body.style.cursor = (
            handle === 'nw' || handle === 'se' ? 'nwse-resize' : 'nesw-resize'
        );
    }

    // ---------------------------------------------------------
    // Splitting a splittable block (Paragraph) at the caret so a
    // block-level insertion (image, table, ...) can land exactly
    // where the cursor is, instead of only ever after the whole
    // block. Mirrors the `splittable` flag already defined on the
    // Python Block classes (Paragraph=True, Image/Table/Math=False)
    // — those blocks get the html appended after them unchanged.
    // ---------------------------------------------------------

    function _rangeIsAtStartOfBlock(block, range)
    {
        try {
            var beforeRange = document.createRange();
            beforeRange.setStart(block, 0);
            beforeRange.setEnd(range.startContainer, range.startOffset);
            if (beforeRange.toString().length > 0) return false;
            var contents = beforeRange.cloneContents();
            return !contents.querySelector ||
                   !contents.querySelector('img, .math-inline, .math-block, table');
        } catch (e) {
            return false;
        }
    }

    function _fragmentHasContent(fragment)
    {
        if (!fragment) return false;
        if (fragment.textContent && fragment.textContent.trim().length > 0) return true;
        return !!(fragment.querySelector &&
                  fragment.querySelector('img, .math-inline, .math-block, table'));
    }

    // Returns true if it successfully inserted `html` by splitting
    // the block at `range`'s caret position; false if the block
    // isn't splittable or the range isn't usable, so the caller
    // should fall back to the block-level insertion instead.
    function _splitBlockAndInsertAt(range, html)
    {
        if (!range) return false;

        var container = range.startContainer;
        if (!container || !document.contains(container)) return false;

        var node = container.nodeType === Node.TEXT_NODE
            ? container.parentElement : container;
        if (!node || !node.closest) return false;

        var block = node.closest('.block');
        if (!block || !block.parentElement) return false;

        // Non-splittable blocks (Image, Table, MathBlock) — just
        // drop the new block after them, same as before.
        var blockType = block.getAttribute('data-type');
        if (blockType !== 'Paragraph') {
            block.insertAdjacentHTML('afterend', html);
            return true;
        }

        // Cursor at the very start of the paragraph — nothing to
        // split, just drop the image right before it and leave the
        // block completely untouched.
        if (_rangeIsAtStartOfBlock(block, range)) {
            block.insertAdjacentHTML('beforebegin', html);
            return true;
        }

        var afterRange;
        try {
            afterRange = document.createRange();
            afterRange.setStart(range.startContainer, range.startOffset);
            afterRange.setEnd(block, block.childNodes.length);
        } catch (e) {
            return false;
        }

        var afterFragment;
        try {
            afterFragment = afterRange.extractContents();
        } catch (e) {
            return false;
        }
        var afterHasContent = _fragmentHasContent(afterFragment);

        block.insertAdjacentHTML('afterend', html);

        if (afterHasContent) {
            var imageBlock = block.nextElementSibling;
            var newBlock = block.cloneNode(false);
            newBlock.setAttribute('data-id', generateId());
            newBlock.appendChild(afterFragment);
            if (imageBlock && imageBlock.parentElement) {
                imageBlock.insertAdjacentElement('afterend', newBlock);
            } else {
                block.insertAdjacentElement('afterend', newBlock);
            }
        }

        return true;
    }

    // Picks the best available cursor position to split at:
    //   1. The live selection, if it's still sitting inside a
    //      .block — covers the common case where inserting doesn't
    //      involve any focus-stealing round trip (e.g. a toolbar
    //      button or shortcut while the page keeps its selection).
    //   2. A range saved earlier via _saveCursorRangeForInsert() /
    //      _requestPaste(), for cases where a QFileDialog or an
    //      async clipboard read stole focus in between.
    function _getUsableInsertRange()
    {
        var sel = window.getSelection();
        if (sel && sel.rangeCount) {
            var range = sel.getRangeAt(0);
            var container = range.startContainer;
            if (container && document.contains(container)) {
                var node = container.nodeType === Node.TEXT_NODE
                    ? container.parentElement : container;
                if (node && node.closest && node.closest('.block')) {
                    return range.cloneRange();
                }
            }
        }

        if (pendingInsertRange) {
            var saved = pendingInsertRange;
            pendingInsertRange = null;
            if (saved.startContainer && document.contains(saved.startContainer)) {
                return saved;
            }
        }

        return null;
    }

    // Saves the current caret position so it can survive an
    // upcoming focus-stealing operation (e.g. opening a native
    // QFileDialog for "Insert Image"). Consumed by
    // _getUsableInsertRange() the next time an image/block is
    // inserted.
    function _saveCursorRangeForInsert()
    {
        var sel = window.getSelection();
        if (sel && sel.rangeCount) {
            pendingInsertRange = sel.getRangeAt(0).cloneRange();
        }
    }

    // ---------------------------------------------------------
    // Public image operations (called from Python via runJavaScript)
    // ---------------------------------------------------------

    function insertImage(src, alt, afterBlockId)
    {
        if (!src) return;

        var blockId = generateId();
        var encodedSrc = _encodeHtmlAttr(src);
        var encodedAlt = _encodeHtmlAttr(alt || '');

        var html = '<div class="block" data-type="Image" data-id="' + blockId + '">'
                 + '<img src="' + encodedSrc + '" alt="' + encodedAlt + '">'
                 + '</div>';

        // Priority for insertion position:
        //   1. A usable cursor Range — splits the paragraph exactly
        //      at the caret, so the image lands where the user was
        //      actually typing instead of always after the whole
        //      paragraph.
        //   2. afterBlockId parameter (passed from Python — block-
        //      level fallback, survives focus loss from QFileDialog
        //      when no Range was saved)
        //   3. pendingInsertBlockId (saved from right-click position)
        //   4. current selection's block
        //   5. lastFocusedBlockId (tracked by selectionchange)
        var range = _getUsableInsertRange();

        if (!range || !_splitBlockAndInsertAt(range, html)) {
            var insertAfterBlock = null;

            if (afterBlockId) {
                try {
                    insertAfterBlock = document.querySelector(
                        '.block[data-id="' + CSS.escape(afterBlockId) + '"]'
                    );
                } catch (e) {
                    // CSS.escape may not be available in older engines
                    insertAfterBlock = document.querySelector(
                        '.block[data-id="' + afterBlockId + '"]'
                    );
                }
            }

            if (!insertAfterBlock && pendingInsertBlockId) {
                try {
                    insertAfterBlock = document.querySelector(
                        '.block[data-id="' + CSS.escape(pendingInsertBlockId) + '"]'
                    );
                } catch (e) {
                    insertAfterBlock = document.querySelector(
                        '.block[data-id="' + pendingInsertBlockId + '"]'
                    );
                }
                pendingInsertBlockId = null;
            }

            if (insertAfterBlock) {
                insertAfterBlock.insertAdjacentHTML('afterend', html);
            } else {
                _insertBlockAtCursor(html);
            }
        }

        // Clear any pending range (consumed or not)
        pendingInsertRange = null;

        // Select the newly inserted image
        var block = document.querySelector('.block[data-id="' + blockId + '"]');
        if (block) {
            var img = block.querySelector('img');
            if (img) {
                // Wait for image to load before selecting (so naturalWidth
                // is available for aspect-ratio-preserving resize)
                img.onload = function() { _selectImage(img); };
                // If already cached, onload may not fire
                if (img.complete) _selectImage(img);
            }
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function deleteImage()
    {
        if (!selectedImageBlock) return;
        var block = selectedImageBlock;
        _clearImageSelection();
        if (block && block.parentElement) block.remove();
        if (bridge) bridge.reportSelection({ type: 'None' });
        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    // ---------------------------------------------------------
    // Selection-change reporter
    // ---------------------------------------------------------
    //
    // Listens to document.selectionchange and reports the current
    // format state to Python via bridge.reportSelection(). This
    // lets the host application update toolbar button states
    // (bold/italic/underline highlight, alignment, etc.) when the
    // cursor moves or the selection changes.
    //
    // Throttled to ~100ms to avoid flooding Python with events
    // during rapid cursor movement.
    // ---------------------------------------------------------

    var selectionChangeTimer = null;
    var selectionChangeAttached = false;

    // The data-id of the last block that had the cursor. Updated on
    // every selectionchange inside the editor. We store the ID (not
    // the DOM element) because Editor.setDocument() rebuilds the
    // entire DOM, making old element references stale. Looking up
    // by data-id always finds the current element.
    var lastFocusedBlockId = null;

    function _trackFocusedBlock()
    {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        var node = sel.anchorNode;
        if (!node) return;
        if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        if (!node || !node.closest) return;
        var block = node.closest('.block');
        if (block && block.hasAttribute('data-id')) {
            lastFocusedBlockId = block.getAttribute('data-id');
        }
    }

    function _attachSelectionChangeReporter()
    {
        if (selectionChangeAttached) return;
        selectionChangeAttached = true;

        document.addEventListener('selectionchange', function () {
            // Track the focused block immediately (not throttled) so
            // it's always current even if the reporter is debounced.
            _trackFocusedBlock();

            // Track the last non-collapsed selection for the context
            // menu (right-click collapses the selection, so we need
            // to remember what was selected before).
            _trackNonCollapsedSelection();

            if (selectionChangeTimer) clearTimeout(selectionChangeTimer);
            selectionChangeTimer = setTimeout(function () {
                selectionChangeTimer = null;
                if (!bridge) return;
                if (!_ensureSelectionInEditor()) return;
                var state = queryFormatState();
                state.type = 'Format';
                bridge.reportSelection(state);
            }, 100);
        });
    }

    // ---------------------------------------------------------
    // Block drag-and-drop (move image OR table block to a new position)
    // ---------------------------------------------------------
    //
    // Uses HTML5 drag-and-drop API. Two triggers:
    //   - Images: the <img> gets draggable="true" when selected
    //   - Tables: a dedicated .table-drag-handle (☰) appears when
    //     the table is selected; the handle has draggable="true"
    //
    // On dragstart we mark the source block with .image-dragging
    // or .table-dragging. On dragover another block, we show a
    // blue drop indicator line. On drop, we move the block to
    // the indicator's position.
    // ---------------------------------------------------------

    function _attachImageDragHandlers()
    {
        if (imageDragHandlersAttached) return;
        imageDragHandlersAttached = true;

        var root = document.getElementById('editor');
        if (!root) return;

        root.addEventListener('dragstart', function (e) {
            // ── Table drag handle? ──
            var handle = e.target.closest ? e.target.closest('.table-drag-handle') : null;
            if (handle) {
                var block = handle.closest('.block');
                if (!block) return;
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', block.getAttribute('data-id'));
                block.classList.add('table-dragging');
                return;
            }

            // ── Image drag? ──
            var img = _findImageElement(e.target);
            if (!img) return;
            var block = img.closest('.block');
            if (!block) return;

            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', block.getAttribute('data-id'));
            block.classList.add('image-dragging');
        });

        root.addEventListener('dragend', function (e) {
            // Cleanup — handles both image and table drag
            document.querySelectorAll('.image-dragging, .table-dragging').forEach(function (el) {
                el.classList.remove('image-dragging');
                el.classList.remove('table-dragging');
            });
            document.querySelectorAll('.image-drop-indicator, .block-drop-indicator').forEach(function (el) {
                el.remove();
            });
        });

        root.addEventListener('dragover', function (e) {
            if (!e.dataTransfer || e.dataTransfer.types.indexOf('text/plain') < 0) return;

            // Check for either image or table being dragged
            var dragging = root.querySelector('.image-dragging, .table-dragging');
            if (!dragging) return;

            var targetBlock = e.target.closest('.block');
            if (!targetBlock || targetBlock === dragging) return;

            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';

            // Determine top/bottom half
            var rect = targetBlock.getBoundingClientRect();
            var before = e.clientY < rect.top + rect.height / 2;

            // Remove old indicators
            document.querySelectorAll('.image-drop-indicator, .block-drop-indicator').forEach(function (el) {
                el.remove();
            });

            // Add new indicator
            var indicator = document.createElement('div');
            indicator.className = 'block-drop-indicator';
            if (before) {
                targetBlock.parentElement.insertBefore(indicator, targetBlock);
            } else {
                targetBlock.parentElement.insertBefore(indicator, targetBlock.nextSibling);
            }
        });

        root.addEventListener('drop', function (e) {
            var dragging = root.querySelector('.image-dragging, .table-dragging');
            if (!dragging) return;

            e.preventDefault();
            e.stopPropagation();

            var targetBlock = e.target.closest('.block');
            if (!targetBlock || targetBlock === dragging) {
                document.querySelectorAll('.image-drop-indicator, .block-drop-indicator').forEach(function (el) {
                    el.remove();
                });
                return;
            }

            var rect = targetBlock.getBoundingClientRect();
            var before = e.clientY < rect.top + rect.height / 2;

            if (before) {
                targetBlock.parentElement.insertBefore(dragging, targetBlock);
            } else {
                targetBlock.parentElement.insertBefore(dragging, targetBlock.nextSibling);
            }

            document.querySelectorAll('.image-drop-indicator, .block-drop-indicator').forEach(function (el) {
                el.remove();
            });
            dragging.classList.remove('image-dragging');
            dragging.classList.remove('table-dragging');

            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
        });
    }

/* ******** Text Formatting *********/

    // ---------------------------------------------------------
    // Text formatting via document.execCommand()
    //
    // While execCommand() is technically deprecated, it remains
    // the most practical approach for contenteditable editors
    // and works reliably in QtWebEngine (Chromium-based). Each
    // command operates on the current selection — if the cursor
    // is collapsed (no selection), the format applies to text
    // typed next.
    //
    // For font size, execCommand('fontSize') only supports sizes
    // 1-7 (HTML <font size>). To support arbitrary pixel sizes,
    // we use a custom span-wrapping approach via the Selection
    // and Range API.
    // ---------------------------------------------------------

    function _ensureSelectionInEditor()
    {
        // Make sure there's a selection inside a .page before
        // running a format command. If the user hasn't clicked
        // into a page, commands would silently fail.
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return false;

        var node = sel.anchorNode;
        if (!node) return false;

        var page = node.nodeType === Node.TEXT_NODE
            ? node.parentElement.closest('.page')
            : (node.closest ? node.closest('.page') : null);

        return !!page;
    }

    function _execFormat(command, value)
    {
        if (!_ensureSelectionInEditor()) return;

        // focus the editor's page so the command applies to the
        // right selection
        var sel = window.getSelection();
        if (sel.anchorNode && sel.anchorNode.parentElement) {
            var page = sel.anchorNode.parentElement.closest('.page');
            if (page) page.focus();
        }

        try {
            document.execCommand(command, false, value || null);
        } catch (e) {
            // Some commands may not be supported in all engines
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    // ── Basic text styles ───────────────────────────────

    function formatBold()         { _execFormat('bold'); }
    function formatItalic()       { _execFormat('italic'); }
    function formatUnderline()    { _execFormat('underline'); }
    function formatStrikethrough(){ _execFormat('strikeThrough'); }
    function formatSubscript()    { _execFormat('subscript'); }
    function formatSuperscript()  { _execFormat('superscript'); }

    // ── Colors ──────────────────────────────────────────

    function formatTextColor(color)
    {
        // Check if a math element is selected (or the cursor is
        // inside one). Math elements are contenteditable="false",
        // so execCommand('foreColor') can't reach them — we apply
        // the color directly to the math element's style.
        var mathEl = _getSelectedMathElement();
        if (mathEl) {
            mathEl.style.color = color;
            // Also set color on the inner KaTeX span so the formula
            // renders in the chosen color
            var katexSpan = mathEl.querySelector('.katex');
            if (katexSpan) katexSpan.style.color = color;
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
            return;
        }
        _execFormat('foreColor', color);
    }

    function formatHighlight(color)
    {
        var mathEl = _getSelectedMathElement();
        if (mathEl) {
            mathEl.style.backgroundColor = color;
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
            return;
        }
        _execFormat('hiliteColor', color);
    }

    // Returns the math element (.math-block or .math-inline) that
    // is either: (a) the element at the cursor position, or (b)
    // contained within the current selection. Returns null if no
    // math element is involved.
    function _getSelectedMathElement()
    {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return null;

        var range = sel.getRangeAt(0);

        // Case 1: collapsed cursor — check if it's inside a math element
        if (range.collapsed) {
            var node = range.startContainer;
            if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
            while (node && node.classList) {
                if (node.classList.contains('math-block') ||
                    node.classList.contains('math-inline')) {
                    return node;
                }
                node = node.parentElement;
            }
            return null;
        }

        // Case 2: non-collapsed selection — check if it contains
        // or intersects a math element
        var container = range.commonAncestorContainer;
        if (container.nodeType === Node.TEXT_NODE) container = container.parentElement;
        if (!container || !container.querySelectorAll) return null;

        var mathEls = container.querySelectorAll('.math-block, .math-inline');
        for (var i = 0; i < mathEls.length; i++) {
            // Check if this math element is within the selection range
            try {
                var mathRange = document.createRange();
                mathRange.selectNode(mathEls[i]);
                // If the selection contains or intersects the math element
                if (range.intersectsNode(mathEls[i])) {
                    // Verify it's actually within the selection bounds
                    var startCmp = range.compareBoundaryPoints(Range.START_TO_START, mathRange);
                    var endCmp = range.compareBoundaryPoints(Range.END_TO_END, mathRange);
                    if (startCmp <= 0 && endCmp >= 0) {
                        return mathEls[i];  // fully contained
                    }
                    // Or partially overlapping — still return it
                    return mathEls[i];
                }
            } catch (e) {}
        }
        return null;
    }

    // ── Font family ─────────────────────────────────────

    function formatFontFamily(font)   { _execFormat('fontName', font); }

    // ── Font size (custom, supports arbitrary px) ───────
    //
    // execCommand('fontSize') only supports 1-7. We wrap the
    // selection in a <span style="font-size: Npx"> instead so
    // any pixel size works.

    function formatFontSize(size)
    {
        if (!_ensureSelectionInEditor()) return;

        var sel = window.getSelection();
        if (!sel.rangeCount) return;

        // Normalize size to a string like "16px"
        var sizeStr = String(size).trim();
        if (/^\d+$/.test(sizeStr)) sizeStr += 'px';
        if (!/^\d+(px|em|rem|pt|%)$/.test(sizeStr)) return;

        var range = sel.getRangeAt(0);

        if (range.collapsed) {
            // No selection — insert a zero-width space wrapped in
            // a span so subsequent typing inherits the size
            var span = document.createElement('span');
            span.style.fontSize = sizeStr;
            span.appendChild(document.createTextNode('\u200B'));
            range.insertNode(span);

            // Move cursor after the span
            var newRange = document.createRange();
            newRange.setStartAfter(span);
            newRange.collapse(true);
            sel.removeAllRanges();
            sel.addRange(newRange);
        } else {
            // Wrap the selection's contents in a span
            var span = document.createElement('span');
            span.style.fontSize = sizeStr;
            try {
                range.surroundContents(span);
            } catch (e) {
                // surroundContents fails if the range spans
                // multiple block elements. Fall back to extract
                // and reinsert.
                var contents = range.extractContents();
                span.appendChild(contents);
                range.insertNode(span);
            }
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    // ── Text alignment ──────────────────────────────────

    function formatAlignLeft()    { _execFormat('justifyLeft'); }
    function formatAlignCenter()  { _execFormat('justifyCenter'); }
    function formatAlignRight()   { _execFormat('justifyRight'); }
    function formatAlignJustify() { _execFormat('justifyFull'); }

    // ── Indentation ─────────────────────────────────────

    function formatIndent()       { _execFormat('indent'); }
    function formatOutdent()      { _execFormat('outdent'); }

    // ── Lists ───────────────────────────────────────────

    function formatOrderedList()  { _execFormat('insertOrderedList'); }
    function formatUnorderedList(){ _execFormat('insertUnorderedList'); }

    // ── Line height ─────────────────────────────────────
    //
    // No execCommand for line-height, so we wrap the selection
    // in a <span style="line-height:..."> manually.

    function formatLineHeight(value)
    {
        if (!value) return;
        if (!_ensureSelectionInEditor()) return;
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        var range = sel.getRangeAt(0);
        if (range.collapsed) return;

        var span = document.createElement('span');
        span.style.lineHeight = value;
        try {
            range.surroundContents(span);
        } catch (e) {
            var frag = range.extractContents();
            span.appendChild(frag);
            range.insertNode(span);
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    // ── Letter spacing ──────────────────────────────────

    function formatLetterSpacing(value)
    {
        if (!value) return;
        if (!_ensureSelectionInEditor()) return;
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        var range = sel.getRangeAt(0);
        if (range.collapsed) return;

        var span = document.createElement('span');
        span.style.letterSpacing = value;
        try {
            range.surroundContents(span);
        } catch (e) {
            var frag = range.extractContents();
            span.appendChild(frag);
            range.insertNode(span);
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    // ── Clear formatting ────────────────────────────────

    function formatClear()
    {
        _execFormat('removeFormat');
        // Also remove any inline font-size spans from the selection
        _clearFontSizeSpans();
    }

    function _clearFontSizeSpans()
    {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;

        var range = sel.getRangeAt(0);
        if (range.collapsed) return;

        // Find all spans with font-size in the selection
        var container = range.commonAncestorContainer;
        var root = container.nodeType === Node.TEXT_NODE
            ? container.parentElement
            : container;

        var spans = root.querySelectorAll
            ? root.querySelectorAll('span[style*="font-size"]')
            : [];

        for (var i = 0; i < spans.length; i++) {
            var span = spans[i];
            // Check if this span is inside the selection range
            var spanRange = document.createRange();
            spanRange.selectNodeContents(span);
            if (range.intersectsNode(span)) {
                var parent = span.parentNode;
                while (span.firstChild) {
                    parent.insertBefore(span.firstChild, span);
                }
                parent.removeChild(span);
            }
        }
    }

    // ── Query current format state ──────────────────────
    //
    // Returns a dict of active formats at the current cursor
    // position. Useful for updating toolbar button states.

    function queryFormatState()
    {
        if (!_ensureSelectionInEditor()) return {};

        var state = {
            bold:          document.queryCommandState('bold'),
            italic:        document.queryCommandState('italic'),
            underline:     document.queryCommandState('underline'),
            strikeThrough: document.queryCommandState('strikeThrough'),
            subscript:     document.queryCommandState('subscript'),
            superscript:   document.queryCommandState('superscript'),
            justifyLeft:   document.queryCommandState('justifyLeft'),
            justifyCenter: document.queryCommandState('justifyCenter'),
            justifyRight:  document.queryCommandState('justifyRight'),
            justifyFull:   document.queryCommandState('justifyFull'),
            insertOrderedList:   document.queryCommandState('insertOrderedList'),
            insertUnorderedList: document.queryCommandState('insertUnorderedList'),
            fontName:      document.queryCommandValue('fontName'),
            fontSize:      document.queryCommandValue('fontSize'),
            foreColor:     document.queryCommandValue('foreColor'),
            hiliteColor:   document.queryCommandValue('hiliteColor')
        };

        // Try to extract pixel font-size from a wrapping span
        var sel = window.getSelection();
        if (sel && sel.rangeCount) {
            var node = sel.anchorNode;
            if (node && node.nodeType === Node.TEXT_NODE) {
                node = node.parentElement;
            }
            while (node && node.classList && !node.classList.contains('page')) {
                if (node.style && node.style.fontSize) {
                    state.fontSizePx = node.style.fontSize;
                    break;
                }
                node = node.parentElement;
            }
        }

        // Include current text direction (rtl/ltr/auto)
        state.direction = queryDirection();

        // Include the data-id of the block at cursor position.
        // Python stores this and passes it back to insertImage()
        // so the image lands at the right position even after
        // the editor loses focus (e.g. QFileDialog).
        if (sel && sel.rangeCount) {
            var bNode = sel.anchorNode;
            if (bNode && bNode.nodeType === Node.TEXT_NODE) {
                bNode = bNode.parentElement;
            }
            if (bNode && bNode.closest) {
                var bEl = bNode.closest('.block');
                if (bEl && bEl.hasAttribute('data-id')) {
                    state.blockId = bEl.getAttribute('data-id');
                }
            }
        }

        return state;
    }

/* ******** Text Direction (RTL/LTR) *********/

    // ---------------------------------------------------------
    // Right-to-left / left-to-right text direction support.
    //
    // - formatDirection(dir) sets the `dir` attribute on the
    //   closest block element (<p>, <h1>, <li>, <div>, etc.)
    //   containing the cursor.
    // - The chosen direction is remembered in `lastDirection`
    //   and automatically applied to any new <p> created by
    //   pressing Enter, until the user changes direction again.
    // - A MutationObserver watches .page-content for new <p>
    //   children and applies the remembered direction.
    // ---------------------------------------------------------

    // 'ltr' | 'rtl' | 'auto'  — null means "don't auto-apply"
    var lastDirection = null;
    var directionObserverAttached = false;

    // Block-level tags that should receive the `dir` attribute.
    var _DIRECTION_BLOCK_TAGS = {
        'P': true, 'H1': true, 'H2': true, 'H3': true,
        'H4': true, 'H5': true, 'H6': true,
        'LI': true, 'BLOCKQUOTE': true, 'PRE': true,
        'DIV': true, 'TD': true, 'TH': true
    };

    function _findDirectionBlock(node)
    {
        if (!node) return null;
        if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        while (node && node.classList && !node.classList.contains('page')) {
            if (_DIRECTION_BLOCK_TAGS[node.tagName]) return node;
            node = node.parentElement;
        }
        return null;
    }

    function formatDirection(dir)
    {
        // dir: 'ltr' | 'rtl' | 'auto'
        if (dir !== 'ltr' && dir !== 'rtl' && dir !== 'auto') return;

        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;

        // Find the block containing the cursor / selection
        var node = sel.anchorNode;
        var block = _findDirectionBlock(node);

        if (!block) {
            // No block element — fall back to the closest .page
            var page = document.querySelector('.page');
            if (page) {
                var content = page.querySelector('.page-content') || page;
                content.setAttribute('dir', dir);
            }
        } else {
            block.setAttribute('dir', dir);
        }

        // Remember for future paragraphs
        lastDirection = dir;

        // Report to Python so it can update toolbar state
        if (bridge) {
            bridge.reportSelection({ type: 'Direction', direction: dir });
        }

        if (bridge && typeof bridge.notifyContentChanged === 'function') {
            bridge.notifyContentChanged();
        }
    }

    function setPageDirection(direction)
    {
        document.body.dir = direction;
    }
    function queryDirection()
    {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return lastDirection || 'ltr';

        var block = _findDirectionBlock(sel.anchorNode);
        if (block) {
            var dir = block.getAttribute('dir');
            if (dir === 'rtl' || dir === 'ltr' || dir === 'auto') return dir;
        }
        // Fall back to inherited/computed direction
        if (block) {
            var cs = window.getComputedStyle(block);
            if (cs.direction === 'rtl') return 'rtl';
        }
        return lastDirection || 'ltr';
    }

    // ── Auto-apply remembered direction to new <p> elements ──
    //
    // When the user presses Enter inside a contenteditable, the
    // browser creates a new <p> (or <div>) for the next paragraph.
    // We watch for these insertions and apply `lastDirection` so
    // the user doesn't have to re-set direction on every paragraph.

    function _attachDirectionObserver()
    {
        if (directionObserverAttached) return;
        directionObserverAttached = true;

        var observer = new MutationObserver(function (mutations) {
            if (!lastDirection) return;  // no direction chosen yet

            for (var i = 0; i < mutations.length; i++) {
                var added = mutations[i].addedNodes;
                for (var j = 0; j < added.length; j++) {
                    var node = added[j];
                    if (node.nodeType !== Node.ELEMENT_NODE) continue;

                    // The new node itself might be a <p>
                    if (node.tagName === 'P' && !node.hasAttribute('dir')) {
                        node.setAttribute('dir', lastDirection);
                    }
                    // Or it might contain <p> children (e.g. a wrapper)
                    var ps = node.querySelectorAll ? node.querySelectorAll('p:not([dir])') : [];
                    for (var k = 0; k < ps.length; k++) {
                        ps[k].setAttribute('dir', lastDirection);
                    }
                }
            }
        });

        // Observe all .page-content containers. New pages created
        // by pagination will be picked up because they share the
        // same class — but we attach to #editor so it survives
        // setDocument() rebuilding .pages-wrapper.
        var root = document.getElementById('editor');
        if (root) {
            observer.observe(root, {
                childList: true,
                subtree: true
            });
        }
    }

    function renderMathFormulas()
    {
        // ── Wrap un-wrapped KaTeX elements first ──
        // This handles pasted KaTeX content that renders visually
        // but isn't inside a .math-block / .math-inline wrapper.
        // After wrapping, the formulas become editable.
        _wrapUnwrappedKaTeX();

        // Render math formulas using KaTeX auto-render
        if (typeof renderMathInElement !== "undefined") 
        {
            try 
            {
                var wrapper = document.querySelector(".pages-wrapper");
                if (wrapper) 
                {
                    renderMathInElement(wrapper, {
                        delimiters: [
                            { left: "$$", right: "$$", display: true },
                            { left: "\\[", right: "\\]", display: true },
                            { left: "$", right: "$", display: false },
                            { left: "\\(", right: "\\)", display: false }
                        ],
                        throwOnError: false
                    });
                }
            } 
            catch (e) 
            {
                console.warn("KaTeX rendering failed:", e);
            }
        }

        // Also render .math-block and .math-inline elements
        document.querySelectorAll(".math-block, .math-inline").forEach(function (el) 
        {
            var formula = el.getAttribute("data-formula");
            
            if (formula && typeof katex !== "undefined") 
            {
                try 
                {
                    var isDisplay = el.classList.contains("math-block");
                    el.innerHTML = "";
                    var span = document.createElement('span');
                    span.dir= "ltr";
                    span.contentEditable="false";
                    span.title = 'Double click to Edit';
                    //span.className = 'katex-render-target';
                    el.appendChild(span);
                    katex.render(formula, span, { 
                        displayMode: isDisplay,
                        throwOnError: false 
                    });
                } 
                catch (e) 
                {
                    el.textContent = formula;
                }
            }
        });
    }

    function applyEditableState()
    {
        // Apply contenteditable / spellcheck to any .page that is
        // missing it. Called after paginateAll() creates new pages
        // (via splits) so that those pages become editable without
        // re-attaching per-page listeners.
        if (!editable) return;

        document.querySelectorAll(".page").forEach(function (page) {
            if (page.getAttribute("contenteditable") !== "true") {
                page.setAttribute("contenteditable", "true");
                page.setAttribute("spellcheck", "true");
            }
        });
    }

    function ensureNextPage(wrapper, page) {
        var next = page.nextElementSibling;
        if (next && next.classList.contains("page")) {
            return next;
        }

        var newPage = document.createElement("div");
        newPage.className = "page";
        newPage.innerHTML = '<div class="page-content"></div>';

        if (page.nextSibling) {
            wrapper.insertBefore(newPage, page.nextSibling);
        } else {
            wrapper.appendChild(newPage);
        }

        return newPage;
    }

    function moveBlockToNextPage(wrapper, page, block) {
        var nextPage = ensureNextPage(wrapper, page);
        var nextContent = getPageContent(nextPage);
        nextContent.insertBefore(block, nextContent.firstChild);
    }

    function endOfContainer(container) {
        if (!container.lastChild) {
            return { node: container, offset: 0 };
        }
        var node = container.lastChild;
        if (node.nodeType === Node.TEXT_NODE) {
            return { node: node, offset: node.length };
        }
        return { node: container, offset: container.childNodes.length };
    }

    function findParagraphSplitPoint(p, maxBottom) {
        var walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
        var node;
        var lastValid = null;

        while ((node = walker.nextNode())) {
            for (var i = 0; i <= node.length; i++) {
                var range = document.createRange();
                range.setStart(p, 0);
                range.setEnd(node, i);

                var rects = range.getClientRects();
                if (!rects.length) {
                    continue;
                }

                var bottom = rects[rects.length - 1].bottom;

                if (bottom > maxBottom + 1) {
                    return lastValid;
                }

                if (i > 0 || node !== p.firstChild || lastValid !== null) {
                    lastValid = { node: node, offset: i };
                }
            }
        }

        return null;
    }

    // ──────────────────────────────────────────────────────────────
    // Block splitting — generalized for ANY splittable tag type.
    //
    // A "block" is a top-level element inside .page-content, wrapped
    // in a <div class="block" data-type="...">. The block's content
    // can be a <p>, <h1>-<h6>, <table>, <ul>/<ol>, <blockquote>,
    // <pre>, <div>, or any other tag.
    //
    // When a block overflows its page, we try to split it:
    //   1. Table  → split by rows (preserving thead)
    //   2. List   → split by <li> items
    //   3. Text   → split by line (p, h1-h6, blockquote, pre)
    //   4. Generic → split by child elements (div, section, etc.)
    //
    // If split succeeds, the tail portion is moved to a NEW block
    // on the next page. The new block becomes an independent
    // first-level block — satisfying the rule that "nested elements
    // can become independent blocks in case of overflow."
    //
    // If split fails (e.g. the content is a single unbreakable
    // element), the whole block is moved to the next page.
    // ──────────────────────────────────────────────────────────────

    /**
     * Split a text-containing block (p, h1-h6, blockquote, pre) at
     * the last line that fits on the current page. The tail is moved
     * to a new block on the next page, preserving the original tag.
     */
    function splitTextBlock(block, page, content)
    {
        // Find the first text-container element inside the block.
        // Supports p, h1-h6, blockquote, pre — all use the same
        // TreeWalker line-split logic.
        var textContainer = block.querySelector(
            "p, h1, h2, h3, h4, h5, h6, blockquote, pre"
        );
        if (!textContainer || !textContainer.textContent.trim())
        {
            return false;
        }

        var pageRect = page.getBoundingClientRect();
        var cs = getComputedStyle(page);
        var padBottom = parseFloat(cs.paddingBottom) || 0;
        var maxBottom = pageRect.bottom - padBottom;

        var splitPoint = findParagraphSplitPoint(textContainer, maxBottom);
        if (!splitPoint || (splitPoint.node === textContainer.firstChild && splitPoint.offset === 0))
        {
            return false;
        }

        var range = document.createRange();
        range.setStart(splitPoint.node, splitPoint.offset);
        range.setEnd(endOfContainer(textContainer).node, endOfContainer(textContainer).offset);

        var tail = range.extractContents();

        if (!textContainer.textContent || !textContainer.textContent.trim()) {
            textContainer.appendChild(tail);
            return false;
        }

        if (!tail.textContent || !tail.textContent.trim()) {
            textContainer.appendChild(tail);
            return false;
        }

        var wrapper = page.closest(".pages-wrapper");
        var nextPage = ensureNextPage(wrapper, page);
        var nextContent = getPageContent(nextPage);

        var newBlock = document.createElement("div");
        newBlock.className = block.className;
        // Copy ALL attributes from the original .block wrapper —
        // style, data-type, dir, data-*, etc. — so the split block
        // keeps the same styling as the original.
        _copyAttributes(block, newBlock, { 'data-id': true });
        newBlock.setAttribute("data-id", generateId());

        // Preserve the original tag name (p, h1, blockquote, pre, ...)
        // and ALL its attributes (class, style, dir, data-*, etc.)
        var tagName = textContainer.tagName.toLowerCase();
        var newContainer = document.createElement(tagName);
        _copyAttributes(textContainer, newContainer);
        newContainer.appendChild(tail);
        newBlock.appendChild(newContainer);

        nextContent.insertBefore(newBlock, nextContent.firstChild);
        return true;
    }

    /**
     * Split a list block (ul/ol) at the last <li> that fits on the
     * current page. Remaining <li> items are moved to a new list
     * block on the next page.
     */
    function splitListBlock(block, page)
    {
        var list = block.querySelector("ul, ol");
        if (!list) return false;

        // Snapshot children (HTMLCollection is live)
        var items = Array.prototype.slice.call(list.children);
        if (items.length < 2) return false;

        var pageRect = page.getBoundingClientRect();
        var cs = getComputedStyle(page);
        var padBottom = parseFloat(cs.paddingBottom) || 0;
        var maxBottom = pageRect.bottom - padBottom;

        // Find the first <li> that overflows the page
        var splitIdx = -1;
        for (var i = 0; i < items.length; i++) {
            var rect = items[i].getBoundingClientRect();
            if (rect.bottom > maxBottom + 1) {
                splitIdx = i;
                break;
            }
        }

        // If even the first item overflows, can't split here — let
        // the caller move the whole block or try a deeper split.
        if (splitIdx <= 0) return false;

        var wrapper = page.closest(".pages-wrapper");
        var nextPage = ensureNextPage(wrapper, page);
        var nextContent = getPageContent(nextPage);

        var newBlock = document.createElement("div");
        newBlock.className = block.className;
        // Copy ALL attributes from the original .block wrapper —
        // style, data-type, dir, data-*, etc. — so the split block
        // keeps the same styling as the original.
        _copyAttributes(block, newBlock, { 'data-id': true });
        newBlock.setAttribute("data-id", generateId());

        // Create a new list of the same type (ul or ol), preserving
        // ALL attributes (class, style, start, type, reversed, dir,
        // data-*, etc.) — not just the few that were hardcoded.
        var newList = document.createElement(list.tagName);
        _copyAttributes(list, newList);

        // Move items from splitIdx onwards to the new list.
        // This is safe because we snapshotted items to a plain Array.
        for (var j = splitIdx; j < items.length; j++) {
            newList.appendChild(items[j]);
        }
        newBlock.appendChild(newList);

        nextContent.insertBefore(newBlock, nextContent.firstChild);
        return true;
    }

    /**
     * Split a generic container block (div, section, article, etc.)
     * by its child elements. The first child that overflows and all
     * subsequent children are moved to a new block on the next page.
     *
     * This handles blocks that contain multiple sub-elements but
     * aren't tables, lists, or single text containers.
     */
    function splitGenericBlock(block, page)
    {
        // Find the main content element inside the .block div.
        // This is the first element child (not text node).
        var contentEl = null;
        for (var i = 0; i < block.children.length; i++) {
            contentEl = block.children[i];
            break;
        }
        if (!contentEl) return false;

        // Get the children of the content element
        var children = Array.prototype.slice.call(contentEl.children);
        if (children.length < 2) return false;

        var pageRect = page.getBoundingClientRect();
        var cs = getComputedStyle(page);
        var padBottom = parseFloat(cs.paddingBottom) || 0;
        var maxBottom = pageRect.bottom - padBottom;

        // Find the first child that overflows
        var splitIdx = -1;
        for (var i = 0; i < children.length; i++) {
            var rect = children[i].getBoundingClientRect();
            if (rect.bottom > maxBottom + 1) {
                splitIdx = i;
                break;
            }
        }

        if (splitIdx <= 0) return false;

        var wrapper = page.closest(".pages-wrapper");
        var nextPage = ensureNextPage(wrapper, page);
        var nextContent = getPageContent(nextPage);

        var newBlock = document.createElement("div");
        newBlock.className = block.className;
        // Copy ALL attributes from the original .block wrapper —
        // style, data-type, dir, data-*, etc. — so the split block
        // keeps the same styling as the original.
        _copyAttributes(block, newBlock, { 'data-id': true });
        newBlock.setAttribute("data-id", generateId());

        // Clone the content element's tag + ALL attributes (class,
        // style, dir, data-*, etc.) — not just className and style.
        var newContentEl = document.createElement(contentEl.tagName);
        _copyAttributes(contentEl, newContentEl);

        // Move children from splitIdx onwards to the new content element
        for (var j = splitIdx; j < children.length; j++) {
            newContentEl.appendChild(children[j]);
        }
        newBlock.appendChild(newContentEl);

        nextContent.insertBefore(newBlock, nextContent.firstChild);
        return true;
    }

    /**
     * Dispatcher: try to split a block based on its content type.
     * Returns true if the block was successfully split, false if it
     * should be moved whole to the next page.
     *
     * Order matters:
     *   1. Table  (most specific — needs row splitting)
     *   2. List   (ul/ol — needs li splitting)
     *   3. Text   (p, h1-h6, blockquote, pre — line splitting)
     *   4. Generic (div, section — child splitting)
     */
    function trySplitBlock(block, page, content)
    {
        // 1. Table → split by rows
        if (block.querySelector("table")) {
            if (splitTableBlock(block, page)) return true;
            // If table split failed (e.g. only 1 row), fall through
            // to try other strategies or move whole.
        }

        // 2. List → split by <li> items
        if (block.querySelector("ul, ol")) {
            if (splitListBlock(block, page)) return true;
        }

        // 3. Text container → split by lines
        var textContainer = block.querySelector(
            "p, h1, h2, h3, h4, h5, h6, blockquote, pre"
        );
        if (textContainer && textContainer.textContent.trim()) {
            if (splitTextBlock(block, page, content)) return true;
        }

        // 4. Generic container → split by children
        if (splitGenericBlock(block, page)) return true;

        // All split strategies failed — caller should move whole block
        return false;
    }

    function splitTableBlock(block, page)
    {
        var table = block.querySelector("table");
        if (!table) return false;

        var pageRect = page.getBoundingClientRect();
        var tableRect = table.getBoundingClientRect();
        var cs = getComputedStyle(page);
        var padBottom = parseFloat(cs.paddingBottom) || 0;
        // Available space on current page for this table's rows.
        // Measured from the table's top (which includes thead/caption)
        // to the page's bottom padding edge.
        var available = pageRect.bottom - padBottom - tableRect.top;

        if (available <= 0) return false;

        var tbody = table.tBodies && table.tBodies[0];

        if (!tbody) return false;

        // ── FIX ─────────────────────────────────────────────
        // tbody.rows is a LIVE HTMLCollection. Appending a row
        // to another parent immediately removes it from the
        // collection and reindexes every subsequent row, which
        // scrambles the iteration and produces out-of-order,
        // partially-moved rows on the next page.
        //
        // Snapshot to a plain Array first so the loop indices
        // stay stable across the mutations below.
        // ────────────────────────────────────────────────────
        var rows = Array.prototype.slice.call(tbody.rows);
        if (!rows.length || rows.length < 2) return false;

        var splitIdx = -1;
        var cum = 0;

        for (var i = 0; i < rows.length; i++)
        {
            var rowH = rows[i].offsetHeight;

            if (rowH <= 0) continue;

            if (cum + rowH > available)
            {
                splitIdx = i;
                break;
            }
            cum += rowH;
        }

        if (splitIdx <= 0 || splitIdx >= rows.length) return false;

        var wrapper = page.closest(".pages-wrapper");
        var nextPage = ensureNextPage(wrapper, page);
        var nextContent = getPageContent(nextPage);

        var newBlock = document.createElement("div");
        newBlock.className = block.className;
        // Copy ALL attributes from the original .block wrapper to the
        // new one — style (margins, etc.), data-type, data-id stays
        // unique (generated below), dir, and any data-* attributes.
        _copyAttributes(block, newBlock, { 'data-id': true });
        newBlock.setAttribute("data-id", generateId());

        var newTable = document.createElement("table");
        // Copy ALL attributes from the original <table> — className,
        // style (width, borders, font, background, etc.), width,
        // border, cellpadding, cellspacing, dir, data-*, etc.
        _copyAttributes(table, newTable);

        // ── Copy <colgroup> (column widths) ──
        // The colgroup defines column widths via <col style="width:Npx">.
        // Without it, the split table's columns collapse to auto width.
        var colgroup = table.querySelector("colgroup");
        if (colgroup) {
            newTable.appendChild(colgroup.cloneNode(true));
        }

        // ── Copy <thead> (header rows repeat on each split) ──
        var thead = table.querySelector("thead");
        if (thead) {
            newTable.appendChild(thead.cloneNode(true));
        }

        // Note: <caption> and <tfoot> are intentionally NOT copied
        // to the continuation. <caption> belongs on the first part
        // only; <tfoot> belongs on the last part only. Most editor
        // tables don't use either, so we leave them on the original.

        var newTbody = document.createElement("tbody");
        // Copy tbody attributes (some tables put style/class on tbody)
        _copyAttributes(tbody, newTbody);

        // Safe to iterate the static snapshot — moving rows
        // out of `tbody` no longer affects `rows.length` or indices.
        for (var j = splitIdx; j < rows.length; j++)
        {
            newTbody.appendChild(rows[j]);
        }
        newTable.appendChild(newTbody);
        newBlock.appendChild(newTable);

        nextContent.insertBefore(newBlock, nextContent.firstChild);
        return true;
    }

    // ── Copy all attributes from src to dst ──────────────────
    // Used by splitTableBlock to preserve ALL table properties
    // (style, width, border, cellpadding, cellspacing, dir,
    // data-*, etc.) on the split table. Without this, only
    // className was copied and the split table lost its styling.
    //
    // `skip` is an optional object whose keys are attribute names
    // to skip (e.g. { 'data-id': true } to avoid overwriting the
    // newly-generated data-id on the .block wrapper).
    function _copyAttributes(src, dst, skip)
    {
        if (!src || !dst) return;
        skip = skip || {};
        for (var i = 0; i < src.attributes.length; i++) {
            var attr = src.attributes[i];
            if (skip[attr.name]) continue;
            dst.setAttribute(attr.name, attr.value);
        }
    }

    function removeEmptyPages(wrapper)
    {
        wrapper.querySelectorAll(".page").forEach(function (page)
        {
            var content = getPageContent(page);
            var blocks = content.querySelectorAll(":scope > .block");
            if (!blocks.length && !content.textContent.trim())
            {
                page.remove();
            }
        });
    }

    function renumberPages(wrapper)
    {
        var pages = wrapper.querySelectorAll(".page");

        pages.forEach(function (page, index)
        {
            page.setAttribute("data-page", String(index));
        });

        // ── Page-number markers in the gaps ──────────────────
        // Remove any previously-inserted markers first, so we
        // never accumulate stale ones across paginateAll() calls.
        wrapper.querySelectorAll(".page-number").forEach(function (el)
        {
            el.remove();
        });

        // Insert a marker before every page except the first.
        // The marker shows the upcoming page's number (1-indexed
        // for display). Change `i + 1` to `i` for 0-indexed, or
        // to `"Page " + (i + 1)` for a labeled form.
        for (var i = 1; i < pages.length; i++)
        {
            var marker = document.createElement("div");
            marker.className = "page-number";
            marker.innerHTML = '<span>PAGE ' + String(i) +'</span>';
            wrapper.insertBefore(marker, pages[i]);
        }
    }

    // ── Editor mode: 'paged' (default) or 'continuous' ──
    // In 'paged' mode, paginateAll() splits content into fixed-size
    // pages with page-number markers between them.
    // In 'continuous' mode, the single draft page grows to fit all
    // content — no splitting, no page numbers. paginateAll() is a
    // no-op in this mode.
    var editorMode = 'paged';

    function setMode(mode)
    {
        if (mode !== 'paged' && mode !== 'continuous') return;
        editorMode = mode;
        var root = document.getElementById('editor');
        if (!root) return;
        if (mode === 'continuous') 
        {
            root.classList.add('continuous-mode');
        } else 
        {
            root.classList.remove('continuous-mode');
            // Remove the style attribute entirely if it's now empty
            root.removeAttribute('style');
        }
    }

    function getMode()
    {
        return editorMode;
    }

    function paginateAll()
    {
        var wrapper = document.querySelector(".pages-wrapper");

        if (!wrapper) return "[]";

        // In continuous mode, pagination is a no-op — the single
        // draft page already contains all content and grows to fit.
        // We just renumber (which is a no-op for one page) and
        // export so the Python model stays in sync.
        if (editorMode === 'continuous') {
            return Editor.exportDocument();
        }

        var maxIter = 2000;

        // ── Phase 1: Same-page table merge ──
        // Merge adjacent Table blocks on the SAME page into a single
        // <table>. This handles saved files that contain pre-split
        // table fragments — after reload, they all land on the draft
        // page as separate blocks. Without this pass, they'd stay as
        // multiple stacked <table> elements (disjointed appearance).
        //
        // Run this BEFORE the split pass so the split pass can
        // re-split the merged table if it overflows.
        _mergeAdjacentTablesOnAllPages(wrapper);

        // ── Phase 2: Split pass ──
        // Move blocks forward (to the next page) until no page
        // overflows. This fills each page to capacity from the
        // top, but may create extra pages if the initial metrics
        // (e.g. fallback fonts) were larger than the real metrics.
        for (var iter = 0; iter < maxIter; iter++)
        {
            var moved = false;
            var pages = wrapper.querySelectorAll(".page");

            for (var pi = 0; pi < pages.length; pi++)
            {
                var page = pages[pi];
                var content = getPageContent(page);

                var overflow = content.scrollHeight - content.clientHeight;

                if (overflow <= 2) continue;

                var blocks = content.querySelectorAll(":scope > .block");

                if (!blocks.length) continue;

                var lastBlock = blocks[blocks.length - 1];

                // ── Unsplitable block → move whole to next page ──
                // (Image, Math, or blocks with only void elements)
                if (isUnsplitableBlock(lastBlock))
                {
                    if (blocks.length === 1) continue;

                    moveBlockToNextPage(wrapper, page, lastBlock);
                    moved = true;
                    continue;
                }

                // ── Try to split the block ──
                // trySplitBlock dispatches to the right splitter based
                // on the block's content (table, list, text, or generic).
                // If split succeeds, the tail is moved to a new block on
                // the next page. If it fails, we move the whole block.
                if (trySplitBlock(lastBlock, page, content))
                {
                    moved = true;
                    continue;
                }

                // ── Split failed → move whole block to next page ──
                if (blocks.length === 1) continue;

                moveBlockToNextPage(wrapper, page, lastBlock);
                moved = true;
            }

            if (!moved) break;
        }

        // ── Phase 3: Cross-page merge pass ──
        // After the split pass, some pages may have free space at
        // the bottom (because a block was too tall to fit and moved
        // whole, or because font metrics changed after the initial
        // split). This pass pulls blocks BACK from the next page
        // into the current page when they fit, eliminating
        // unnecessary pages.
        //
        // Without this pass, a 1.5-page document could end up on 3
        // pages: the split pass creates 3 pages with fallback font
        // metrics, real fonts load (shorter content), but no page
        // overflows so nothing re-paginates. The merge pass detects
        // the free space and consolidates.
        _mergePagesBack(wrapper);

        removeEmptyPages(wrapper);
        renumberPages(wrapper);
        applyEditableState();
        renderMathFormulas();

        // ── Safety net: re-check after fonts load ──
        // paginateAll() uses getBoundingClientRect() to find split
        // points. If fonts were still loading when this ran, the
        // measurements used fallback metrics. Once the real fonts
        // load, text reflows and may overflow pages that looked OK.
        // This one-shot listener re-checks for overflow after fonts
        // are ready and re-paginates if needed.
        // _scheduleFontReadyRecheck is idempotent (guarded by a flag)
        // so calling paginateAll() multiple times doesn't stack up
        // multiple listeners.
        _scheduleFontReadyRecheck();

        return Editor.exportDocument();
    }

    /**
     * Same-page table merge: for each page, scan for adjacent Table
     * blocks and merge their rows into a single <table>.
     *
     * This handles saved files that contain pre-split table fragments.
     * When such a file is loaded, all fragments land on the draft page
     * as separate <div class="block" data-type="Table"> blocks, each
     * with its own <table> element. Without this pass, they'd stay as
     * multiple stacked tables (disjointed appearance).
     *
     * Algorithm: for each page, iterate through blocks. When two
     * adjacent blocks are both Table type, move all rows from the
     * second block's <tbody> into the first block's <tbody>, then
     * remove the now-empty second block. Repeat until no more adjacent
     * table pairs exist on the page.
     *
     * Note: this pass does NOT check page overflow — it merges
     * unconditionally. If the merged table now overflows, the split
     * pass will have already run (Phase 1), and the cross-page merge
     * pass (Phase 3) will run after this. The split pass won't re-run
     * automatically, but the font-ready safety net will catch any
     * overflow on the next paginateAll() call.
     *
     * Actually, to be safe, we DO check overflow: if merging would
     * cause the page to overflow, we skip the merge (leave them as
     * separate blocks on the same page — they'll be split properly
     * on the next paginateAll() cycle).
     */
    function _mergeAdjacentTablesOnAllPages(wrapper)
    {
        var pages = wrapper.querySelectorAll(".page");

        pages.forEach(function(page) {
            _mergeAdjacentTablesOnPage(page);
        });
    }

    function _mergeAdjacentTablesOnPage(page)
    {
        var content = getPageContent(page);
        if (!content) return;

        // Iterate through blocks. Use a while loop with index because
        // we're modifying the list (removing blocks) during iteration.
        var i = 0;
        var blocks = content.children;
        while (i < blocks.length - 1)
        {
            var blockA = blocks[i];
            var blockB = blocks[i + 1];

            // Both must be Table blocks
            if (!blockA || !blockB) break;
            if (blockA.getAttribute("data-type") !== "Table" ||
                blockB.getAttribute("data-type") !== "Table")
            {
                i++;
                continue;
            }

            var tableA = blockA.querySelector("table");
            var tableB = blockB.querySelector("table");
            if (!tableA || !tableB)
            {
                i++;
                continue;
            }

            var tbodyA = tableA.tBodies && tableA.tBodies[0];
            var tbodyB = tableB.tBodies && tableB.tBodies[0];
            if (!tbodyA || !tbodyB)
            {
                i++;
                continue;
            }

            // Snapshot B's rows (live HTMLCollection)
            var rowsB = Array.prototype.slice.call(tbodyB.rows);
            if (rowsB.length === 0)
            {
                // B is empty — just remove it
                blockB.remove();
                // Don't increment i — the next block shifts into position i+1
                continue;
            }

            // Tentatively move all rows from B to A
            for (var j = 0; j < rowsB.length; j++)
            {
                tbodyA.appendChild(rowsB[j]);
            }

            // Check if page now overflows
            if (content.scrollHeight - content.clientHeight > 2)
            {
                // Overflow — move all rows back to B and stop merging
                // this pair. The split pass will handle re-splitting
                // if needed on the next paginateAll() cycle.
                for (var k = 0; k < rowsB.length; k++)
                {
                    tbodyB.appendChild(rowsB[k]);
                }
                i++;
            }
            else
            {
                // No overflow — remove the now-empty block B
                blockB.remove();
                // Don't increment i — block A might merge with the
                // next block too (if there was a 3rd table fragment)
            }
        }
    }

    /**
     * Merge pass: for each page (except the last), pull blocks from
     * the beginning of the next page into the end of the current page,
     * as long as they fit without overflowing.
     *
     * This is the counterpart to the split pass. The split pass only
     * moves blocks FORWARD; this pass moves blocks BACKWARD when
     * there's room. Together they produce the minimum number of pages.
     *
     * Algorithm: for each page pi, try to move blocks from page pi+1
     * to page pi. After moving a block, check if page pi overflows;
     * if so, move the block back and stop (subsequent blocks are
     * unlikely to be smaller). Then advance to page pi+1 and repeat.
     *
     * ── Table row merging ──
     * When the next page's first block is a table that was split
     * from the current page's last table block, we don't just move
     * the whole block — we merge its rows back into the original
     * table. This prevents "disjointed rows" where a single logical
     * table appears as multiple separate <table> elements stacked
     * on the same page after the merge pass.
     */
    function _mergePagesBack(wrapper)
    {
        var pages = wrapper.querySelectorAll(".page");

        for (var pi = 0; pi < pages.length - 1; pi++)
        {
            var page = pages[pi];
            var content = getPageContent(page);
            var nextPage = pages[pi + 1];
            var nextContent = getPageContent(nextPage);

            // Pull blocks from next page until current page is full
            while (nextContent.children.length > 0)
            {
                var firstBlock = nextContent.children[0];

                // ── Try table row merge first ──
                // If both the current page's last block and the next
                // page's first block are Table blocks, try to merge
                // the rows from the next block's table into the
                // current block's table. This keeps the visual table
                // intact instead of leaving two separate <table>
                // elements stacked.
                if (firstBlock.getAttribute("data-type") === "Table")
                {
                    var prevBlock = content.children[content.children.length - 1];
                    if (prevBlock && prevBlock.getAttribute("data-type") === "Table")
                    {
                        var mergeResult = _tryMergeTableRows(prevBlock, firstBlock, content);
                        if (mergeResult === "removed")
                        {
                            // All rows merged, src block removed —
                            // continue to next block on next page
                            continue;
                        }
                        if (mergeResult === "partial")
                        {
                            // Some rows merged, but src block still
                            // has rows that don't fit. We can't move
                            // the whole src block here (it would
                            // create disjointed stacked tables), so
                            // stop pulling from this page pair.
                            break;
                        }
                        // mergeResult === "none" — no rows could
                        // merge. The src block might be empty (handled
                        // by "removed") or the first row doesn't fit.
                        // Don't fall through to whole-block move for
                        // table-to-table adjacency — that creates
                        // disjointed tables. Stop this page pair.
                        break;
                    }
                }

                // Tentatively move the block to the end of current page
                content.appendChild(firstBlock);

                // Check if current page now overflows
                if (content.scrollHeight - content.clientHeight > 2)
                {
                    // Doesn't fit — move it back to next page and stop
                    nextContent.insertBefore(firstBlock, nextContent.firstChild);
                    break;
                }
                // Fits — keep it and try the next block from next page
            }
        }
    }

    /**
     * Try to merge rows from srcTableBlock's table into dstTableBlock's
     * table. Moves rows one at a time from src to dst, checking that
     * the page doesn't overflow after each move. Stops when the page
     * is full or src has no more rows.
     *
     * If srcTableBlock becomes empty (all rows moved), it is removed.
     *
     * Returns:
     *   "removed"  — all rows merged, src block removed
     *   "partial"  — some rows merged, src block still has rows
     *   "none"     — no rows merged (first row didn't fit), src intact
     */
    function _tryMergeTableRows(dstTableBlock, srcTableBlock, dstPageContent)
    {
        var dstTable = dstTableBlock.querySelector("table");
        var srcTable = srcTableBlock.querySelector("table");
        if (!dstTable || !srcTable) return "none";

        var dstTbody = dstTable.tBodies && dstTable.tBodies[0];
        var srcTbody = srcTable.tBodies && srcTable.tBodies[0];
        if (!dstTbody || !srcTbody) return "none";

        // Snapshot src rows (live HTMLCollection)
        var srcRows = Array.prototype.slice.call(srcTbody.rows);
        if (srcRows.length === 0)
        {
            // Source table has no tbody rows — remove the empty block
            srcTableBlock.remove();
            return "removed";
        }

        var movedAny = false;
        var dstPageContentEl = dstPageContent;

        for (var i = 0; i < srcRows.length; i++)
        {
            var row = srcRows[i];
            // Tentatively append to dst tbody
            dstTbody.appendChild(row);

            // Check if dst page now overflows
            if (dstPageContentEl.scrollHeight - dstPageContentEl.clientHeight > 2)
            {
                // Doesn't fit — move the row back to src
                srcTbody.appendChild(row);
                break;
            }
            // Fits — keep the row in dst
            movedAny = true;
        }

        // If we moved all rows, remove the now-empty src block
        if (srcTbody.rows.length === 0)
        {
            srcTableBlock.remove();
            return "removed";
        }

        return movedAny ? "partial" : "none";
    }

    var _fontRecheckScheduled = false;

    function _scheduleFontReadyRecheck()
    {
        if (_fontRecheckScheduled) return;
        if (!document.fonts || !document.fonts.ready) return;

        _fontRecheckScheduled = true;

        document.fonts.ready.then(function() {
            _fontRecheckScheduled = false;

            // Only re-paginate if we're still in paged mode and there
            // is actual overflow. This avoids unnecessary work when
            // fonts were already loaded before paginateAll() ran.
            if (editorMode !== 'paged') return;

            var pages = document.querySelectorAll('.pages-wrapper > .page');
            var needsRepaginate = false;
            for (var i = 0; i < pages.length; i++) {
                var c = pages[i].querySelector('.page-content');
                if (c && c.scrollHeight - c.clientHeight > 2) {
                    needsRepaginate = true;
                    break;
                }
            }

            if (needsRepaginate) {
                // Use requestAnimationFrame to ensure layout has
                // settled after the font swap before re-paginating.
                requestAnimationFrame(function() {
                    requestAnimationFrame(function() {
                        paginateAll();
                    });
                });
            }
        });
    }

/* ******** Context Menu *********/

    // ---------------------------------------------------------
    // Right-click context menu.
    //
    // The menu adapts to what was right-clicked:
    //   - Text selection: Cut / Copy / Paste / Delete
    //   - Table cell: + Add Row / Add Column / Remove Row /
    //     Remove Column / Delete Table (with separator)
    //   - Image: Cut / Copy / Paste Image (from clipboard)
    //
    // Default text operations (Cut/Copy/Paste) use the
    // clipboard API + execCommand for maximum compatibility.
    // Paste Image reads image data from the clipboard and
    // inserts it as a new Image block.
    // ---------------------------------------------------------

    var contextMenuAttached = false;
    var contextMenuImageBuffer = null;  // {src, alt} for image copy/cut

    // The last NON-COLLAPSED selection inside the editor.
    // Updated continuously on selectionchange. When the user
    // right-clicks, the browser collapses the selection to the
    // click point — so by the time _saveSelectionForMenu() runs,
    // the selection is gone. We fall back to this saved range.
    var lastNonCollapsedRange = null;
    var lastNonCollapsedPage = null;

    function _trackNonCollapsedSelection()
    {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;

        var range = sel.getRangeAt(0);
        if (range.collapsed) return;  // only save non-collapsed

        // Make sure it's inside the editor
        var node = range.startContainer;
        if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        if (!node || !node.closest || !node.closest('.page')) return;

        lastNonCollapsedRange = range.cloneRange();
        lastNonCollapsedPage = node.closest('.page');
    }

    // Saved selection at the moment the context menu was opened.
    // execCommand('cut'/'copy'/'paste') requires a focused
    // contenteditable with an active selection — but clicking a
    // menu item moves focus to the menu. We restore this range
    // before running the command so it targets the right text.
    var contextMenuSavedRange = null;
    var contextMenuSavedPage = null;

    function _saveSelectionForMenu(clickX, clickY)
    {
        var sel = window.getSelection();
        var currentRange = (sel && sel.rangeCount) ? sel.getRangeAt(0) : null;
        var currentIsCollapsed = !currentRange || currentRange.collapsed;

        // Only use lastNonCollapsedRange if the right-click point is
        // INSIDE that range. If the user right-clicked elsewhere, they
        // want the caret at the click point, not the old selection.
        if (currentIsCollapsed && lastNonCollapsedRange && clickX !== undefined && clickY !== undefined) {
            // Check if the click point is inside lastNonCollapsedRange
            var rect = lastNonCollapsedRange.getBoundingClientRect();
            var insideOldSelection = (
                clickX >= rect.left && clickX <= rect.right &&
                clickY >= rect.top && clickY <= rect.bottom
            );
            if (insideOldSelection) {
                contextMenuSavedRange = lastNonCollapsedRange.cloneRange();
                contextMenuSavedPage = lastNonCollapsedPage;
                return;
            }
        }

        // Use the current selection (either non-collapsed, or the
        // caret placed at the right-click point by _placeCursorAtPoint)
        if (currentRange) {
            contextMenuSavedRange = currentRange.cloneRange();
            var node = sel.anchorNode;
            if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
            while (node && node.classList && !node.classList.contains('page')) {
                node = node.parentElement;
            }
            contextMenuSavedPage = node;
        } else {
            contextMenuSavedRange = null;
            contextMenuSavedPage = null;
        }
    }

    function _restoreSelectionForMenu()
    {
        if (!contextMenuSavedRange || !contextMenuSavedPage) return false;
        try {
            contextMenuSavedPage.focus();
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(contextMenuSavedRange);
            return true;
        } catch (e) {
            return false;
        }
    }

    function _execTextCommand(cmd)
    {
        // Restore the selection that was active when the menu opened,
        // then focus the page so execCommand has a valid target.
        _restoreSelectionForMenu();

        // Cut and Copy are routed through Python because
        // document.execCommand('cut'/'copy') is unreliable in
        // QtWebEngine (works only in secure contexts with user
        // gesture, and silently fails otherwise). Delete and
        // other commands work fine via execCommand.
        if (cmd === 'cut' || cmd === 'copy') 
        {
            _cutCopyViaBridge(cmd);
            return;
        }

        try 
        {
            document.execCommand(cmd, false, null);
        } 
        catch (e) {}
        if (bridge && typeof bridge.notifyContentChanged === 'function') 
        {
            bridge.notifyContentChanged();
        }
    }

    function _cutCopyViaBridge(cmd)
    {
        // Capture the selection's text and HTML before doing anything.
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;

        var range = sel.getRangeAt(0);
        if (range.collapsed) return;

        var text = sel.toString();
        var html = '';
        try {
            // Clone the range contents to a fragment, then wrap
            // in a div so we can get innerHTML.
            var fragment = range.cloneContents();
            var div = document.createElement('div');
            div.appendChild(fragment);
            html = div.innerHTML;
        } catch (e) {
            html = text;  // fallback
        }

        // Send to Python via bridge — Python will write to the
        // system clipboard via QGuiApplication.
        if (bridge) {
            if (cmd === 'cut' && typeof bridge.requestCut === 'function') {
                bridge.requestCut(text, html);
            } else if (cmd === 'copy' && typeof bridge.requestCopy === 'function') {
                bridge.requestCopy(text, html);
            }
        }

        // For cut, also delete the selection locally.
        // execCommand('delete') is allowed (not blocked like 'cut').
        if (cmd === 'cut') {
            try {
                document.execCommand('delete', false, null);
            } catch (e) {
                // Fallback: manually delete the range contents
                try { range.deleteContents(); } catch (e2) {}
            }
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
        }
    }

    // When Python calls back to insert an image (after reading the
    // clipboard), the original cursor position may be lost because
    // the bridge call is async. We save the range here and restore
    // it inside insertImage() / insertImageFromDataUrl() before
    // the actual DOM insertion.
    var pendingInsertRange = null;

    function _requestPaste(kind)
    {
        // Restore selection first so the paste target is correct
        _restoreSelectionForMenu();

        // Save the current range for the async callback from Python.
        // By the time Python calls Editor.insertImageFromDataUrl() or
        // Editor.pasteImageFromBuffer(), the selection may be gone.
        var sel = window.getSelection();
        if (sel && sel.rangeCount) 
        {
            pendingInsertRange = sel.getRangeAt(0).cloneRange();
        } else if (contextMenuSavedRange) 
        {
            pendingInsertRange = contextMenuSavedRange.cloneRange();
        }

        // Ask Python to read the system clipboard and insert content.
        // This bypasses the browser's paste permission restriction
        // (document.execCommand('paste') is blocked in QtWebEngine).
        if (bridge && typeof bridge.requestPaste === 'function') 
        {
            bridge.requestPaste(kind || 'text');
        } else {
            // Fallback: try execCommand (will likely fail, but no harm)
            try { document.execCommand('paste', false, null); } catch (e) {}
        }
    }

    function _restorePendingRange()
    {
        if (!pendingInsertRange) return false;
        try {
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(pendingInsertRange);
            return true;
        } catch (e) {
            return false;
        }
    }

    // Called from the "Paste Image" menu item click — saves the
    // current block at cursor position so insertImage() can find
    // it even after the async round-trip through Python.
    function _savePendingInsertFromSelection()
    {
        // If pendingInsertBlockId was already set by _showContextMenu
        // (from caretRangeFromPoint), keep it — it's more accurate.
        if (pendingInsertBlockId) return;

        var sel = window.getSelection();
        if (sel && sel.rangeCount) {
            var node = sel.anchorNode;
            if (node && node.nodeType === Node.TEXT_NODE) {
                node = node.parentElement;
            }
            if (node && node.closest) {
                var block = node.closest('.block');
                if (block && block.hasAttribute('data-id')) {
                    pendingInsertBlockId = block.getAttribute('data-id');
                }
            }
        }
    }


    function _attachContextMenu()
    {
        if (contextMenuAttached) return;
        contextMenuAttached = true;

        var root = document.getElementById('editor');
        if (!root) return;

        // Right-click → show context menu
        root.addEventListener('contextmenu', function (e) {
            e.preventDefault();
            _showContextMenu(e.clientX, e.clientY, e.target);
        });

        // Click outside → hide menu
        document.addEventListener('mousedown', function (e) {
            var menu = document.getElementById('context-menu');
            if (!menu || menu.style.display === 'none') return;
            if (!menu.contains(e.target)) {
                _hideContextMenu();
            }
        });

        // Escape → hide menu
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') _hideContextMenu();
        });

        // Scroll → hide menu (stays anchored to wrong position otherwise)
        document.addEventListener('scroll', function () {
            _hideContextMenu();
        }, true);
    }

    function _hideContextMenu()
    {
        var menu = document.getElementById('context-menu');
        if (menu) menu.style.display = 'none';
    }

    function _addMenuItem(menu, label, action, shortcut, disabled)
    {
        var item = document.createElement('div');
        item.className = 'context-menu-item' + (disabled ? ' disabled' : '');
        var labelSpan = document.createElement('span');
        labelSpan.textContent = label;
        item.appendChild(labelSpan);
        if (shortcut) {
            var sc = document.createElement('span');
            sc.className = 'context-menu-shortcut';
            sc.textContent = shortcut;
            item.appendChild(sc);
        }
        if (!disabled) {
            item.addEventListener('click', function () {
                _hideContextMenu();
                try { action(); } catch (err) {}
            });
        }
        menu.appendChild(item);
    }

    function _addMenuSeparator(menu)
    {
        var sep = document.createElement('div');
        sep.className = 'context-menu-separator';
        menu.appendChild(sep);
    }

    function _addMenuLabel(menu, text)
    {
        var label = document.createElement('div');
        label.className = 'context-menu-section-label';
        label.textContent = text;
        menu.appendChild(label);
    }

    // Add a menu item with a submenu (hover to reveal).
    // Returns the submenu element so items can be added to it.
    function _addSubmenuItem(menu, label)
    {
        var item = document.createElement('div');
        item.className = 'context-menu-item has-submenu';
        var labelSpan = document.createElement('span');
        labelSpan.textContent = label;
        item.appendChild(labelSpan);

        var submenu = document.createElement('div');
        submenu.className = 'context-submenu';
        item.appendChild(submenu);

        menu.appendChild(item);
        return submenu;
    }

    // The data-id of the block at the right-click position.
    // Stored as a string (not DOM ref) so it survives DOM rebuilds.
    var pendingInsertBlockId = null;

    function _placeCursorAtPoint(x, y)
    {
        // Use caretRangeFromPoint to get the range at the click
        // coordinates, then set the selection there. This ensures
        // the cursor is at the right-click position, not wherever
        // it happened to be before.
        var range = null;
        if (document.caretRangeFromPoint) {
            range = document.caretRangeFromPoint(x, y);
        } else if (document.caretPositionFromPoint) {
            var pos = document.caretPositionFromPoint(x, y);
            if (pos) {
                range = document.createRange();
                range.setStart(pos.offsetNode, pos.offset);
                range.collapse(true);
            }
        }
        if (range) {
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        }
        return range;
    }

    function _showContextMenu(x, y, target)
    {
        var menu = document.getElementById('context-menu');
        if (!menu) return;
        menu.innerHTML = '';

        // Detect context: table cell / image / text
        var cell = _findCellElement(target);
        var img  = _findImageElement(target);
        var table = cell ? _findTableElement(cell) : null;

        // Check if there's currently a non-collapsed selection.
        // If so, DON'T move the cursor — we want to preserve the
        // user's selection so Cut/Copy work on it. Only place the
        // cursor at the click point if there's no selection (so
        // Paste knows where to insert).
        var sel = window.getSelection();
        var hasSelection = sel && sel.rangeCount && !sel.getRangeAt(0).collapsed;

        if (!img && !table && !hasSelection) {
            _placeCursorAtPoint(x, y);
        }

        // Save the current selection NOW so cut/copy/paste can
        // restore it after the menu item is clicked. Pass the click
        // coordinates so we can check if the right-click was inside
        // the last non-collapsed selection.
        _saveSelectionForMenu(x, y);

        // Also save the block's data-id at the click point for
        // reliable image insertion (survives async round-trip).
        // Use caretRangeFromPoint WITHOUT modifying the selection
        // — just read the block at the click position.
        pendingInsertBlockId = null;
        if (!img && !table) {
            var clickRange = document.caretRangeFromPoint
                ? document.caretRangeFromPoint(x, y) : null;
            if (clickRange) {
                var container = clickRange.startContainer;
                if (container.nodeType === Node.TEXT_NODE) {
                    container = container.parentElement;
                }
                if (container && container.closest) {
                    var clickBlock = container.closest('.block');
                    if (clickBlock && clickBlock.hasAttribute('data-id')) {
                        pendingInsertBlockId = clickBlock.getAttribute('data-id');
                    }
                }
            }
        }

        // ── Text operations (always shown) ──
        if (img) {
            _addMenuLabel(menu, 'Image');
            _addMenuItem(menu, 'Cut', function () { _cutImage(img); }, 'Ctrl+X');
            _addMenuItem(menu, 'Copy', function () { _copyImage(img); }, 'Ctrl+C');
            _addMenuItem(menu, 'Delete', function () { _deleteImageElement(img); }, 'Del');
            _addMenuSeparator(menu);
            _addMenuItem(menu, 'Paste Image from Clipboard', function () {
                // Save the block at cursor for insertion position
                _savePendingInsertFromSelection();
                if (bridge && typeof bridge.requestPaste === 'function') {
                    bridge.requestPaste('image');
                } else {
                    _pasteImageFromClipboard();
                }
            });
            _addMenuSeparator(menu);
            _addMenuItem(menu,"Left", function(){_floatObject(img,"left");});
            _addMenuItem(menu,"Right", function(){_floatObject(img,"right");});
            _addMenuItem(menu,"Justify", function(){_floatObject(img,"none");});
            
        } else if (table) 
        {
            // ── Table operations ──
            _addMenuLabel(menu, 'Table');

            // Make sure table is selected so add/remove row/col target it
            _selectTable(table, cell);

            _addMenuItem(menu, 'Add Row',    function () { addRow(); });
            _addMenuItem(menu, 'Add Column', function () { addColumn(); });
            _addMenuItem(menu, 'Remove Row',    function () { removeRow(); },
                         null, !selectedTable || selectedRowIdx < 0);
            _addMenuItem(menu, 'Remove Column', function () { removeColumn(); },
                         null, !selectedTable || selectedColIdx < 0);
            _addMenuSeparator(menu);
            _addMenuItem(menu, 'Delete Table', function () { deleteTable(); });
            
            _addMenuSeparator(menu);
            _addMenuItem(menu,"Left", function(){_floatObject(table,"left");});
            _addMenuItem(menu,"Right", function(){_floatObject(table,"right");});
            _addMenuItem(menu,"Justify", function(){_floatObject(table,"none");});

            _addMenuSeparator(menu);

            // ── Text operations (still available in cells) ──
            _addMenuLabel(menu, 'Text');
            _addMenuItem(menu, 'Cut',    function () { _execTextCommand('cut'); },    'Ctrl+X', !hasSelection);
            _addMenuItem(menu, 'Copy',   function () { _execTextCommand('copy'); },   'Ctrl+C', !hasSelection);
            // Paste (default = plain text) + submenu with options
            _addMenuItem(menu, 'Paste',  function () { _requestPaste('text'); },      'Ctrl+V');
            var submenu = _addSubmenuItem(menu, 'Special options...');
            _addMenuItem(submenu, 'Paste plain text',           function () { _requestPaste('text'); });
            _addMenuItem(submenu, 'Preserve source formatting', function () { _requestPaste('text_formatted'); });
            _addMenuItem(menu, 'Delete', function () { _execTextCommand('delete'); }, 'Del',     !hasSelection);
        }
        else {
            // ── Plain text context ──
            _addMenuItem(menu, 'Cut',    function () { _execTextCommand('cut'); },    'Ctrl+X', !hasSelection);
            _addMenuItem(menu, 'Copy',   function () { _execTextCommand('copy'); },   'Ctrl+C', !hasSelection);
            // Paste (default = plain text) + submenu with options
            _addMenuItem(menu, 'Paste',  function () { _requestPaste('text'); },      'Ctrl+V');
            var submenu2 = _addSubmenuItem(menu, 'Special options...');
            _addMenuItem(submenu2, 'Paste plain text',           function () { _requestPaste('text'); });
            _addMenuItem(submenu2, 'Preserve source formatting', function () { _requestPaste('text_formatted'); });
            _addMenuItem(menu, 'Delete', function () { _execTextCommand('delete'); }, 'Del',     !hasSelection);
            _addMenuSeparator(menu);
            _addMenuItem(menu, 'Paste Image from Clipboard', function () {
                _savePendingInsertFromSelection();
                _requestPaste('image');
            });
        }

        // Position menu at cursor, clamped to viewport
        menu.style.display = 'block';
        menu.style.left = '0px';
        menu.style.top = '0px';
        var rect = menu.getBoundingClientRect();
        var left = x;
        var top = y;
        if (left + rect.width > window.innerWidth) {
            left = window.innerWidth - rect.width - 4;
        }
        if (top + rect.height > window.innerHeight) {
            top = y - rect.height;
            if (top < 0) top = 4;
        }
        menu.style.left = left + 'px';
        menu.style.top = top + 'px';
    }

    function _floatObject(obj, pos)
    {
        var block = obj.closest('.block');
        block.style.float = pos;
    }
    // ── Image cut/copy/paste ──
    function _copyImage(img)
    {
        var block = img.closest('.block');
        contextMenuImageBuffer = {
            src: img.getAttribute('src') || '',
            alt: img.getAttribute('alt') || '',
            width: img.getAttribute('width') || '',
            height: img.getAttribute('height') || ''
        };

        // Also try to write image to system clipboard so the user
        // can paste into other apps. This may fail silently in
        // QtWebEngine if clipboard write is restricted — that's OK,
        // the internal buffer still works for paste-image.
        try {
            if (navigator.clipboard && img.src) {
                // Best-effort; ignore errors
                fetch(img.src).then(function (r) { return r.blob(); })
                    .then(function (blob) {
                        navigator.clipboard.write([
                            new ClipboardItem({ 'image/png': blob })
                        ]).catch(function () {});
                    }).catch(function () {});
            }
        } catch (e) {}
    }

    function _cutImage(img)
    {
        _copyImage(img);
        _deleteImageElement(img);
    }

    function _deleteImageElement(img)
    {
        var block = img.closest('.block');
        if (block && block.parentElement) {
            block.remove();
            if (selectedImageBlock === block) {
                _clearImageSelection();
            }
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
            if (bridge) bridge.reportSelection({ type: 'None' });
        }
    }

    function _pasteImageFromClipboard()
    {
        // Save the caret now — navigator.clipboard.read() is async,
        // and by the time it resolves the live selection may have
        // moved or been cleared.
        _saveCursorRangeForInsert();

        // Try clipboard.read() for image items first (modern API)
        if (navigator.clipboard && navigator.clipboard.read) {
            navigator.clipboard.read().then(function (items) {
                for (var i = 0; i < items.length; i++) {
                    var types = items[i].types;
                    for (var j = 0; j < types.length; j++) {
                        if (types[j].indexOf('image/') === 0) {
                            items[i].getType(types[j]).then(function (blob) {
                                var reader = new FileReader();
                                reader.onload = function () {
                                    insertImage(reader.result, '');
                                };
                                reader.readAsDataURL(blob);
                            });
                            return;
                        }
                    }
                }
                // No image in clipboard — fall back to internal buffer
                _pasteImageFromBuffer();
            }).catch(function () {
                // Permission denied or not supported — fall back to buffer
                _pasteImageFromBuffer();
            });
        } else {
            _pasteImageFromBuffer();
        }
    }

    function _pasteImageFromBuffer()
    {
        if (!contextMenuImageBuffer || !contextMenuImageBuffer.src) return;
        insertImage(
            contextMenuImageBuffer.src,
            contextMenuImageBuffer.alt || ''
        );
    }

    window.Editor =
    {
        ready: false,

        setDocument: function (html) 
        {  
            var root = document.getElementById("editor");
            if (!root) return;

            editable = false;
            root.innerHTML = '<div class="pages-wrapper">' + html + "</div>";
            renderMathFormulas();
        },
        collectPageGeometry: collectPageGeometry,
        paginateAll: paginateAll,

        // ── Mode switching (paged vs continuous) ──
        setMode: function (mode) { setMode(mode); },
        getMode: function () { return getMode(); },

        exportDocument: function () 
        {
            var pages = [];

            document.querySelectorAll(".pages-wrapper > .page").forEach(function (page) 
            {
                var blocks = [];

                page.querySelectorAll(".page-content > .block").forEach(function (block) 
                {
                    blocks.push({
                        id: block.getAttribute("data-id"),
                        type: block.getAttribute("data-type"),
                        html: block.innerHTML,
                        style: block.getAttribute("style") || "",
                        outer_html: block.outerHTML
                    });
                });

                pages.push(blocks);
            });

            return JSON.stringify(pages);
        },

        makeEditable: function () {
            editable = true;

            // ── Event delegation on #editor ───────────────────
            // Listeners live on the root container so they survive
            // setDocument() rebuilding .pages-wrapper, and they apply
            // automatically to any .page created later by paginateAll().
            // The _editorDelegated flag prevents double-attachment on
            // repeated makeEditable() calls (e.g. after refresh()).
            var root = document.getElementById("editor");
            if (root && !root._editorDelegated) {
                root._editorDelegated = true;

                root.addEventListener("input", function (e) {
                    if (e.target.closest(".page")) {
                        scheduleContentChanged();
                    }
                });

                // ── Render math formulas after Enter keypress ──
                // When the user types LaTeX delimiters ($...$, $$...$$)
                // as plain text, the formulas don't render until
                // something triggers renderMathFormulas() (like a
                // pagination pass). The user expects formulas to
                // render when they press Enter to commit the line.
                //
                // We listen for keydown Enter on the editor root.
                // Using keydown (not keypress) because we need to
                // render AFTER the browser processes Enter and creates
                // the new paragraph. setTimeout(0) defers the render
                // to the next event-loop tick, after the browser has
                // inserted the new <p> or <div> from the Enter key.
                root.addEventListener("keydown", function (e) {
                    if ((e.key === "Enter" || e.keyCode === 13) &&
                        !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
                        // Only handle Enter inside a .page (the editable area)
                        var page = e.target.closest ? e.target.closest(".page") : null;
                        if (page) {
                            // Defer render to after the browser processes Enter
                            setTimeout(function() {
                                renderMathFormulas();
                            }, 0);
                        }
                    }
                });

                /*root.addEventListener("click", function (e) {
                    if (!bridge) return;

                    var page = e.target.closest(".page");
                    if (page) {
                        var pageNumber = parseInt(page.getAttribute("data-page"), 10);
                        if (!isNaN(pageNumber)) {
                            bridge.pageClicked(pageNumber);
                        }
                    }

                    var mathElement = _findMathElement(e.target);
                    if (mathElement) {
                        var mathId = mathElement.getAttribute('data-math-id') || mathElement.getAttribute('data-id') || '';
                        bridge.reportSelection({
                            type: 'Math',
                            id: mathId,
                            formula: mathElement.getAttribute('data-formula') || '',
                            inline: mathElement.classList.contains('math-inline')
                        });
                    }
                });
                */
                root.addEventListener("dblclick", function (e)
                {
                    var mathElement = _findMathElement(e.target);

                    if (mathElement)
                    {
                        e.preventDefault();
                        _beginMathEdit(mathElement);
                    }
                });
            }

            // Attach table selection + resize handlers (idempotent)
            _attachTableHandlers();

            // Attach image drag-and-drop handlers (idempotent)
            _attachImageDragHandlers();

            // Attach selection-change reporter for toolbar updates
            _attachSelectionChangeReporter();

            // Attach direction observer for auto-applying RTL/LTR
            // to new paragraphs created by pressing Enter
            _attachDirectionObserver();

            // Attach right-click context menu
            _attachContextMenu();

            applyEditableState();
        },
        getPageContents: function()
        {   
            var pages = document.querySelectorAll('.pages-wrapper > .page');
            const contents =[];
            for (var i = 0; i < pages.length; i++) 
            {
                var c = pages[i].querySelector('.page-content');
                
                if(this.isVisuallyEmpty(c)) contents.push("");
                
                else contents.push(c.innerHTML); 
            }
            return JSON.stringify(contents);
        },
        
        isVisuallyEmpty: function(element) 
        {
            // Any visible text?
            if (element.textContent.replace(/\u00A0/g, "").trim() !== "") return false;

            // Any rendered object?
            return !element.querySelector("img, svg, canvas, video, audio, iframe, embed, object, " +
                                          "table, math, input, textarea, select, button");
        },
        /*getHtml: function () 
        {
            var wrapper = document.querySelector(".pages-wrapper");
            return wrapper ? wrapper.innerHTML : "";
        },*/

        insertMathFormula: function (formula, isInline) {insertMathFormula(formula, isInline);},

        updateMathFormula: function (id, formula, isInline) {updateMathFormula(id, formula, isInline);},

        // -------------------------------------------------
        // Table operations (called from Python via runJavaScript)
        // -------------------------------------------------
        insertTable: function (rows, cols) {insertTable(rows, cols);},

        deleteTable: function () {deleteTable();},

        addRow: function () {addRow();},

        addColumn: function () {addColumn();},

        removeRow: function () {removeRow();},

        removeColumn: function () {removeColumn();},

        getSelectedTable: function () 
        {
            if (!selectedTable) return null;
            var block = selectedTable.closest('.block');
            return {
                tableId: block ? block.getAttribute('data-id') : '',
                row: selectedRowIdx,
                col: selectedColIdx,
                rows: selectedTable.rows.length,
                cols: selectedTable.rows[0] ? selectedTable.rows[0].cells.length : 0
            };
        },

        // -------------------------------------------------
        // Image operations (called from Python via runJavaScript)
        // -------------------------------------------------

        insertImage: function (src, alt, afterBlockId) {
            insertImage(src, alt, afterBlockId);
        },

        // Called from Python right before opening a focus-stealing
        // native dialog (e.g. QFileDialog for "Insert Image"), so
        // the exact caret position survives the round trip and the
        // image can still be split into the paragraph precisely,
        // not just dropped after the whole block.
        saveCursorRangeForInsert: function () {
            _saveCursorRangeForInsert();
        },

        deleteImage: function () {
            deleteImage();
        },

        getSelectedImage: function () {
            if (!selectedImage) return null;
            var block = selectedImage.closest('.block');
            return {
                imageId: block ? block.getAttribute('data-id') : '',
                src: selectedImage.getAttribute('src') || '',
                width: selectedImage.getAttribute('width') || '',
                height: selectedImage.getAttribute('height') || '',
                naturalWidth: selectedImage.naturalWidth || 0,
                naturalHeight: selectedImage.naturalHeight || 0
            };
        },

        // -------------------------------------------------
        // Text formatting (called from Python via runJavaScript)
        // -------------------------------------------------
        //
        // All methods operate on the current selection inside a
        // .page. If the cursor is collapsed (no selection), the
        // format applies to text typed next. Use queryFormatState()
        // to update toolbar button states on selection change.
        // -------------------------------------------------

        formatBold:          function () { formatBold(); },
        formatItalic:        function () { formatItalic(); },
        formatUnderline:     function () { formatUnderline(); },
        formatStrikethrough: function () { formatStrikethrough(); },
        formatSubscript:     function () { formatSubscript(); },
        formatSuperscript:   function () { formatSuperscript(); },

        formatTextColor:   function (color) { formatTextColor(color); },
        formatHighlight:   function (color) { formatHighlight(color); },
        formatFontFamily:  function (font)  { formatFontFamily(font); },
        formatFontSize:    function (size)  { formatFontSize(size); },

        formatAlignLeft:    function () { formatAlignLeft(); },
        formatAlignCenter:  function () { formatAlignCenter(); },
        formatAlignRight:   function () { formatAlignRight(); },
        formatAlignJustify: function () { formatAlignJustify(); },

        formatIndent:    function () { formatIndent(); },
        formatOutdent:   function () { formatOutdent(); },

        formatOrderedList:   function () { formatOrderedList(); },
        formatUnorderedList: function () { formatUnorderedList(); },

        formatLineHeight:    function (value) { formatLineHeight(value); },
        formatLetterSpacing: function (value) { formatLetterSpacing(value); },

        formatClear: function () { formatClear(); },

        // -------------------------------------------------
        // Special characters
        // -------------------------------------------------

        // Insert a half-space (Zero Width Non-Joiner, U+200C).
        // Commonly used in Persian/Arabic typography to prevent
        // letter joining. Also inserts a regular space-like
        // half-space visible character (U+200C is invisible).
        // For RTL languages this is essential for proper word
        // rendering.
        insertHalfSpace: function () {
            if (!_ensureSelectionInEditor()) return;
            var sel = window.getSelection();
            if (!sel || !sel.rangeCount) return;
            var range = sel.getRangeAt(0);
            range.deleteContents();
            // U+200C = Zero Width Non-Joiner (half-space)
            var textNode = document.createTextNode('\u200C');
            range.insertNode(textNode);
            // Move caret after the inserted character
            range.setStartAfter(textNode);
            range.setEndAfter(textNode);
            sel.removeAllRanges();
            sel.addRange(range);
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
        },

        // -------------------------------------------------
        // Text direction (RTL/LTR)
        // -------------------------------------------------
        setPageDirection: function(dir){setPageDirection(dir);},
        setGlobalFont: function(family){document.body.style.fontFamily = family + " !important";},
        formatDirection: function (dir) { formatDirection(dir); },

        queryDirection: function () {
            return queryDirection();
        },

        setDirectionRtl:  function () { formatDirection('rtl'); },
        setDirectionLtr:  function () { formatDirection('ltr'); },
        setDirectionAuto: function () { formatDirection('auto'); },

        queryFormatState: function () {
            return JSON.stringify(queryFormatState());
        },

        // -------------------------------------------------
        // Context menu / clipboard integration
        // -------------------------------------------------

        pasteImageFromClipboard: function () {
            _pasteImageFromClipboard();
        },

        // Called from Python with a data URL after Python reads
        // the system clipboard (QGuiApplication.clipboard().image()).
        // This is the reliable path for image paste in QtWebEngine,
        // where navigator.clipboard.read() is often blocked.
        insertImageFromDataUrl: function (dataUrl, alt, afterBlockId) {
            if (!dataUrl) return;
            insertImage(dataUrl, alt || '', afterBlockId);
        },

        // Paste image from the JS-side internal buffer (populated
        // by _copyImage when an image is cut/copied inside the
        // editor). Called from Python when the system clipboard
        // has no image but the user requested image paste.
        pasteImageFromBuffer: function () {
            _pasteImageFromBuffer();
        },

        cut:    function () { _execTextCommand('cut'); },
        copy:   function () { _execTextCommand('copy'); },
        paste:  function () { _execTextCommand('paste'); },
        delete: function () { _execTextCommand('delete'); },

        // Atomic paste: restores the saved selection AND inserts
        // the text in a single JS call. This avoids the async gap
        // where the selection would be lost between Python reading
        // the clipboard and calling back to insert the text.
        pasteTextAtSelection: function (text) {
            if (!text) return;
            // Restore the selection saved when the context menu opened
            _restoreSelectionForMenu();
            // Insert immediately — no async gap
            try {
                document.execCommand('insertText', false, text);
            } catch (e) {
                // Fallback: insert via Range
                var sel = window.getSelection();
                if (sel && sel.rangeCount) {
                    var range = sel.getRangeAt(0);
                    range.deleteContents();
                    range.insertNode(document.createTextNode(text));
                }
            }
            // ── Render math formulas after paste ──
            // Pasted text may contain LaTeX delimiters ($...$, $$...$$)
            // that need to be rendered. Also handles the case where
            // pasted content includes KaTeX-rendered HTML.
            renderMathFormulas();
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
        },

        // Atomic HTML paste: restores the saved selection AND inserts
        // HTML in a single JS call. Used for "Paste preserving source
        // formatting" — the HTML may include <span> styles, <b>, <i>,
        // etc. from the source application.
        pasteHtmlAtSelection: function (html) {
            if (!html) return;
            // Restore the selection saved when the context menu opened
            _restoreSelectionForMenu();
            // Insert HTML immediately — execCommand('insertHTML')
            // is allowed (not blocked like 'paste')
            try {
                document.execCommand('insertHTML', false, html);
            } catch (e) {
                // Fallback: parse and insert via Range
                var sel = window.getSelection();
                if (sel && sel.rangeCount) {
                    var range = sel.getRangeAt(0);
                    range.deleteContents();
                    var div = document.createElement('div');
                    div.innerHTML = html;
                    var frag = document.createDocumentFragment();
                    while (div.firstChild) {
                        frag.appendChild(div.firstChild);
                    }
                    range.insertNode(frag);
                }
            }
            // ── Render and wrap math formulas after paste ──
            // Pasted HTML from external sources (web pages, other
            // editors) may contain:
            //  1. LaTeX delimiters ($...$, $$...$$) as plain text
            //     → renderMathFormulas() renders them via auto-render
            //  2. KaTeX-rendered spans (<span class="katex">) without
            //     our wrapper → _wrapUnwrappedKaTeX() (called inside
            //     renderMathFormulas) wraps them with data-formula
            //     so they become editable
            renderMathFormulas();
            if (bridge && typeof bridge.notifyContentChanged === 'function') {
                bridge.notifyContentChanged();
            }
        },

        // -------------------------------------------------
        // Custom head-element injection (load rules 1-5)
        // -------------------------------------------------
        //
        // These methods let Python populate <head> with the
        // document's metadata after setDocument() runs:
        //   - setCustomStyle: writes CSS into <style id="custom-style">
        //   - setMeta: creates/updates <meta name="...">
        //   - addScript: appends a <script> to <head>
        //   - clearCustomElements: removes all of the above so
        //     re-loading a document doesn't accumulate stale ones
        // -------------------------------------------------

        setCustomStyle: function (cssText) 
        {
            var style = document.getElementById("custom-style");
            if (!style) {
                style = document.createElement("style");
                style.id = "custom-style";
                document.head.appendChild(style);
            }
            style.textContent = cssText || "";
        },
// ── Page layout settings ──

setPageMargin: function (margin) 
{
    // margin is a CSS value: "60px", "2cm", "1in", etc.
    document.querySelectorAll(".page").forEach(p=>{
        p.style.setProperty("padding",margin);
    })
},

setBackgroundColor: function (color) 
{
    // color is any CSS color: "#1a1a1a", "darkgray", etc.
    document.body.style.setProperty('background-color', color);
},
setMeta: function (name, content) 
{
    var meta = document.querySelector('meta[name="' + name + '"]');
    if (!meta) 
    {
        meta = document.createElement("meta");
        meta.setAttribute("name", name);
        document.head.appendChild(meta);
    }
    meta.setAttribute("content", content);
},

addScript: function (src, inline)
{
    var script = document.createElement("script");
    script.setAttribute("data-custom", "true");

    if (inline) 
    {
        // Synchronous execution — the script runs immediately
        // when appended. This ensures any DOMContentLoaded
        // listeners are registered before we dispatch the
        // synthetic event via fireContentLoaded().
        script.textContent = inline;
    }
    else if (src) 
    {
        script.src = src;
    } 
    else return;

    document.head.appendChild(script);
},

        // Dispatch a synthetic DOMContentLoaded event so that scripts
        // injected after page load (via addScript) can use the standard
        // document.addEventListener('DOMContentLoaded', ...) pattern.
        // The real DOMContentLoaded already fired when base.html loaded,
        // so without this, those listeners would never run.
        fireContentLoaded: function () 
        {
            document.dispatchEvent(new Event('DOMContentLoaded'));
        },

        clearCustomElements: function ()
        {
            var style = document.getElementById("custom-style");
            if (style) style.textContent = "";

            document.querySelectorAll(
                'meta[name="abdh-document"]'
            ).forEach(function (m) { m.remove(); });

            document.querySelectorAll(
                'head > script[data-custom="true"]'
            ).forEach(function (s) { s.remove(); });
        },

        // -------------------------------------------------
        // Loading spinner
        // -------------------------------------------------
        //
        // Toggles the #loading-overlay element. The overlay is
        // visible by default (class="visible" in base.html) so
        // it covers the initial editor boot. Python calls
        // showLoading() before file parsing begins and
        // hideLoading() after pagination completes.
        //
        // showLoading(text?) — text is optional; if omitted the
        //   existing label is kept.
        // -------------------------------------------------

        showLoading: function (text) 
        {
            var overlay = document.getElementById("loading-overlay");
            
            if (!overlay) return;
            
            if (text) 
            {
                var label = overlay.querySelector(".loading-text");
                if (label) label.textContent = text;
            }
            overlay.classList.add("visible");
        },

        hideLoading: function () 
        {
            var overlay = document.getElementById("loading-overlay");
            if (!overlay) return;
            overlay.classList.remove("visible");
        }
    };

    if (document.readyState === "loading") 
    {
        document.addEventListener("DOMContentLoaded", connectBridge);
    }
    else 
    {
        connectBridge();
    }
