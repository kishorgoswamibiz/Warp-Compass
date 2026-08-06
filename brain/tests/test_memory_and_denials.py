"""P17c — a refusal survives the session (WC-25), and the brief carries memory (WC-26).

Two complaints from the same live sessions, and they are opposites of one another:

* **WC-25 / nothing you refuse sticks.** *"the project timeline is not my job"* (said three times),
  *"SA does not do anything in quality assurance"*, *"I do not demo a solution to the client"*. The
  live model classified every one of them and the runner threw the classification away, because
  `answer-log.schema.json` had nowhere to put it. So the gap stayed open and the question came back.
* **WC-26 / nothing you said is remembered.** The brief carried `open_threads` (what we still want)
  and never what we already have, so the interviewer could not say *"you told me X — has that
  changed?"* Testers noticed: *"I had replied in my previous sessions."*

The pair is deliberate: one stops asking what was refused, the other stops re-asking what was
answered. See `docs/plan/phase-17-interview-fidelity.md` §6 and ADRs #43/#44.

No Neo4j, no network. The bus is a tmp_path folder; refusals go into the Planner as a plain dict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from conftest import FakeGraphStore
from jsonschema import validate

from warp_compass_brain.bus import FolderBus
from warp_compass_brain.lifecycle import Refusal, refusals
from warp_compass_brain.models import (
    ConfidenceStatus,
    Edge,
    EdgeType,
    NodeCard,
    NodeType,
    Provenance,
)
from warp_compass_brain.ontology import load_ontology
from warp_compass_brain.planner import Planner

ONT = load_ontology()
TS = "2026-08-06T10:00:00Z"

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "session-brief.schema.json").read_text(
        encoding="utf-8"
    )
)


def _prov(persona="persona.A", status=ConfidenceStatus.CONFIRMED):
    return Provenance(said_by=persona, session_id="s1", confidence=0.9, status=status, ts=TS)


def _node(node_id, ntype, name, *, persona="persona.A", **kw) -> NodeCard:
    return NodeCard(
        id=node_id,
        type=ntype,
        canonical_name=name,
        description=f"{name} description",
        category_codes=["02"],
        key_attributes=kw.pop("key_attributes", {}),
        provenance=[_prov(p) for p in ([persona] if isinstance(persona, str) else persona)],
    )


def _edge(etype, a, b) -> Edge:
    return Edge(type=etype, from_id=a, to_id=b, provenance=[_prov()])


def _bare_activity(g, act_id, name, *, persona="persona.A", role_id="role.rep"):
    """An activity with a performer and no completeness fields → one gap per field."""
    g.upsert_node(_node(act_id, NodeType.ACTIVITY, name, persona=persona))
    if role_id not in g.nodes:
        g.upsert_node(_node(role_id, NodeType.ROLE, role_id.split(".")[-1], persona=persona))
    g.add_edge(_edge(EdgeType.PERFORMS, role_id, act_id))


def _planner(g, **kw) -> Planner:
    return Planner(g, ONT, now=TS, **kw)


def _ids(brief) -> set[str]:
    return {t.id for t in brief.open_threads}


def _write_log(bus: FolderBus, participant_id: str, name: str, entries: list[dict], *, persona=None):
    bus.ensure_participant(participant_id)
    bus.write_profile(participant_id, {"persona_id": persona or participant_id})
    logs = bus.participant_dir(participant_id) / "answer_logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / name).write_text(
        json.dumps({"session_id": name.removesuffix(".json"), "entries": entries}),
        encoding="utf-8",
    )


def _entry(raw, *, thread_id=None, classification=None) -> dict:
    e: dict = {"kind": "guided", "raw_answer": raw, "ts": TS, "thread_id": thread_id}
    if classification:
        e["classification"] = classification
    return e


# --- reading refusals off the bus (WC-25) -------------------------------------------------------


def test_dont_know_scopes_to_the_thread_and_not_mine_to_the_whole_node(tmp_path):
    bus = FolderBus(str(tmp_path))
    _write_log(
        bus,
        "kishor",
        "s1.json",
        [
            _entry("No idea what starts it.", thread_id="t.trigger", classification="dont_know"),
            _entry("The project timeline is not my job.", thread_id="t.plan", classification="not_mine"),
        ],
        persona="persona.kishor",
    )

    assert refusals(bus) == {
        "persona.kishor": {Refusal("t.trigger", "thread"), Refusal("t.plan", "node")}
    }


def test_only_the_two_refusals_count_and_only_with_a_thread_to_point_at(tmp_path):
    """A refusal with nothing to point at cannot suppress anything, and an ANSWER never suppresses.

    `tangent` matters most here: `runner.respond` nulls the thread_id when the person drifts, so
    drifting off a question is structurally incapable of being read as refusing it — the field it
    would need is already gone.
    """
    bus = FolderBus(str(tmp_path))
    _write_log(
        bus,
        "kishor",
        "s1.json",
        [
            _entry("A clear answer.", thread_id="t.a", classification="clear"),
            _entry("It depends.", thread_id="t.b", classification="vague"),
            _entry("Anyway, the weather.", thread_id=None, classification="tangent"),
            _entry("Free narration, no thread.", thread_id=None, classification="not_mine"),
            _entry("An old log, written before P17c.", thread_id="t.c"),
        ],
        persona="persona.kishor",
    )

    assert refusals(bus) == {}


def test_refusals_survive_retirement_and_key_on_persona_id(tmp_path):
    """Archived folders count, for the same reason `all_answer_entries` reads them: a departed
    colleague's "that was never my job" is still true about the business."""
    bus = FolderBus(str(tmp_path))
    _write_log(bus, "live-1", "s1.json", [_entry("not mine", thread_id="t.x", classification="not_mine")], persona="persona.live")
    _write_log(bus, "gone-1", "s1.json", [_entry("nor mine", thread_id="t.y", classification="not_mine")], persona="persona.gone")
    bus.move_to_archive("gone-1", "gone-1__2026-08-01")

    assert refusals(bus) == {
        "persona.live": {Refusal("t.x", "node")},
        "persona.gone": {Refusal("t.y", "node")},
    }


# --- the Planner acts on them (WC-25) -----------------------------------------------------------


def test_a_dont_know_closes_only_that_question():
    """They do the work, they just can't answer this bit — the rest of the activity is fair game."""
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order")
    refused = {"persona.A": [Refusal("thread.missing_field.act.a.trigger", "thread")]}

    brief = _planner(g, refusals=refused).plan("persona.A", session_id="s")

    assert "thread.missing_field.act.a.trigger" not in _ids(brief)
    assert "thread.missing_field.act.a.trigger" not in brief.reserve_threads
    # ...and the activity is still being asked about.
    assert any(t.id.startswith("thread.missing_field.act.a.") for t in brief.open_threads)


def test_a_not_mine_closes_every_question_about_that_piece_of_work():
    """The WC-25 regression proper.

    P17a clusters up to three threads onto one node, so a thread-scoped suppression would return
    the other two next round — the same repetition in a new costume. A person who says *"that's not
    my job"* has answered every question about it at once.
    """
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order")
    _bare_activity(g, "act.b", "Pack order")
    refused = {"persona.A": [Refusal("thread.missing_field.act.a.trigger", "node")]}

    brief = _planner(g, refusals=refused).plan("persona.A", session_id="s")

    assert not [t for t in brief.open_threads if ".act.a." in f".{t.id}."]
    assert not [t for t in brief.reserve_threads if ".act.a." in f".{t}."]
    assert [t for t in brief.open_threads if ".act.b." in f".{t.id}."]  # untouched


def test_a_refusal_is_per_persona_and_never_global():
    """One Business Analyst not doing something is not evidence that no Business Analyst does."""
    g = FakeGraphStore()
    g.upsert_node(_node("act.a", NodeType.ACTIVITY, "Take order", persona=["persona.A", "persona.B"]))
    g.upsert_node(_node("role.rep", NodeType.ROLE, "Rep"))
    g.add_edge(_edge(EdgeType.PERFORMS, "role.rep", "act.a"))
    refused = {"persona.A": [Refusal("thread.missing_field.act.a.trigger", "node")]}
    planner = _planner(g, refusals=refused)

    def about_the_order(persona: str) -> list[str]:
        brief = planner.plan(persona, session_id="s")
        return [t.id for t in brief.open_threads if ".act.a." in f".{t.id}."]

    assert about_the_order("persona.A") == []
    assert about_the_order("persona.B")


def test_a_not_mine_still_bites_after_someone_else_answered_that_exact_question():
    """The node-scope fallback, and the reason it cannot be skipped.

    Kishor refuses "who picks up Take order?". A colleague then answers it, so that gap closes and
    the thread stops existing — leaving the refusal pointing at nothing. Resolving the node from
    the thread id is what keeps the *rest* of the activity suppressed for him; without it a refusal
    would quietly expire the moment anyone else filled in the field it named.
    """
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order")
    g.upsert_node(_node("role.wh", NodeType.ROLE, "Warehouse"))
    g.add_edge(_edge(EdgeType.HANDS_OFF_TO, "act.a", "role.wh"))  # next_handoff now answered
    refused = {"persona.A": [Refusal("thread.missing_field.act.a.next_handoff", "node")]}

    brief = _planner(g, refusals=refused).plan("persona.A", session_id="s")

    assert "thread.missing_field.act.a.next_handoff" not in _ids(brief)  # gone anyway
    assert not [t for t in brief.open_threads if ".act.a." in f".{t.id}."]  # and so is the rest


def test_the_routing_prefix_is_not_part_of_the_question():
    """`role.`/`orphan.` record why a thread REACHED you, not what was asked.

    Kishor refuses a question that arrived via his declared role, so the log holds
    `role.thread.…`. Later he describes that activity himself, so the same gap now arrives as his
    own thread with no prefix. Matching on the raw id would treat that as a new question and ask it.
    """
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order")  # persona.A has provenance → own thread, no prefix
    refused = {"persona.A": [Refusal("role.thread.missing_field.act.a.trigger", "thread")]}

    brief = _planner(g, refusals=refused).plan("persona.A", session_id="s")

    assert "thread.missing_field.act.a.trigger" not in _ids(brief)


def test_no_refusals_changes_nothing():
    """The whole feature is inert on a pre-P17c bus — the P17a brief, byte for byte."""
    g = FakeGraphStore()
    _bare_activity(g, "act.a", "Take order")

    before = _planner(g).plan("persona.A", session_id="s").to_dict()
    after = _planner(g, refusals={}).plan("persona.A", session_id="s").to_dict()

    assert before == after


# --- known facts (WC-26) ------------------------------------------------------------------------


def _described_activity(g, act_id, name, *, stage=None, produces=None, hands_to=None, cadence=None):
    attrs = {"cadence": cadence} if cadence else {}
    g.upsert_node(_node(act_id, NodeType.ACTIVITY, name, key_attributes=attrs))
    if stage:
        g.upsert_node(_node(stage, NodeType.STAGE, stage.split(".")[-1].title()))
        g.add_edge(_edge(EdgeType.PART_OF, act_id, stage))
    if produces:
        g.upsert_node(_node(produces, NodeType.ARTIFACT, produces.split(".")[-1].upper()))
        g.add_edge(_edge(EdgeType.PRODUCES, act_id, produces))
    if hands_to:
        g.upsert_node(_node(hands_to, NodeType.ROLE, hands_to.split(".")[-1].title()))
        g.add_edge(_edge(EdgeType.HANDS_OFF_TO, act_id, hands_to))


def test_known_facts_state_only_what_the_graph_actually_holds():
    """Deterministic, never model-written: every clause is read off an edge or an attribute.

    This block is injected as MEMORY and the interviewer treats it as established. A hallucinated
    line here does not waste a turn — it asserts something the person never said.
    """
    g = FakeGraphStore()
    _described_activity(
        g, "act.brd", "Compile Final BRD",
        stage="stg.presales", produces="art.brd", hands_to="role.ds", cadence="every project",
    )

    brief = _planner(g).plan("persona.A", session_id="s")

    assert brief.known_facts == [
        'You do "Compile Final BRD" (in Presales) — produces BRD; hands to Ds; happens every project'
    ]
    validate(instance=brief.to_dict(), schema=_SCHEMA)


def test_a_sparse_activity_yields_a_short_line_not_a_line_of_unknowns():
    g = FakeGraphStore()
    _described_activity(g, "act.x", "Do the thing")

    assert _planner(g).plan("persona.A", session_id="s").known_facts == ['You do "Do the thing"']


def test_known_facts_lead_with_the_activities_this_brief_walks():
    """Knowing what we know changes the NEXT question, so the facts for the nodes being walked
    come first: "what does X produce?" becomes "you said X produces Y — who picks it up?" """
    g = FakeGraphStore()
    _described_activity(g, "act.zzz-later", "Zulu work", produces="art.z")
    _bare_activity(g, "act.aaa-walked", "Alpha work")  # gappy → this is what the brief pulls on

    brief = _planner(g).plan("persona.A", session_id="s")

    assert any(".act.aaa-walked." in f".{t.id}." for t in brief.open_threads)
    assert brief.known_facts[0].startswith('You do "Alpha work"')


def test_known_facts_are_capped_so_a_busy_person_gets_a_block_not_their_subgraph():
    g = FakeGraphStore()
    for i in range(20):
        _described_activity(g, f"act.n{i:02d}", f"Work {i:02d}", produces=f"art.a{i:02d}")

    brief = _planner(g, known_facts_max=5).plan("persona.A", session_id="s")

    assert len(brief.known_facts) == 5
    validate(instance=brief.to_dict(), schema=_SCHEMA)


def test_facts_cover_only_this_persons_own_account():
    """Same scoping as everything else in the brief: `said_by`, never the whole graph. Telling
    someone "you told us X" about a colleague's answer is the WC-R5 over-reach with a new face."""
    g = FakeGraphStore()
    _described_activity(g, "act.mine", "My work")
    g.upsert_node(_node("act.theirs", NodeType.ACTIVITY, "Their work", persona="persona.B"))

    facts = _planner(g).plan("persona.A", session_id="s").known_facts

    assert facts == ['You do "My work"']


def test_a_disowned_activity_is_not_then_described_back_to_them_as_theirs():
    """Where the two halves of P17c meet — found by running the real graph, not by reading it.

    Kishor refuses "Provide Technical Solutions"; every thread about it disappears, and the memory
    block then opens with *'You do "Provide Technical Solutions"'*. That is WC-25 reappearing inside
    the fix for WC-26, in the worse position: `known_facts` is asserted as established fact rather
    than asked as a question, so there is not even a question to answer "no" to.

    Scope follows the refusal. A `dont_know` leaves the fact standing — they do the work, they were
    hazy on one detail — and only `not_mine` removes it.
    """
    g = FakeGraphStore()
    _described_activity(g, "act.mine", "My work", produces="art.m")
    _described_activity(g, "act.theirs", "Their work", produces="art.t")

    def facts(scope: str) -> list[str]:
        refused = {"persona.A": [Refusal("thread.missing_field.act.theirs.trigger", scope)]}
        return _planner(g, refusals=refused).plan("persona.A", session_id="s").known_facts

    assert not [f for f in facts("node") if "Their work" in f]
    assert [f for f in facts("node") if "My work" in f]
    assert [f for f in facts("thread") if "Their work" in f]  # still theirs, just one unknown


def test_cold_start_carries_no_known_facts():
    brief = _planner(FakeGraphStore()).plan("persona.A", session_id="s")
    assert brief.cold_start is True and brief.known_facts == []
    validate(instance=brief.to_dict(), schema=_SCHEMA)


# --- the two planes must agree on what a refusal IS ---------------------------------------------

_PROMPTS_TS = Path(__file__).resolve().parents[2] / "pwa" / "src" / "runner" / "prompts.ts"
_TYPES_TS = Path(__file__).resolve().parents[2] / "pwa" / "src" / "runner" / "types.ts"
_ANSWER_LOG_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "answer-log.schema.json").read_text(
        encoding="utf-8"
    )
)


def _classification_enum() -> list[str]:
    props = _ANSWER_LOG_SCHEMA["properties"]["entries"]["items"]["properties"]
    return props["classification"]["enum"]


def test_every_refusal_scope_is_a_classification_the_contract_allows():
    """`REFUSAL_SCOPES` is the brain's opinion about values the PWA writes.

    Nothing else connects the two: a typo, or a value renamed on one side, produces a brain that
    silently suppresses nothing — the exact pre-P17c behaviour, with a feature in place that looks
    like it should be working. Fails loudly here instead.
    """
    from warp_compass_brain.lifecycle import REFUSAL_SCOPES

    assert set(REFUSAL_SCOPES) <= set(_classification_enum())
    assert set(REFUSAL_SCOPES.values()) == {"thread", "node"}


def test_the_contract_the_runner_and_the_live_prompt_list_the_same_classifications():
    """Three copies of one enum (ADR #18d: no shared TS/Py module), so drift needs a test.

    The live prompt copy matters most: the model can only emit a value it has been shown, so a
    classification present in the contract and absent from the prompt is dead on arrival.
    """
    enum = _classification_enum()

    union = re.search(r"export type Classification =([^;]+);", _TYPES_TS.read_text(encoding="utf-8"))
    assert union, "could not find the Classification union in types.ts"
    assert re.findall(r'"([a-z_]+)"', union.group(1)) == enum

    prompt = _PROMPTS_TS.read_text(encoding="utf-8")
    assert f'{{"classification":"{"|".join(enum)}"' in prompt
    for value in enum:
        assert f'- "{value}"' in prompt, f"{value} is never described to the model"
