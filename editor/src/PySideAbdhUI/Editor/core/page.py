from dataclasses import dataclass, field

from .block import Block


@dataclass
class Page:
    """
    One physical page.

    A Page is only a container of blocks.
    All layout decisions are made by Paginator.
    """

    number: int = 0

    items: list[Block] = field(default_factory=list)

    def add(self, block: Block) -> None:
        self.items.append(block)

    def clear(self) -> None:
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def to_html(self) -> str:
        return "".join(block.to_html() for block in self.items)