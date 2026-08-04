"""Extractor — raw answer → candidate nodes + relations, constrained to the ontology (§7, §12).

The LLM only *proposes* here; nothing is committed. Resolve + the create gate dispose of these
candidates downstream. Output is strict JSON validated into ``ExtractionResult``.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from .llm.base import LLMError, LLMProvider
from .models import CandidateNode, CandidateRelation, ExtractionResult
from .ontology import Ontology, load_ontology
from .roles import RoleRegistry, load_roles

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
- STAGES ARE THE SPINE. When the answer places work in a phase of the journey one piece of work
  takes through the org (pre-sales, kickoff, discovery, build, UAT, go-live, support, and whatever
  else THIS org calls them), emit a Stage and link the activity to it with PART_OF. Use PRECEDES
  when the answer says one phase comes before another. NEVER invent a stage the answer doesn't
  support, and never assume a standard set — every org names its own. Keep stage names broad: a
  phase of work, not a single task. Two people describing the same phase in different words must
  land on one Stage, so put their wording in aliases.
- CADENCE, when stated, goes in key_attributes as {"cadence": "..."} on the Activity, in the
  answer's own terms: "every project", "per opportunity", "monthly", "only on escalation". Most
  real work is per-project, NOT daily — never write a daily cadence unless it was actually said.
- EXPECTATIONS AND GOALS ARE DATA, NOT NOISE. When someone states an outcome they want, or what
  they expect of another stage/team/role, emit an Objective (PURSUES from the role who holds it,
  OBJECTIVE_FOR the stage it is about) and record it AS STATED. Do not soften it, correct it, or
  reconcile it against anything else in the graph — the gap between what one person expects and
  what another describes is a finding worth reporting.
- If the answer contains no process knowledge, return {"nodes":[],"relations":[]}.
- No prose, no markdown — JSON only."""


_BRACKETED = re.compile(r"\[[^\]]*\]")
_PUNCT = " \t\r\n.,;:!?-–—…'\"()"


def has_extractable_content(answer: str) -> bool:
    """True if an answer carries anything worth spending an LLM call on.

    Voice sessions arrive with ElevenLabs Scribe's audio-event tags standing in for non-speech
    sound — an answer whose entire content is ``[click]`` or ``[pause]``. Strip those and there
    is nothing left to extract, so the model returns an empty body instead of the required JSON
    and the round dies on an answer that never had knowledge in it. Skipping these here also
    keeps us from paying for a call whose only correct answer is ``{"nodes":[],"relations":[]}``.
    """
    return bool(_BRACKETED.sub(" ", answer or "").strip(_PUNCT))


class Extractor:
    def __init__(
        self,
        llm: LLMProvider,
        ontology: Ontology | None = None,
        roles: RoleRegistry | None = None,
    ) -> None:
        self._llm = llm
        self._ont = ontology or load_ontology()
        self._roles = roles or load_roles()

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
            f"ALLOWED CATEGORY CODES: {codes}\n"
            f"{self._known_roles_block()}\n"
            f"ANSWER:\n\"\"\"\n{answer}\n\"\"\""
        )

    def _known_roles_block(self) -> str:
        """The registry's canonical role names, so "the PM" is emitted as "Delivery Specialist".

        Fixes role forking at the SOURCE rather than repairing it at resolve time (P15a). Note the
        wording: **prefer** these names, not "only these exist". Real interviews name roles nobody
        self-declares as — ``End Client``, ``Resource Manager`` — and closing this list would delete
        the client from the process map. Unlike node/edge types, the role list is open.
        """
        lines = [
            f"  {r.canonical_name}  (also said as: {', '.join(r.aliases)})"
            if r.aliases
            else f"  {r.canonical_name}"
            for r in self._roles.roles
        ]
        return (
            "KNOWN ROLES — when the answer refers to one of these, emit it under the EXACT\n"
            "canonical name on the left, so every mention lands on one node. Roles NOT on this\n"
            "list are still allowed and expected (e.g. an external client) — this list is a\n"
            "preference, not a limit.\n"
            + "\n".join(lines)
            + "\n"
        )

    def extract(self, answer: str) -> ExtractionResult:
        """Extract candidates from one answer.

        Parses node-by-node and relation-by-relation, **dropping** anything that violates the
        ontology (unknown type/edge, bad direction, dangling ref) rather than failing the whole
        answer — one malformed proposal must not discard the rest. The create gate is the real
        guard; this just keeps obviously-invalid proposals out of resolution.

        An answer with no extractable content (see ``has_extractable_content``) returns empty
        without calling the model at all.
        """
        if not has_extractable_content(answer):
            return ExtractionResult()

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
