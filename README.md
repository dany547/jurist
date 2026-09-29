# jurist

MVP local pentru retrieval juridic românesc/UE: SQLite + FTS5, normalizare română, rutare pe domenii, version coverage și citation validator. Este un motor de cercetare, nu consiliere juridică și nu declară conformitatea unui document.

## Statusul datelor

Corpusul real este definit în `sources/corpus.yaml`: **46 de acte (17 România + 29 UE)** și **50 de relații** în `sources/relations.tsv`, toate descărcate din sursele oficiale și ingerate în `data/legal.db`:

- România: Portal Legislativ SOAP (`http://legislatie.just.ro/apiws`) pentru descoperire + HTML-ul oficial consolidat identificat prin `LinkHtml` — fără scraping;
- UE: EUR-Lex + Publications Office Cellar (XHTML consolidat, cu content gate).

Numerele live (provizii, aliasuri, versiuni, ultima sincronizare) le dă `python3 -m jurist corpus-status --json`.

## Rulare

```bash
python3 -m pytest -q
python3 -m jurist --help
python3 -m jurist corpus-status --json
python3 -m jurist search --query "banner cookie" --json
python3 -m jurist provision --act GDPR --article 6 --json
```

Căutarea la nivel de articol funcționează: `provision --act GDPR --article 6` întoarce întregul articol (reconstruit din alineate/litere când nu există rând de articol). `--context article|section` aduce articolul complet sau articolul + vecinii. Contractul public are exact cinci comenzi: `resolve`, `search`, `provision`, `related`, `corpus-status`.

## Pipeline

```bash
python3 scripts/fetch_corpus.py            # descarcă corpus.yaml din surse oficiale în raw/ (checksum + manifest)
python3 scripts/ingest_corpus.py --fresh   # parsează și reconstruiește data/legal.db
python3 -m pytest -q                       # regresie (inclusiv citări cunoscute)
python3 scripts/eval_recall.py             # eval 40 întrebări, recall@10
```

`fetch_corpus.py` este singurul punct de intrare de fetch; `scripts/fetch_ro.py` rămâne ca bibliotecă SOAP folosită de acesta.

## Structură

- `AGENTS.md` — contractul executabil complet și gates A–I;
- `SKILL.md` — instrucțiuni scurte pentru agent;
- `sources/corpus.yaml` — registrul uman al actelor și aliasurilor;
- `jurist/engine.py` — schema SQLite, FTS5, routing și răspunsuri JSON;
- `scripts/fetch_corpus.py` (+ `scripts/fetch_ro.py`, bibliotecă SOAP) — fetch oficial, opt-in, cu manifest/checksum în `raw/`;
- `scripts/parse_*.py`, `scripts/diff_versions.py`, `scripts/validate.py` — build și verificare;
- `tests/eval_questions_40.tsv` — set de regresie recall@10.

## Comportament de siguranță

Fiecare răspuns expune `warnings[]` și `next_action`. Pentru RO, `version_coverage=current_only`; o dată istorică explicită primește `NOT_VERIFIED_FOR_DATE`. Pentru directive, rezultatele poartă `DIRECTIVE_NOT_DIRECTLY_APPLICABLE` și relațiile de transpunere când există.

Validatorul determinist al citărilor (`UNKNOWN_CITATION`, `CITED_WITHOUT_RETRIEVAL`, `OUTDATED_PROVISION`) verifică draft-ul contra `retrieval_log`-ului de sesiune; setează `JURIST_SESSION=<id>` pentru a grupa apelurile aceleiași sesiuni de lucru (altfel toate intră în sesiunea `current`).

Skill-ul separă două axe: sarcina cerută (`rewrite`, `describe_source`, `answer_legal`, `audit_perception`) și statutul fiecărei afirmații (`verified`, `source_reported`, `editorial`, `out_of_corpus`, `unverified`). Rescrierea și descrierea păstrează proveniența textului sau a sursei, iar concluziile juridice se bazează pe retrieval și citări; nicio sarcină nu este implicit consultanță sau validare juridică exhaustivă. Auditul de percepție juridică semnalează formulările care pot fi citite ca îndrumare juridică după forma lor lingvistică, fără să verifice fondul juridic.
