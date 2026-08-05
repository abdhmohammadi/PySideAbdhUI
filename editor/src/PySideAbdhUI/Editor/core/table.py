from dataclasses import dataclass

from .block import Block


@dataclass
class Table(Block):
    """
    Table block.
    """

    html: str = ""

    @property
    def splittable(self) -> bool:
        return False

    def to_html(self) -> str:
        return self.html
