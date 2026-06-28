"""Core domain models for the Warp Compass brain.

These mirror the language-neutral schemas in ``contracts/`` (node-card, answer-log,
session-brief) so the Python brain and the TypeScript planes share one contract.
Keep this module dependency-light — only pydantic. See docs/DATA-CONTRACTS.md.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

SLUG_RE = re.compile(r"^[a-z]+\.[a-z0-9-]+$")


class NodeType(StrEnum):
    """Fixed node vocabulary from the ontology (§6.2). The LLM may only choose from these."""

    ROLE = "Role"
    ACTIVITY = "Activity"
    SYSTEM = "System"
    ARTIFACT = "Artifact"
    EVENT = "Event"
    APPROVAL_POINT = "ApprovalPoint"
    RULE = "Rule"
    PROBLEM = "Problem"
    DESIRE = "Desire"
    KPI = "KPI"


class EdgeType(StrEnum):
    """Fixed edge vocabulary from the ontology (§6.2)."""

    PERFORMS = "PERFORMS"
    USES = "USES"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    TRIGGERS = "TRIGGERS"
    REQUIRES_APPROVAL_FROM = "REQUIRES_APPROVAL_FROM"
    HANDS_OFF_TO = "HANDS_OFF_TO"
    ESCALATES_TO = "ESCALATES_TO"
    GOVERNED_BY = "GOVERNED_BY"
    BLOCKS = "BLOCKS"
    MEASURED_BY = "MEASURED_BY"
    REPORTS_TO = "REPORTS_TO"


class ConfidenceStatus(StrEnum):
    """Status only ever rises with evidence (§6.5). Docs render only ``confirmed`` by default."""

    PROPOSED = "proposed"
    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    CONFLICTING = "conflicting"


class Provenance(BaseModel):
    """Who said a fact, when, and how sure — the traceability + confidence backbone."""

    said_by: str = Field(..., description="persona_id of the source")
    session_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: ConfidenceStatus = ConfidenceStatus.UNVERIFIED
    ts: str = Field(..., description="ISO-8601 timestamp")


class NodeCard(BaseModel):
    """The compact canonical card every graph node carries (§6.4).

    ``aliases`` is the dedup superpower: different employees name the same thing
    differently, and aliases collapse them onto one node.
    """

    id: str
    type: NodeType
    canonical_name: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    description: str = Field(..., min_length=1)
    category_codes: list[str] = Field(..., min_length=1)
    key_attributes: dict[str, object] = Field(default_factory=dict)
    provenance: list[Provenance] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(
                f"node id {v!r} must be a slug like 'role.sales-manager' "
                "('<prefix>.<kebab-case>')"
            )
        return v


class Edge(BaseModel):
    """A typed relationship between two nodes, with its own provenance."""

    type: EdgeType
    from_id: str
    to_id: str
    provenance: list[Provenance] = Field(default_factory=list)


# --- Extraction output (pre-resolution: the LLM proposes these; they have no id yet) ---


class CandidateNode(BaseModel):
    """A node the extractor proposes from one answer, before resolve/create-gate (§7).

    No slug id yet — identity is assigned only after the create gate passes. Relations refer
    to candidates by their ``ref`` (a local handle unique within one extraction).
    """

    ref: str = Field(..., description="Local handle, unique within this extraction (e.g. 'n1').")
    type: NodeType
    canonical_name: str = Field(..., min_length=1)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    category_codes: list[str] = Field(default_factory=list)
    key_attributes: dict[str, object] = Field(default_factory=dict)


class CandidateRelation(BaseModel):
    """A proposed relation between two candidate refs (or, later, resolved ids)."""

    type: EdgeType
    from_ref: str
    to_ref: str


class ExtractionResult(BaseModel):
    """The constrained JSON the extractor returns for a single answer."""

    nodes: list[CandidateNode] = Field(default_factory=list)
    relations: list[CandidateRelation] = Field(default_factory=list)
