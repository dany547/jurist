---
name: jurist
description: >
  Cercetare juridică grounded pentru dreptul românesc și UE, din corpusul
  local (CLI `jurist --json`). Auditul percepției juridice și rescrierea
  editorială se aplică oricărui text juridic-administrativ în română;
  cercetarea cu citări acoperă corpusul local: GDPR/cookies, e-commerce,
  contracte la distanță, clauze abuzive, semnătură electronică, plăți,
  siguranța și răspunderea pentru produse, green claims, Data Act,
  transparența AI Act, lege aplicabilă/competență în T&C, transferuri
  SCC/DPF, DSA cu aplicarea RO (ANCOM) și NIS2 — RO+UE. Nu folosi pentru
  afirmații verificate în materii fiscale, de muncă sau penale.
  Nu inventa articole, date sau citate.
---

# jurist

| Intrare | Sarcină | Statut implicit |
|---|---|---|
| text furnizat + „rescrie / formatează / simplifică” | `rewrite` | `editorial` |
| „poate fi perceput ca sfat juridic?”, „sună a consultanță?” | `audit_perception` | analiza nu produce statut juridic |
| „ce scrie în formular / pe pagina autorității?” | `describe_source` | `source_reported` |
| „este obligatoriu / legal / conform / se aplică?” | `answer_legal` | `verified` sau `out_of_corpus` |
| text furnizat **fără** verb de sarcină | se întreabă | — |
| cerere cu mai multe verbe | fiecare parte pe rândul ei; statut per afirmație | — |

**Rutare:** prima potrivire câștigă. Precedență: `answer_legal` > `audit_perception` > `describe_source` > `rewrite`.

**RETRIEVE → VERIFY → REASON → CITE**

## Două axe

Sarcina și statutul epistemic sunt variabile separate; o cerere mixtă poate avea statute amestecate.

### Axa A — sarcina cerută

| Sarcină | Ce livrează agentul |
|---|---|
| `rewrite` | text rescris, în limitele textului primit |
| `describe_source` | ce arată o sursă oficială consultată |
| `answer_legal` | concluzie juridică cu retrieval și citări |
| `audit_perception` | listă de pasaje care pot fi citite ca îndrumare juridică |

### Axa B — statutul fiecărei afirmații din livrabil

| Statut | Înseamnă |
|---|---|
| `verified` | retrieval efectuat, citare canonică, dată și statut verificate |
| `source_reported` | apare într-o sursă oficială identificată; fără concluzie despre efect |
| `editorial` | provine din textul furnizat; neverificat independent |
| `out_of_corpus` | afirmație juridică pe care corpusul local nu o poate acoperi |
| `unverified` | nesusținută de nimic; se marchează sau se scoate |

Etichetele vechi se mapează astfel: `legal_verified` = `answer_legal` + `verified`, `informational_editorial` = `rewrite` + `editorial`, `source_factual` = `describe_source` + `source_reported`.

## Ieșirea `out_of_corpus`

Corpusul acoperă RO+UE: GDPR și date personale, cookies, e-commerce, contracte la distanță, clauze abuzive, semnătură electronică, plăți, siguranța și răspunderea pentru produse, green claims, Data Act, transparență AI Act, lege aplicabilă/competență în T&C, transferuri internaționale (SCC/DPF), DSA cu aplicarea RO (Legea 50/2024, ANCOM) și NIS2. Auditul și rescrierea se aplică indiferent de domeniu, dar pentru CAEN, ONRC, înființare firmă sau materii fiscale, de muncă ori penale:

- nu promite verificare și nu spune „urmează să verific”; înaintea unei promisiuni, rulează `jurist corpus-status --json`;
- marchează afirmația `out_of_corpus` și trimite la sursa oficială externă sau la un jurist — nu la un mod al acestui skill.

## Când îl folosești

Privacy, cookies, e-commerce, contracte la distanță, clauze abuzive, semnătură electronică, plăți, siguranța și răspunderea pentru produse, green claims, Data Act, transparență AI Act, T&C (lege aplicabilă/competență), transferuri SCC/DPF, DSA/ANCOM, NIS2 — RO+UE. Pentru o întrebare din afara corpusului, `jurist corpus-status --json`; nu completa din memorie.

## Procedură

1. Jurisdicție (RO / UE / ambele), data relevantă, B2B sau B2C dacă contează.
2. Referință cunoscută („art. 6 GDPR”, „Legea 506”) → `resolve` apoi `provision`. Fără `search`.
3. Întrebare conceptuală → `search --corpus legislation`. Citește `routed_domains` și `warnings`.
4. Ia textul exact: `provision --context article`. Nu încheia din snippet.
5. La o directivă UE, `related --relations transposed_by`. Nu trata directiva ca lege română.
6. Citează numai `canonical_citation` / `source_url` din răspunsurile din sesiunea asta — logul de retrieval e grupat pe `JURIST_SESSION`, iar validatorul de citări verifică contra lui.

`next_action` se urmează doar dacă e complet (are act **și** articol). Dacă e `null`, decizi tu următorul apel.

## Semnale — nu le ignora

| Semnal | Ce faci |
|---|---|
| `NOT_VERIFIED_FOR_DATE` | RO e `current_only`. Textul de azi nu e forma de la `as_of`. Spune-o. |
| `DIRECTIVE_NOT_DIRECTLY_APPLICABLE` | Directivă: transpunerea RO, nu textul UE ca obligație privată. |
| `STALE_CORPUS` | Nu pretinde prospețime. |
| `NO_MATCH_ABOVE_THRESHOLD` | Reformulează sau spune golul. Nu încheia din `summary_ro`. |
| `citable_as_binding_basis = 0` | Considerent / preambul: nu e singura bază a unei obligații. |

## Exemplu

Întrebare: „trebuie banner de cookies pe site?”

```bash
jurist search --query "trebuie banner de cookies pe site" --corpus legislation --json
jurist provision --act RO:LEGE:506:2004 --article 4 --paragraph 5 --context article --json
jurist related --act-id EU:DIR:2002:58 --relations transposed_by --json
```

Răspunsul citează 506/2004 art. 4 alin. (5) și semnalează că 2002/58 nu e direct aplicabilă. Nu inventa „banner obligatoriu” dacă textul vorbește de stocare pe echipamentul terminal și de consimțământ.

## Contract CLI (exact 5)

| Tool | Invocare |
|---|---|
| resolve | `jurist resolve --reference "legea cookie-urilor" --json` |
| search | `jurist search --query "drept de retragere" --corpus legislation --json` |
| provision | `jurist provision --act RO:OUG:34:2014 --article 9 --as-of 2025-01-01 --json` |
| related | `jurist related --act-id EU:DIR:2002:58 --relations transposed_by --json` |
| corpus-status | `jurist corpus-status --json` |

Fiecare răspuns are `ok`, `as_of`, `warnings[]`, `next_action`. Search-ul e lexical: citare exactă → alias → domeniu → FTS5. `corpus-status` spune ce e descărcat; nu ține minte un tabel de acte.

## Răspuns

Concluzie scurtă. Legea aplicabilă, cu citare la articol/alineat. Efect practic. Excepții și fapte lipsă. Ce urmează. Surse: citarea canonică + `source_url` din tool.

## Redactare (T&C, privacy, cookies, DPA)

Fapte cunoscute, apoi goluri, apoi retrieval, apoi text. Nu inventa: denumire, sediu, CUI, TVA, scopuri, temeiuri, durate, subprocessori, transferuri, plăți, retur, DPO, contact. Placeholder explicit. Nu declara documentul „conform”.

## Limite

Nu e avocat. Litigiu, amendă serioasă, breșă majoră, AI cu risc ridicat, sănătate, penal: research grounded, apoi avocat. Considerentele nu țin o pretenție obligatorie. Textul UE consolidat e ajutor de lucru, nu JO autentic.
