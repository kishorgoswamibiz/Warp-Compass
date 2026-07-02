"""Extractor — raw answer → candidate nodes + relations, constrained to the ontology (§7, §12).

The LLM only *proposes* here; nothing is committed. Resolve + the create gate dispose of these
candidates downstream. Output is strict JSON validated into ``ExtractionResult``.
"""

from __future__ import annotations

from pydantic import ValidationError

from .llm.base import LLMError, LLMProvider
from .models import CandidateNode, CandidateRelation, ExtractionResult
from .ontology import Ontology, load_ontology

_SYSTEM = """You are a knowledge extractor for a business-process discovery system.
Given one interview answer and the list of ALLOWED node types and edge types, output ONLY JSON.

Schema:
{
  "nodes": [
    {"ref":"n1","type":"<AllowedNodeType>","canonical_name":"...","description":"...",
     "aliases":["..."],"category_codes":["..."],"key_attributes":{}}
  ],
  "relations": [
    {"type":"<AllowedEdgeType>","from_ref":"n1","to_ref":"n2"}
  ]
}

Rules:
- Use ONLY the allowed node types and edge types. Never invent types.
- Each node needs a unique "ref" (n1, n2, ...) used by relations.
- Prefer FEWER, well-formed nodes over many noisy ones.
- Be an ACTIVE EDITOR, never a transcriber: distill what was said into clean factual
  statements. Never copy conversational text ("well, usually I kind of...") into any field.
- canonical_name is a short normalized name (2-4 words); aliases are the OTHER keywords or
  surface variants people use for the same thing. Together they are the node's identifier —
  write them so a later reader can decide at a glance whether a new mention is this node.
- description is 1-3 plain factual sentences: WHAT this is and WHY it exists in the process
  (its purpose or place in the flow). No filler, no first person, no quotes.
- ABSTRACT PEOPLE INTO ROLES: never emit a personal name ("John", "Priya ma'am") as a node
  or inside any field. Name the organizational role that person plays, inferred from what
  they do in the answer (e.g. "John approves my discounts" -> a Role like "Discount Approver"
  or their stated title). People change; roles persist.
- Only emit category_codes that are in the allowed list; if unsure, leave it empty.
- A relation's endpoints must obey the edge's (from_type -> to_type) direction.
- If the answer contains no process knowledge, return {"nodes":[],"relations":[]}.
- No prose, no markdown — JSON only."""


class Extractor:
    def __init__(self, llm: LLMProvider, ontology: Ontology | None = None) -> None:
        self._llm = llm
        self._ont = ontology or load_ontology()

    def _user_prompt(self, answer: str) -> str:
        node_types = ", ".join(sorted(self._ont.node_types))
        edges = "\n".join(
            f"  {et}: {self._ont.edge_endpoints(et)[0]} -> {self._ont.edge_endpoints(et)[1]}"
            for et in sorted(self._ont.edge_types)
        )
        codes = ", ".join(sorted(self._ont.category_codes))
        return (
            f"ALLOWED NODE TYPES: {node_types}\n"
            f"ALLOWED EDGE TYPES (direction):\n{edges}\n"
            f"ALLOWED CATEGORY CODES: {codes}\n\n"
            f"ANSWER:\n\"\"\"\n{answer}\n\"\"\""
        )

    def extract(self, answer: str) -> ExtractionResult:
        """Extract candidates from one answer.

        Parses node-by-node and relation-by-relation, **dropping** anything that violates the
        ontology (unknown type/edge, bad direction, dangling ref) rather than failing the whole
        answer — one malformed proposal must not discard the rest. The create gate is the real
        guard; this just keeps obviously-invalid proposals out of resolution.
        """
        raw = self._llm.complete_json(_SYSTEM, self._user_prompt(answer))
        if not isinstance(raw, dict):
            raise LLMError("extractor did not return a JSON object")

        nodes: list[CandidateNode] = []
        type_by_ref: dict[str, object] = {}
        for nd in raw.get("nodes") or []:
            try:
                cand = CandidateNode.model_validate(nd)
            except ValidationError:
                continue  # unknown node type or malformed node — drop it
            cand.category_codes = [c for c in cand.category_codes if self._ont.is_category_code(c)]
            nodes.append(cand)
            type_by_ref[cand.ref] = cand.type

        relations: list[CandidateRelation] = []
        for rd in raw.get("relations") or []:
            try:
                rel = CandidateRelation.model_validate(rd)
            except ValidationError:
                continue  # unknown edge type or malformed relation — drop it
            if rel.from_ref not in type_by_ref or rel.to_ref not in type_by_ref:
                continue  # dangling endpoint
            want_from, want_to = self._ont.edge_endpoints(rel.type)
            if type_by_ref[rel.from_ref] != want_from or type_by_ref[rel.to_ref] != want_to:
                continue  # endpoints violate the ontology direction
            relations.append(rel)

        return ExtractionResult(nodes=nodes, relations=relations)
