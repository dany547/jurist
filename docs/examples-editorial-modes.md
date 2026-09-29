# Exemple pentru modurile editoriale și statutul afirmațiilor

Aceste exemple separă sarcina rutată de statutul epistemic al afirmațiilor. Statutul se aplică fiecărei afirmații materiale, nu întregului răspuns.

## Exemplul 1 — rescriere pură

**Cererea utilizatorului:** „Rescrie pentru website: «Aplicația verifică datele introduse și afișează documentele relevante.»”

**Sarcina rutată:** `rewrite`

**Statut per afirmație:**

- „Aplicația verifică datele introduse și afișează documentele relevante.” — `editorial` (text furnizat de utilizator; nu a fost verificat juridic).

**Răspunsul așteptat pe scurt:** „Aplicația verifică datele introduse și îți afișează documentele relevante.” Se păstrează sensul primit, fără retrieval și fără a adăuga afirmații despre obligații sau efecte juridice. Nota de statut se livrează separat de copy.

## Exemplul 2 — audit de percepție

**Cererea utilizatorului:** „Poate fi perceput ca sfat juridic acest text despre modificarea obiectului de activitate? «Trebuie să depui hotărârea AGA. Se semnează de toți asociații. Acestea sunt toate documentele necesare. După depunere ești autorizat.»”

**Sarcina rutată:** `audit_perception`

**Statut per afirmație:**

- „Trebuie să depui hotărârea AGA.” — `editorial` (afirmație din textul primit; auditul nu îi verifică adevărul juridic).
- „Se semnează de toți asociații.” — `editorial` (afirmație din textul primit; subiectul semnatarului este ambiguu).
- „Acestea sunt toate documentele necesare.” — `editorial` (afirmație de exhaustivitate din textul primit).
- „După depunere ești autorizat.” — `out_of_corpus` (efect juridic privind CAEN/ONRC, materie neacoperită de corpus).

**Răspunsul așteptat pe scurt:**

```text
Mod: audit_perception
Verificare juridică: nu a fost efectuată
Risc de percepție ca îndrumare juridică: ridicat (derivat din constatarea efect_juridic; nu este o apreciere de fond)

Pasaje de revizuit:
- „Trebuie să depui hotărârea AGA.”
  Categorie: obligatie
  Subiect: utilizator
  Motiv: forma afirmației, nu conținutul ei
  Sugestie editorială: „Aplicația include depunerea hotărârii AGA în pașii afișați.”
- „Se semnează de toți asociații.”
  Categorie: semnatar
  Subiect: utilizator
  Motiv: forma afirmației, nu conținutul ei
  Sugestie editorială: „Aplicația afișează câmpurile pentru semnatari.”
- „Acestea sunt toate documentele necesare.”
  Categorie: exhaustivitate
  Subiect: utilizator
  Motiv: forma afirmației, nu conținutul ei
  Sugestie editorială: „Aplicația listează documentele prevăzute în acest flux.”
- „După depunere ești autorizat.”
  Categorie: efect_juridic
  Subiect: utilizator
  Motiv: forma afirmației, nu conținutul ei
  Sugestie editorială: „Aplicația afișează pasul de depunere; efectul juridic nu este verificat aici.”

Afirmații care nu pot fi verificate din acest corpus:
- „După depunere ești autorizat.”: materie CAEN/ONRC în afara scopului (statut `out_of_corpus`) → sursă oficială externă sau jurist.
```

## Exemplul 3 — descrierea unui formular oficial

**Cererea utilizatorului:** „Ce arată formularul oficial de pe pagina autorității? Spune dacă este obligatoriu și ce efect juridic produce.”

**Sarcina rutată:** `describe_source`

**Statut per afirmație:**

- „Formularul conține câmpurile și instrucțiunile vizibile pe pagina oficială consultată.” — `source_reported`.
- „Formularul este obligatoriu.” — `unverified` (nu rezultă doar din descrierea formularului).
- „Depunerea formularului produce efectul juridic X.” — `unverified` (nu se deduce din aspectul formularului).

**Răspunsul așteptat pe scurt:** Se descriu numai elementele observabile și se indică sursa oficială. Nu se afirmă obligativitatea sau efectul juridic fără retrieval juridic separat; dacă utilizatorul le dorește, cererea se rerutează la `answer_legal`.

## Exemplul 4 — întrebare juridică din corpus

**Cererea utilizatorului:** „Pentru un site care folosește cookie-uri neesențiale, ce trebuie verificat înainte de activare?”

**Sarcina rutată:** `answer_legal`

**Statut per afirmație:**

- Concluzia despre cerințele aplicabile cookie-urilor și protecției datelor — `verified`, numai după retrieval în corpus pentru actele și versiunile relevante.
- Trimiterea la textele recuperate din Legea nr. 506/2004 și RGPD — `verified`, cu citarea canonică și statutul verificate.

**Răspunsul așteptat pe scurt:** Se consultă corpusul pentru dispozițiile despre echipamentul terminal, consimțământ și temeiurile RGPD, apoi se răspunde concis cu citări exacte, data de referință, statutul actelor și eventualele avertismente. Nu se folosește doar un fragment de rezultat.

## Exemplul 5 — întrebare juridică din afara corpusului

**Cererea utilizatorului:** „Este obligatoriu să semneze toți asociații pentru modificarea codurilor CAEN și ce acte trebuie depuse la ONRC?”

**Sarcina rutată:** `answer_legal`

**Statut per afirmație:**

- „Este obligatoriu să semneze toți asociații.” — `out_of_corpus` (CAEN, ONRC și hotărârile societare nu sunt acoperite de corpusul local).
- „Acestea sunt actele care trebuie depuse la ONRC.” — `out_of_corpus` (nu există retrieval verificabil în corpus pentru această materie).

**Răspunsul așteptat pe scurt:** Se declară explicit `out_of_corpus`; nu se completează din memoria modelului și nu se promite verificare ulterioară în acest skill. Se recomandă consultarea sursei oficiale ONRC/legislației relevante sau a unui jurist.

## Exemplul 6 — cerere mixtă

**Cererea utilizatorului:** „Rescrie pentru site: «Legea cere banner de cookie-uri și, dacă îl accepți, ești conform.» Apoi spune dacă afirmația este corectă pentru site-ul meu.”

**Sarcina rutată:** `rewrite` pentru copy și `answer_legal` pentru întrebarea de verificare; partea juridică are precedență asupra simplei rescrieri.

**Statut per afirmație:**

- „Legea cere banner de cookie-uri.” din textul primit — `editorial` în copia rescrisă până la verificare; citarea preexistentă se păstrează verbatim și nu se corectează tacit.
- „Dacă îl accepți, ești conform.” din textul primit — `editorial` în copia rescrisă, nu concluzie juridică.
- Concluzia despre site-ul concret — `verified` numai după întrebări despre implementare și retrieval relevant din corpus; orice fapt lipsă rămâne `unverified` și primește placeholderul `[de verificat: ...]`.

**Răspunsul așteptat pe scurt:** Se livrează o rescriere neutră, de exemplu „Site-ul afișează opțiunile pentru cookie-uri; verifică informațiile prezentate.” Separat, se marchează afirmațiile ca neverificate în copy și se face `answer_legal` doar după clarificarea faptelor, cu citări oficiale și limitele aplicabilității.
