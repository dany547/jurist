import json, subprocess, sys
from jurist import JuristEngine


def engine(tmp_path): return JuristEngine(tmp_path / "test.db", seed=True)

def test_schema_and_fts(tmp_path):
    e=engine(tmp_path)
    assert e.conn.execute("select count(*) from legislation_fts").fetchone()[0] >= 6
    assert e.legal_search("consimțământ")["results"]

def test_cedilla_and_alias(tmp_path):
    e=engine(tmp_path)
    assert e.legal_search("obţinerea accesului")["results"]
    assert e.resolve_act("legea cookie-urilor")["matches"][0]["id"] == "RO:LEGE:506:2004"

def test_exact_citation_context_and_status(tmp_path):
    e=engine(tmp_path); result=e.get_provision("EU:REG:2016:679:art:6", "article", "2020-01-01")
    assert result["provision"]["status"] == "in_force"
    assert len(result["context"]) == 1
    ro=e.get_provision("RO:LEGE:506:2004:art:4:5", as_of="2020-01-01")["provision"]
    assert ro["applicability"] == "NOT_VERIFIED_FOR_DATE"

def test_directive_domain_routing_and_guidance_counter(tmp_path):
    e=engine(tmp_path)
    act=e.resolve_act("eprivacy")["matches"][0]
    assert "DIRECTIVE_NOT_DIRECTLY_APPLICABLE" in act["warnings"] and act["transposed_by"]
    search=e.legal_search("trebuie banner de cookies?")
    assert search["routed_domains"] == ["cookies"] and search["guidance_hits_excluded"] == 0

def test_relations_status_validator_and_noop_update(tmp_path):
    e=engine(tmp_path)
    assert e.find_related("EU:DIR:2002:58")["relations"]
    assert "REAL_SOURCES_NOT_DOWNLOADED" in e.corpus_status()["warnings"]
    draft="EU:REG:2016:679:art:6 EU:REG:2016:679:art:99"
    issues={x["code"] for x in e.validate_citations(draft)["issues"]}
    assert issues == {"CITED_WITHOUT_RETRIEVAL", "UNKNOWN_CITATION"}
    e.get_provision("RO:LEGE:506:2004:art:4:5")
    assert e.validate_citations("RO:LEGE:506:2004:art:4:5", "2020-01-01")["issues"][0]["code"] == "OUTDATED_PROVISION"
    assert e.update()["status"] == "NO_OP"

def test_cli(tmp_path):
    db=tmp_path / "cli.db"
    out=subprocess.check_output([sys.executable,"-m","jurist","--db",str(db),"--seed","legal_search","--json","cookies"],text=True)
    assert json.loads(out)["status"] == "OK"

def test_fixture_provenance_warning(tmp_path):
    e = JuristEngine(tmp_path / "fixture.db", seed=True)
    result = e.resolve_act("GDPR")
    assert any("FIXTURE_NOT_OFFICIAL_TEXT" in w for w in result["warnings"])
    prov = e.get_provision("EU:REG:2016:679:ART:6")
    assert any("FIXTURE_NOT_OFFICIAL_TEXT" in w for w in prov["warnings"])
    e.close()
    e2 = JuristEngine(tmp_path / "fixture.db", seed=True)
    assert e2.get_provision("EU:REG:2016:679:ART:6")["warnings"]
    e2.close()

def test_empty_db_no_seed(tmp_path):
    e = JuristEngine(tmp_path / "empty.db")
    assert e.conn.execute("SELECT COUNT(*) FROM acts").fetchone()[0] == 0
    e.close()


def test_resolve_next_action_is_null(tmp_path):
    e = engine(tmp_path)
    assert e.resolve_act("GDPR")["next_action"] is None
    assert e.resolve_act("nu-exista-act-xyz")["next_action"] is None


def test_cookie_search_prefers_provision_tags(tmp_path):
    e = engine(tmp_path)
    ids = [h["provision_id"] for h in e.legal_search("trebuie banner de cookies?")["results"]]
    assert "RO:LEGE:506:2004:ART:4:P:5" in ids
    assert ids, "cookie routing must return the tagged provision, not an empty act dump"


def test_routing_targets_exist_on_corpus_acts():
    from pathlib import Path
    from jurist.engine import fold
    root = Path(__file__).resolve().parents[1]
    corpus_tags = set()
    for line in (root / "sources" / "corpus.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("domains:"):
            rest = stripped.split(":", 1)[1].strip()
            if rest.startswith("["):
                corpus_tags.update(fold(x.strip().strip("'\"")) for x in rest.strip("[]").split(",") if x.strip())
    routing_targets = set()
    for line in (root / "sources" / "routing_keywords.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 2:
            routing_targets.update(fold(x) for x in fields[1].split(",") if fold(x))
    extra = routing_targets - corpus_tags
    assert not extra, f"routing targets missing from corpus.yaml acts: {sorted(extra)}"
