"""Stable, human-readable node identity slugs (§6.3).

Format ``<type-prefix>.<kebab-name>`` e.g. ``role.sales-manager``. Slugs are never reused;
on collision with a different node, a numeric suffix is appended.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .models import NodeType
from .ontology import Ontology

_NON_KEBAB = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = _NON_KEBAB.sub("-", name.strip().lower()).strip("-")
    return s or "item"


def mint_slug(
    ontology: Ontology,
    node_type: NodeType,
    name: str,
    exists: Callable[[str], bool],
) -> str:
    """Return a unique slug for a new node. ``exists(slug)`` reports if the slug is taken."""
    prefix = ontology.slug_prefix(node_type)
    base = f"{prefix}.{slugify(name)}"
    if not exists(base):
        return base
    i = 2
    while exists(f"{base}-{i}"):
        i += 1
    return f"{base}-{i}"
