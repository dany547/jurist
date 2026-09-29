"""Article-level lookup on the real corpus + session-scoped citation validation.

These tests use data/legal.db read-only. JURIST_SESSION is pinned so the runs
do not pollute the default 'current' session.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jurist import JuristEngine

ROOT = Path(__file__).resolve().parents[1]
REAL_DB = ROOT / "data" / "legal.db"

requires_real_db = pytest.mark.skipif(not REAL_DB.exists(), reason="data/legal.db lipsește")


@requires_real_db
def test_real_db_gdpr_article_level_lookup(monkeypatch):
    monkeypatch.setenv("JURIST_SESSION", "test")
    e = JuristEngine(REAL_DB)
    try:
        result = e.get_provision(act="GDPR", article="6")
        assert result["ok"] is True
        provision = result["provision"]
        assert provision["provision_id"] == "EU:REG:2016:679:ART:6"
        assert provision["canonical_citation"] == "EU:REG:2016:679:ART:6"
        assert provision["citable_as_binding_basis"] == 1
        assert provision["paragraph"] is None and provision["letter"] is None
        assert provision["status"] == "in_force"
        assert provision["full_article_available"] is True
        assert "context_call" in provision
        assert "(1)" in provision["text"] and "(2)" in provision["text"]
        assert "(1) lit. (f)" in provision["text"]
        # child rows AND the article-level id are both recorded for this session
        logged = {r[0] for r in e.conn.execute(
            "SELECT provision_id FROM retrieval_log WHERE session_id='test'")}
        assert "EU:REG:2016:679:ART:6" in logged
        assert "EU:REG:2016:679:ART:6:P:1:L:f" in logged
        assert e.validate_citations("EU:REG:2016:679:ART:6:P:1:L:f")["valid"]
    finally:
        e.close()


@requires_real_db
def test_real_db_ro_article_with_context(monkeypatch):
    monkeypatch.setenv("JURIST_SESSION", "test")
    e = JuristEngine(REAL_DB)
    try:
        result = e.get_provision(act="RO:LEGE:506:2004", article="4", context="article")
        assert result["ok"] is True
        provision = result["provision"]
        assert provision["provision_id"] == "RO:LEGE:506:2004:ART:4"
        assert provision["citable_as_binding_basis"] == 1
        assert "(5)" in provision["text"] and "lit. (a)" in provision["text"]
        context_ids = [item["provision_id"] for item in result["context"]]
        assert "RO:LEGE:506:2004:ART:4:P:1" in context_ids
        assert "RO:LEGE:506:2004:ART:4:P:6" in context_ids
        logged = {r[0] for r in e.conn.execute(
            "SELECT provision_id FROM retrieval_log WHERE session_id='test'")}
        assert "RO:LEGE:506:2004:ART:4" in logged
        assert "RO:LEGE:506:2004:ART:4:P:5" in logged
    finally:
        e.close()


@requires_real_db
def test_real_db_cli_article_context(monkeypatch):
    monkeypatch.setenv("JURIST_SESSION", "test")
    env = dict(os.environ, JURIST_SESSION="test")
    out = subprocess.check_output(
        [sys.executable, "-m", "jurist", "provision", "--act", "GDPR", "--article", "6",
         "--context", "article", "--json"],
        text=True, env=env, cwd=str(ROOT))
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["provision"]["provision_id"] == "EU:REG:2016:679:ART:6"


@requires_real_db
def test_real_db_session_isolation(monkeypatch):
    # 'current' has this citation logged, but session 'test-isolation' does not:
    # the draft must still be rejected with CITED_WITHOUT_RETRIEVAL.
    monkeypatch.setenv("JURIST_SESSION", "test-isolation")
    e = JuristEngine(REAL_DB)
    try:
        issues = e.validate_citations("RO:LEGE:506:2004:ART:4:P:5")["issues"]
        assert issues and issues[0]["code"] == "CITED_WITHOUT_RETRIEVAL"
    finally:
        e.close()


def test_session_scoped_validation(tmp_path, monkeypatch):
    db = tmp_path / "sessions.db"
    monkeypatch.setenv("JURIST_SESSION", "sess-x")
    e1 = JuristEngine(db, seed=True)
    try:
        assert e1.get_provision("EU:REG:2016:679:ART:6")["ok"]
        draft = "Conform EU:REG:2016:679:ART:6."
        assert e1.validate_citations(draft)["valid"] is True
    finally:
        e1.close()
    # a different session retrieved nothing: the same draft is rejected
    monkeypatch.setenv("JURIST_SESSION", "sess-y")
    e2 = JuristEngine(db, seed=True)
    try:
        issues = e2.validate_citations(draft)["issues"]
        assert issues and issues[0]["code"] == "CITED_WITHOUT_RETRIEVAL"
    finally:
        e2.close()
