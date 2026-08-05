# Editor2/layout/renderer.py
from ..core.block import Block
from ..core.document import Document


class PageRenderer:
    """
    Renders a paginated Document into HTML.
    """

    PAGE_TEMPLATE = """
        <div class="page" data-page="{page}">
            <div class="page-content">
        {content}
            </div>
        </div>
        """

    BLOCK_TEMPLATE = """
        <div class="block"
            data-id="{id}"
            data-type="{type}"{style}>
        {html}
        </div>
        """

    def __init__(self):
        pass

    # ---------------------------------------------------------

    def render_block(self, block:Block):

        # If the block has outer_html set (captured from the DOM
        # via exportDocument), output it verbatim. This preserves
        # ALL user-applied properties — every attribute on the
        # wrapper div, every inline style on inner elements,
        # everything. Nothing can be lost because we're storing
        # the actual DOM HTML.
        if hasattr(block, "outer_html") and block.outer_html:
            return block.outer_html

        # Fall back to template + to_html() for blocks created
        # in Python that haven't been through the DOM yet.
        style_attr = ""
        if hasattr(block, "style") and block.style:
            style_attr = f' style="{block.style}"'

        return self.BLOCK_TEMPLATE.format(
            id=block.id,
            type=block.block_type,
            style=style_attr,
            html=block.to_html()
        )

    # ---------------------------------------------------------

    def render_page(self, page_number, page):

        blocks = []

        for block in page:

            blocks.append(self.render_block(block))

        return self.PAGE_TEMPLATE.format(
            page=page_number,
            content="\n".join(blocks)
        )

    # ---------------------------------------------------------

    def render_blocks(self, blocks):

        return "\n".join(self.render_block(block) for block in blocks)

    # ---------------------------------------------------------

    def render_document(self, document:Document)->str:

        pages = []

        for i, page in enumerate(document.pages):

            pages.append(self.render_page(i, page))

        return "\n".join(pages)
