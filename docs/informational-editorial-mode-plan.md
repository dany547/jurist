# Plan: statut editorial și audit al percepției juridice

## Scop

Un agent care redactează sau revizuiește texte despre legi, formulare ori proceduri administrative trebuie să știe **când nu face cercetare juridică**. Astăzi skill-ul răspunde bine la întrebări juridice, dar rutarea către modurile ne-juridice depinde de memoria modelului, nu de un mecanism.

Obiectivul acestui plan este rutarea corectă, nu doctrina: un model slab, care citește doar `SKILL.md`, trebuie să ajungă în modul potrivit fără să rețină reguli.

Exemplu de lucru: instrucțiuni dintr-un website care explică ce documente se verifică, se completează sau se semnează într-un flux de modificare a obiectului de activitate al unei firme (coduri CAEN).

## Ce există deja și ce e nou

Livrat: `legal_verified`, `informational_editorial`, `source_factual` — `SKILL.md:16-30`, `AGENTS.md` Rule 11 (§14), §26 „Informational/editorial website copy", §27, §31, §37, `README.md:38`.

Nou în acest plan:

1. modul `legal_perception_audit`;
2. separarea sarcinii de statutul epistemic (două axe, nu o listă de patru moduri);
3. ieșirea **în afara corpusului**, care astăzi lipsește;
4. rutarea ca tabel decizional determinist, plasat sus în `SKILL.md`;
5. descoperirea skill-ului pentru texte din afara domeniilor de retrieval;
6. lexicul de semnale ca fișier de date, nu ca listă în proză;
7. teste de contract.

Bug de corectat pe drum: `SKILL.md:16` spune „Două moduri de lucru" și listează trei.

## Principiul arhitectural

`AGENTS.md` §30 (R3): siguranța se impune mecanic prin unelte, nu prin ce ține minte modelul. Modurile sunt deocamdată pur prompt-level — exact clasa de reguli despre care documentul spune că nu rezistă la modele slabe.

Aplicat aici, principiul cere trei lucruri:

- rutarea să fie un tabel cu o singură intrare pe rând, nu un paragraf de judecată;
- detecția semnalelor de percepție să pornească dintr-o listă scrisă de om, versionată, ca `sources/routing_keywords.tsv`;
- nivelul de risc să fie o funcție de constatări, nu o apreciere.

Ce rămâne inevitabil în sarcina modelului: testul de subiect al propoziției (§Semnale). Acolo mecanica dă recall, modelul dă precizie — aceeași împărțire ca la rutarea în trei niveluri din §13.

## Două axe

Confuzia din varianta anterioară: `legal_verified` / `informational_editorial` / `source_factual` descriu **statutul unei afirmații**, iar `legal_perception_audit` descrie **o sarcină**. Un audit produce el însuși un text informativ; nu sunt valori ale aceleiași variabile.

**Axa A — sarcina cerută:**

| Sarcină | Ce livrează agentul |
|---|---|
| `rewrite` | text rescris, în limitele textului primit |
| `describe_source` | ce arată o sursă oficială consultată |
| `answer_legal` | concluzie juridică cu retrieval și citări |
| `audit_perception` | listă de pasaje care pot fi citite ca îndrumare juridică |

**Axa B — statutul fiecărei afirmații din livrabil:**

| Statut | Înseamnă |
|---|---|
| `verified` | retrieval efectuat, citare canonică, dată și statut verificate |
| `source_reported` | apare într-o sursă oficială identificată; fără concluzie despre efect |
| `editorial` | provine din textul furnizat; neverificat independent |
| `out_of_corpus` | afirmație juridică pe care corpusul local nu o poate acoperi |
| `unverified` | nesusținută de nimic; se marchează sau se scoate |

Beneficiul practic: **cererea mixtă încetează să fie caz special.** Regula generală devine „fiecare afirmație materială poartă un statut", iar cererea mixtă e doar un livrabil cu statute amestecate. Dispare regula „separă rezultatele", care cerea modelului să decidă unde e granița.

## Ieșirea `out_of_corpus`

Golul cel mai mare al variantei anterioare. Corpusul acoperă GDPR, cookies, e-commerce, contracte la distanță, clauze abuzive — RO+UE. Înființarea și modificarea firmelor, CAEN, ONRC, hotărârile AGA nu sunt în corpus, iar `SKILL.md` interzice explicit ieșirea din scop.

Prin urmare, pe exemplul CAEN, „escaladează la `legal_verified`" e o instrucțiune neexecutabilă: `search` ar returna `NO_MATCH_ABOVE_THRESHOLD`, iar agentul ar rămâne cu ispita de a completa din memorie — exact eșecul pe care skill-ul îl previne în rest.

Regula corectă:

1. auditul semnalează pasajul indiferent de domeniu — analiza de formulare nu depinde de corpus;
2. înainte de a promite verificare, agentul rulează `jurist corpus-status --json` sau constată din domeniu că materia e în afara scopului;
3. dacă e în afara scopului, statutul afirmației e `out_of_corpus`, iar recomandarea e sursa oficială externă ori un jurist — **nu** un mod al acestui skill;
4. agentul nu spune niciodată „urmează să verific" pentru o materie pe care corpusul nu o conține.

## Descoperirea skill-ului

Problemă de rutare care precedă toate celelalte: `description` din frontmatter enumeră doar domeniile de retrieval. Un agent care primește „rescrie textul ăsta despre CAEN ca să nu sune a sfat juridic" **nu va încărca skill-ul**, deci niciun mod nu contează.

Asimetrie de reținut: retrieval-ul e legat de domeniu, auditul de percepție e lingvistic și deci independent de domeniu.

Modificare în `description`: se adaugă că auditul percepției juridice și rescrierea editorială se aplică oricărui text juridic-administrativ în română, în timp ce cercetarea cu citări rămâne limitată la domeniile din corpus. Formularea „nu folosi pentru fiscal, muncă, penal" se recalifică: nu folosi **pentru afirmații verificate**, nu „nu folosi deloc".

## Rutare

Tabel decizional, prima potrivire câștigă. Locul lui e imediat sub titlu în `SKILL.md`.

| Intrare | Sarcină | Statut implicit |
|---|---|---|
| text furnizat + „rescrie / formatează / simplifică" | `rewrite` | `editorial` |
| „poate fi perceput ca sfat juridic?", „sună a consultanță?" | `audit_perception` | analiza nu produce statut juridic |
| „ce scrie în formular / pe pagina autorității?" | `describe_source` | `source_reported` |
| „este obligatoriu / legal / conform / se aplică?" | `answer_legal` | `verified` sau `out_of_corpus` |
| text furnizat **fără** verb de sarcină | se întreabă | — |
| cerere cu mai multe verbe | fiecare parte pe rândul ei; statut per afirmație | — |

Regula de ambiguitate rămâne, dar se restrânge la un caz: text prezent, sarcină neexprimată. Atunci agentul întreabă dacă se dorește rescriere editorială sau verificare juridică. Nu completează din memoria modelului.

Precedență, când semnalele se bat: `answer_legal` > `audit_perception` > `describe_source` > `rewrite`. O cerere de rescriere care conține și o întrebare despre obligativitate nu e o rescriere.

## Semnale de percepție juridică

### Testul primar: subiectul

Un imperativ nu e prin el însuși îndrumare juridică. Semnalul e produsul dintre o marcă deontică și subiectul propoziției:

| Subiect | Citire implicită |
|---|---|
| aplicația / fluxul / ecranul | descriere de produs — fără semnal |
| legea / autoritatea / actul normativ | afirmație juridică — semnal |
| utilizatorul ca subiect de drept, în situația lui concretă | afirmație de aplicabilitate — semnal, prioritate maximă |

Contrastele care trebuie să apară chiar lângă lexic, nu în altă secțiune:

- „Verifică documentul afișat" — produs, fără semnal.
- „Legea impune verificarea documentului" — juridic, semnal.
- „Aplicația generează documentul pe baza datelor introduse" — produs, fără semnal.
- „Documentul este obligatoriu pentru situația ta" — aplicabilitate, semnal prioritar.

### Categorii

| Categorie | Exemple |
|---|---|
| `obligatie` | „trebuie", „este obligatoriu", „se impune", „nu poți fără" |
| `semnatar` | „se semnează de asociatul unic", „valabil numai dacă e semnat de toți" |
| `aprobare` | „necesită avizul...", „se cere autorizația..." |
| `scutire` | „nu ai nevoie de...", „nu se aplică în cazul tău" |
| `efect_juridic` | „depunerea produce efectul...", „după depunere ești autorizat" |
| `conformitate` | „astfel vei fi conform", „procedura este completă legal" |
| `exhaustivitate` | „acestea sunt documentele necesare", orice listă prezentată ca închisă |
| `termen_cuantum` | „în 15 zile", „taxa este X lei" |
| `sanctiune` | „riști amendă de...", „actul poate fi anulat" |

Ultimele trei sunt adăugate față de varianta anterioară. `exhaustivitate` este, pe exemplul CAEN, categoria cea mai riscantă: o listă închisă e o afirmație juridică deghizată în interfață. `scutire` se desprinde din `aprobare` — afirmația negativă e mai periculoasă decât cea pozitivă, fiindcă nimeni nu o verifică. `termen_cuantum` prinde cifrele copiate dintr-o sursă neverificată.

### Fișier de date

`sources/perception_signals.tsv`, în formatul lui `routing_keywords.tsv`: marcă sau tipar → categorie, comentarii cu `#`, potrivire cu diacriticele pliate (§9). Scris de om, versionat, revizuit când testele arată goluri. Rolul lui e recall; precizia rămâne la testul de subiect.

### Limita auditului

Semnalarea se face **după forma lingvistică, nu după suspiciunea de incorectitudine**. Auditul nu spune niciodată „probabil e greșit" și nu clasifică o afirmație drept riscantă pentru că pare falsă. Altfel modul redevine, pe ușa din dos, o judecată de fond fără retrieval.

## Nivelul de risc

Derivat, nu apreciat:

- **ridicat** — apare `efect_juridic`, `conformitate`, `sanctiune`, sau orice afirmație cu subiect „utilizatorul în situația lui concretă";
- **mediu** — apare `obligatie`, `semnatar`, `aprobare`, `scutire`, `exhaustivitate` sau `termen_cuantum`, fără niciuna de mai sus;
- **scăzut** — nicio constatare; textul descrie funcții sau pași ai aplicației.

Devine reproductibil între rulări și verificabil într-un test.

## Formatul rezultatului pentru audit

```text
Mod: audit_perception
Verificare juridică: nu a fost efectuată
Risc de percepție ca îndrumare juridică: scăzut / mediu / ridicat  (derivat din constatări)

Pasaje de revizuit:
- „...citatul exact..."
  Categorie: obligatie | semnatar | aprobare | scutire | efect_juridic |
             conformitate | exhaustivitate | termen_cuantum | sanctiune
  Subiect: aplicație | lege/autoritate | utilizator
  Motiv: forma afirmației, nu conținutul ei
  Sugestie editorială: ...

Afirmații care nu pot fi verificate din acest corpus:
- „...": materie în afara scopului (statut out_of_corpus) → sursă oficială externă sau jurist
```

Ultima secțiune înlocuiește „afirmații care necesită verificare juridică separată", care sugera că verificarea urmează să se întâmple aici.

## Reguli pentru rescriere

Preferă:

- „documentul este precompletat pe baza datelor introduse";
- „verifică informațiile afișate";
- „aplicația include în listă...";
- „textul prezintă pașii din flux";
- „pentru clarificări, consultă sursa oficială relevantă".

Evită, fără verificare: „legea obligă...", „este obligatoriu...", „se semnează de...", „nu ai nevoie de...", „documentul este suficient pentru...", „vei fi conform dacă...".

### Citări preexistente în textul primit

Caz nedecis anterior, și cel mai probabil în practică: textul furnizat conține deja o trimitere („conform art. 5 GDPR"). Regula: **se păstrează verbatim, se semnalează, nu se verifică necerut și nu se corectează tacit.** O corectură tăcută transformă rescrierea în validare juridică; o verificare necerută încalcă modul.

### Convenția de placeholder

„Folosește placeholder" nu e implementabil. Forma fixă, greppabilă:

```
[de verificat: <ce anume>]
```

Placeholder-ul supraviețuiește în livrabil. Agentul nu îl rezolvă din memorie și nu îl scoate în tăcere. Testabil prin căutarea șirului în ieșire.

### Nota de statut

Se livrează separat de copy, niciodată injectată automat în website:

> Statut: text informativ/editorial. Nu reprezintă consultanță juridică și nu confirmă exhaustiv actualitatea, aplicabilitatea, efectul juridic sau conformitatea pentru un caz concret.

## Aplicare pe exemplul CAEN

Pentru textul despre declarație, hotărârea AGA și actul constitutiv:

1. skill-ul trebuie mai întâi să fie *ales* — vezi §Descoperirea skill-ului; fără asta, restul nu se întâmplă;
2. sarcina e `audit_perception`, eventual urmată de `rewrite`;
3. „necesită verificare și semnare" → `obligatie`, subiect ambiguu, se semnalează;
4. afirmația despre cine semnează → `semnatar`;
5. afirmația despre avize → `aprobare`;
6. instrucțiunea privind codurile neautorizate din certificatul constatator → `efect_juridic`;
7. lista de documente, dacă e prezentată ca suficientă → `exhaustivitate`;
8. risc derivat: **ridicat**, din pasajul 6 — nu „mediu" prin apreciere;
9. rescrierea reformulează totul ca instrucțiuni ale aplicației;
10. agentul **nu** decide dacă instrucțiunile CAEN sau de semnare sunt corecte juridic;
11. materia fiind în afara corpusului, afirmațiile primesc `out_of_corpus`, nu promisiunea unei verificări ulterioare.

## Etape

### Etapa 1 — rutare vizibilă pentru model

`SKILL.md`: tabelul decizional imediat sub titlu; cele două axe; corectarea titlului „Două moduri"; adăugarea `audit_perception` și `out_of_corpus`. Ținta e ca rutarea să încapă într-un ecran — e singurul document încărcat la runtime.

`SKILL.md` frontmatter: `description` extinsă cu domeniul de aplicare al modurilor ne-juridice.

Gate: `SKILL.md` rămâne sub ~120 de rânduri, iar tabelul de rutare are exact o intrare pe rând.

### Etapa 2 — reguli executabile

`AGENTS.md`: Rule 11 se rescrie pe cele două axe; se adaugă Rule 12 (audit de percepție, cu limita „formă, nu fond") și Rule 13 (`out_of_corpus`). §27 primește formatul de audit. §31 primește trei interdicții noi: să prezinte auditul ca verificare; să promită retrieval pentru materie din afara corpusului; să corecteze tacit o citare dintr-un text primit spre rescriere.

`README.md`: o frază despre auditul de percepție.

`CONTEXT.md` rămâne neatins — artefact istoric.

### Etapa 3 — date și exemple

`sources/perception_signals.tsv`. Exemple, câte unul pentru: rescriere pură; audit; descrierea unui formular; întrebare juridică în corpus; întrebare juridică în afara corpusului; cerere mixtă.

Gate: fiecare exemplu declară sarcina și statutul per afirmație.

### Etapa 4 — sincronizarea copiei globale

Varianta anterioară cerea „actualizează copia globală" fără mecanism — exact așa divergează cele două copii. Se adaugă `scripts/sync_skill.py` sau o verificare de egalitate care pică în teste.

### Etapa 5 (opțional) — scanner determinist

`scripts/perception_scan.py --json`: primește text, întoarce spanuri candidate cu categoria din TSV. **Nu** e a șasea subcomandă `jurist`; contractul de cinci unelte rămâne intact. Modelul aplică testul de subiect peste candidați.

Se face doar dacă Etapa 3 arată că modelele slabe scapă pasaje. Beneficiu: recall determinist. Cost: încă un artefact de întreținut.

## Teste

În `tests/test_contract.py`, mecanice:

1. `jurist` expune exact cinci subcomenzi.
2. `SKILL.md` conține tabelul de rutare și toate cele patru sarcini.
3. `description` din frontmatter menționează aplicabilitatea ne-juridică.
4. Fiecare categorie din `perception_signals.tsv` apare în `AGENTS.md`.
5. Nivelul de risc e derivabil: pentru un set fix de constatări, funcția dă un singur rezultat.
6. Copia globală a skill-ului e identică cu cea din repo.

Manual sau prin eval, pe fixturi:

7. „Rescrie acest text pentru website" nu declanșează retrieval.
8. „Poate fi perceput ca sfat juridic?" produce audit de formulare, nu verdict juridic.
9. „Este obligatoriu să semneze toți asociații?" duce la `answer_legal` și, pentru CAEN, la `out_of_corpus` — nu la o concluzie din memorie.
10. Descrierea unui formular nu afirmă obligativitatea sau efectul.
11. Un disclaimer nu justifică o afirmație inventată.
12. Nota de statut nu intră în copy-ul public.
13. O citare preexistentă supraviețuiește verbatim într-o rescriere.

Testul 9 e cel nou și cel mai important: e singurul care prinde regresia „completează din memorie când corpusul tace".

## Decizie

Se adaugă `audit_perception` ca sarcină și `out_of_corpus` ca statut, peste cele două axe. Contractul de cinci unelte CLI rămâne neschimbat: schimbarea ține de rutare, statut epistemic și politică de redactare.

Diferența față de varianta anterioară a planului: rutarea nu mai e lăsată în seama judecății modelului, iar auditul nu mai promite o verificare pe care corpusul nu o poate onora.

## Rămas deschis

- Etapa 5 se face sau nu — depinde de ce arată Etapa 3.
- Dacă `description` se lărgește prea mult, skill-ul va fi încărcat pentru texte care nu au nimic juridic. Merită măsurat după prima săptămână.
