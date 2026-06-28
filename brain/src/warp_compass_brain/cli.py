"""Small operator CLI for the brain.

    python -m warp_compass_brain.cli check-models
    python -m warp_compass_brain.cli extract "It hits my queue, I check stock, then escalate."
    python -m warp_compass_brain.cli ingest  "..."  --persona persona.A --session s_demo
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC

from .config import get_settings

# Windows consoles default to cp1252, which can't encode characters that appear in node
# names or JSON output. Force UTF-8 so the CLI never crashes on a stray unicode glyph.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _now() -> str:
    # Workflow scripts forbid Date.now(); here in normal Python we just use the clock.
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def cmd_check_models(_args) -> int:
    from .llm.deepseek import DeepSeekProvider

    s = get_settings()
    if not s.deepseek_api_key:
        print("DEEPSEEK_API_KEY is empty - set it in brain/.env and save the file.")
        return 1
    provider = DeepSeekProvider(s)
    models = provider.list_models()
    print("Models available to this key:")
    for m in sorted(models):
        print(f"  - {m}")
    print(
        f"\nConfigured: batch={s.deepseek_model_batch!r} live={s.deepseek_model_live!r}\n"
        "If those IDs aren't listed above, update DEEPSEEK_MODEL_BATCH / DEEPSEEK_MODEL_LIVE "
        "in brain/.env."
    )
    return 0


def cmd_extract(args) -> int:
    from .extractor import Extractor
    from .llm.deepseek import DeepSeekProvider

    s = get_settings()
    extractor = Extractor(DeepSeekProvider(s))
    result = extractor.extract(args.text)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    return 0


def _build_ingestor(settings):
    from .create_gate import CreateGate
    from .extractor import Extractor
    from .graphstore.neo4j_store import Neo4jGraphStore
    from .ingest import Ingestor
    from .llm.deepseek import DeepSeekProvider
    from .ontology import load_ontology
    from .queues import JsonlQueue
    from .resolve import Resolver
    from .vectorindex.embedder import get_embedder
    from .vectorindex.local_index import LocalVectorIndex

    graph = Neo4jGraphStore(settings)
    graph.connect()
    ont = load_ontology()
    llm = DeepSeekProvider(settings)
    vector = LocalVectorIndex(settings.vector_db_path, get_embedder(settings.embedding_model))
    ingestor = Ingestor(
        graph=graph,
        vector=vector,
        ontology=ont,
        extractor=Extractor(llm, ont),
        resolver=Resolver(graph, vector, ont, llm, settings.retrieval_top_k),
        gate=CreateGate(ont, settings.similarity_ceiling),
        quarantine=JsonlQueue(settings.quarantine_path),
        pending_taxonomy=JsonlQueue(settings.pending_taxonomy_path),
    )
    return graph, ingestor


def cmd_ingest(args) -> int:
    s = get_settings()
    graph, ingestor = _build_ingestor(s)
    try:
        summary = ingestor.ingest_answer(
            args.text, persona_id=args.persona, session_id=args.session, ts=_now()
        )
    finally:
        graph.close()
    print(json.dumps(summary.model_dump(), indent=2, ensure_ascii=False))
    return 0


def cmd_ingest_log(args) -> int:
    """Read an Answer Log file (the runner's output) and ingest each entry's raw_answer.

    The runner (Phase 5) only ever WRITES Answer Logs; the brain only ever READS them. This is the
    file-level consumer of the answer-log contract — feed `raw_answer` per entry through the same
    extract→resolve→gate→persist pipeline as `ingest`. (Phase 8 automates polling the sync bus;
    this is the manual, single-file primitive it will build on.)
    """
    with open(args.path, encoding="utf-8") as fh:
        log = json.load(fh)

    persona_id = log["persona_id"]
    session_id = log["session_id"]
    entries = log.get("entries", [])

    s = get_settings()
    graph, ingestor = _build_ingestor(s)
    totals = {"created": [], "merged": [], "conflicts": [], "quarantined": 0, "edges": 0}
    ingested = 0
    try:
        for entry in entries:
            raw = (entry.get("raw_answer") or "").strip()
            if not raw:
                continue
            summary = ingestor.ingest_answer(
                raw,
                persona_id=persona_id,
                session_id=session_id,
                ts=entry.get("ts") or _now(),
            )
            ingested += 1
            totals["created"] += summary.created
            totals["merged"] += summary.merged
            totals["conflicts"] += summary.conflicts
            totals["quarantined"] += summary.quarantined
            totals["edges"] += summary.edges
    finally:
        graph.close()

    out = {
        "persona_id": persona_id,
        "session_id": session_id,
        "entries_total": len(entries),
        "entries_ingested": ingested,
        "created": totals["created"],
        "merged": totals["merged"],
        "conflicts": totals["conflicts"],
        "quarantined": totals["quarantined"],
        "edges": totals["edges"],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_run_round(args) -> int:
    """One daily batch round over the sync bus: register new participants, ingest new Answer Logs
    into the single graph, re-plan, and write each persona's next Session Brief back to its folder.

    Resumable: a participant's `profile.json` tracks which logs are already ingested, so re-running
    after a transient failure picks up where it left off (Phase 8, docs/02 §3.2/§14).
    """
    from .bus import FolderBus
    from .cycle import RoundRunner
    from .ontology import load_ontology
    from .planner import Planner

    s = get_settings()
    bus = FolderBus(args.bus or s.bus_root)
    graph, ingestor = _build_ingestor(s)
    try:
        planner = Planner(graph, load_ontology(), max_threads=s.planner_max_threads, now=_now())
        runner = RoundRunner(bus, ingestor, planner, now=_now())
        summary = runner.run(session_id=args.session)
    finally:
        graph.close()
    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_completeness(args) -> int:
    from dataclasses import asdict

    from .completeness import CompletenessEngine
    from .graphstore.neo4j_store import Neo4jGraphStore
    from .ontology import load_ontology
    from .threads import build_threads

    s = get_settings()
    graph = Neo4jGraphStore(s)
    graph.connect()
    try:
        engine = CompletenessEngine(
            graph,
            load_ontology(),
            persona_threshold=s.persona_satisfied_threshold,
            org_threshold=s.org_satisfied_threshold,
        )
        report = engine.assess()
        threads = build_threads(report, now=_now())
    finally:
        graph.close()

    out = {
        "satisfied": report.satisfied,
        "org": asdict(report.org) | {"score": report.org.score},
        "persona_scores": [
            {
                "role_id": ps.role_id,
                "role_name": ps.role_name,
                "score": round(ps.score, 4),
                "activities_complete": ps.activities_complete,
                "activities_total": ps.activities_total,
            }
            for ps in report.persona_scores
        ],
        "gap_count": len(report.gaps),
        "threads": [asdict(t) for t in (threads if args.threads else [])],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_docgen(args) -> int:
    """Generate the living deliverables (Phase 10): end-to-end process + per-role SOPs + problem
    register, as Markdown + Mermaid, straight from the current graph.

    Renders `confirmed` knowledge by default (conflicts always surfaced with a marker); pass
    --include-unverified to add unverified facts (marked). Broken links are shown, never bridged.
    Write to a file with --out, else prints to stdout.
    """
    from .docgen import DocGenerator, render_markdown
    from .graphstore.neo4j_store import Neo4jGraphStore
    from .ontology import load_ontology

    s = get_settings()
    graph = Neo4jGraphStore(s)
    graph.connect()
    try:
        docs = DocGenerator(
            graph, load_ontology(), include_unverified=args.include_unverified
        ).generate()
        markdown = render_markdown(docs)
    finally:
        graph.close()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        print(f"wrote {args.out} ({len(markdown)} chars)")
    else:
        print(markdown)
    return 0


def cmd_corroborate(args) -> int:
    """Cross-persona pass (Phase 9): bidirectional handoff verdicts + conflict routing.

    Read-only by default (shows each handoff's state, conflicting nodes, and routed-thread counts
    per persona). With --apply it also writes evidence-based confidence promotions to the graph
    (≥2-persona nodes -> confirmed; both-sided handoffs -> confirmed edge).
    """
    from collections import Counter

    from .crosspersona import CrossPersonaEngine
    from .graphstore.neo4j_store import Neo4jGraphStore
    from .ontology import load_ontology

    s = get_settings()
    graph = Neo4jGraphStore(s)
    graph.connect()
    try:
        engine = CrossPersonaEngine(graph, load_ontology(), now=_now())
        report = engine.assess()
        applied = engine.corroborate() if args.apply else None
    finally:
        graph.close()

    per_persona = Counter(rt.persona_id for rt in report.routed)
    out = {
        "handoffs": [
            {"from_activity": h.from_activity, "to_role": h.to_role, "state": h.state}
            for h in report.handoffs
        ],
        "conflicts": report.conflicts,
        "routed_threads_per_persona": dict(sorted(per_persona.items())),
        "applied": (
            {
                "promoted_nodes": applied.promoted_nodes,
                "confirmed_handoffs": applied.confirmed_handoffs,
                "routed_receiver": applied.routed_receiver,
                "routed_discoverer": applied.routed_discoverer,
                "conflicts": applied.conflicts,
            }
            if applied is not None
            else None
        ),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_plan(args) -> int:
    from .graphstore.neo4j_store import Neo4jGraphStore
    from .ontology import load_ontology
    from .planner import Planner

    s = get_settings()
    graph = Neo4jGraphStore(s)
    graph.connect()
    try:
        planner = Planner(
            graph, load_ontology(), max_threads=s.planner_max_threads, now=_now()
        )
        if args.persona:
            briefs = [planner.plan(args.persona, session_id=args.session)]
        else:
            briefs = planner.plan_all(session_id=args.session)
    finally:
        graph.close()

    out = [b.to_dict() for b in briefs]
    print(json.dumps(out if not args.persona else out[0], indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="warp-compass-brain")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check-models", help="list DeepSeek models your key can access").set_defaults(
        func=cmd_check_models
    )

    pe = sub.add_parser("extract", help="run the extractor on one answer (no DB)")
    pe.add_argument("text")
    pe.set_defaults(func=cmd_extract)

    pi = sub.add_parser("ingest", help="full pipeline extract->resolve->gate->persist (Neo4j)")
    pi.add_argument("text")
    pi.add_argument("--persona", default="persona.demo")
    pi.add_argument("--session", default="s_demo")
    pi.set_defaults(func=cmd_ingest)

    pil = sub.add_parser(
        "ingest-log", help="ingest a runner Answer Log file (each entry's raw_answer) (Neo4j)"
    )
    pil.add_argument("path", help="path to an answer-log JSON file written by the runner")
    pil.set_defaults(func=cmd_ingest_log)

    pr = sub.add_parser(
        "run-round",
        help="one daily cycle over the bus: register, ingest new logs, plan, distribute (Neo4j)",
    )
    pr.add_argument("--bus", default=None, help="bus root (default: settings.bus_root)")
    pr.add_argument("--session", default="s_next", help="session_id stamped on the emitted briefs")
    pr.set_defaults(func=cmd_run_round)

    pc = sub.add_parser(
        "completeness", help="score the graph vs the ontology + list open threads (Neo4j)"
    )
    pc.add_argument(
        "--threads", action="store_true", help="include the prioritized open-thread list"
    )
    pc.set_defaults(func=cmd_completeness)

    pcorr = sub.add_parser(
        "corroborate",
        help="cross-persona handoff verification + conflict routing; --apply writes promotions",
    )
    pcorr.add_argument(
        "--apply",
        action="store_true",
        help="write confidence promotions (≥2-persona nodes + both-sided handoffs -> confirmed)",
    )
    pcorr.set_defaults(func=cmd_corroborate)

    pdoc = sub.add_parser(
        "docgen",
        help="generate the living docs (E2E process + SOPs + problem register) as Markdown (Neo4j)",
    )
    pdoc.add_argument(
        "--include-unverified",
        action="store_true",
        help="also render unverified facts (marked); default is confirmed-only",
    )
    pdoc.add_argument("--out", default=None, help="write Markdown to this file (default: stdout)")
    pdoc.set_defaults(func=cmd_docgen)

    pp = sub.add_parser(
        "plan", help="emit per-persona Session Brief(s) from the live graph (Neo4j)"
    )
    pp.add_argument(
        "--persona", default=None, help="a single persona_id; omit to plan for all personas"
    )
    pp.add_argument("--session", default="s_next", help="session_id to stamp on the brief(s)")
    pp.set_defaults(func=cmd_plan)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
