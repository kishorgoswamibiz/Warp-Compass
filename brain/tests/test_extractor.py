"""Phase 2 — extractor parses + sanitizes constrained JSON (no network)."""

from __future__ import annotations

from conftest import FakeLLM

from warp_compass_brain.extractor import Extractor


def test_extractor_parses_nodes_and_relations():
    payload = {
        "nodes": [
            {"ref": "n1", "type": "Role", "canonical_name": "Inventory Lead", "description": "x"},
            {"ref": "n2", "type": "Activity", "canonical_name": "Check stock", "description": "y"},
        ],
        "relations": [{"type": "PERFORMS", "from_ref": "n1", "to_ref": "n2"}],
    }
    ex = Extractor(FakeLLM([payload]))
    res = ex.extract("...")
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
    res = Extractor(FakeLLM([payload])).extract("...")
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
    res = Extractor(FakeLLM([payload])).extract("...")
    assert res.nodes[0].category_codes == ["02"]  # 99.9 not in registry
