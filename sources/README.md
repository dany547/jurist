# Surse corpus jurist

- `corpus.yaml` este registrul unic: acte, alias-uri, domenii, rezumate draft, identificatori, `version_coverage` și metadata de fetch.
- `registry.json` enumeră sursele oficiale permise și metodele de retrieval.
- `lemmas_ro.tsv` și `routing_keywords.tsv` sunt tabele manuale folosite la normalizare și rutare.
- `corpus-audit.md` documentează acoperirea, deciziile și omisiunile.

## Validare locală

Din rădăcina proiectului, fără descărcarea actelor:

```bash
python - <<'PY'
import json
from pathlib import Path
import yaml

root = Path("sources")
corpus = yaml.safe_load((root / "corpus.yaml").read_text())
registry = json.loads((root / "registry.json").read_text())
assert corpus["schema_version"] == "1.0"
assert registry["schema_version"] == "1.0"
acts = corpus["acts"]
assert len(acts) == 46, len(acts)
required = {"id", "fetch", "authority_class", "version_coverage", "domains", "aliases", "summary_ro", "source"}
ids = set()
for act in acts:
    assert required <= act.keys(), act.get("id")
    assert act["id"] not in ids, act["id"]
    ids.add(act["id"])
    assert act["fetch"]["source_id"]
    assert act["source"]["links"]
    assert act["summary_ro"]["confidence"] == "draft_neconfirmat"
    assert act["version_coverage"] in {"current_only", "point_in_time"}
print(f"OK: {len(acts)} acte, YAML și JSON parsează")
PY
```

La retrieval, starea reală de fetch (URL oficial efectiv, hash, `retrieved_at`) se scrie pe `act_versions` în `data/legal.db` de `scripts/fetch_corpus.py` + `scripts/ingest_corpus.py`; `jurist corpus-status --json` o randează. Resolverul trebuie să folosească exclusiv sursele `enabled: true` din registry.
