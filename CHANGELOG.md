# Changelog

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
