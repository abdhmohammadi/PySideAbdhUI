from dataclasses import dataclass

from .block import Block
  

@dataclass(kw_only=True)
class Paragraph(Block):
    """
    A single paragraph block.

    The html property contains only the paragraph itself,
    for example:

        <p>Hello</p>

    The renderer will wrap it inside:

        <div class="block" data-id="...">
            ...
        </div>
    """

    html: str = "<p><br></p>"

    @property
    def splittable(self) -> bool: return True

    def to_html(self) -> str: return self.html