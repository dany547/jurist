# jurist — structural audit (read-only), 2026-09-29

Scope: /home/dan/CODE/jurist. No project file modified. Commands run: `pytest -q`, the 5 `python3 -m jurist` subcommands (incl. `--as-of` probes), sqlite3 read-only queries on `data/legal.db` / `data/jurist.db`, grep/wc over scripts and docs.
Baseline: 27 tests pass (`pytest -q` → "27 passed in 0.29s"); `scripts/eval_recall.py` → `"passed": true` (recall@10 = 1.0); DB: 28 acts / 5,896 provisions / 101 aliases / 18 relations.

## 1. Contract bug #1 — article-level `provision` returns NOT_FOUND (66% of articles)

- `python3 -m jurist provision --act RO:LEGE:506:2004 --article 4 --json` → `NOT_FOUND`. Same for `--act GDPR --article 6`, and for `--context article`. With `--paragraph 5` it works (full status: STALE_CORPUS, corpus_age_days=31 — the stale-corpus suspicion is resolved: warnings work).
- Cause: `get_provision` (jurist/engine.py:766) builds the citation via `_provision_citation_for_row` (engine.py:827) → `RO:LEGE:506:2004:ART:4`, then `SELECT ... WHERE p.id=?` (engine.py:783–784) → no row → `_error(... "NOT_FOUND" ...)` (engine.py:785). Ingest only stores paragraph/letter/point rows; there is no ART:4 row.
- Scale (sqlite, provisions grouped by act_id+article vs `paragraph IS NULL` rows): **714 of 1,074 articles (66%) lack an article-level row** (GDPR 82/99, DSA 81/93, eIDAS 69/82, Legea 506 15/17...). A few acts have article rows for some articles (e.g. RO:LEGE:363:2007, RO:OUG:155:2024), so behavior is inconsistent per act.
- Impact: breaks AGENTS.md §12.3 examples (`--article 6` without paragraph), SKILL.md step 4 ("Ia textul exact: `provision --context article`", SKILL.md:69) and README.md:19 (`provision --act GDPR --article 6 --context article` — documented and broken). The `context_call` pattern still works because it echoes act+article… only when a paragraph was supplied.
- Minimal fix (S, low risk): in `get_provision`, when the exact `cid` misses and `paragraph is None`, fall back to fetching all rows for `(act_id, article)` ordered by `sequence` and serve them as the article payload (first row as `provision`, all as `context`); or synthesize the article text by concatenation. Add a regression test: article-without-paragraph for 3 acts (RO/EU, with/without article rows).

## 2. Contract gaps vs AGENTS.md §12/§30 (from live CLI runs)

Verified working: envelope `warnings[]`+`next_action` on all 5 subcommands; STALE_CORPUS (>30d); NOT_VERIFIED_FOR_DATE + earliest_version_date for RO as-of 2020-01-01 (provision --paragraph 5 --as-of 2020-01-01); DIRECTIVE_NOT_DIRECTLY_APPLICABLE + transposed_by inline on directive hits (search for "banner cookie" → EU:DIR:2002:58:ART:5:P:3 with transposed_by RO:LEGE:506:2004); guidance corpus honest `NO_MATCH_ABOVE_THRESHOLD` with 0 results; `resolve --jurisdiction EU` honest empty; related EU:DIR:2019:770 → RO:OUG:141:2021 transposed_by. Gaps:

1. **Duplicated payload arrays** (3×): resolve returns `matches` AND `acts` (engine.py:522 — same list twice); search returns `results` AND `hits` (engine.py:753); provision returns `provision` AND `provisions` (duplicate with different `status` casing: `in_force` vs `IN_FORCE`). Doubles response size; two shapes invite drift. Fix: emit one canonical key (S).
2. **`authority_class` vocabulary drift**: DB values `ro_law`, `eu_directive`, `eu_regulation`, `binding_legislation` (mixed); AGENTS.md §3/§8.1 requires a single enum (`binding_legislation` for all binding acts); §8.10 seed ranks (`RO_LEGE`, `EU_PRIMARY_LAW`…) differ from the actual `authority_ranks` rows (lowercase, `case_law`=70 vs §8.10 CJEU_BINDING=95). Self-consistent internally; contract text is stale. Decide one vocabulary; prefer updating the docs (S) over re-tagging the DB.
3. **`domains` are not the §8.9 closed taxonomy**: 44 free-form English tags in DB (`privacy`, `direct_marketing`, `ecommerce`, `employment`, `cybersecurity`…) vs the frozen ~30-tag list (§8.9: `marketing_direct`, `temeiuri_legale`, `personal_data`…). `routing_keywords.tsv` correctly targets tags that exist (e.g. `cookies`), so routing works (eval 1.0), but §8.9's "closed vocabulary" claim is false. Fix: replace §8.9 list with the actual tag inventory, or re-tag (decision + S doc edit; re-tag is M).
4. **`scope_provisions` are range strings, not provision_ids**: corpus.yaml:68 `["art. 5-11", ...]`; resolve returns them JSON-decoded but non-canonical (§5.6 requires `provision_id`s; §16 grammar). Not used mechanically anywhere → doc-level fix or leave as display ranges and rename the field (S).
5. **corpus-status source counters wrong + typo**: prints `jurislatie_just_ro` (missing 'g') with `documents: 2` and eurlex `documents: 1`, while 28 act_versions exist. Origin: scripts/ingest_corpus.py:331 inserts per-run counters (2 RO files ingested in the last run) into `corpus_status`; engine.py:869 derives the warning from it. Fix the typo and compute counts from `acts.source_system` (S).
6. **`last_build: null`** in corpus-status and data/manifest.json is a stale skeleton (`built_at: null`, `documents: 0`, `acts: {}` — §22 contract). Either populate manifest at ingest or have corpus-status stop promising it (S).

## 3. Dead / duplicate files (evidence)

- **data/jurist.db — dead.** 118KB, Aug 29 07:52; contains the seed era: 4 acts / 6 provisions. Zero code references (`grep -rn "jurist.db"` hits only tests/test_jurist.py:5, which uses the name for a throwaway tmp DB). DEFAULT_DB is data/legal.db (engine.py:173–186). Candidate for deletion (needs owner confirmation; not done here).
- **scripts/download_via_soap.py — dead.** No importer, no doc reference (grep across *.py/*.md/*.yaml). Superseded by the fetch_ro.py SOAP flow.
- **scripts/fetch_365.py — one-off turned helper.** Only consumer: scripts/fetch_official_batch.py:22 imports `discover_link_html, fetch_html`. Its download logic is dead; the two helpers belong in fetch_ro.py. Fold + delete (S/M, low risk).
- **scripts/validate_sources.py** — no importers; standalone checker. Keep only if used in Etapa gates; else dead.
- **scripts/build_index.py** — referenced only by AGENTS.md/CONTEXT.md; ingest_corpus.py builds FTS itself. Verify against the Etapa E gate before deleting.
- **tests/eval_questions_40.tsv.fixture-era** — leftover backup next to the live file (wc/grep); archive or delete.
- **ingest/eu + ingest/ro (25 files)** — intermediate parse inputs referenced by download_all/fetch_365/parse_eu; AGENTS.md §6 layout only knows raw/. Fine to keep, but the layout doc should mention ingest/ or it will look like drift forever.
- Real fetch pipeline is actually 3 entry points: fetch_ro.py (SOAP), fetch_eu.py (Cellar), download_all.py + fetch_official_batch.py (drivers) — acceptable; the residue is the two files above.

## 4. Doc drift

- **sources/corpus-audit.md:5–7** — "25 de acte", "Nu a fost descărcat niciun corpus", `not_fetched` — reality: 28 acts ingested with official source_url on every act_version. Stale on every claim. Rewrite the summary + coverage numbers (S).
- **README.md:7–9** — "seed demonstrativ mic... REAL_SOURCES_NOT_DOWNLOADED... Nu pretinde că cele 25 de acte au fost descărcate" — stale; that warning is now unreachable (source statuses are `ingested`; engine.py:869). Also README.md:19 documents the broken provision invocation (finding #1). Update both (S).
- **AGENTS.md §12 response examples** — no example matches actual output (extra `status`, duplicated keys, different `authority_class` values). If payloads are deduped (§2.1), update §12.1–12.3 examples once, minimally (S).
- **AGENTS.md §5/§441 "~25 acts"** — acceptable as plan text; corpus-audit.md is where the real number belongs. CONTEXT.md is explicitly historical — leave untouched.
- **data/manifest.json** — skeleton contradicts §22 (see §2.6).

## 5. Refactors worth doing (each scoped)

| # | Change | Effort | Risk |
|---|---|---|---|
| R1 | Article-level fallback in `get_provision` (finding #1) + regression tests | S | Low |
| R2 | Dedupe response payloads (matches/acts, results/hits, provision/provisions; fix IN_FORCE casing) | S | Low (tests + eval re-run) |
| R3 | Fix jurislatie typo + corpus-status counts from acts table; populate or drop manifest `last_build` | S | Low |
| R4 | Fold fetch_365 helpers into fetch_ro; delete download_via_soap.py (+ dead files in §3) after owner OK | S | Low |
| R5 | Split engine.py (1,048 lines) — only if touching it again anyway: pure citation grammar (lines 27–169) → `jurist/citations.py`; ingest path (create_schema/ingest_seed/ingest_snapshot/apply_tags, lines 244–417, 910–1036) → `jurist/ingest.py`; runtime engine stays ~600 lines. Justified: scripts/ingest_corpus.py:29 already imports engine internals, coupling build pipeline to runtime module. | M | Low-med (imports move; tests exercise via CLI) |
| R6 | Doc pass: corpus-audit.md, README status+example, AGENTS.md §12 examples, §8.9 tag inventory decision | S | Low |

Order: R1 → R2 → R3 (all behavior), then R6, then R4/R5 opportunistically. Re-run `pytest -q` + `eval_recall.py` after each.

## 6. Do NOT do (overengineering temptations)

- No PostgreSQL/Elasticsearch/vector DB or embeddings — corpus is 12MB, lexical retrieval evals at 1.0 (§33/§35).
- No MCP server wrapper yet — CLI is the contract; wrap later over the same code (§12).
- No schema rewrite toward §8.3's full column list (part/title_no/chapter/section...) — current provisions table serves retrieval; schema-apt is post-v1 RO/EU versioning, not column cosmetic.
- No point-in-time backfill for RO acts — current_only + NOT_VERIFIED_FOR_DATE is the designed honest behavior (§17); weekly snapshots accumulate forward.
- No micro-splitting engine.py beyond R5 (no services/repositories layers; 3 modules max).
- No rewriting AGENTS.md wholesale (87KB is heavy but it is the contract; do targeted §12/§8.9 edits only).
- Don't "fix" §5's "~25 acts" in AGENTS.md — it is the plan text; keep real counts in corpus-audit.md/SKILL.md table.
- Don't touch raw/ (immutable audit trail, §18/§21) or retrieval_log (validator depends on it, §25).
- Don't re-tag the 44 domains by hand now — decide the taxonomy on paper first (§2.3); mechanical re-tag only if the decision says so.
