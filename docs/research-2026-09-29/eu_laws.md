# jurist — EU acts missing from the corpus (research note, 2026-09-29)

**Scop:** acte UE care ar duce corpusul jurist la nivelul următor pentru afaceri online (documente, contracte, garanții, T&C, DPA), cu accent pe norme noi 2022–2026.
**Metodă (toate sursele oficiale, accesate 2026-09-29):** Cellar/Publications Office content negotiation (`http://publications.europa.eu/resource/celex/{CELEX}` cu `Accept: application/xml;notice=branch` + `Accept-Language` — metadate oficiale: in_force, end-of-validity, amended_by, repeals, consolidations; `Accept: application/xhtml+xml` pentru text integral) ; Portal Legislativ SOAP (`GetToken` + `Search`, endpoint `.../FreeWebService.svc/SOAP`) ; OEIL (Parlamentul European) pentru stadiul procedurilor ; texte integrale pentru verificarea datelor-cheie. EUR-Lex HTML este în spatele unui AWS WAF (curl → 202 challenge); conținutul echivalent a fost luat din Cellar.
**Reguli:** nimic inventat; tot ce nu a putut fi verificat e marcat **UNVERIFIED**.

---

## 1. Tabel candidați UE (niciunul în corpus acum)

| Act | Identificator (CELEX / ELI) | De ce contează pentru afaceri online / documente / contracte / garanții | Domenii (tag-uri reutilizate din corpus.yaml) | Relație cu acte existente | Prioritate | Efort (fetch) |
|---|---|---|---|---|---|---|
| Data Act | CELEX 32023R2854; ELI reg/2023/2854/oj | Aplicabil de la 12.09.2025; termeni contractuali B2B nedrept interziși (ch. IV), schimbarea providerului cloud fără costuri de la 12.01.2027, acces la date IoT — afectează SaaS/contracte de hosting și clauze de date din T&C/DPA | online_services, contracts, digital_services, compliance | suplements User Rights Dir 2020/1828 + Enf. Reg 2017/2394 (verificat în notice) | **P1** | Cellar XHTML ~0.6 MB; notice 1.4 MB |
| AI Act | CELEX 32024R1689; ELI reg/2024/1689/oj | Transparență AI (art. 50) aplicabilă de la 02.08.2026 (chatbots, deepfakes, marcare conținut generativ) — relevant pentru roboți chat pe site-uri și T&C; obligații de furnizor/interpreter | online_platforms, online_services, transparency, compliance | **amendat de Reg (UE) 2026/1744** (vezi §3) | **P1** | XHTML mare (148 pagini); notice 1.5 MB |
| Digital Omnibus on AI (adoptat) | CELEX 32026R1744 | Adus la reglementare simplificată: **întârzie high-risk Annex III la 02.12.2027, Annex I la 02.08.2028**; tranziție 4 luni pentru marcare genAI (art. 50(2)) deja pe piață înainte de 02.08.2026; elimină implementing acts pt. codes of practice (art. 50(7)) → guidelines până la 01.08.2027. Adoptat 08.07.2026, aplicabil de la 27.07.2026 | (nu intră separat; se leagă la AI Act) | amends 2024/1689, 2018/1139, 2023/1230 (verificat) | **P1** (ca versiune/amendament al AI Act) | XHTML 0.35 MB |
| eIDAS 2.0 | CELEX 32024R1183; ELI reg/2024/1183/oj | EUDI Wallet: fiecare MS trebuie să ofere un wallet „în 24 luni de la intrarea în vigoare a implementing acts” (art. 5a(1) — text verificat); obligații de acceptare pentru servicii online (relying parties) — impact pe login/checkout și semnătură în contractele online | identity, electronic_signature, trust_services, ecommerce | **amends EU:REG:2014:910** (din 20.05.2024, verificat); 910/2014 e amendat și de NIS2 (18.10.2024) | **P1** | XHTML 0.58 MB |
| GPSR (produse generale) | CELEX 32023R0988 | Aplicabil din 13.12.2024; abroga GPSD 2001/95 + Reg 87/357 de la 13.12.2024; obligații pentru marketplace-uri online (persoană responsabilă, info securitate, retragere produse) — relevant pentru orice magazin online cu produse fizice | consumer, product_information, online_platforms, ecommerce | repeals 32001L0095, 31987L0357; **amendat de Reg (UE) 2024/2748 din 29.05.2026** (omnibus produse — modificări minore pentru jurist) | **P1** | notice 1.5 MB |
| Empowering Consumers (EmpCo / anti-greenwashing) | CELEX 32024L0825; ELI dir/2024/825/oj | **Aplicabil de la 27.09.2026** (acum!); transpunere 27.03.2026; interzice claim-uri generice de mediu, etichete nesustenținute de scheme certificate, statement-uri de performanță bazate doar pe offset-uri — impact direct pe pagini de produs, reclame și Legea 363/2007 | consumer, marketing, advertising, ecommerce | amends EU:DIR:2005:29 + EU:DIR:2011:83 (verificat, din 26.03.2024) | **P1** | XHTML 0.16 MB |
| Product Liability Directive (PLD) | CELEX 32024L2853 | Răspundere obiectivă pentru produse defectuoase **inclusiv software și servicii conexe software** (SaaS, AI); obligație de producere a dovezilor; transpunere **09.12.2026** (abroga 85/374 de la aceeași dată) — cheie pentru disclaimere și termeni de răspundere | consumer, contracts, ecommerce, digital_services | repeals 31985L0374 (din 09.12.2026, verificat) | **P1** | notice 1.27 MB |
| SCC (transfere date) | Dec Implementare (UE) 2021/914 | Clauze contractuale standard operator→operator; baza oricărui DPA cu transfere extra-UE | privacy, international_transfers, terms_and_conditions | repeals Dec 2001/497 + 2010/87 de la 27.09.2021 (verificat) | **P1** | notice 1.07 MB |
| SCC procesor→procesor | Dec Implementare (UE) 2021/915 | Clauze standard împuternicit→sub-împuternicit (al treilea document din setul DPA) | privacy, international_transfers, imputerniciti | — | **P1** | notice 0.79 MB |
| Decizie de adecvare UE–SUA (DPF) | Dec (UE) 2023/1795 | Nivel adecvat de protecție pentru transfere US; **confirmată de TGUE, T-553/23, 03.09.2025, Latombe v Comisie — acțiune respinsă** (text integral verificat, CELEX 62023TJ0553) | privacy, international_transfers | completes Dec Implementare 2021/914 (folosirea SCC + certificare DPF) | **P1** | notice 0.86 MB |
| NIS2 | CELEX 32022L2555 | Securitate cibernetică pentru entități esențiale/importante (inclusiv servicii digitale, online marketplace-uri, DNS); aplicabil 18.10.2024 | cybersecurity, online_services, ecommerce | **transposed_by RO:OUG:155:2024** (relație lipsește în corpus; aprobare RO: **Legea nr. 124/07.07.2025**, LinkHtml 299675 — verificat SOAP); amends Reg 910/2014 (18.10.2024), repeals Dir 2016/1148 | **P1** (cel mai ieftin: adaugi act + relație) | notice 2.35 MB |
| Rome I | CELEX 32008R0593 | Legea aplicabilă contractelor (art. 6 — protecția consumatorului la alegerea legii în T&C online); nicio modificare (verificat) | contracts, terms_and_conditions, consumer | — | **P1/P2** | notice 1.12 MB |
| Brussels I a (recast) | CELEX 32012R1215 | Competența în litigii de consum (arts. 17–19 — clauze de jurisdicție din T&C; consumatorul poate acționa acasă) | contracts, disputes, consumer | amended by Reg 2015/281 + 542; repeals Reg 44/2001 (verificat) | **P2** | notice 1.55 MB |
| Right to Repair | CELEX 32024L1799 | Obligații de reparare, piese, repairability — afectează garanții/conformitate pentru bunuri; **amendat de Dir (UE) 2026/74** (actualizare anexă II, din 10.05.2026); deadline transpunere RO 31.07.2026 | consumer, conformity, sales, ecommerce | **amends EU:DIR:2019:771** (SGD! din 30.07.2024, verificat), Reg 2017/2394, Dir 2020/1828 | **P2** | notice 1.4 MB; transpunerea RO **negăsită** prin SOAP (titlu „reparare”, 2026 → 0 rezultate) |
| Cyber Resilience Act | CELEX 32024R2847 | Cerințe de securitate pentru produse cu elemente digitale (software comercial); raportare vulnerabilități din 11.09.2026; obligații principale 11.12.2027; **amendat de Reg 2025/327 (EHDS) din 26.03.2027** | cybersecurity, digital_services, ecommerce | amends Reg 2019/1020 + altele | **P2** | notice 1.5 MB |
| CCD2 (credit de consum) | CELEX 32023L2225 | Acoperă **BNPL**/descoperiri; publicitate credit; aplicabil 20.11.2026 (abroga 2008/48 de la aceeași dată) | consumer, payments, marketing | repeals 32008L0048 (20.11.2026, verificat) | **P2** | notice 1.6 MB; transpunere RO negăsită (SOAP) |
| ODR repeal + consecințe | Reg (UE) 2024/3228 (CELEX 32024R3228) | Abroga Reg ODR 524/2013 de la **20.07.2025** (platforma ODR a dispărut) + **Dir (UE) 2025/2647** (16.12.2025, aplicabil 19.01.2026) care curăță referințele ODR din ADR/Package Travel/Omnibus/Representative Actions | disputes, consumer, complaints | repeals Reg 524/2013; amends Reg 2017/2394, 2018/1724; Dir 2025/2647 amends **EU:DIR:2013:11** + **EU:DIR:2019:2161** (verificat) | **P2** (fix de prospețime pentru răspunsuri ADR) | notices 1.03 MB + 1.57 MB |
| Market Surveillance Reg | CELEX 32019R1020 | Operator economic pentru produse vândute online în UE; bază pentru verificări marketplace; amendat de CRA/PPWR/2023/1542/2025/14/2026/1738 | consumer, ecommerce, enforcement | amendat de mai multe acte 2024–2026 (verificat) | **P2** | notice 1.5 MB |
| Digital Omnibus on data (propunere) | CELEX 52025PC0837 (COM(2025) 837) | Propunere (nov. 2025): ar amenda **GDPR, ePrivacy Dir, Data Act**, NIS2, 2018/1724/1725 — de urmărit; **NU adoptată** la 29.09.2026 (GDPR fără niciun amending act în Cellar — verificat) | — | proposal amending 2016/679, 2002/58, 2023/2854, 2022/2555, 2022/2557, 2018/1724, 2018/1725 | **P2 watchlist** | notice 1.35 MB |
| Distance marketing financial services | CELEX 32023L2673 | Drept de retragere specific serviciilor financiare la distanță, „buton de respingere” IBIP; aplicabil 19.06.2026 (abroga Dir 2002/65); periferic pentru v1 jurist | consumer, distance_contracts, withdrawal | amends EU:DIR:2011:83 (verificat); repeals 32002L0065 | **P2/P3** | notice 1.8 MB; transpunere RO negăsită |
| DMA | CELEX 32022R1925 | Doar pentru gatekeeperi desemnați — corpusul servește afaceri mici/mijlocii online | online_platforms, competition→nu există tag | amends Dir 2018/1808, 2019/1937 (verificat) | **P3** | notice 1.37 MB |
| Data Governance Act | CELEX 32022R0868 | Intermediere de date, data altruism — suprapunere parțială cu Data Act | online_services, digital_services | — | **P3** | notice 1.36 MB |
| Political Advertising | CELEX 32024R0900 | Aplicabil 10.10.2025; doar pentru publicitate politică | marketing, advertising | — | **P3** | notice 1.39 MB |
| EMFA | Dir (UE) 2024/1083 | Obligații minime pentru platforme re: mass-media; **identificator NECESITAT: CELEX 32024L1083 negăsit în Cellar (2 încercări) iar căutarea ELI pe EUR-Lex a returnat „No results found” → UNVERIFIED** | online_platforms | — | **P3 / UNVERIFIED** | — |
| Instant Payments | CELEX 32024R0886 | Plăți instant la checkout; aplicat etapizat 2025; nu schimbă esențial răspunsurile de consum | payments, ecommerce | amends PSD2, Reg 260/2012, 2021/1230 (verificat) | **P3** | notice 1.6 MB |
| Late Payment Dir | CELEX 32011L0007 | Termene de plată B2B (SaaS B2B) — util, dar vechi și marginal pentru v1 | contracts | repeals Dir 2000/35 | **P3** | notice 1.47 MB |

## 2. Note scurte pe candidați (ce am verificat textual)

- **Data Act (32023R2854):** notice → in force, EIF 11.01.2024; aplicare principală 12.09.2025, prevederi selectate 12.09.2026 / 12.09.2027 (date de ENTRY_INTO_FORCE din notice). Text integral: „12 January 2027, providers of data processing services shall not impose any switching charges”; „unfair contractual terms” (ch. IV). Pentru jurist: întrebări „contract cloud / poate furnizorul să-mi refuze datele / penalizări de switch”.
- **AI Act (32024R1689):** notice → EIF 01.08.2024, aplicare etapizată: 02.02.2025, **02.08.2026 (general, inclusiv art. 50)**, 02.08.2027. **Amendment adoptat:** Reg (UE) 2026/1744 „Digital Omnibus on AI” (adoptat 08.07.2026, aplicabil 27.07.2026) — din text: high-risk art. 6(2)/Annex III → **02.12.2027**; art. 6(1)/Annex I → **02.08.2028**; tranziție de 4 luni pt. marcare genAI (art. 50(2)) pt. sisteme pe piață înainte de 02.08.2026; art. 50(7)/56(6)/72(3) — empowerment-uri de implementing acts eliminate (guidelines cel târziu 01.08.2027). Corpusul trebuie să modeleze asta ca versiune point_in_time, altfel va răspunde greșit pe termene.
- **EmpCo (32024L0825):** text → „27 March 2026, Member States shall adopt and publish the measures necessary”; aplicare **27 September 2026** (apărută și ca DOC_DATE în notice). Transpunerea RO: cautare SOAP (an=2026, titlu „practici”/„practicile comerciale incorecte”) → **0 rezultate relevante** → transpunere RO neidentificată (RO pare în întârziere; termenul a trecut pe 27.03.2026). Răspunsurile RO prin Legea 363/2007 rămân pe textul pre-EmpCo → avertisment obligatoriu.
- **GPSR (32023R0988):** aplicabil 13.12.2024; abroga GPSD (32001L0095, in_force=false, end validity 12.12.2024) — nu era în corpus, deci doar câștig. Amendat de Reg (UE) 2024/2748 („omnibus” produse — construcții/ascensoare etc., cu patch-uri procedurale la GPSR) din 29.05.2026.
- **PLD (32024L2853):** EIF 08.12.2024; repeals 85/374 din 09.12.2026 → transpunere RO 09.12.2026; software ca produs =直接影响 pentru SaaS (clauze de răspundere/disclaimer). Transpunere RO neidentificată (SOAP).
- **SCC set (2021/914, 2021/915, 2023/1795):** toate in force (verificat). T-553/23 (03.09.2025): „THE GENERAL COURT (Tenth Chamber, Extended Composition) hereby: 1. Dismisses the action…” — DPF rămâne valid (posibil apel la CJUE — nu am găsit decizie de apel → neafirmat).
- **NIS2 (32022L2555):** aplicabil 18.10.2024; OUG 155/2024 e deja în corpus **fără relație**; am găsit prin SOAP și **Legea nr. 124 din 07.07.2025 pentru aprobarea OUG 155/2024** (LinkHtml http://legislatie.just.ro/Public/DetaliiDocument/299675). Acțiune ieftină cu efect mare.
- **eIDAS 2.0 (32024R1183):** valid de la 20.05.2024; consolidație existentă 02014R0910-20240520 pentru baza 910/2014 (verificat). Wallet: art. 5a(1) — „within 24 months of the date of entry into force of the implementing acts” (nu există o dată calendaristică fixă în text; orice „dec. 2026” e aproximare editorială, nu act).
- **Rome I / Brussels I a:** in force, fără modificări relevante (Brussels I a: amendat de 2015/281 + 2015/542; aplicabil 10.01.2015). Fundament pentru clauze de lege aplicabilă/jurisdicție din T&C.
- **ODR:** Reg 2024/3228 abroga 524/2013 de la 20.07.2025; Dir 2025/2647 (adoptată 16.12.2025, aplicabilă 19.01.2026) modifică ADR 2013/11 și Omnibus 2019/2161 — **ambele acte existente în corpus au fost modificate → note de stare obligatorii.**
- **Green Claims (COM(2023) 280, procedura 2023/0169(COD)):** OEIL (deschis 29.09.2026): **NU e retrasă** — „Awaiting Parliament's position in 1st reading”; aprobare în comisie a textului provizoriu 03.06.2026; dată indicativă plenă 19.10.2026. Watchlist P3 (continuă seria EmpCo cu cerințe de substantiere).
- **PSD3 (COM(2023) 360, 2023/0205(COD)):** OEIL — propunere 28.06.2023, raport ECON A9-0183/2024, negocieri interinstituționale deschise (dec. 2024), status „Awaiting Parliament's position in 1st reading” → **neadoptată**.
- **PSR:** numărul de procedură/CELEX pe care l-am probeat (52023PC0361) **nu există** (EUR-Lex: „The requested document does not exist”; fiche 2023/0206(COD) e alt act — Reg 2024/2594 pescuit). Status PSR → **UNVERIFIED**.
- **ePrivacy Regulation (propunere, 52017PC0010):** fiche OEIL 2017/0010(COD) → „This procedure either does not exist…” (2 încercări) → **status retragere UNVERIFIED**. Directiva 2002/58 rămâne în vigoare (verificat în notice; amendamente doar 2006/24 + 2009/136).
- **GDPR procedural regulation:** CELEX-ul probeat (52023PC0372) e alt act (Malta RRF); fiche OEIL 2023/0222(COD) „not found” → **UNVERIFIED**.
- **Digital Fairness Act:** pagina digital-strategy.ec.europa.eu/en/policies/digital-fairness → „Page not found” (29.09.2026) → **nu există încă act identificabil oficial → UNVERIFIED**; nu se pune în corpus.
- **EMFA:** UNVERIFIED (vezi tabel).
- **Instant Payments (32024R0886):** EIF 08.04.2024; aplicare etapizată în 2025 (datele exacte 09.01/09.10.2025 **nu au fost reverificate din text** — nu le afirma în răspunsuri fără fetch).
- **RO, în plus:** **OUG nr. 5/12.02.2026** (MO 172/05.03.2026, LinkHtml 308068 — verificat prin HTML oficial) modifică acte din domeniul instituțiilor de credit, adecvare de capital și servicii de plată — semnal RO de pregătire pentru pachetul de plăți UE; nu e transpunere a PSD3 (inexistentă). Neintrat în recomandări (domeniu plăți B2C marginal).

## 3. Schimbări de stare ale actelor EXISTENTE în corpus (obligatoriu de reflectat)

| Act din corpus | Schimbare | Sursă (verificată) |
|---|---|---|
| EU:REG:2014:910 (eIDAS) | amendat de 2024/1183 (din 20.05.2024) și de NIS2 2022/2555 (din 18.10.2024); consolidație 02014R0910-20240520 | Cellar notice 32014R0910 |
| EU:DIR:2011:83 (CRD) | amendat de 2023/2673 (18.12.2023), 2024/825 (26.03.2024), + 2019/2161, 2015/2302 | Cellar notice 32011L0083 |
| EU:DIR:2005:29 (UCPD) | amendat de 2024/825 (26.03.2024) + 2019/2161 | Cellar notice 32005L0029 |
| EU:DIR:1998:6 (prețuri) | amendat de 2019/2161 (07.01.2020) — nu și de EmpCo | Cellar notice 31998L0006 |
| EU:DIR:2013:11 (ADR) | **amendat de Dir (UE) 2025/2647 (19.01.2026)** — referințele la platforma ODR căzute (platforma abrogată de la 20.07.2025) | Cellar notices 32013L0011, 32025L2647, 32024R3228 |
| EU:DIR:2019:2161 (Omnibus) | **amendat de Dir (UE) 2025/2647 (19.01.2026)** | Cellar notice 32019L2161 |
| EU:DIR:2019:771 (SGD) | **amendat de Dir (UE) 2024/1799 — Right to Repair (30.07.2024)** | Cellar notice 32019L0771 |
| EU:DIR:2015:2366 (PSD2) | amendat de DORA 2022/2556 (16.01.2023) și de Reg 2024/886 instant payments (08.04.2024); înlocuire PSD3 pending | Cellar notice 32015L2366 |
| EU:DIR:2002:58 (ePrivacy) | **fără schimbări** (doar 2006/24 + 2009/136) | Cellar notice 32002L0058 |
| EU:REG:2016:679 (GDPR) | **fără amending act adoptat**; doar propunere 52025PC0837 (omnibus date) | Cellar notice 32016R0679 + 52025PC0837 |
| EU:REG:2019:1150 (P2B), EU:REG:2018:302 (geoblocare), EU:REG:2022:2065 (DSA) | fără amendamente adoptate (verificat) | Cellar notices |
| EU:DIR:2019:882 (EAA) | in force; **mijloc de aplicare din 28.06.2025 (art. 32) — data NU reverificată din text în sesiunea de azi → reverifica la ingest** | notice (EIF 27.06.2019) |
| RO:OUG:155:2024 (NIS2 RO) | **aprobată prin Legea nr. 124/07.07.2025**; relația transposed_by spre EU:DIR:2022:2555 lipsește din relations.tsv | SOAP Search (an=2024, nr=155; titlu „securitatea cibernetică”) |

## 4. Top-10 adăugiri recomandate (ordonate)

1. **Reg (UE) 2023/2854 (Data Act)** — deja aplicabil; contracte cloud/B2B terms = conversații reale ale publicului-țintă.
2. **Reg (UE) 2024/1689 (AI Act) + Reg (UE) 2026/1744 (omnibus AI)** — obligatoriu modelate împreună ca versiuni; fără 2026/1744 corpusul greșește termenele.
3. **Dir (UE) 2024/825 (EmpCo)** — aplicabilă de la 27.09.2026; actualizează automat UCPD/CRD și răspunsurile RO prin Legea 363/2007 (cu avertisment de transpunere).
4. **Reg (UE) 2023/988 (GPSR)** — aplicabil din 12.2024; piețe online și produse fizice.
5. **Dir (UE) 2024/2853 (PLD nouă)** — răspundere pentru software; cheie pentru disclaimere/limitări din T&C SaaS.
6. **Deciziile 2021/914 + 2021/915 + 2023/1795 (SCC, P2P-SCC, DPF)** — setul minim pentru DPA și transfere; plus citarea T-553/23 (respinsă, 03.09.2025).
7. **Reg (UE) 2024/1183 (eIDAS 2.0)** — ca act nou + actualizarea intrării 910/2014 (consolidație 2024-05-20).
8. **Dir (UE) 2022/2555 (NIS2)** + relația `transposed_by → RO:OUG:155:2024` (+ mențiune Legea 124/2025 de aprobare) — cost minim, corectitudine imediată.
9. **Reg (UE) 593/2008 (Rome I)** (+ perechea Reg 1215/2012 Brussels I a la P2) — fundament pentru clauzele de lege aplicabilă/jurisdicție din T&C.
10. **Reg (UE) 2024/3228 (ODR repeal) + Dir (UE) 2025/2647** — fix de prospețime: ADR/Omnibus din corpus sunt deja modificate.

## 5. Deliberat NU recomandate (și de ce)

- **DMA (2022/1925)** — obligații doar pentru gatekeeperi desemnați; publicul-țintă (afaceri online mici/mijlocii) nu e subiect; distorsionează recall-ul eval-ului.
- **DGA (2022/868)** — intermedierea de date; suprapus parțial cu Data Act; doar dacă apare cerere reală.
- **Political Ads (2024/900)** — nișă (publicitate politică), în afara domeniilor de v1.
- **EMFA (2024/1083)** — nișă media + identificator neconfirmat → skip până la nevoie reală.
- **Instant payments (2024/886), Late Payment (2011/7)** — plăți B2B/B2C marginale pentru documentele generate de jurist; cost vs. valoare slab.
- **ePrivacy Regulation (propunere)** — statut de retragere neverificat azi; directiva + Legea 506/2004 rămân baza. Dacă confirmă oficial retragerea, adăugăm doar o notă în SKILL.md.
- **GDPR procedural reg / PSD3 / PSR / Digital Fairness Act** — neadoptate / neverificate oficial azi → watchlist în corpus-audit, nu intrări de corpus (regula: niciun act „includ pentru că e la modă”).
- **Green Claims (COM(2023) 280)** — doar watchlist până la adoptare (plenă indicativă 19.10.2026); abia după adoptare intră alături de EmpCo.
- **Reg 2024/2748, Reg 2025/327 (EHDS), Reg 2025/40 (PPWR), Reg 2026/1738, Dir 2026/74** — omnibus/tehnice care ating acts din corpus doar marginal; se notează ca amendamente la ingest, nu ca intrări.
- **VAT e-commerce (pachetul 2017/2455 etc.)** — fiscal = out_of_corpus prin design (AGENTS.md §14 Rule 13).
- **FiDA, CSAM, Data Act secundare, DSA delegated acts** — nu există act final sau nu sunt în scopul v1.

## 6. Note de efort / integrare

- **Fetch UE:** Cellar funcționează deterministic din curl: `GET http://publications.europa.eu/resource/celex/{CELEX}` cu `Accept: application/xml;notice=branch` + `Accept-Language: ro|eng` (metadate: in_force, end-of-validity, ENTRY_INTO_FORCE, AMENDED_BY cu date, REPEALS, CONSOLIDATIONS) și `Accept: application/xhtml+xml` pentru text. Notice: 0.8–2.5 MB XML/act; XHTML: 0.15–0.6 MB/act. EUR-Lex HTML direct = blocat de WAF pt. curl (folosiți browserul sau Cellar).
- **Fetch RO:** SOAP `GetToken` + `Search` la `http://legislatie.just.ro/apiws/FreeWebService.svc/SOAP`; câmpurile utile: `SearchAn`+`SearchNumar` (funcționale) și `SearchTitlu` (fuzzy funcțional); `SearchText` pare nefuncțional (0 rezultate sistematic). TipAct NU e parametru de filtrare → filtrați client-side.
- **Consolidații:** pentru actele din corpus amendate, adăugați manifestări consolidate (ex. 02014R0910-20240520) — modelul point_in_time există deja.
- **Transpunerile RO absente** (EmpCo, R2R, PLD, CCD2, FSCD): marcați explicit „transpunere neidentificată la data X (căutare SOAP)” și NU legați relații inventate.

## 7. URL-uri oficiale accesate (sesiunea de cercetare 2026-09-29)

- Cellar branch notices (Accept: application/xml;notice=branch): `http://publications.europa.eu/resource/celex/` pentru CELEX: 31998L0006, 32000L0031, 32001L0095, 32002L0058, 32005L0029, 32008R0593, 32011L0007, 32011L0083, 32012R1215, 32013L0011, 32015L2366, 32016R0679, 32018R0302, 32019L0770, 32019L0771, 32019L0882, 32019L2161, 32019R1020, 32019R1150, 32021D0914, 32021D0915, 32022L2555, 32022R0868, 32022R1925, 32022R2065, 32023D1795, 32023L2225, 32023L2673, 32023R0988, 32023R2854, 32024L0825, 32024L1799, 32024L2853, 32024R0886, 32024R0900, 32024R1183, 32024R1689, 32024R2748, 32024R2847, 32024R3228, 32025L2647, 32025R0014, 32025R0040, 32025R0327, 32026L0074, 32026R1738, 32026R1744, 52025PC0836, 52025PC0837, 52023PC0372, 52024R2594, 62023TJ0553 (2748/2594 doar titlu+date)
- Texte integrale XHTML (Accept: application/xhtml+xml): 32026R1744, 32024L0825, 32024R1183, 32023R2854, 62023TJ0553
- Portal Legislativ: `https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl` + endpoint `/SOAP` (GetToken, Search: 2024/155; titluri „securitatea cibernetică”, „practici”, „credit”, „servicii financiare”, „reparare”); `https://legislatie.just.ro/Public/DetaliiDocument/308068` (OUG 5/2026)
- OEIL (Parliament): `https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference=2023%2F0169%28COD%29&l=en` (Green Claims — OK), `...2023%2F0205%28COD%29` (PSD3 — OK), `...2023%2F0206%28COD%29` (s-a dovedit alt act — Reg 2024/2594 pescuit), `...2017%2F0010%28COD%29` și `...2023%2F0222%28COD%29` („not found” → UNVERIFIED)
- EUR-Lex (browser, prin WAF): `https://eur-lex.europa.eu/eli/dir/2024/1083/oj` („No results found” → EMFA UNVERIFIED), `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52023PC0361` („does not exist” → PSR ID UNVERIFIED)
- European Commission: `https://digital-strategy.ec.europa.eu/en/policies/digital-fairness` („Page not found” → DFA UNVERIFIED)

*Notă finală: toate datele „applicabile de la/applicabil din” din tabel provin din câmpurile ENTRY_INTO_FORCE/date-of-effect ale noticelor Cellar sau din texte integrale citate; unde nu am găsit câmp dedicat (ex. aplicarea etapizată Instant Payments, art. 32 EAA), data NU este afirmată ca verificată. Sesiunile de browser folosite au fost script-mode, închise automat la final.*
