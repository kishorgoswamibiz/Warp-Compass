"""Documentation generator (Phase 10) — turns the live graph into the deliverables.

``traverse`` walks the graph into render-agnostic models; ``render`` emits Markdown + Mermaid.
The split keeps traversal pure/testable and lets new renderers (Word/PDF) slot in later.
"""

from __future__ import annotations

from .render import render_markdown
from .traverse import DocGenerator, GeneratedDocs

__all__ = ["DocGenerator", "GeneratedDocs", "render_markdown"]
