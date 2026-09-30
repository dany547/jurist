# Audit corpus v1

## Rezumat

`corpus.yaml` este sursa unică de adevăr pentru **48 de acte UE/RO (19 România + 29 UE)** din zona privacy, comerț electronic, protecția consumatorului, plăți, semnătură electronică, produse și servicii digitale. `registry.json` definește sursele oficiale și metodele de rezolvare. Actele sunt descărcate din sursele oficiale prin `scripts/fetch_corpus.py` (SOAP Portal Legislativ + LinkHtml; Cellar/EUR-Lex) și ingerate în `data/legal.db` prin `scripts/ingest_corpus.py`; proveniența fiecărei manifestări (URL oficial, checksum, `retrieved_at`) stă pe `act_versions`, iar numerele live le randează `jurist corpus-status --json`. Relațiile EU↔RO (transpunere, completare, modificare) sunt în `sources/relations.tsv` — 50 de rânduri, fiecare cu dovada din textul oficial.

Extinderea din 2026-09-29 (28 → 48 acte) a pornit de la o cercetare pe surse oficiale (notice-uri Cellar, texte integrale, SOAP Portal Legislativ, OEIL); dovada fiecărei relații e în coloana 4 din `sources/relations.tsv`.

## Acoperire

| Domeniu | Acte în corpus |
|---|---|
| Privacy, date personale, cookie-uri și comunicații | GDPR 2016/679; Directiva 2002/58/CE; Legea 190/2018; Legea 506/2004 |
| Comerț electronic, platforme și servicii online | Directiva 2000/31/CE; Legea 365/2002; Regulamentul 2019/1150 (P2B); DSA 2022/2065 + Legea 50/2024 (aplicare RO, ANCOM) |
| Contracte la distanță și retragere | Directiva 2011/83/UE; OUG 34/2014; Directiva 2023/2673 (servicii financiare la distanță); Directiva 2024/825 (EmpCo) |
| Practici comerciale, publicitate, green claims și prețuri | Directiva 2005/29/CE; Directiva 98/6/CE + HG 947/2000; Directiva 2019/2161; Legea 363/2007; OUG 58/2022; Regulamentul 2018/302 (geoblocare) |
| Bunuri, conținut și servicii digitale | Directivele 2019/771 și 2019/770 + OUG 140/2021 și OUG 141/2021; Data Act 2023/2854; AI Act 2024/1689 (transparență, art. 50) |
| Produse: siguranță, răspundere, accesibilitate | Regulamentul 2023/988 (GPSR); Directiva 2024/2853 (PLD); Directiva 2019/882 + Legea 232/2022 |
| Plăți | PSD2 2015/2366; Legea 209/2019 |
| Semnătură electronică și identitate digitală | eIDAS 910/2014; Legea 214/2024 |
| Transferuri internaționale de date | Decizia 2021/914 (SCC); Decizia 2021/915 (SCC procesor→procesor); Decizia 2023/1795 (DPF UE–SUA) |
| Litigii și protecție generală | Directiva 2013/11/UE + OG 38/2015 (SAL); Regulamentul 2024/3228 (abrogarea ODR); OG 21/1992; Legea 193/2000 |
| Securitate cibernetică | NIS2 2022/2555; OUG 155/2024 |
| Lege aplicabilă și competență (clauze din T&C) | Roma I 593/2008; Bruxelles I bis (recast) 1215/2012 |
| Dreptul comun al contractelor și identificarea firmei | Codul civil — Legea 287/2009, **parțial** (`ingest_articles`: art. 1164–1762 și 2500–2544); Legea 31/1990 — **doar art. 74** |

Numărul de acte: **29 UE + 19 România = 48** (Codul civil și Legea 31/1990 ingerate parțial, prin `ingest_articles`). Fiecare intrare are `id`, `fetch`, `authority_class`, `version_coverage`, `domains`, `aliases`, `summary_ro`, identificator oficial și link de sursă; `scope_provisions` este prezent unde delimitarea este utilă.

## Candidați verificați și decizie

Deciziile listei inițiale sunt explicite în `candidate_decisions`; pentru actele adăugate la 2026-09-29, sursa oficială e în `source.links` din `corpus.yaml`, iar relațiile au dovada în `relations.tsv`.

- **Legea 363/2007 — include.** Actul național relevant pentru practici comerciale incorecte; link Portal Legislativ: <https://legislatie.just.ro/Public/DetaliiDocument/88290>. Reper UE: <https://eur-lex.europa.eu/eli/dir/2005/29/oj>.
- **Directiva (UE) 2019/770 — include.** Reper UE pentru conținut/servicii digitale; transpunerea română este OUG 141/2021: <https://eur-lex.europa.eu/eli/dir/2019/770/oj>, <https://legislatie.just.ro/Public/DetaliiDocument/250054>.
- **Directiva (UE) 2019/771 — include.** Reper UE pentru vânzarea de bunuri; transpunerea română este OUG 140/2021: <https://eur-lex.europa.eu/eli/dir/2019/771/oj>, <https://legislatie.just.ro/Public/DetaliiDocument/250044>.
- **Regulamentul (UE) 2018/302 — include.** Direct aplicabil și specific pentru geoblocarea din comerțul online: <https://eur-lex.europa.eu/eli/reg/2018/302/oj>.
- **Regulamentul (UE) nr. 910/2014 — include.** Direct aplicabil pentru identificare și servicii de încredere: <https://eur-lex.europa.eu/eli/reg/2014/910/oj>. Amendamentul 2024/1183 este roadmap (vezi mai jos).
- **Directiva 2002/58/CE — include, ambele niveluri.** Reperul UE și transpunerea operațională (Legea 506/2004) sunt indexate împreună, cu relația de transpunere: <https://eur-lex.europa.eu/eli/dir/2002/58/oj>, <https://legislatie.just.ro/Public/DetaliiDocument/56973>.

## Omisiuni / roadmap

- **OUG 18/2026** (transpunerea RO pentru Directivele 2024/825 și 2023/2673; în vigoare 26.03.2026, DetaliiDocument/308474) este identificată prin research, dar neingestrată. Până la ingest, Legea 363/2007 și OUG 34/2014 din corpus răspund pe textul pre-modificare; regulile noi se aplică de la 27.09.2026 (2024/825), respectiv 19.06.2026 (2023/2673). Prioritar.
- **eIDAS 2.0 (Regulamentul (UE) 2024/1183)** este roadmap, nu duplicat al eIDAS în v1; corpusul păstrează 910/2014 ca identificator de bază (amendat din 20.05.2024). Stratul RO (Legea 214/2024) este deja în corpus: <https://eur-lex.europa.eu/eli/reg/2024/1183/oj>.
- **Right to Repair (Directiva (UE) 2024/1799)** — în afara corpusului; transpunerea RO **negăsită** prin SOAP (termenul de transpunere, 31.07.2026, a trecut); amendă Directiva 2019/771 din 30.07.2024. Watchlist până apare transpunerea: <https://eur-lex.europa.eu/eli/dir/2024/1799/oj>.
- **PLD (Directiva (UE) 2024/2853)** este în corpus; transpunerea RO **negăsită** (SOAP). Termenul de transpunere este 09.12.2026, când abrogă Directiva 85/374; Legea 240/2004 (transpunerea veche, în afara corpusului) intră atunci în sunset.
- **CCD2 (Directiva (UE) 2023/2225, credit de consum)** — P2; acoperă BNPL; aplicabilă 20.11.2026; transpunere RO negăsită: <https://eur-lex.europa.eu/eli/dir/2023/2225/oj>.
- **Cyber Resilience Act (Regulamentul (UE) 2024/2847)** — P2; raportarea vulnerabilităților din 11.09.2026, obligațiile principale din 11.12.2027: <https://eur-lex.europa.eu/eli/reg/2024/2847/oj>.
- **Watchlist (neadoptate sau fără act identificabil oficial, starea 2026-09-29):** Digital Omnibus on data — propunerea 52025PC0837 (GDPR nu are niciun act amendator adoptat); Green Claims — COM(2023) 280, în procedură; PSD3/PSR — propuneri neadoptate; Digital Fairness Act — niciun act identificabil oficial. Jurisprudența, ghidurile administrative (ANSPDCP/ANPC) și embeddings rămân excluse din v1.
- **Propunerea de regulament ePrivacy** nu este act normativ adoptat; statutul exact de retragere rămâne neverificat oficial (52017PC0010). Directiva 2002/58 + Legea 506/2004 rămân baza.

## Observații de integritate

1. URL-urile canonice pentru acte UE sunt ELI EUR-Lex; identificatorii CELEX sunt în YAML. Pentru acte românești se folosește Portalul Legislativ (SOAP pentru descoperire și metadate; HTML-ul oficial `LinkHtml` ca text canonic).
2. Nu se folosesc agregatoare drept `source` sau `fetch`. Registry-ul le marchează explicit necanonice/disabled.
3. Starea de fetch este proveniență pe `act_versions` în `data/legal.db` (`source_url`, checksum SHA-256, `retrieved_at`), nu în registry; `sources/corpus.yaml` păstrează `retrieval_status` doar ca metadat de registru. `jurist corpus-status --json` randează starea reală.
4. Pentru modificări ulterioare: se actualizează mai întâi `corpus.yaml`, apoi `python3 scripts/fetch_corpus.py`, `python3 scripts/ingest_corpus.py --fresh`, `python3 -m pytest -q` și `python3 scripts/eval_recall.py`.
