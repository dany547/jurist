"""Relations are reported once, in the queried act's own direction.

relations.tsv stores each relation in both directions; `related` and the
inline `transposed_by` on search/resolve must not echo the inverse rows.
Uses data/legal.db read-only (JURIST_SESSION pinned to 'test').
"""
from pathlib import Path

import pytest

from jurist import JuristEngine

ROOT = Path(__file__).resolve().parents[1]
REAL_DB = ROOT / "data" / "legal.db"

pytestmark = pytest.mark.skipif(not REAL_DB.exists(), reason="data/legal.db lipsește")


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("JURIST_SESSION", "test")
    e = JuristEngine(REAL_DB)
    yield e
    e.conn.execute("DELETE FROM retrieval_log WHERE session_id='test'")
    e.conn.commit()
    e.close()


def test_related_lists_only_outgoing_relations(engine):
    relations = engine.find_related("EU:DIR:2024:825")["relations"]
    assert relations, "EU:DIR:2024:825 trebuie să aibă relații"
    assert all(r["source_act_id"] == "EU:DIR:2024:825" for r in relations)
    pairs = {(r["relation_type"], r["target_act_id"]) for r in relations}
    assert pairs == {
        ("amends", "EU:DIR:2005:29"),
        ("amends", "EU:DIR:2011:83"),
        ("transposed_by", "RO:LEGE:363:2007"),
        ("transposed_by", "RO:OUG:34:2014"),
    }
    assert len(relations) == len(pairs), "fără duplicate"


def test_related_filter_by_relation_type(engine):
    relations = engine.find_related("RO:LEGE:506:2004", relations=["transposes"])["relations"]
    assert [(r["relation_type"], r["target_act_id"]) for r in relations] == [("transposes", "EU:DIR:2002:58")]
    assert engine.find_related("RO:LEGE:506:2004", relations=["transposed_by"])["relations"] == []


def test_search_transposed_by_is_directional(engine):
    results = engine.legal_search("trebuie banner de cookies pe site", limit=10)["results"]
    by_id = {r["provision_id"]: r for r in results}
    directive = by_id["EU:DIR:2002:58:ART:5:P:3"]
    assert [t["act_id"] for t in directive["transposed_by"]] == ["RO:LEGE:506:2004"]
    assert all(t["relation_type"] == "transposed_by" for t in directive["transposed_by"])
    # A Romanian transposition law is not itself "transposed_by" the directive.
    assert by_id["RO:LEGE:506:2004:ART:4:P:5"]["transposed_by"] == []
