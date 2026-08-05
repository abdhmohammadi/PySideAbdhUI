from dataclasses import dataclass, field, fields
from typing import Iterator

from .image import Image
from .math import MathBlock
from .paragraph import Paragraph
from .table import Table
from .block import Block
from .page import Page


@dataclass
class ScriptEntry:
    """
    A script extracted from a loaded HTML document.

    Either `src` is set (external script) or `inline` is set
    (inline script content). Both are stored verbatim — no
    sanitization is performed; the `allow_scripts` flag on
    open_html_file() / open_html_string() controls whether
    these are injected at all.
    """
    src: str = ""
    inline: str = ""


@dataclass
class DocumentMetadata:
    """
    Head-level metadata preserved across the load → edit → save
    cycle. Populated by html_loader when an HTML document is
    opened, and serialized back into the <head> by
    Editor.save_html_file().
    """

    # <meta name="abdh-document" content="version=...; page-system=...">
    version: str = "0.1.0" # DEFUAT
    page_system: str = "multi-page"

    # CSS extracted from <style> tags in the source HTML, with
    # any `body { ... }` rules stripped (the editor owns body
    # styling via style.css). Multiple <style> tags are
    # concatenated in document order.
    custom_css: str = ""

    # Scripts extracted from <script> tags. Each entry is either
    # an external reference (src set) or inline JS (inline set).
    # Only injected into the editor when allow_scripts=True at
    # load time. Always serialized back on save so the user's
    # original scripts survive the round-trip even if they were
    # not active during editing.
    scripts: list = field(default_factory=list)

    # Whether scripts were allowed (injected) when this document
    # was loaded. Carried through to save so the same flag applies
    # on re-save.
    allow_scripts: bool = False

    #pagination_mode = "paged"

    #page_margin = "60px"

class Document:
    """
    The logical document.

    blocks:
        Linear sequence of all blocks.

    pages:
        Physical pages produced by the paginator.

    metadata:
        Head-level metadata (custom CSS, scripts, abdh-document
        version tag) preserved across load/save cycles.
    """

    def __init__(self):

        self.blocks: list[Block] = []

        self.pages: list[Page] = []

        self.metadata: DocumentMetadata = DocumentMetadata()

    # ---------------------------------------------------------
    # Block operations
    # ---------------------------------------------------------

    def append(self, block: Block) -> None:
        self.blocks.append(block)

    def insert(self, index: int, block: Block) -> None:
        self.blocks.insert(index, block)

    def remove(self, block: Block) -> None:
        self.blocks.remove(block)

    def clear(self) -> None:
        self.blocks.clear()
        self.pages.clear()

    def index(self, block: Block) -> int:
        return self.blocks.index(block)

    def set_blocks(self, blocks) -> None:
        """
        Replace the block list. Used by Editor when rebuilding the
        document from the paginated DOM structure exported by JS
        (after a split creates new blocks with fresh ids). Prefers
        this method over direct `document.blocks = ...` assignment
        so any future invariants (uniqueness, type checks) live in
        one place.
        """
        self.blocks = list(blocks)

    
    def to_html(self) -> str:
        """
    Key rule
    
    Never call editor.document.to_html() or editor.document.to_list() directly after user edits. Always use:

        editor.get_content_html(callback) — for HTML string
        editor.export_blocks(callback) — for block list
        editor.export_blocks_json(callback) — for JSON
    
    These all call sync_from_dom() internally before reading the Python model."""
        return "\n".join(block.to_html() for block in self.blocks)

    # ---------------------------------------------------------
    # Block list serialization (extract / load)
    # ---------------------------------------------------------

    def to_list(self) -> list: 
        """
    Key rule
    
    Never call editor.document.to_html() or editor.document.to_list() directly after user edits. Always use:

        editor.get_content_html(callback) — for HTML string
        editor.export_blocks(callback) — for block list
        editor.export_blocks_json(callback) — for JSON
    
    These all call sync_from_dom() internally before reading the Python model."""
        return [block.to_dict() for block in self.blocks]

    def from_list(self, blocks_list) -> None:

        self.blocks = []
        self.pages = []

        for entry in (blocks_list or []):
            
            if not isinstance(entry, dict): continue
            try:
                block = Block.from_dict(entry)
                self.blocks.append(block)
            
            except Exception:
                # Skip malformed entries rather than aborting the
                # whole load. Production code should log this.
                continue
    
    # ---------------------------------------------------------
    # Page operations
    # ---------------------------------------------------------

    def clear_pages(self) -> None: self.pages.clear()

    def add_page(self, page: Page) -> None:
        page.number = len(self.pages)
        self.pages.append(page)

    # ---------------------------------------------------------
    # Python helpers
    # ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self.blocks)

    def __getitem__(self, index: int) -> Block:
        return self.blocks[index]

    def __iter__(self) -> Iterator[Block]:
        return iter(self.blocks)
