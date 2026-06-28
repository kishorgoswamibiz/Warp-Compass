"""Loads and validates against the controlled vocabulary in ``contracts/ontology.json``.

This is the *completeness compass*: a fixed set of node/edge types and a governed taxonomy
of category codes. The LLM may only ever choose from these (anything new is routed to a BA
review queue by the create gate in Phase 2). See docs/02-technical-approach.md §6.2 / §7.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import EdgeType, NodeType

# contracts/ lives at the repo root, two levels above brain/.
_DEFAULT_ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "ontology.json"
)


class Ontology:
    """In-memory view of the controlled vocabulary with cheap validation helpers."""

    def __init__(self, data: dict) -> None:
        self._data = data
        self.node_types: set[str] = {n["type"] for n in data["node_types"]}
        self.edge_types: set[str] = {e["type"] for e in data["edge_types"]}
        self.slug_prefixes: dict[str, str] = {
            n["type"]: n["slug_prefix"] for n in data["node_types"]
        }
        # The completeness compass: which fields make a node of each type "fully described".
        self._completeness_fields: dict[str, list[str]] = {
            n["type"]: list(n.get("completeness_fields", [])) for n in data["node_types"]
        }
        self.category_codes: set[str] = {
            c["code"] for c in data["taxonomy_registry"]["codes"]
        }
        # code -> human label, the document section numbering (§11): "05" -> "Approvals".
        self._category_labels: dict[str, str] = {
            c["code"]: c["label"] for c in data["taxonomy_registry"]["codes"]
        }
        # (from_type, edge_type) -> allowed to_type, for edge endpoint validation.
        self._edge_endpoints: dict[str, tuple[str, str]] = {
            e["type"]: (e["from"], e["to"]) for e in data["edge_types"]
        }

    # --- vocabulary checks (used by the Phase-2 create gate) ---

    def is_node_type(self, t: str) -> bool:
        return t in self.node_types

    def is_edge_type(self, t: str) -> bool:
        return t in self.edge_types

    def is_category_code(self, code: str) -> bool:
        """A genuinely new code must go to the pending-taxonomy queue, not the graph."""
        return code in self.category_codes

    def slug_prefix(self, node_type: NodeType | str) -> str:
        t = node_type.value if isinstance(node_type, NodeType) else node_type
        return self.slug_prefixes[t]

    def completeness_fields(self, node_type: NodeType | str) -> list[str]:
        """The ontology's completeness fields for a node type (the Phase-3 compass §9)."""
        t = node_type.value if isinstance(node_type, NodeType) else node_type
        return list(self._completeness_fields.get(t, []))

    def category_label(self, code: str) -> str | None:
        """The taxonomy label for a category code (the document's section title, §11)."""
        return self._category_labels.get(code)

    def categories_sorted(self) -> list[tuple[str, str]]:
        """All (code, label) pairs in taxonomy order — the zero-padded codes sort lexically
        (``05`` < ``05.1`` < ``06`` < ``10``), which is the section numbering."""
        return [(code, self._category_labels[code]) for code in sorted(self._category_labels)]

    def edge_endpoints(self, edge_type: EdgeType | str) -> tuple[str, str]:
        """Return (from_type, to_type) the ontology declares for an edge."""
        t = edge_type.value if isinstance(edge_type, EdgeType) else edge_type
        return self._edge_endpoints[t]

    def validate_card_codes(self, codes: list[str]) -> list[str]:
        """Return the subset of codes that are NOT in the registry (empty == all valid)."""
        return [c for c in codes if not self.is_category_code(c)]


@lru_cache(maxsize=1)
def load_ontology(path: str | Path | None = None) -> Ontology:
    """Load the ontology JSON (cached). Pass a path to override the default location."""
    p = Path(path) if path is not None else _DEFAULT_ONTOLOGY_PATH
    with p.open("r", encoding="utf-8") as fh:
        return Ontology(json.load(fh))
