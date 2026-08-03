"""Phase 2 — extractor parses + sanitizes constrained JSON (no network)."""

from __future__ import annotations

from conftest import FakeLLM

from warp_compass_brain.extractor import Extractor, has_extractable_content


def test_extractor_parses_nodes_and_relations():
    payload = {
        "nodes": [
            {"ref": "n1", "type": "Role", "canonical_name": "Inventory Lead", "description": "x"},
            {"ref": "n2", "type": "Activity", "canonical_name": "Check stock", "description": "y"},
        ],
        "relations": [{"type": "PERFORMS", "from_ref": "n1", "to_ref": "n2"}],
    }
    ex = Extractor(FakeLLM([payload]))
    res = ex.extract("The lead checks stock every morning.")
    assert {n.canonical_name for n in res.nodes} == {"Inventory Lead", "Check stock"}
    assert len(res.relations) == 1


def test_extractor_drops_unknown_type_and_bad_edge_direction():
    payload = {
        "nodes": [
            {"ref": "n1", "type": "Sandwich", "canonical_name": "Bad", "description": "x"},
            {"ref": "n2", "type": "Activity", "canonical_name": "Check stock", "description": "y"},
            {"ref": "n3", "type": "Role", "canonical_name": "Lead", "description": "z"},
        ],
        "relations": [
            {"type": "PERFORMS", "from_ref": "n2", "to_ref": "n3"},  # wrong direction (Act->Role)
            {"type": "PERFORMS", "from_ref": "n3", "to_ref": "n2"},  # valid (Role->Activity)
            {"type": "PERFORMS", "from_ref": "n1", "to_ref": "n2"},  # n1 dropped
        ],
    }
    res = Extractor(FakeLLM([payload])).extract("The lead checks stock every morning.")
    names = {n.canonical_name for n in res.nodes}
    assert "Bad" not in names  # unknown type dropped
    assert len(res.relations) == 1  # only the valid Role->Activity survives


def test_extractor_filters_unregistered_category_codes():
    payload = {
        "nodes": [
            {
                "ref": "n1",
                "type": "Activity",
                "canonical_name": "Check stock",
                "description": "y",
                "category_codes": ["02", "99.9"],
            }
        ],
        "relations": [],
    }
    res = Extractor(FakeLLM([payload])).extract("The lead checks stock every morning.")
    assert res.nodes[0].category_codes == ["02"]  # 99.9 not in registry


# --- content-free answers (voice sessions record Scribe's audio-event tags as answers) ---


class CountingLLM(FakeLLM):
    """FakeLLM that records how many times the model was actually asked."""

    def __init__(self) -> None:
        super().__init__([])
        self.calls = 0

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict:
        self.calls += 1
        return super().complete_json(system, user, temperature=temperature)


def test_audio_event_tags_are_not_extractable():
    for noise in ("[click]", "[pause]", "  [ laughter ] ", "[click] [pause]", "", "   ", "..."):
        assert not has_extractable_content(noise), noise


def test_real_speech_is_extractable_even_with_tags():
    for real in ("I raise the invoice.", "[pause] I raise the invoice.", "we use SAP [click]"):
        assert has_extractable_content(real), real


def test_extract_skips_the_model_entirely_for_a_content_free_answer():
    llm = CountingLLM()
    res = Extractor(llm).extract("[click]")
    assert res.nodes == [] and res.relations == []
    assert llm.calls == 0  # never pay for an answer with nothing in it


def test_extract_still_calls_the_model_for_real_speech():
    llm = CountingLLM()
    Extractor(llm).extract("The analyst writes the BRD.")
    assert llm.calls == 1
