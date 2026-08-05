from dataclasses import dataclass

from .block import Block


@dataclass
class MathBlock(Block):
    r"""
    Mathematics formula block rendered with KaTeX.

    Supports both block-level and inline formulas:
    - Block: $$formula$$ or \\[formula\\]
    - Inline: $formula$ or \\(formula\\)

    The formula content is stored in the `content` property and
    serialized as a <div class="math-block"> with data-formula
    attribute for round-tripping.

    Example serialized form:
        <div class="math-block" data-formula="x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}"></div>

    When exported to the DOM, the formula is wrapped in delimiters
    for KaTeX auto-render to process.
    """

    content: str = ""
    is_inline: bool = False

    @property
    def splittable(self) -> bool:
        return False

    def to_html(self) -> str:
        """
        Serialize to HTML with data-formula attribute for preservation.
        KaTeX rendering happens client-side via auto-render.
        """
        if not self.content:
            return '<div class="math-block" data-formula=""></div>'

        # Escape quotes in formula for HTML attribute
        escaped_formula = self.content.replace('"', "&quot;")

        if self.is_inline:
            return f'<span class="math-inline" data-formula="{escaped_formula}"></span>'
        else:
            return f'<div class="math-block" data-formula="{escaped_formula}"></div>'
