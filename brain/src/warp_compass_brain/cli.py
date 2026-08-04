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

from .config import get_settings, resolve_graph_root


def _open_graph(settings):
    from .graphstore.okf_store import OkfGraphStore

    graph = OkfGraphStore(resolve_graph_root(settings))
    graph.connect()
    return graph

# Windows consoles default to cp1252, which can't encode characters that appear in node
# names or JSON output. Force UTF-8 so the CLI never crashes on a stray unicode glyph.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _same_path(a: str, b: str) -> bool:
    """Do two path strings point at the same place? Unresolvable paths compare as strings."""
    from pathlib import Path

    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def _configure_fs_retry() -> None:
    """Apply FS_RETRY_* before any command touches a path that might live on a synced drive."""
    from . import fsretry

    s = get_settings()
    fsretry.configure(attempts=s.fs_retry_attempts, base_delay=s.fs_retry_base_delay)


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
    from .ingest import Ingestor
    from .llm.deepseek import DeepSeekProvider
    from .ontology import load_ontology
    from .queues import JsonlQueue
    from .resolve import Resolver
    from .vectorindex.embedder import get_embedder
    from .vectorindex.local_index import LocalVectorIndex

    graph = _open_graph(settings)
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
    from .lifecycle import effective_retired
    from .ontology import load_ontology
    from .planner import Planner

    s = get_settings()
    bus = FolderBus(args.bus or s.bus_root)
    graph, ingestor = _build_ingestor(s)
    try:
        planner = Planner(
            graph,
            load_ontology(),
            max_threads=s.planner_max_threads,
            orphan_max=s.planner_orphan_max,
            # P13: skip briefs for people who have left, and hand their unanswered questions to
            # whoever is still here. `effective_retired` ignores a stale marker on someone whose
            # folder has been restored.
            retired_personas=effective_retired(bus),
            now=_now(),
        )
        runner = RoundRunner(bus, ingestor, planner, now=_now())
        summary = runner.run(session_id=args.session)
    finally:
        graph.close()
    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    if summary.missing_participants:
        print(
            f"\n⚠ {len(summary.missing_participants)} persona(s) had no participant folder and no "
            "retirement record — see the warning above.",
            file=sys.stderr,
        )
    return 0


def cmd_seed_roles(args) -> int:
    """Seed the engagement's role registry into the graph (P15a).

    **Run this before the first round.** Answers ingested first mint role nodes under whatever name
    the extractor picked, and the aliases arrive too late to stop "the PM" forking away from
    "Delivery Specialist" — see `docs/plan/phase-15-lifecycle-and-alignment.md` §4.3.
    """
    from .roles import load_roles, seed_roles

    registry = load_roles(args.roles) if args.roles else load_roles()
    s = get_settings()
    graph = _open_graph(s)
    try:
        result = seed_roles(graph, registry, now=_now(), dry_run=args.dry_run)
    finally:
        graph.close()

    verb = "WOULD seed" if args.dry_run else "Seeded"
    print(f"{verb} {len(registry.roles)} registry roles:")
    print(f"  created   : {len(result.created)} ({', '.join(result.created) or 'none'})")
    print(f"  updated   : {len(result.updated)} ({', '.join(result.updated) or 'none'})")
    print(f"  unchanged : {len(result.unchanged)}")
    if result.adopted:
        print("  adopted   : aliases added to an EXISTING node instead of minting a rival —")
        for slug, existing in result.adopted:
            print(f"                {slug} → {existing}  (its id is stamped into edges; kept)")
    if args.dry_run:
        print("\n(dry run — nothing changed. Re-run without --dry-run to apply.)")
    return 0


def cmd_completeness(args) -> int:
    from dataclasses import asdict

    from .completeness import CompletenessEngine
    from .ontology import load_ontology
    from .threads import build_threads

    s = get_settings()
    graph = _open_graph(s)
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


def cmd_coverage(args) -> int:
    """The stage × role matrix — which stage has no interviewed owner (P15b, plan §8.4).

    Read-only, derived entirely from the graph. This is the operator's "who to invite next" list.
    """
    from dataclasses import asdict

    from .coverage import build_coverage, render_coverage

    s = get_settings()
    graph = _open_graph(s)
    try:
        report = build_coverage(graph)
    finally:
        graph.close()

    if args.json:
        out = asdict(report) | {
            "silent_stages": [st.stage_id for st in report.silent_stages],
            "unowned_stages": [st.stage_id for st in report.stages if st.is_unowned],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(render_coverage(report))
    return 0


def cmd_docgen(args) -> int:
    """Generate the living deliverables (Phase 10): end-to-end process + per-role SOPs + problem
    register, as Markdown + Mermaid, straight from the current graph.

    Renders `confirmed` knowledge by default (conflicts always surfaced with a marker); pass
    --include-unverified to add unverified facts (marked). Broken links are shown, never bridged.
    Write to a file with --out, else prints to stdout.
    """
    from .bus import FolderBus
    from .docgen import DocGenerator, render_markdown
    from .lifecycle import persona_display_names
    from .ontology import load_ontology

    s = get_settings()
    # P13: source lines read "Rahul Mehta (Business Analyst)" instead of a slug. Resolved from the
    # bus profiles, so an unknown or pre-P13 persona still renders as its raw id.
    names = persona_display_names(FolderBus(args.bus or s.bus_root))
    graph = _open_graph(s)
    try:
        docs = DocGenerator(
            graph, load_ontology(), include_unverified=args.include_unverified
        ).generate()
        markdown = render_markdown(docs, names)
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
    from .ontology import load_ontology

    s = get_settings()
    graph = _open_graph(s)
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


def cmd_retire_participant(args) -> int:
    """Remove one person from the engagement — bus only, never the graph (P13, ADR #30).

    Archives their folder to `_archive/<id>__<date>/` and records the retirement so the next round
    stops writing them briefs (and stops recreating the folder). Their contributed knowledge stays
    in the graph; their unanswered questions are re-offered to live personas as orphan threads.
    """
    from .bus import FolderBus
    from .lifecycle import LifecycleError, retire_participant

    s = get_settings()
    bus = FolderBus(args.bus or s.bus_root)
    try:
        result = retire_participant(
            bus,
            args.id,
            now=_now(),
            hard_delete=args.hard_delete,
            dry_run=args.dry_run,
        )
    except LifecycleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    who = result.display_name or result.participant_id
    verb = "WOULD retire" if result.dry_run else "Retired"
    print(f"{verb} {who} ({result.role_title or 'role not declared'}) — `{result.participant_id}`")
    print(f"  answer logs: {result.answer_logs}   briefs: {result.briefs}")
    if result.hard_deleted:
        print("  folder: DELETED (no archive kept)")
    elif result.archived_to:
        print(f"  folder: {'would move' if result.dry_run else 'moved'} to {result.archived_to}")
    print("  graph: untouched — their knowledge stays; open questions pass to the team.")
    if result.dry_run:
        print("\n(dry run — nothing changed. Re-run without --dry-run to apply.)")
    return 0


def cmd_list_participants(args) -> int:
    """Who is in this engagement — live participants, then retired ones."""
    from .bus import FolderBus
    from .lifecycle import roster

    s = get_settings()
    entries = roster(FolderBus(args.bus or s.bus_root))
    if not entries:
        print("No participants yet. A person appears the moment their first session syncs.")
        return 0

    for e in entries:
        if e.retired:
            print(
                f"  ⏸  {e.display_name or e.id} — {e.role_title or '?'}  `{e.id}`"
                f"   retired {e.retired_at[:10]}"
            )
        else:
            print(
                f"  ●  {e.display_name or e.id} — {e.role_title or '?'}  `{e.id}`"
                f"   logs: {e.answer_logs}  briefs: {e.briefs}"
                + (f"  last seen {e.last_seen[:10]}" if e.last_seen else "")
            )
    live = sum(1 for e in entries if not e.retired)
    print(f"\n{live} active, {len(entries) - live} retired.")
    return 0


def cmd_reset_engagement(args) -> int:
    """Wipe the engagement back to empty — for starting a clean round of testing (P13 §7)."""
    from pathlib import Path

    from .bus import FolderBus
    from .lifecycle import reset_engagement

    s = get_settings()
    bus_root = args.bus or s.bus_root
    bus = FolderBus(bus_root)
    # Resolve the graph against the bus we were actually pointed at. Deferring to
    # `resolve_graph_root(settings)` here would wipe the REAL graph while resetting a scratch bus.
    graph_root = s.graph_root or str(Path(bus_root) / "graph")

    # `_state/` (vectors + review queues) is global to this brain install, not to a bus. Clearing
    # it while resetting SOMEONE ELSE'S bus would silently destroy the configured engagement's
    # embeddings — so only clear it when we're resetting the configured bus.
    is_configured_bus = _same_path(bus_root, s.bus_root)
    state_paths: list[str] = (
        [s.vector_db_path, s.quarantine_path, s.pending_taxonomy_path] if is_configured_bus else []
    )

    if not args.yes and not args.dry_run:
        print(
            "refusing to reset without --yes.\n"
            f"This deletes every participant folder under {bus_root}, the graph at {graph_root}"
            + (", and the local vector/queue state" if is_configured_bus else "")
            + ". Preview it first with --dry-run.",
            file=sys.stderr,
        )
        return 1

    result = reset_engagement(
        bus,
        graph_root,
        state_paths,
        dry_run=args.dry_run,
        keep_archive=args.keep_archive,
    )

    verb = "WOULD delete" if result.dry_run else "Deleted"
    print(f"{verb} (bus: {bus_root}):")
    print(f"  participants : {len(result.participants_removed)} "
          f"({', '.join(result.participants_removed) or 'none'})")
    print(f"  graph        : {graph_root if result.graph_removed else 'nothing there'}")
    print(f"  retired list : {'yes' if result.retired_removed else 'nothing there'}")
    print(f"  archive      : {'yes' if result.archive_removed else 'kept / nothing there'}")
    if is_configured_bus:
        print(f"  local state  : {', '.join(result.state_files_removed) or 'nothing there'}")
    else:
        print("  local state  : SKIPPED — belongs to the configured bus, not this one")
    if result.dry_run:
        print("\n(dry run — nothing changed. Re-run with --yes to apply.)")
    else:
        print(
            "\nClean. Verify with `run-round` (zero participants) and an all-zero graph/index.md.\n"
            "Still to do by hand: clear each test device via the app's 'Switch user', and "
            "regenerate deliverable.md if it holds old test data."
        )
    return 0


def cmd_plan(args) -> int:
    from .bus import FolderBus
    from .lifecycle import effective_retired
    from .ontology import load_ontology
    from .planner import Planner

    s = get_settings()
    graph = _open_graph(s)
    try:
        planner = Planner(
            graph,
            load_ontology(),
            max_threads=s.planner_max_threads,
            orphan_max=s.planner_orphan_max,
            retired_personas=effective_retired(FolderBus(s.bus_root)),
            now=_now(),
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

    pi = sub.add_parser("ingest", help="full pipeline extract->resolve->gate->persist (OKF graph)")
    pi.add_argument("text")
    pi.add_argument("--persona", default="persona.demo")
    pi.add_argument("--session", default="s_demo")
    pi.set_defaults(func=cmd_ingest)

    pil = sub.add_parser(
        "ingest-log", help="ingest a runner Answer Log file (each entry's raw_answer) (OKF graph)"
    )
    pil.add_argument("path", help="path to an answer-log JSON file written by the runner")
    pil.set_defaults(func=cmd_ingest_log)

    pr = sub.add_parser(
        "run-round",
        help="one daily cycle over the bus: register, ingest new logs, plan, distribute",
    )
    pr.add_argument("--bus", default=None, help="bus root (default: settings.bus_root)")
    pr.add_argument("--session", default="s_next", help="session_id stamped on the emitted briefs")
    pr.set_defaults(func=cmd_run_round)

    pret = sub.add_parser(
        "retire-participant",
        help="remove one person from the engagement (bus only — the graph is never touched)",
    )
    pret.add_argument("--id", required=True, help="the participant id (see list-participants)")
    pret.add_argument("--bus", default=None, help="bus root (default: settings.bus_root)")
    pret.add_argument(
        "--dry-run", action="store_true", help="show what would happen; change nothing"
    )
    pret.add_argument(
        "--hard-delete",
        action="store_true",
        help="delete the folder instead of archiving it to _archive/",
    )
    pret.set_defaults(func=cmd_retire_participant)

    plist = sub.add_parser("list-participants", help="who is in this engagement (live + retired)")
    plist.add_argument("--bus", default=None, help="bus root (default: settings.bus_root)")
    plist.set_defaults(func=cmd_list_participants)

    prst = sub.add_parser(
        "reset-engagement",
        help="DESTRUCTIVE: wipe participants + graph + local state to start a clean engagement",
    )
    prst.add_argument("--bus", default=None, help="bus root (default: settings.bus_root)")
    prst.add_argument("--yes", action="store_true", help="required to actually delete anything")
    prst.add_argument(
        "--dry-run", action="store_true", help="show what would be deleted; change nothing"
    )
    prst.add_argument(
        "--keep-archive", action="store_true", help="preserve _archive/ (retired people's folders)"
    )
    prst.set_defaults(func=cmd_reset_engagement)

    psr = sub.add_parser(
        "seed-roles",
        help="seed contracts/roles.json into the graph — RUN BEFORE THE FIRST ROUND (P15a)",
    )
    psr.add_argument("--roles", default=None, help="registry path (default: contracts/roles.json)")
    psr.add_argument(
        "--dry-run", action="store_true", help="print what would change without writing"
    )
    psr.set_defaults(func=cmd_seed_roles)

    pc = sub.add_parser(
        "completeness", help="score the graph vs the ontology + list open threads (OKF graph)"
    )
    pc.add_argument(
        "--threads", action="store_true", help="include the prioritized open-thread list"
    )
    pc.set_defaults(func=cmd_completeness)

    pcov = sub.add_parser(
        "coverage",
        help="stage x role matrix — which lifecycle stage has no interviewed owner (P15b)",
    )
    pcov.add_argument("--json", action="store_true", help="emit the raw report instead of a table")
    pcov.set_defaults(func=cmd_coverage)

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
        help="generate the living docs (E2E process + SOPs + problem register) as Markdown",
    )
    pdoc.add_argument(
        "--include-unverified",
        action="store_true",
        help="also render unverified facts (marked); default is confirmed-only",
    )
    pdoc.add_argument("--out", default=None, help="write Markdown to this file (default: stdout)")
    pdoc.add_argument(
        "--bus", default=None, help="bus root, for persona names (default: settings.bus_root)"
    )
    pdoc.set_defaults(func=cmd_docgen)

    pp = sub.add_parser(
        "plan", help="emit per-persona Session Brief(s) from the live graph (OKF graph)"
    )
    pp.add_argument(
        "--persona", default=None, help="a single persona_id; omit to plan for all personas"
    )
    pp.add_argument("--session", default="s_next", help="session_id to stamp on the brief(s)")
    pp.set_defaults(func=cmd_plan)

    args = p.parse_args(argv)
    _configure_fs_retry()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
