import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from jurist import JuristEngine
from jurist.__main__ import _parser
from scripts.perception_risk import ALLOWED_CATEGORIES, derive_risk
from jurist.engine import canonical_citation, normalize_citation
from scripts.parse_ro import parse_ro_text


def test_one_citation_grammar_preserves_official_keys():
    assert canonical_citation("EU", "REG", "679", 2016, article="6") == "EU:REG:2016:679:ART:6"
    assert canonical_citation("RO", "LEGE", "506", 2004, article="4", paragraph="5") == "RO:LEGE:506:2004:ART:4:P:5"
    assert normalize_citation("ro:lege:506:2004:art:4:5") == "RO:LEGE:506:2004:ART:4:P:5"


def test_common_envelope_and_historical_warning(tmp_path):
    engine = JuristEngine(tmp_path / "legal.db", seed=True)
    resolved = engine.resolve_act("Legea 506/2004", as_of="2020-01-01")
    assert {"ok", "as_of", "warnings", "next_action"} <= resolved.keys()
    assert "NOT_VERIFIED_FOR_DATE" in resolved["warnings"]
    search = engine.legal_search("banner cookie", as_of="2020-01-01")
    assert {"results", "guidance_hits_excluded", "warnings", "next_action"} <= search.keys()
    assert any("DIRECTIVE_NOT_DIRECTLY_APPLICABLE" in hit["warnings"] for hit in search["results"])
    engine.close()


def test_ro_parser_keeps_paragraphs_and_normalizes_text():
    rows = parse_ro_text("Art. 4\n(5) Text cu ş cedilă.\nArticolul 5\nText.", act_type="LEGE", number="506", year=2004)
    assert rows[0]["id"] == "RO:LEGE:506:2004:ART:4:P:5"
    assert "ș" in rows[0]["text"]


def test_public_cli_has_exact_five_commands(tmp_path):
    output = subprocess.check_output([sys.executable, "-m", "jurist", "--db", str(tmp_path / "x.db"), "--seed", "resolve", "--reference", "GDPR", "--json"], text=True)
    payload = json.loads(output)
    assert payload["tool"] == "jurist resolve"
    help_text = subprocess.check_output([sys.executable, "-m", "jurist", "--help"], text=True)
    assert "resolve,search,provision,related,corpus-status" in help_text.replace(" ", "")


def test_public_parser_exposes_only_the_five_contract_commands():
    subparsers = next(action for action in _parser()._actions if getattr(action, "choices", None) is not None)
    assert set(subparsers.choices) == {"resolve", "search", "provision", "related", "corpus-status"}


def test_skill_contains_routing_table_tasks_and_statement_statuses():
    skill = Path("SKILL.md").read_text(encoding="utf-8")
    assert "| Intrare | Sarcină | Statut implicit |" in skill
    for task in ("rewrite", "describe_source", "answer_legal", "audit_perception"):
        assert f"`{task}`" in skill
    for status in ("verified", "source_reported", "editorial", "out_of_corpus", "unverified"):
        assert f"`{status}`" in skill


def test_skill_description_covers_non_legal_editorial_applicability():
    frontmatter = Path("SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    description = " ".join(frontmatter.split())
    assert "Auditul percepției juridice și rescrierea editorială" in description
    assert "oricărui text juridic-administrativ" in description


def test_perception_signal_categories_match_agents_contract():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    categories = set()
    for line in Path("sources/perception_signals.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        columns = line.split("\t")
        assert len(columns) == 2
        categories.add(columns[1])
    assert categories == ALLOWED_CATEGORIES
    assert all(category in agents for category in categories)


@pytest.mark.parametrize(
    ("categories", "user_subject", "expected"),
    [
        (set(), False, "scazut"),
        ({"obligatie"}, False, "mediu"),
        ({"termen_cuantum", "exhaustivitate"}, False, "mediu"),
        ({"efect_juridic"}, False, "ridicat"),
        ({"obligatie", "conformitate"}, False, "ridicat"),
        (set(), True, "ridicat"),
    ],
)
def test_derive_risk_is_deterministic(categories, user_subject, expected):
    assert derive_risk(categories, user_subject=user_subject) == expected
    assert derive_risk(categories, user_subject=user_subject) == expected


def test_derive_risk_rejects_unknown_categories():
    with pytest.raises(ValueError):
        derive_risk({"alta_categorie"})


def test_global_skill_copy_has_no_drift():
    global_root = Path(os.environ.get("JURIST_GLOBAL_SKILL", "~/.claude/skills/jurist")).expanduser()
    if not global_root.exists():
        pytest.skip("copia globală a skill-ului nu există")
    result = subprocess.run([sys.executable, "scripts/sync_skill.py", "--check"], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
