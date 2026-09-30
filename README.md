# Jurist - Asistent juridic cu AI

> [!WARNING]
> **jurist nu înlocuiește un avocat sau un profesionist în domeniul juridic.** Este un instrument de cercetare și un punct de plecare: găsește și citează texte de lege, dar nu oferă consultanță juridică și nu garantează că un răspuns, un document sau o practică este legală ori conformă. Rezultatele trebuie verificate de un specialist înainte de orice decizie. **Folosirea se face pe propria răspundere.** Detalii în [Declinarea răspunderii](#declinarea-răspunderii).

Skill de cercetare juridică *grounded* pentru dreptul românesc și al Uniunii Europene, gândit pentru afaceri online: site-uri, SaaS, magazine online, platforme. Un agent AI (Claude Code sau orice agent care poate rula comenzi) întreabă un corpus local de legislație oficială prin CLI-ul `jurist`, în loc să citeze legea din memorie.

Principiul: **RETRIEVE → VERIFY → REASON → CITE**. Fiecare concluzie juridică trebuie să se sprijine pe un text de lege extras în sesiune, cu citare canonică, dată și statut verificate.

Ce **nu** este: nu e consultanță juridică, nu declară un document „conform” și nu acoperă fiscal, muncă, penal, CAEN/ONRC. Pentru ce e în afara corpusului, agentul marchează afirmația `out_of_corpus` și trimite la sursa oficială sau la un jurist.

## Ce conține corpusul

48 de acte (19 RO + 29 UE), ~11.300 de prevederi, 50 de relații UE↔RO, toate descărcate din surse oficiale:

| Domeniu | UE | România |
|---|---|---|
| Date personale, cookies | GDPR 2016/679, ePrivacy 2002/58, SCC 2021/914 și 2021/915, DPF UE–SUA 2023/1795 | Legea 190/2018, Legea 506/2004 |
| Comerț electronic, platforme | Directiva 2000/31, DSA 2022/2065, P2B 2019/1150, geoblocare 2018/302 | Legea 365/2002, Legea 50/2024 (aplicarea DSA, ANCOM) |
| Consumatori, contracte la distanță | CRD 2011/83 (consolidată 2026), UCPD 2005/29, Omnibus 2019/2161, 2024/825 (green claims), 2023/2673 (servicii financiare la distanță), prețuri 98/6, ADR 2013/11, abrogarea ODR 2024/3228 | OUG 34/2014, Legea 363/2007 (ambele cu modificările din OUG 18/2026), OG 21/1992, Legea 193/2000, OUG 58/2022, HG 947/2000, OG 38/2015 |
| Bunuri, conținut digital, garanții | Directivele 2019/770 și 2019/771 | OUG 140/2021, OUG 141/2021 |
| Produse | GPSR 2023/988, PLD 2024/2853 | — |
| Date, AI, securitate | Data Act 2023/2854, AI Act 2024/1689, NIS2 2022/2555 | OUG 155/2024 |
| Semnătură electronică, plăți | eIDAS 910/2014 (consolidat, include 2024/1183), PSD2 2015/2366 | Legea 214/2024, Legea 209/2019 |
| Dreptul comun al contractelor | — | Codul civil (Legea 287/2009), **parțial**: art. 1164–1762 (obligații, formarea și interpretarea contractului, clauze standard, forță majoră, daune, vânzare și vicii ascunse) și art. 2500–2544 (prescripția extinctivă) |
| Identificarea firmei | — | Legea 31/1990, **doar art. 74** (datele de identificare pe facturi, oferte, comenzi și pe site) |
| Contracte transfrontaliere | Roma I 593/2008, Bruxelles I bis 1215/2012 | — |
| Accesibilitate | Directiva 2019/882 | Legea 232/2022 |

Lista autoritară e `sources/corpus.yaml`; numerele live le dă `jurist corpus-status --json`. Ce lipsește și de ce: `sources/corpus-audit.md`.

## Instalare

### Cerințe

- Python **3.10+** și **PyYAML** (`python3 -m pip install --user 'PyYAML>=6.0'`);
- SQLite cu **FTS5** și `remove_diacritics 2` (SQLite ≥ 3.27; orice Python recent îl are). Scriptul de instalare verifică asta;
- rețea doar pentru actualizarea corpusului; interogările sunt 100% locale.

### Ca skill Claude Code (recomandat)

```bash
git clone git@github.com:dany547/jurist.git
cd jurist
./scripts/install_skill.sh
```

Scriptul:

1. verifică Python, PyYAML și FTS5;
2. copiază codul, `SKILL.md`, `AGENTS.md` și `sources/` în `~/.claude/skills/jurist` (prin `scripts/sync_skill.py`);
3. copiază baza `data/legal.db` (sync-ul nu copiază `data/` intenționat);
4. scrie launcher-ul `~/.local/bin/jurist`, care rulează `python3 -m jurist` din copia instalată;
5. rulează `jurist corpus-status --json` ca verificare.

Căi alternative: `JURIST_GLOBAL_SKILL=/alt/dir` și `JURIST_BIN_DIR=/alt/bin`. Dacă `~/.local/bin` nu e în `PATH`, scriptul te avertizează.

Claude Code încarcă automat skill-urile din `~/.claude/skills/`, deci după instalare skill-ul `jurist` apare în lista de skill-uri și se activează pe întrebări despre GDPR, cookies, e-commerce etc. (vezi `description` din `SKILL.md`). Se poate invoca și explicit cu `/jurist`.

Actualizarea unei instalări existente: `git pull && ./scripts/install_skill.sh`. Scriptul e idempotent.

### Instalare de către un agent AI

Pași neinteractivi, pentru un agent (Claude Code, Codex etc.) căruia i s-a cerut „instalează skill-ul jurist”. Execută-i în ordine și oprește-te la primul eșec.

```bash
# 1. codul (sau `git pull` dacă directorul există deja)
git clone https://github.com/dany547/jurist.git ~/src/jurist
cd ~/src/jurist

# 2. dependența Python, doar în user site (fără sudo)
python3 -c "import yaml" 2>/dev/null || python3 -m pip install --user 'PyYAML>=6.0'

# 3. instalarea propriu-zisă
./scripts/install_skill.sh

# 4. verificare (comenzi independente de directorul curent)
cd /tmp
jurist corpus-status --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['ok'] and d['counts']['acts'] >= 48, d; print('OK', d['counts'])"
JURIST_SESSION=install-check jurist provision --act GDPR --article 6 --paragraph 1 --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['ok'], d; print('OK', d['provision']['provision_id'])"
```

Instalarea e reușită dacă pasul 3 se termină cu `verificare: True {...}` și ambele comenzi din pasul 4 afișează `OK`.

Repository-ul e privat: clonarea cere acces la GitHub. Folosește `gh repo clone dany547/jurist ~/src/jurist` dacă `gh` e autentificat, sau URL-ul SSH `git@github.com:dany547/jurist.git`. Dacă nu ai acces, cere-l utilizatorului; nu căuta copii ale repository-ului în altă parte.

Reguli pentru agent:

- **Nu** folosi `sudo`, `pip install` fără `--user` sau `pip install .` fără `-e`.
- **Nu** rula `fetch_corpus.py` sau `ingest_corpus.py` la instalare. `data/legal.db` vine gata construit în repository; reconstruirea descarcă ~30 MB din surse oficiale și durează minute.
- **Nu** modifica fișiere din repository și nu copia manual în `~/.claude/skills/`. Totul trece prin `install_skill.sh`.
- Pentru alt agent decât Claude Code, setează directorul lui de skill-uri: `JURIST_GLOBAL_SKILL=<dir>/jurist ./scripts/install_skill.sh`. Apoi agentul trebuie să citească `SKILL.md` din acel director.
- La final, raportează utilizatorului ieșirea pașilor 3–4, fără să o parafrazezi.

| Eșec | Ce faci |
|---|---|
| `jurist: e nevoie de Python >= 3.10` | Oprește-te și spune-i utilizatorului; nu instala alt Python. |
| `lipsește PyYAML` după pasul 2 | `pip` nu e disponibil. Raportează; nu încerca `sudo apt`. |
| `SQLite ... fără FTS5` | Python-ul are un SQLite prea vechi. Raportează versiunea afișată. |
| `lipsește data/legal.db` | Clonare incompletă sau director greșit. Verifică `git status` și că ești în rădăcina repository-ului; nu reconstrui baza fără acordul utilizatorului. |
| `jurist: command not found` la pasul 4 | `~/.local/bin` nu e în `PATH`. Folosește `~/.local/bin/jurist` în pasul 4 și spune-i utilizatorului să adauge directorul în `PATH`. |
| `No module named jurist` | Launcher-ul nu găsește copia instalată. Rulează din nou pasul 3. |
| `database is locked` | Altă comandă `jurist`/ingest rulează. Așteaptă câteva secunde și reia o singură dată. |

### Doar CLI, pentru dezvoltare

```bash
cd jurist
python3 -m jurist corpus-status --json      # din rădăcina repo-ului
# sau, ca să ai comanda `jurist` în PATH:
python3 -m pip install --user -e .
```

Folosește **`-e`** (editable). Engine-ul caută baza la `<pachet>/../data/legal.db`, iar un `pip install .` obișnuit ar copia pachetul în `site-packages` fără `data/`.

## Cum funcționează

### La interogare (runtime)

```text
întrebare
  │
  ├─ Nivel 1: referință exactă   „art. 6 GDPR”, „Legea 506”, „RO:OUG:34:2014”
  │           → alias / citare canonică → provision direct, fără search
  │
  ├─ Nivel 2: rutare pe domenii  sources/routing_keywords.tsv
  │           „banner de cookies” → domeniul cookies
  │           (potrivire pe subșir, fără diacritice; câștigă fraza cea mai lungă)
  │
  ├─ Nivel 3: FTS5/BM25 limitat la prevederile/actele cu domeniile rutate,
  │           cu expansiune de leme din sources/lemmas_ro.tsv
  │
  └─ Fallback: NO_MATCH_ABOVE_THRESHOLD + rezumatele actelor candidate
```

Toate răspunsurile sunt JSON cu un plic comun: `ok`, `as_of`, `warnings[]`, `next_action`. Semnalele de siguranță sunt în date, nu doar în prompt, ca să funcționeze și cu modele mai slabe:

| Semnal | Înseamnă |
|---|---|
| `NOT_VERIFIED_FOR_DATE` | Actele RO sunt `current_only`: sursa oficială dă doar forma actuală. Pentru o dată trecută primești textul de azi, marcat ca neverificat pentru acea dată. |
| `DIRECTIVE_NOT_DIRECTLY_APPLICABLE` | Rezultat dintr-o directivă. Vine cu `transposed_by` (actul RO de transpunere). |
| `STALE_CORPUS` | Actul nu a fost reverificat de peste 30 de zile. |
| `NO_MATCH_ABOVE_THRESHOLD` | Nimic relevant. Agentul reformulează sau spune golul, nu completează din memorie. |
| `citable_as_binding_basis = 0` | Considerent sau preambul: nu susține singur o obligație. |

Actele UE sunt `point_in_time`: se descarcă o consolidare datată (ex. `02011L0083-20260927`). Consolidarea e text de lucru, nu Jurnalul Oficial autentic.

### Citări canonice

O singură gramatică, cu parser și formatter testate dus-întors:

```text
EU:REG:2016:679:ART:6:P:1:L:f   GDPR, art. 6 alin. (1) lit. f)
RO:LEGE:506:2004:ART:4:P:5      Legea 506/2004, art. 4 alin. (5)
RO:OUG:58:2022:ART:II           OUG 58/2022, art. II (act de modificare)
EU:REG:2016:679:REC:32          GDPR, considerentul 32 (neobligatoriu)
```

UE: `TIP:AN:NUMĂR`; RO: `TIP:NUMĂR:AN`, ca în identificatorii oficiali.

### Construirea corpusului (build)

```text
sources/corpus.yaml
   │  scripts/fetch_corpus.py
   ├─ RO: SOAP legislatie.just.ro (GetToken + Search, paginat, filtrat pe tip)
   │      → HTML-ul oficial consolidat de la LinkHtml → raw/ro/<TIP>_<NR>_<AN>.html
   └─ UE: Cellar (Publications Office), XHTML consolidat, cu content gate
          → ingest/eu/<CELEX>.html + raw/eu/ + ingest/eu/MANIFEST.json
   │  scripts/ingest_corpus.py --fresh
   ├─ parse_ro.py / parse_eu.py → articol / alineat / literă / considerent / anexă
   ├─ normalizare (NFC, ş/ţ cu sedilă → ș/ț cu virgulă)
   ├─ relations.tsv, tags.tsv, aliasuri, domenii
   └─ data/legal.db (SQLite + FTS5)
```

Reguli de proveniență: doar surse oficiale; textul SOAP `Text` (forma inițial publicată) nu e folosit niciodată ca text canonic; interfața de căutare a portalului nu e „scrapuită”; `raw/` e arhiva imuabilă de audit; fiecare versiune are URL, checksum SHA-256 și `retrieved_at`.

## Utilizare CLI

Cinci comenzi, toate cu `--json`:

```bash
# 1. rezolvă un nume informal
jurist resolve --reference "legea cookie-urilor" --json
#   → RO:LEGE:506:2004, status in_force, version_coverage current_only

# 2. căutare conceptuală (rutare + FTS)
jurist search --query "trebuie banner de cookies pe site" --json
#   → routed_domains [cookies]; RO:LEGE:506:2004:ART:4:P:5, EU:DIR:2002:58:ART:5:P:3
#     + DIRECTIVE_NOT_DIRECTLY_APPLICABLE, transposed_by Legea 506/2004

# 3. textul exact: articolul întreg sau un alineat/o literă
jurist provision --act GDPR --article 6 --context article --json
jurist provision --act RO:LEGE:506:2004 --article 4 --paragraph 5 --json
jurist provision --act RO:OUG:34:2014 --article 9 --as-of 2020-01-01 --json
#   → NOT_VERIFIED_FOR_DATE (actul RO e current_only)

# 4. relații: transpuneri, modificări, completări
jurist related --act-id EU:DIR:2024:825 --json
#   → transposed_by RO:LEGE:363:2007 și RO:OUG:34:2014 (prin OUG 18/2026)

# 5. ce conține corpusul și cât de proaspăt e
jurist corpus-status --json
```

Filtre utile pentru `search`: `--jurisdiction RO|EU`, `--domains cookies,pricing`, `--as-of AAAA-LL-ZZ`, `--limit N`. `--act` acceptă aliasuri („GDPR”, „Legea 214/2024”) sau ID canonic.

### Validatorul de citări

Fiecare prevedere returnată e scrisă în `retrieval_log`, grupată pe sesiune. Validatorul verifică un draft fără LLM:

```bash
export JURIST_SESSION=client-x-2026-09     # un id per sesiune de lucru
jurist provision --act GDPR --article 6 --paragraph 1 --json
python3 scripts/citation_validator.py draft.md --session "$JURIST_SESSION"
```

Coduri: `UNKNOWN_CITATION` (nu există în corpus), `CITED_WITHOUT_RETRIEVAL` (nu a fost extrasă în sesiune), `OUTDATED_PROVISION` (nu e în vigoare la data cerută). Fără `JURIST_SESSION`, totul intră în sesiunea `current`.

## Actualizarea corpusului

```bash
python3 scripts/fetch_corpus.py --dry-run          # ce s-ar descărca
python3 scripts/fetch_corpus.py                    # tot corpusul (sau --only ID1,ID2 / --jurisdiction RO)
python3 scripts/ingest_corpus.py --fresh           # reconstruiește data/legal.db
python3 -m pytest -q                               # 136 de teste
python3 scripts/eval_recall.py                     # 70 de întrebări, recall@10 trebuie ≥ 0.9
./scripts/install_skill.sh                         # publică în copia instalată
```

`fetch_corpus.py` raportează per act `fetched | unchanged | failed`. Un act nemodificat nu e rescris; la RO, checksum-ul ignoră tokenul volatil din pagina portalului.

### Adăugarea unui act

1. **`sources/corpus.yaml`**: intrare nouă după modelul celor existente (`id`, `title`, `jurisdiction`, `authority_class`, `version_coverage`, `aliases`, `domains`, `summary_ro`, `source`, `fetch`).
   - RO: `fetch: {method: soap, tip: LEGE|OUG|OG|HG, numar, an}`.
   - UE: `fetch: {method: cellar, celex: 3AAAATNNNN}` și, dacă există consolidări, `consolidated:` cu cea mai nouă în vigoare. O găsești cu `python3 scripts/fetch_corpus.py --list-consolidations 32011L0083`.
   - Act mare din care interesează doar o parte: `ingest_articles: ["1164-1762", "2500-2544"]` (intervale inclusive; `1203^1` intră ca 1203). Verifică limitele pe textul descărcat înainte de ingest.
   - Pentru actele foarte mari, portalul întoarce o pagină-cadru care încarcă forma consolidată din alt document; `fetch_corpus.py` urmează automat linkul `DetaliiDocumentAfis/<id>`.
2. **`sources/relations.tsv`**: relațiile în ambele sensuri (`transposed_by`/`transposes` etc.), cu dovada din textul oficial în coloana 4.
3. **`sources/tags.tsv`**: domenii pe articolele-cheie. **`sources/routing_keywords.tsv`**: fraze de utilizator → domenii. Potrivirea e pe subșir, deci folosește fraze specifice de 2+ cuvinte (un cuvânt scurt precum „rată” prinde și „declarată”).
4. **`tests/eval_questions_40.tsv`**: 1–3 întrebări formulate ca de utilizator, cu ID-urile corecte juridic. Nu ajusta ID-urile așteptate după ce returnează căutarea.
5. Fetch → ingest → teste → eval → `install_skill.sh`.

### Lansarea unei versiuni

Versionare semantică `MAJOR.MINOR.PATCH`. Versiunea curentă e în `pyproject.toml`, istoricul în `CHANGELOG.md`, iar fiecare versiune are un tag `vX.Y.Z` și un GitHub Release. Release-ul îl face CI-ul (`.github/workflows/ci.yml`).

1. Crește `version` în `pyproject.toml`: PATCH pentru corecturi și documentație, MINOR pentru acte noi sau funcții noi, MAJOR pentru schimbări incompatibile ale contractului CLI.
2. Adaugă în `CHANGELOG.md` o secțiune `## X.Y.Z — AAAA-LL-ZZ` cu ce s-a schimbat. Fără ea, CI-ul pică.
3. Local: testele, eval-ul și `./scripts/install_skill.sh`.
4. Commit și `git push` pe `main`. **Nu crea tag-ul manual.**

La fiecare push și pull request, CI-ul rulează testele pe Python 3.10 și 3.13, eval-ul (recall@10 ≥ 0.9) și verifică dacă există note în CHANGELOG pentru versiunea curentă. Pe `main`, dacă versiunea nu are încă un Release, creează tag-ul `vX.Y.Z` pe commit-ul testat și publică Release-ul cu notele din CHANGELOG (`scripts/release_info.py`). Un push fără schimbare de versiune nu publică nimic.

## Teste și calitate

| Verificare | Comandă | Prag |
|---|---|---|
| Teste unitare și de contract | `python3 -m pytest -q` | toate trec |
| Recall pe întrebări reale | `python3 scripts/eval_recall.py` | recall@10 ≥ 0.9 (acum 0.986) |
| Copia instalată e la zi | `python3 scripts/sync_skill.py --check` | exit 0 |

Testul `test_global_skill_copy_has_no_drift` pică dacă ai modificat repo-ul și n-ai rulat `install_skill.sh`.

## Structură

```text
SKILL.md                  instrucțiunile scurte încărcate de agent
AGENTS.md                 contractul complet de arhitectură (schema, CLI, reguli, etape A–I)
CHANGELOG.md
jurist/engine.py          schema SQLite, FTS5, rutare, cele 5 comenzi, validator
jurist/__main__.py        CLI
scripts/fetch_corpus.py   fetch din surse oficiale (singurul punct de intrare)
scripts/fetch_ro.py       client SOAP legislatie.just.ro (folosit de fetch_corpus)
scripts/parse_ro.py       parser HTML Portal Legislativ
scripts/parse_eu.py       parser XHTML EUR-Lex/Cellar
scripts/ingest_corpus.py  construiește data/legal.db
scripts/install_skill.sh  instalare ca skill Claude Code
sources/                  corpus.yaml, relații, taguri, rutare, leme, registry, audit
data/legal.db             baza gata construită
raw/, ingest/             arhiva oficială descărcată (audit, reproductibilitate)
tests/                    teste + setul de eval
docs/                     planuri și rapoartele de cercetare din 2026-09-29
```

## Depanare

| Simptom | Cauză și soluție |
|---|---|
| `No module named jurist` | Rulezi `python3 -m jurist` din alt director. Folosește launcher-ul `jurist` (instalat de `install_skill.sh`) sau rulează din rădăcina repo-ului. |
| `database is locked` | Un ingest rulează în paralel. Așteaptă să termine; nu rula două `ingest_corpus.py` simultan. |
| `fts5` / `no such tokenizer` | SQLite prea vechi. Folosește un Python ≥ 3.10 cu SQLite ≥ 3.27. |
| Fetch RO eșuează cu 403 | Portalul filtrează user-agent-ul; `fetch_ro.py` trimite unul de browser. Reîncearcă mai târziu; nu scrapui interfața de căutare. |
| EUR-Lex HTML dă 202/challenge | EUR-Lex e în spatele unui WAF. `fetch_corpus.py` folosește doar Cellar. |
| `NOT_VERIFIED_FOR_DATE` la o întrebare istorică RO | Comportament intenționat: sursa oficială nu oferă forme istorice. |
| `STALE_CORPUS` | Rulează ciclul de actualizare de mai sus. |

## Limite

- **RO `current_only`:** istoricul se acumulează doar de la prima descărcare; nu există forme istorice retroactive.
- **Doar legislație:** jurisprudența (CJUE, ReJust) și ghidurile (EDPB, ANSPDCP) sunt în roadmap, nu în v1.
- **Căutare lexicală, fără embeddings:** întrebările cu vocabular foarte diferit de lege depind de `routing_keywords.tsv` și `lemmas_ro.tsv`.
- **Rezumatele `summary_ro`** din `corpus.yaml` sunt marcate `draft_neconfirmat`.
- Pentru litigii, amenzi mari, breșe majore, AI cu risc ridicat, sănătate sau penal: research grounded, apoi avocat.

## Declinarea răspunderii

- **Nu este consultanță juridică.** jurist este un instrument de cercetare. Răspunsurile lui, și ale oricărui agent AI care îl folosește, nu reprezintă consultanță juridică și nu creează o relație avocat–client.
- **Nu înlocuiește un profesionist.** Aplicarea legii la o situație concretă depinde de fapte, de jurisprudență, de practica autorităților și de interpretări pe care acest instrument nu le acoperă. Pentru orice decizie cu efecte juridice, consultă un avocat sau un alt specialist calificat.
- **Este un punct de plecare.** Folosește-l ca să găsești textele de lege relevante și să îți pregătești întrebările pentru specialist, nu ca verdict final.
- **Fără garanții.** Corpusul poate fi incomplet sau neactualizat, parserele pot greși, iar un agent AI poate interpreta greșit un text corect. Textele consolidate sunt forme de lucru, nu publicațiile oficiale autentice (Monitorul Oficial, Jurnalul Oficial al UE). Nu există nicio garanție privind exactitatea, actualitatea sau caracterul complet al rezultatelor.
- **Documentele generate nu sunt „conforme” prin simplul fapt că au fost generate.** Termenii și condițiile, politicile de confidențialitate, contractele și celelalte texte redactate cu ajutorul acestui skill trebuie revizuite de un specialist înainte de publicare sau semnare.
- **Pe propria răspundere.** Folosind acest instrument, accepți că autorii și contribuitorii nu răspund pentru nicio pierdere, sancțiune sau prejudiciu rezultat din folosirea sau interpretarea rezultatelor.
