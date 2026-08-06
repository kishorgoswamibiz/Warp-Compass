"""Measure whether `similarity_ceiling` is safe for THIS graph, before you change it (P17b).

Run FROM the brain/ folder (so the package + .env resolve):

    uv run --extra vectors python ..\\scripts\\similarity_probe.py
    uv run --extra vectors python ..\\scripts\\similarity_probe.py --min 0.75 --type Activity

**Why this exists.** Phase 17 originally planned to lower `similarity_ceiling` from 0.86 to ~0.79 to
merge the duplicate activity nodes a live engagement had grown. Measuring first showed that would
have destroyed real process distinctions, and the plan was reversed (ADR #41): the ceiling went
UP to 0.90 and the semantic work moved to the adjudicator, which now sees each node's stage and
performing role (ADR #40).

The finding that reversed it, on the live graph 06 Aug 2026:

    0.874  create-project-timeline (pre-sales)     vs manage-project-timelines (project-delivery)
    0.862  code-review                             vs review-checks
    0.808  give-demo (discovery)                   vs give-uat-demos (uat)
    0.785  provide-effort-estimation (Delivery)   vs approve-effort-estimation (Customer)

The 1st, 3rd and 4th are DIFFERENT work; the 2nd is one habit described twice. Real duplicates and
genuinely-distinct work occupy the same cosine band, so no threshold separates them — but the
lifecycle stage and the performing role do.

So this script does not just print similarities. For every close pair it reports whether the two
nodes **share a stage and a performer** — the actual ground-truth signal — and then shows what each
candidate ceiling would auto-merge, split by that classification. A ceiling is safe only while it
merges nothing in the "differ" column.

Read the output as: SAME-PLACE pairs are probably duplicates the adjudicator should merge;
DIFFERENT-PLACE pairs are probably distinct work that any ceiling low enough to catch the former
will destroy.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain" / "src"))

from warp_compass_brain.config import get_settings, resolve_graph_root  # noqa: E402
from warp_compass_brain.graphstore.okf_store import OkfGraphStore  # noqa: E402
from warp_compass_brain.models import EdgeType, NodeType  # noqa: E402
from warp_compass_brain.vectorindex.embedder import get_embedder  # noqa: E402

CEILINGS = (0.95, 0.92, 0.90, 0.88, 0.86, 0.82, 0.80, 0.78, 0.75)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min", type=float, default=0.70, help="report pairs at/above this cosine")
    ap.add_argument("--type", default="Activity", help="node type to probe (default: Activity)")
    args = ap.parse_args(argv)

    settings = get_settings()
    emb = get_embedder(settings.embedding_model)
    print(f"embedder : {type(emb).__name__} (dim {emb.dim})")
    if type(emb).__name__ == "HashingEmbedder":
        print("!! LEXICAL FALLBACK ACTIVE — these scores are not semantic. Run `uv sync --extra "
              "vectors` first, or every number below is meaningless.")

    ntype = NodeType(args.type)
    graph = OkfGraphStore(resolve_graph_root(settings))
    graph.connect()
    try:
        cards = graph.nodes_by_type(ntype)
        # The exact text `ingest._card_text` stores, so these scores match what resolve sees.
        texts = [
            f"{c.canonical_name}. {c.description}. aliases: {', '.join(c.aliases)}"
            for c in cards
        ]
        names = {c.id: c.canonical_name for t in NodeType for c in graph.nodes_by_type(t)}
        performs: dict[str, set[str]] = {}
        part_of: dict[str, set[str]] = {}
        for e in graph.edges(EdgeType.PERFORMS):
            performs.setdefault(e.to_id, set()).add(e.from_id)
        for e in graph.edges(EdgeType.PART_OF):
            part_of.setdefault(e.from_id, set()).add(e.to_id)
    finally:
        graph.close()

    print(f"graph    : {resolve_graph_root(settings)}")
    print(f"nodes    : {len(cards)} of type {ntype.value}\n")
    if len(cards) < 2:
        print("Not enough nodes to compare.")
        return 0

    vecs = emb.embed(texts)
    same_place: list[tuple[float, str, str]] = []
    diff_place: list[tuple[float, str, str]] = []
    unknown: list[tuple[float, str, str]] = []

    def _classify(a_id: str, b_id: str) -> str:
        """same | differ | unknown, from the two signals that actually discriminate (ADR #40).

        ``unknown`` is a real answer and must not be folded into ``same``: two nodes nobody has
        placed yet share nothing — we simply cannot tell, and counting them as duplicates would let
        this script talk you into a ceiling the evidence never supported.
        """
        ra, rb = performs.get(a_id, set()), performs.get(b_id, set())
        sa, sb = part_of.get(a_id, set()), part_of.get(b_id, set())
        if not (ra and rb) and not (sa and sb):
            return "unknown"
        if (ra and rb and not ra & rb) or (sa and sb and not sa & sb):
            return "differ"
        return "same"

    for (i, a), (j, b) in itertools.combinations(list(enumerate(cards)), 2):
        score = sum(x * y for x, y in zip(vecs[i], vecs[j], strict=True))
        if score < args.min:
            continue
        bucket = {"same": same_place, "differ": diff_place, "unknown": unknown}
        bucket[_classify(a.id, b.id)].append((score, a.id, b.id))

    def place(nid: str) -> str:
        roles = ", ".join(sorted(names.get(r, r) for r in performs.get(nid, set())))
        stages = ", ".join(sorted(names.get(s, s) for s in part_of.get(nid, set())))
        return f"{roles or '?'} / {stages or '?'}"

    for label, rows in (
        ("SAME performer and stage — likely DUPLICATES the adjudicator should merge", same_place),
        ("DIFFERENT performer or stage — likely DISTINCT work a ceiling destroys", diff_place),
        ("UNPLACED — no evidence either way (not counted below)", unknown),
    ):
        print(f"--- {label}: {len(rows)} pairs at/above {args.min}")
        for score, a, b in sorted(rows, reverse=True):
            print(f"  {score:.3f}  {a}\n           {b}")
            print(f"           [{place(a)}]  vs  [{place(b)}]")
        print()

    print(f"current similarity_ceiling = {settings.similarity_ceiling}")
    print("The ceiling OVERRULES the adjudicator, so it is safe only while 'wrongly merges' is 0.")
    print("If no value gives you merges>0 and wrong=0, the ceiling is the wrong tool — that is")
    print("exactly what happened in P17b, and why the fix was to give the adjudicator the stage")
    print("and role instead of retuning this number (ADR #40/#41).\n")
    print(f"  {'ceiling':>8}  {'merges duplicates':>18}  {'wrongly merges':>15}")
    for c in CEILINGS:
        good = sum(1 for s, _, _ in same_place if s >= c)
        bad = sum(1 for s, _, _ in diff_place if s >= c)
        flag = "  <-- UNSAFE" if bad else ""
        print(f"  {c:>8.2f}  {good:>18}  {bad:>15}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
