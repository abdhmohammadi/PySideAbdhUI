from dataclasses import dataclass, field, fields
from abc import ABC, abstractmethod
import uuid


# Registry of known block subclasses, populated below.
# Used by Block.from_dict() to dispatch on the "type" key.
_KNOWN_BLOCK_TYPES = {}


def _register_block_type(cls):
    """Decorator: register a Block subclass in the known-types map."""
    _KNOWN_BLOCK_TYPES[cls.__name__] = cls
    return cls


@dataclass
class Block(ABC):
    """
    Base class for all document blocks.

    Paragraph
    ImageBlock
    TableBlock
    ListBlock
    ...

    The `id` field is generated automatically when a block is created,
    but it is also accepted as a constructor keyword argument so that
    blocks deserialized from the browser (which carries the original
    `data-id` attribute, or assigns a fresh one when a block is split)
    can be reconstructed with a specific id.

    Serialization:
        to_dict()   — export all fields (id + type + subclass fields)
                      to a plain dict for JSON / list-based storage
        from_dict() — reverse of to_dict(); returns a new Block instance
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    style: str = ""

    outer_html: str = ""

    @property
    def block_type(self) -> str:
        return self.__class__.__name__

    @property
    def splittable(self) -> bool:
        return False

    @abstractmethod
    def to_html(self) -> str:
        pass

    # ---------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------

    def to_dict(self) -> dict:
        result = {"id": self.id, "type": self.block_type}
        for f in fields(self):
            if f.name == "id":
                continue
            result[f.name] = getattr(self, f.name)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        # Local import to avoid circular imports at module load time.
        from .paragraph import Paragraph
        from .image import Image
        from .table import Table
        from .math import MathBlock

        block_type = (data or {}).get("type", "Paragraph")
        block_id = (data or {}).get("id", "")

        # Dispatch to the correct subclass.
        # Unknown types fall through to RawBlock, which preserves
        # the original type name and HTML so it round-trips without
        # data loss.
        if block_type == "Image":
            target = Image
        elif block_type == "Table":
            target = Table
        elif block_type == "MathBlock":
            target = MathBlock
        elif block_type == "Paragraph":
            target = Paragraph
        elif block_type in _KNOWN_BLOCK_TYPES:
            target = _KNOWN_BLOCK_TYPES[block_type]
        else:
            # Unknown type — use RawBlock to preserve it
            target = RawBlock

        valid_names = {f.name for f in fields(target)}

        kwargs = {}
        for key, value in (data or {}).items():
            if key in ("id", "type"):
                continue
            if key in valid_names:
                kwargs[key] = value

        if block_id:
            kwargs["id"] = block_id

        # For RawBlock, store the original type name
        if target is RawBlock:
            kwargs["raw_type"] = block_type

        return target(**kwargs)


@_register_block_type
@dataclass
class RawBlock(Block):
    """
    A block of unknown type.

    Used when from_dict() encounters a "type" that doesn't match
    any known subclass. Stores the original type name in raw_type
    so to_dict() round-trips it correctly, and stores the HTML
    content verbatim for rendering.

    This provides minimal support for unknown block types — they
    are preserved as-is and can be exported back without loss,
    even though the editor doesn't understand their internal
    structure.
    """

    raw_type: str = "Unknown"
    html: str = ""

    @property
    def block_type(self) -> str:
        return self.raw_type

    def to_html(self) -> str:
        return self.html

