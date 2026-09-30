# Changelog

## 0.1.9 — 2026-09-30

- Curățenie: șterse `CONTEXT.md` (artefact istoric), `docs/` (rapoarte de audit și cercetare, planuri de mod editorial) și scripturile moarte `build_index.py`, `diff_versions.py`, `normalize.py`, `update.py`, `update_manifest.py`, `scripts/jurist.py`. Istoricul rămâne în git.
- CI rulează și `validate_sources.py`, `validate.py` și `tag_domains.py --check`.
- AGENTS.md §6 descrie structura reală a repository-ului; README și `corpus-audit.md` nu mai trimit la fișierele șterse.

## 0.1.8 — 2026-09-30

- CI GitHub Actions (`.github/workflows/ci.yml`): teste pe Python 3.10 și 3.13, verificarea FTS5, eval-ul recall@10 și notele din CHANGELOG, la fiecare push și pull request.
- Release automat: la un push pe `main` cu o versiune nouă în `pyproject.toml`, CI-ul creează tag-ul `vX.Y.Z` și GitHub Release-ul cu notele din secțiunea corespunzătoare din CHANGELOG.
- `scripts/release_info.py` (versiunea curentă și notele ei) și `tests/test_release_info.py`.
- Acțiuni pe Node 24 (`actions/checkout@v5`, `actions/setup-python@v6`) și runner fixat pe `ubuntu-24.04`.

## 0.1.7 — 2026-09-30

- README: titlul devine „Jurist - Asistent juridic cu AI”; avertisment vizibil la început și secțiunea „Declinarea răspunderii” (nu înlocuiește un avocat, punct de plecare, folosire pe propria răspundere).
- Versiunile sunt marcate cu tag-uri git anotate `vX.Y.Z`, începând cu v0.1.3.

## 0.1.6 — 2026-09-29

- Corpus 46 → 48 acte: **Codul civil** (Legea 287/2009), ingerat parțial: art. 1164–1762 (obligații, contracte, clauze standard, interpretare, forță majoră, daune, vânzare și vicii ascunse) și 2500–2544 (prescripția extinctivă). **Legea 31/1990**, doar art. 74 (datele de identificare ale societății pe documente și pe site).
- `corpus.yaml` acceptă `ingest_articles` (intervale inclusive de articole) pentru acte ingerate parțial.
- `parse_ro.py`: numerele de articol peste 999 scrise cu punct de mii („Articolul 1.164”) erau citite ca 1 și se suprapuneau cu art. 1–999; acum se citesc corect.
- `fetch_corpus.py`: pentru actele foarte mari, portalul întoarce o pagină-cadru; se urmează automat linkul oficial `DetaliiDocumentAfis/<id>` către forma consolidată curentă.
- Rutare: fraze specifice pentru clauze standard, forță majoră, vicii ascunse, prescripție și datele firmei, plus dovada consimțământului GDPR (ca să nu fie confundat cu consimțământul părților din Codul civil).
- Eval: 70 de întrebări, recall@10 = 0.986. Teste noi în `tests/test_partial_acts.py`.
- README: secțiune de instalare pentru agenți AI (pași neinteractivi, verificare, reguli, tabel de erori). SKILL.md: acoperirea parțială a Codului civil e marcată explicit.

## 0.1.5 — 2026-09-29

- `jurist related` și `transposed_by` din `search`/`resolve` listează doar relațiile de ieșire ale actului interogat. `relations.tsv` le stochează în ambele sensuri, deci înainte fiecare relație apărea de două ori, iar o lege RO apărea ca „transpusă de” directiva pe care o transpune.
- Index nou `idx_provisions_id` pe `provisions(id)`: căutarea FTS făcea un scan complet al tabelei pentru fiecare potrivire (8,6 s → 0,08 s per căutare; eval-ul complet în ~1 s). Indexul se creează automat la deschiderea unei baze existente.
- `tests/test_relations.py`: regresie pentru direcția relațiilor.

## 0.1.4 — 2026-09-29

- README rescris: instalare pas cu pas, cum funcționează (rutare pe 3 niveluri, semnale, citări canonice, pipeline de build), utilizare CLI cu exemple reale, validatorul de citări, actualizarea și adăugarea de acte, depanare, limite.
- `scripts/install_skill.sh`: instalare reproductibilă ca skill Claude Code (verifică Python/PyYAML/FTS5, sync, copiază `data/legal.db`, scrie launcher-ul `jurist`).
- `pyproject.toml`: versiunea aliniată cu CHANGELOG.

## 0.1.3 — 2026-09-29

- Engine fixes: article-level `provision` lookup (whole article reconstructed from its paragraph/letter children when no article row exists); single canonical payload keys — `matches` (resolve), `results` (search), `provision` (provision); corpus-status source counters computed from the acts table (fixes the `jurislatie_just_ro` typo).
- New fetch entry point `scripts/fetch_corpus.py` (RO: SOAP + LinkHtml; EU: Cellar XHTML with content gate, manifest upsert, stable-text hash for unchanged acts).
- Corpus expansion 28 → **46 acts (17 RO + 29 EU)**, 50 relations. New RO: HG 947/2000, OG 38/2015, Legea 50/2024, Legea 209/2019, Legea 214/2024. New EU: Reg 2023/988 (GPSR), Reg 2023/2854 (Data Act), Dir 2024/825 (EmpCo), Dir 2023/2673, Dir 2024/2853 (PLD), Dec 2021/914 (SCC), Dec 2021/915 (SCC P2P), Dec 2023/1795 (DPF), Dir 2022/2555 (NIS2), Reg 2024/1689 (AI Act), Reg 2024/3228 (ODR repeal), Reg 593/2008 (Roma I), Reg 1215/2012 (Bruxelles I bis).
- Removed superseded seed-era scripts and data: `scripts/download_via_soap.py`, `scripts/fetch_365.py`, `scripts/download_all.py`, `scripts/fetch_official_batch.py`, `data/jurist.db`, `tests/eval_questions_40.tsv.fixture-era`. `scripts/fetch_ro.py` stays as the SOAP helper library imported by `fetch_corpus.py`.

## 0.1.2

- Ingested Regulation (EU) 2019/1150 (P2B), Legea 232/2022 (EAA) and OUG 155/2024 (NIS2 RO) from Cellar/SOAP+LinkHtml.
- 28 acts, 5896 provisions. Directiva 2019/882 ↔ Legea 232/2022 in relations.tsv.

## 0.1.1

- Provision-level domain tags (`sources/tags.tsv`); search prefers tagged articles over whole acts.
- Routing uses the English corpus.yaml vocabulary; longest phrase wins; stopwords kept out of FTS.
- Eval runs on the real DB (`seed=False`); recall@10 = 1.0 on the 40-question set.
- SKILL.md is the runtime contract (no act table, no AGENTS.md dump). SOAP is discovery; RO text is LinkHtml HTML.

## 0.1.0

- SQLite + FTS5 local legal retrieval with Romanian NFC/cedilla normalization.
- Five JSON tools: resolve, search, provision, related, corpus-status.
- Honest `current_only` RO coverage, directive/transposition warnings, freshness metadata.
- Official-source SOAP (RO) and Cellar (EU) fetchers are opt-in and preserve raw snapshots/checksums.
- Deterministic provision citation validator and 40-question recall regression set.
