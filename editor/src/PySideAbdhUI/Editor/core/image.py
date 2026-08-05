from dataclasses import dataclass

from .block import Block


@dataclass
class Image(Block):
    """
    Image block.

    Images are non-splittable.
    If an image does not fit on the current page,
    the entire image is moved to the next page.
    """

    src: str = ""
    alt: str = ""
    width: str = ""
    height: str = ""
    img_style: str = ""

    @property
    def splittable(self) -> bool:
        return False

    def to_html(self) -> str:

        attrs = [
            f'src="{self.src}"'
        ]

        if self.alt:
            attrs.append(f'alt="{self.alt}"')

        if self.width:
            attrs.append(f'width="{self.width}"')

        if self.height:
            attrs.append(f'height="{self.height}"')

        if self.img_style:
            attrs.append(f'style="{self.img_style}"')

        return f'<img {" ".join(attrs)}>'
