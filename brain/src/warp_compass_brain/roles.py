"""The engagement's role registry — loads ``contracts/roles.json`` (P15a).

Two jobs, and the second is the one that matters:

* it is the **closed list the onboarding multi-select offers** (mirrored in
  ``pwa/src/sync/roles.ts``);
* it carries each role's **aliases**, which are what keep the graph from forking.

Aliases are load-bearing, not decoration. ``GraphStore.find_by_alias`` is an exact, case-insensitive
whole-string match, and the resolver tries it *before* falling back to vector similarity — where
the default hashing embedder is lexical-only. So without an alias entry, an answer mentioning "the
PM" proposes a Role named "Project Manager", matches nothing, and is adjudicated **new**. The graph
holds two nodes for one person, ``_role_owner_personas`` finds no owner for the new one, and every
handoff to them routes back to whoever mentioned them as "who would know?" — forever. Seeding these
roles up front is what makes the first mention land on the right node.
See ``docs/plan/phase-15-lifecycle-and-alignment.md`` §4.3.

**This registry is a closed vocabulary for SELF-DECLARATION ONLY.** The extractor stays free to mint
roles nobody onboards as — ``End Client``, ``Resource Manager`` — otherwise the client would vanish
from the process map. That is the opposite of ``contracts/ontology.json``, where node and edge types
genuinely are closed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# contracts/ lives at the repo root, two levels above brain/ (same convention as ontology.py).
_DEFAULT_ROLES_PATH = Path(__file__).resolve().parents[3] / "contracts" / "roles.json"

#: Provenance ``said_by`` for seeded roles. Deliberately NOT a persona: it must never count as a
#: corroborating voice (see ``ingest.py`` — two distinct personas promote a node to ``confirmed``,
#: and a registry entry is vocabulary, not testimony).
REGISTRY_SAID_BY = "registry"


@dataclass(frozen=True)
class RoleEntry:
    """One registry row: the node it seeds, its formal title, and what people call it."""

    slug: str
    canonical_name: str
    aliases: tuple[str, ...]


class RoleRegistry:
    """In-memory view of ``contracts/roles.json``."""

    def __init__(self, data: dict) -> None:
        self.roles: tuple[RoleEntry, ...] = tuple(
            RoleEntry(
                slug=r["slug"],
                canonical_name=r["canonical_name"],
                aliases=tuple(r.get("aliases", ())),
            )
            for r in data["roles"]
        )
        self._validate()

    def _validate(self) -> None:
        """Fail loudly on a duplicated alias — it would MERGE two roles onto one node.

        The alias table's one dangerous failure mode. A missing alias merely forks (recoverable, and
        ``cli coverage`` shows it as a role with no owner); a *shared* alias silently collapses two
        distinct roles, and no downstream check would notice.
        """
        seen: dict[str, str] = {}
        for role in self.roles:
            for name in (role.canonical_name, *role.aliases):
                key = name.strip().lower()
                if key in seen and seen[key] != role.canonical_name:
                    raise ValueError(
                        f"contracts/roles.json: {name!r} is claimed by both {seen[key]!r} and "
                        f"{role.canonical_name!r} — a shared alias would merge two roles into one "
                        "node. Aliases must be unique across roles."
                    )
                seen[key] = role.canonical_name

    @property
    def canonical_names(self) -> tuple[str, ...]:
        """The titles, in registry order. What the onboarding chips show."""
        return tuple(r.canonical_name for r in self.roles)

    def find(self, name: str) -> RoleEntry | None:
        """The registry row a spoken name refers to, matching canonical name or any alias."""
        needle = name.strip().lower()
        for role in self.roles:
            if needle in {role.canonical_name.lower(), *(a.lower() for a in role.aliases)}:
                return role
        return None


def resolve_declared_roles(titles, role_cards) -> set[str]:
    """Declared role titles → the **Role node ids** they refer to (P16a).

    ``role_cards`` is every ``Role`` node currently in the graph; matching is case-insensitive over
    each card's canonical name *and* its aliases, so "BA", "Business Analyst" and "Business Analysis
    Specialist" all land on one node exactly as a spoken mention would.

    **Why this resolves against the graph and not against the registry slug.** ``seed_roles`` has an
    *adopt* case: when a node under a different id already answers to one of a registry row's names
    (an older graph holding ``role.business-analyst`` where the registry says
    ``role.business-analysis-specialist``) it adds the aliases to the **existing** node and leaves
    its id alone, because ids are stamped into every edge and every provenance entry. Keying
    ownership off ``RoleEntry.slug`` would therefore point at a node that does not exist, and the
    declared role would silently own nothing — the exact failure this function exists to prevent,
    reintroduced one layer up.

    A title that matches nothing is dropped, not invented: it means a role nobody has described yet,
    which ``cli coverage`` reports rather than something to mint a node for here.
    """
    by_name: dict[str, str] = {}
    for card in role_cards:
        for name in (card.canonical_name, *card.aliases):
            key = str(name).strip().lower()
            if key:
                by_name.setdefault(key, card.id)
    out: set[str] = set()
    for title in titles or ():
        node_id = by_name.get(str(title).strip().lower())
        if node_id:
            out.add(node_id)
    return out


def load_roles(path: str | Path | None = None) -> RoleRegistry:
    """Load the registry (cached for the default path, like ``load_ontology``)."""
    if path is None:
        return _load_default()
    return RoleRegistry(json.loads(Path(path).read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _load_default() -> RoleRegistry:
    return RoleRegistry(json.loads(_DEFAULT_ROLES_PATH.read_text(encoding="utf-8")))


# --- seeding the registry into the graph ------------------------------------------------------

#: Roles are organisational structure — the same taxonomy code the graph already files them under.
_ROLE_CATEGORY_CODES = ["04"]


@dataclass
class SeedResult:
    """What ``seed_roles`` did, per registry row. Every list holds node ids."""

    created: list[str] = field(default_factory=list)
    #: Node already existed at the registry slug; missing aliases were added.
    updated: list[str] = field(default_factory=list)
    #: An EXISTING node under a different id already claimed one of these names, so the aliases were
    #: added to *it* rather than minting a rival node (see ``seed_roles`` for why).
    adopted: list[tuple[str, str]] = field(default_factory=list)
    #: Nothing to do — node present, aliases already complete.
    unchanged: list[str] = field(default_factory=list)


def seed_roles(graph, registry: RoleRegistry | None = None, *, now: str, dry_run: bool = False):
    """Ensure every registry role exists as a ``Role`` node carrying its aliases. Idempotent.

    **Run this BEFORE the first round.** If answers are ingested first, they mint role nodes under
    whatever name the extractor chose and the aliases arrive too late to prevent the fork this whole
    mechanism exists to prevent.

    Three cases per registry row:

    * **create** — nothing in the graph answers to this role's names.
    * **update** — the node already exists at the registry slug; add any aliases it is missing.
    * **adopt** — a node under a *different* id already claims one of these names (an older graph
      had ``role.business-analyst`` where the registry says ``role.business-analysis-specialist``).
      We add the aliases to the **existing** node and leave its id alone: ids are stamped into
      every edge and every provenance entry, so minting a rival node would split the person's work
      in two, and renaming one would orphan its facts (ADR #29's reasoning applies to node ids too).
      The canonical name is left as-is as well — it is what the interviewed person actually called
      themselves, and the registry title is reachable through the aliases either way.
    """
    from .models import NodeCard, NodeType, Provenance  # local: keeps this module import-light

    reg = registry or load_roles()
    result = SeedResult()

    for role in reg.roles:
        wanted = [role.canonical_name, *role.aliases]
        existing = graph.get_node(role.slug)

        if existing is None:
            # Does anything already answer to one of these names, under another id?
            claimed = [
                card
                for name in wanted
                for card in graph.find_by_alias(name, NodeType.ROLE.value)
            ]
            if claimed:
                existing = claimed[0]

        if existing is not None:
            missing = [
                a
                for a in wanted
                if a.lower()
                not in {existing.canonical_name.lower(), *(x.lower() for x in existing.aliases)}
            ]
            if not missing:
                result.unchanged.append(existing.id)
                continue
            if not dry_run:
                existing.aliases = [*existing.aliases, *missing]
                graph.upsert_node(existing)
            if existing.id == role.slug:
                result.updated.append(existing.id)
            else:
                result.adopted.append((role.slug, existing.id))
            continue

        card = NodeCard(
            id=role.slug,
            type=NodeType.ROLE,
            canonical_name=role.canonical_name,
            aliases=list(role.aliases),
            description=(
                f"{role.canonical_name} — a role in this organisation. Seeded from the "
                "engagement's role registry so that every way people refer to it resolves onto one "
                "node; its responsibilities are filled in as people describe their work."
            ),
            category_codes=list(_ROLE_CATEGORY_CODES),
            provenance=[
                Provenance(
                    said_by=REGISTRY_SAID_BY,
                    session_id="seed.roles",
                    confidence=1.0,
                    ts=now,
                )
            ],
        )
        if not dry_run:
            graph.upsert_node(card)
        result.created.append(card.id)

    return result
