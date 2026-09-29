# jurist — AGENTS.md

Arhitectură executabilă pentru skill-ul `jurist`: cercetare juridică *grounded* pentru dreptul românesc și dreptul Uniunii Europene, peste un corpus local determinist (SQLite + FTS5). Acest document este sursa unică de adevăr pentru implementare; fiecare etapă are un gate verificabil mecanic (vezi §32).

## 1. Purpose

jurist is a grounded legal-research skill for Romanian and European Union law.

Its purpose is to help an AI agent answer legal and compliance questions for websites, SaaS products, online services, e-commerce businesses, companies and other commercial activities by retrieving applicable law from a curated local corpus instead of relying on model memory or ad-hoc web searches.

The runtime agent MUST treat the local legal corpus as the primary source of legal authority for this skill.

The skill is not a substitute for a licensed lawyer. It is a legal research and drafting assistant that must distinguish verified legal authority from interpretation, guidance, assumptions and missing facts.

Core principle:

    RETRIEVE → VERIFY → REASON → CITE

The agent MUST NOT invent legal citations, article numbers, court decisions, authority decisions, quotations, dates, statuses or obligations.

## 2. Target jurisdictions

Initial scope (v1):

    European Union legislation (regulations and directives relevant to v1 scope);

    Romanian national legislation and transposition acts;

    case law and authority guidance: NOT part of v1 (see §36 roadmap; schema support exists but collections are empty in v1).

Default user-facing language: Romanian, unless the user requests another language.

Preferred source language for Romanian legislation: Romanian.

Preferred source language for EU legislation:

    Romanian;

    English as an optional secondary text for retrieval/debugging when useful.

Do not ingest all 24 EU language versions unless there is a concrete product requirement.

## 3. Legal source classes

All content in the corpus MUST be classified. `authority_class` is one axis; `domains` (see §8.9) is a separate, orthogonal axis.
A. Binding legislation

Examples:

    EU Treaties;

    EU Regulations;

    EU Decisions where applicable;

    EU Directives (see B);

    Romanian Constitution;

    Romanian laws;

    Government Emergency Ordinances (OUG);

    Government Ordinances (OG);

    Government Decisions (HG);

    ministerial orders and other binding normative acts when relevant.

Store as:

    authority_class = binding_legislation
B. EU Directives

Directives MUST be stored as EU legal acts but MUST NOT be treated as interchangeable with Romanian transposition legislation.

Store relations such as:

    transposed_by
    implements
    supplements
C. Case law (post-v1)

    CJEU judgments;

    General Court judgments;

    Romanian court judgments.

Store as:

    authority_class = case_law

Case law MUST be indexed separately from legislation. Not populated in v1.
D. Authority decisions (post-v1)

    ANSPDCP decisions;

    decisions of other competent regulators.

Store as:

    authority_class = authority_decision
E. Official guidance (post-v1)

    EDPB Guidelines, Recommendations, Opinions;

    ANSPDCP guidance.

Store as:

    authority_class = official_guidance

Guidance MUST NOT be described as legislation or as binding law unless its metadata explicitly establishes a binding legal effect.
F. Informational material (post-v1)

Summaries, FAQs and explanatory pages may be stored when useful, but MUST have lower retrieval priority.

Store as:

    authority_class = informational

## 4. Official source registry

Only official or institutionally authoritative sources MUST be used to build the canonical corpus.

Third-party legal aggregators, blogs, law-firm articles, commercial databases, news sites and SEO summaries MUST NOT be used as canonical source text. They may be used only outside the corpus for discovery or comparison, never as the authoritative stored legal text.

### 4.1 European Union legislation — EUR-Lex

Official portal:

    https://eur-lex.europa.eu/

About EUR-Lex:

    https://eur-lex.europa.eu/content/welcome/about.html

EUR-Lex is operated by the Publications Office of the European Union and provides official and comprehensive access to EU legal documents.

Use EUR-Lex for:

    Treaties;

    Regulations;

    Directives;

    Decisions;

    consolidated texts;

    Official Journal documents;

    EU case-law references;

    national transposition references where available.

### 4.2 Stable EU legal identifiers — ELI

Official ELI documentation:

    https://eur-lex.europa.eu/content/help/eurlex-content/eli.html

Permanent-link guidance:

    https://eur-lex.europa.eu/content/help/data-reuse/linking.html

Prefer ELI identifiers and CELEX identifiers as canonical identifiers.

Example ELI pattern:

    https://data.europa.eu/eli/{document_type}/{year}/{number}/oj

Where available, retain:

    CELEX;

    ELI;

    Official Journal reference;

    language;

    document date;

    publication date;

    entry-into-force date;

    date of effect;

    end-of-validity date;

    consolidation date.

### 4.3 EU programmatic search — EUR-Lex Webservice

Official documentation:

    https://eur-lex.europa.eu/content/help/data-reuse/webservice.html

Use for programmatic search and metadata discovery.

Important:

    EUR-Lex Webservice requires registration;

    it can return search data in XML;

    document files should be fetched through Cellar or official stable document links.

Do not build a fragile HTML scraper if an official programmatic method is available. This applies to EU sources and, equally, to Romanian sources (see §4.7): scraping is never an ingestion strategy.

### 4.4 EU document download — Publications Office / Cellar

Official Cellar publications interface:

    https://op.europa.eu/en/web/cellar/cellar-data/publications

Developer documentation:

    https://op.europa.eu/en/web/cellar/documentation

Use Cellar for machine-readable retrieval of EU publications.

Prefer, in this order when available:

    XML;

    XHTML;

    HTML;

    plain text;

    PDF only when no structured version is practical.

Archive the original downloaded manifestation for auditability.

### 4.5 EU bulk reuse / data dumps

Official EUR-Lex reuse documentation:

    https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html

For larger ingestion jobs, prefer official bulk-download mechanisms or direct Cellar access rather than crawling individual EUR-Lex pages.

### 4.6 Official Journal of the European Union

Access through EUR-Lex:

    https://eur-lex.europa.eu/oj/direct-access.html

Where legal authenticity matters, retain references to the Official Journal publication.

Consolidated versions are useful working texts, but the system MUST distinguish them from the authentic acts and amendments published in the Official Journal.

### 4.7 Romanian legislation — Portal Legislativ, Ministry of Justice

Official portal:

    https://legislatie.just.ro/

Portal functionality:

    https://legislatie.just.ro/Public/Functionalitati

**Programmatic access — official SOAP web service (mandatory for discovery and metadata).**

Documentation page:

    https://legislatie.just.ro/serviciulweblegislatie.htm

Service base:

    http://legislatie.just.ro/apiws              (redirects to https)
    https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl   (WSDL, public, no registration)

The WSDL (`FreeWebService`) exposes exactly two operations:

    GetToken()
        → returns tokenKey (limited validity; no registration required)

    Search(tokenKey, NumarPagina, RezultatePagina,
           [SearchAn], [SearchNumar], [SearchTitlu], [SearchText])
        → returns a paged list of acts; each result contains:
            Titlu, Emitent, Numar, TipAct, Publicatie,
            DataVigoare, Text, LinkHtml

Ingestion flow for Romanian acts (see §19, §21):

    corpus.yaml fetch spec (tip, numar, an)
        → GetToken()
        → Search(SearchAn, SearchNumar)
        → record metadata (Titlu, Emitent, Numar, TipAct, Publicatie, DataVigoare, LinkHtml)
        → fetch the official consolidated HTML identified by LinkHtml
        → snapshot (checksum of HTML, retrieved_at, detected_at, data_vigoare_reported)
        → parse_ro HTML (S_ART / S_ALN / S_LIT) → insert

Rules that MUST be respected:

    scraping the HTML portal search UI (ASP.NET/ViewState) is FORBIDDEN;
    SOAP is mandatory for discovery, identifiers, DataVigoare and LinkHtml;

    SOAP `Text` is the ORIGINAL published form, NOT the consolidated current form.
    It MUST NOT be stored as the canonical legal text. Evidence: Legea 506/2004 via
    SOAP still cites Legea 677/2001 (repealed 2018); the LinkHtml consolidation
    contains the current cookie-consent rule.

    Canonical RO text = official Portal Legislativ HTML for the act identified by
    LinkHtml (`parse_ro.py` DOM). Fetching that official document is not portal scraping.

    the HTML, like SOAP, is the CURRENT form only; no point-in-time API;
    therefore every Romanian act is stored with version_coverage = current_only (see §8.1, §17, §21);

    poll SOAP metadata and re-fetch LinkHtml HTML; checksum the HTML (see §21);

    `LinkHtml` is provenance; SOAP fields are authoritative for metadata, not body text.

### 4.8 Romanian official publication — Monitorul Oficial

Official site:

    https://monitoruloficial.ro/

Use Monitorul Oficial as an authenticity/publication reference for Romanian normative acts.

For routine normalized retrieval, Portal Legislativ SOAP discovery + LinkHtml HTML (§4.7) is the ingestion path.

Where exact official publication, publication date or authenticity must be verified, retain Monitorul Oficial metadata/reference.

Do not assume all Monitorul Oficial archival functionality is freely or programmatically available.

### 4.9 Romanian data-protection authority — ANSPDCP (post-v1)

Official site:

    https://www.dataprotection.ro/

Use for:

    ANSPDCP decisions;

    Romanian data-protection guidance;

    official GDPR materials.

Suggested classes:

    decisions → authority_decision;

    guides → official_guidance;

    FAQs/informational material → informational.

Not ingested in v1; registry kept for the roadmap (§36).

### 4.10 European Data Protection Board — EDPB (post-v1)

Official site:

    https://www.edpb.europa.eu/

Documents:

    https://www.edpb.europa.eu/our-work-tools/our-documents_en

Public consultations:

    https://www.edpb.europa.eu/public-consultations_en

Store final/adopted documents separately from draft documents under public consultation.

A draft/public-consultation version MUST be marked:

    document_status = draft

An adopted/final document MUST be marked:

    document_status = final

Do not treat EDPB guidance as legislation. Not ingested in v1; registry kept for the roadmap (§36).

### 4.11 Court of Justice of the European Union — InfoCuria (post-v1)

Official case-law portal:

    https://infocuria.curia.europa.eu/

Where available, store:

    case number;

    ECLI;

    court;

    chamber;

    decision date;

    parties/title;

    document type;

    language;

    cited EU legislation;

    paragraphs;

    source URL.

Case-law paragraphs should be independently retrievable. Not ingested in v1.

### 4.12 Romanian case law — ReJust (post-v1)

Portal:

    https://www.rejust.ro/

ReJust is linked by the Romanian Superior Council of Magistracy and Romanian courts as the national jurisprudence portal.

Use for anonymized Romanian judgments when case-law ingestion is enabled (§36). Not part of v1.

### 4.13 Romanian courts metadata — Portalul instanțelor (post-v1)

Official portal:

    https://portal.just.ro/

Programmatic access information:

    https://portal.just.ro/SitePages/acces.aspx

Use primarily for case/docket metadata where needed. Do not confuse docket metadata with the text of a final judgment.

## 5. Initial MVP corpus (v1)

**v1 scope decision (R11):** privacy + e-commerce, Romanian + EU legislation only, approximately 25 acts, NO case law, NO authority guidance, NO embeddings, RO stored as current_only (see §8.1). Everything else stays in this document as an explicitly marked post-v1 roadmap (§36).

The exact act list is frozen in `sources/corpus.yaml` during Etapa B (§32). Every act in the list MUST define:

    id (canonical, §16);

    fetch spec (SOAP or Cellar, §23);

    authority_class;

    version_coverage;

    domains (§8.9);

    aliases (§8.4);

    summary_ro (§23);

    scope_provisions where the act defines material/territorial scope (§5.6).

The draft v1 list to be verified (not accepted on trust) in Etapa B:

### 5.1 Privacy and data protection (v1)

    Regulation (EU) 2016/679 — GDPR (EU:REG:2016:679);

    Romanian Law no. 190/2018 — GDPR application in Romania (RO:LEGE:190:2018);

    Directive 2002/58/EC — ePrivacy (CELEX 32002L0058) as an explicit EU act reference;

    Romanian Law no. 506/2004 — its Romanian transposition (RO:LEGE:506:2004), aliased "legea cookie-urilor".

Topics in scope: consent, legitimate interest, transparency, privacy notices, processors and controllers, cookies and terminal equipment, direct marketing, data-subject rights, breaches, DPIA, DPO, retention, international transfers (v1 covers the notions addressed by the acts above; a dedicated privacy-domain taxonomy is in §8.9).

### 5.2 E-commerce and consumer law (v1)

At minimum identify and ingest current relevant versions of:

    Romanian Law no. 365/2002 on electronic commerce (RO:LEGE:365:2002);

    Romanian Government Emergency Ordinance no. 34/2014 — distance contracts / withdrawal (RO:OUG:34:2014);

    Romanian Law no. 193/2000 on unfair terms (RO:LEGE:193:2000);

    Romanian Government Ordinance no. 21/1992 on consumer protection (RO:OG:21:1992);

    relevant EU consumer legislation (Directive 2011/83/EU consumer rights, Directive 93/13/EEC unfair terms — as EU references transposed by the acts above);

    digital content / goods: the transposition pair of Directive (UE) 2019/770 (digital content) and Directive (UE) 2019/771 (sale of goods) — Romanian transposition acts to be identified in Etapa B (candidate, not assumed).

Candidate additions for Etapa B, to be verified against official sources, not accepted on trust:

    Romanian Law no. 363/2007 on unfair commercial practices (§5.2 topic is listed; the act is a transposition of Directive 2005/29/EC);

    Regulation (EU) 2018/302 — geo-blocking;

    Regulation (EU) 910/2014 — eIDAS (electronic signatures, relevant to online contracting).

Topics: mandatory trader information, electronic contracting, checkout flow, price presentation, subscriptions, cancellation, withdrawal, refunds, digital content, consumer guarantees, unfair terms, dark patterns where regulated, online marketplace duties.

### 5.3 Contracts and liability (post-v1 roadmap)

Ingest relevant sections of:

    Romanian Civil Code (Law no. 287/2009) — formation, validity, performance, termination, damages, force majeure, interpretation, limitation/exclusion issues.

Avoid indexing only isolated articles when interpretation requires neighboring provisions. Not in v1.

### 5.4 Company law (post-v1 roadmap)

Include relevant current provisions of:

    Romanian Companies Law no. 31/1990 — identification/information duties, representation, administrator/director authority. Not in v1.

### 5.5 Intellectual property (post-v1 roadmap)

Include relevant current provisions of:

    Romanian Law no. 8/1996;

    relevant EU copyright legislation (e.g. Directive 2001/29/EC InfoSoc);

    licensing, user-generated content, platform notice/removal obligations where applicable. Not in v1.

### 5.6 EU digital regulation (post-v1 roadmap, applicability mechanism in v1)

Include at minimum as relevant:

    Digital Services Act — Regulation (EU) 2022/2065;

    AI Act — Regulation (EU) 2024/1689;

    Data Act — Regulation (EU) 2023/2854.

Do not assume each act applies to every business. Applicability must be determined from facts and from retrieved **scope provisions**.

`scope_provisions` is a per-act list of `provision_id`s that define the act's material/territorial scope (e.g. DSA art. 1–2; AI Act art. 1–2). It is stored for every framework act (§8.1, §23) and returned automatically by `jurist resolve` and `jurist corpus-status` so the agent never guesses applicability. In v1 the mechanism is implemented and empty for non-framework acts; the three acts above are ingested post-v1.

## 6. Repository architecture

Recommended layout:

    jurist/
    ├── AGENTS.md                 # executable architecture contract (primary)
    ├── SKILL.md
    ├── CONTEXT.md                # historical source artifact (kept, not edited)
    ├── scripts/
    │   ├── jurist.py              # CLI: resolve | search | provision | related | corpus-status
    │   ├── fetch_corpus.py        # corpus.yaml fetcher: RO SOAP+LinkHtml, EU Cellar (Etapa C)
    │   ├── fetch_ro.py            # SOAP legislatie.just.ro helpers (imported by fetch_corpus.py)
    │   ├── parse_ro.py            # Portal Legislativ HTML parser (Etapa D)
    │   ├── parse_eu.py            # XHTML/Formex parser (Etapa D)
    │   ├── normalize.py           # NFC, cedilă→virgulă, whitespace (Etapa E)
    │   ├── build_index.py         # SQLite + FTS5 + lemmas (Etapa E)
    │   ├── tag_domains.py         # domains on acts + provisions (Etapa F)
    │   ├── diff_versions.py       # per-provision diff, CHANGELOG.md (Etapa H)
    │   ├── eval_recall.py         # 40-question eval, recall@10 (Etapa G)
    │   ├── citation_validator.py  # deterministic validator over retrieval log (Etapa I)
    │   ├── validate.py
    │   └── update_manifest.py
    ├── sources/
    │   ├── corpus.yaml            # canonical corpus definition (Etapa B)
    │   ├── lemmas_ro.tsv          # hand-written RO lemma/synonym table (§10)
    │   ├── routing_keywords.tsv   # hand-written keyword→domain table (§13)
    │   └── README.md
    ├── data/
    │   ├── legal.db
    │   ├── manifest.json
    │   └── schema_version.txt
    ├── tests/
    │   ├── test_known_citations.py
    │   ├── test_versions.py
    │   ├── test_status.py
    │   ├── test_relations.py
    │   ├── test_citation_grammar.py
    │   ├── test_normalization.py
    │   ├── eval_questions_40.tsv   # question → expected provisions
    │   └── fixtures/
    ├── ingest/                    # intermediate fetch/parse staging (RO/EU workspace)
    └── raw/                        # immutable source archive (audit trail)

Runtime retrieval uses only the local normalized database. Scripts are for build/update and MUST NOT be placed in the model context.

If raw originals become too large, move immutable source snapshots to S3-compatible object storage such as Cloudflare R2 or AWS S3 (roadmap; the v1 corpus fits locally, see §34).

Recommended split:

    R2/S3        → immutable original downloads, snapshots, PDFs/XML/XHTML
    SQLite       → normalized metadata, provisions, relations and search indexes

## 7. Storage decision

Use SQLite for the MVP:

    SQLite;

    FTS5;

    optional vector extension only after lexical retrieval works correctly (post-v1).

Do NOT introduce PostgreSQL, Elasticsearch, Pinecone, Qdrant or another external vector database unless scale or operational requirements demonstrate a real need.

Legal retrieval benefits heavily from exact identifiers and lexical matching.

Primary retrieval order:

    1. exact legal-reference lookup;

    2. alias resolution;

    3. domain routing (§13);

    4. structured metadata filters;

    5. FTS5/BM25 lexical search (scoped by domain, §13);

    6. semantic/vector search as fallback or reranker (post-v1).

Semantic similarity MUST NEVER override an exact article citation or a legal-status filter.

## 8. Canonical data model

SQLite schema. All identifiers are canonical (see §16 for the single citation grammar).

### 8.1 acts

An `acts` row is the logical act. Manifestation-specific facts (which URL, which checksum, when retrieved, which parser) belong to `act_versions`, NOT to the act: one act has many manifestations (RO/EN, HTML/PDF, consolidations). The required minimum columns:

    CREATE TABLE acts (
        id TEXT PRIMARY KEY,                -- canonical, e.g. RO:LEGE:506:2004
        jurisdiction TEXT NOT NULL,         -- RO | EU
        source_system TEXT NOT NULL,        -- legislatie_just_ro | eurlex_cellar
        celex TEXT,
        eli TEXT,
        ecli TEXT,
        act_type TEXT NOT NULL,             -- LEGE | OUG | OG | HG | ORDIN | REG | DIR | DEC | ...
        number TEXT,
        year INTEGER,
        title TEXT NOT NULL,
        short_title TEXT,
        issuer TEXT,
        publication_date TEXT,
        status TEXT NOT NULL,               -- in_force | repealed | not_yet_applicable | ...
        authority_class TEXT NOT NULL,      -- binding_legislation | case_law | authority_decision |
                                            -- official_guidance | informational
        version_coverage TEXT NOT NULL      -- point_in_time | current_only
            CHECK (version_coverage IN ('point_in_time', 'current_only')),
        document_status TEXT,               -- final | draft (for guidance/decisions)
        language TEXT NOT NULL,
        is_consolidated INTEGER NOT NULL DEFAULT 0,
        legally_authentic INTEGER,
        official_journal_reference TEXT
    );

Version-capability rule (R2):

    EU acts: version_coverage = point_in_time — dated consolidations are addressable deterministically (CELEX 02016R0679-YYYYMMDD, ELI /eli/reg/2016/679/2016-05-04);

    Romanian acts: version_coverage = current_only — the official source delivers the current form only (SOAP has no point-in-time API; LinkHtml HTML is likewise current). Romania's history accumulates FORWARD from day one (§21); the system never pretends a retroactive point-in-time answer for RO. When an `as_of` falls outside RO coverage the tool returns applicability = NOT_VERIFIED_FOR_DATE with the current text and the earliest archived date (§12, §17).

`scope_provisions` for framework acts is stored as a JSON array of `provision_id`s on the act (or a child table `act_scope_provisions(act_id, provision_id)`); see §5.6.

### 8.2 act_versions (snapshots / manifestations)

One row per downloaded, checksummed snapshot (RO) or per dated consolidation (EU). Per-provision `valid_from`/`valid_to` are DERIVED from diffs between snapshots (hash per canonical citation, §21) — handwritten intervals per paragraph have no source and MUST NOT be entered manually.

    CREATE TABLE act_versions (
        id TEXT PRIMARY KEY,
        act_id TEXT NOT NULL REFERENCES acts(id),
        valid_from TEXT,                 -- EU: real consolidation date; RO: derived (first snapshot where
                                         --   the citation existed), NEVER presented as a legal date
        valid_to TEXT,
        version_date TEXT,               -- consolidation date (EU) / snapshot date (RO)
        consolidation_date TEXT,         -- EU: YYYYMMDD from CELEX/ELI consolidation list
        detected_at TEXT,                -- RO: detection date from polling (§21)
        data_vigoare_reported TEXT,      -- RO: DataVigoare field from the SOAP API (§4.7)
        source_url TEXT NOT NULL,        -- official URL (Cellar/Content or LinkHtml) — provenance
        checksum TEXT NOT NULL,          -- SHA-256 of normalized source text
        retrieved_at TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        language TEXT NOT NULL,
        is_consolidated INTEGER NOT NULL DEFAULT 0,
        legally_authentic INTEGER
    );

Rules:

    detected_at is the date the change was observed; it is NEVER presented to the user as a legal date. Legal presentation for RO uses data_vigoare_reported and, for EU, the real consolidation date;

    never destroy a historical snapshot merely because a newer one exists;

    a snapshot is immutable once inserted.

### 8.3 provisions

    CREATE TABLE provisions (
        id TEXT PRIMARY KEY,
        act_id TEXT NOT NULL REFERENCES acts(id),
        act_version_id TEXT NOT NULL REFERENCES act_versions(id),
        provision_type TEXT NOT NULL       -- article | recital | annex | preamble
            CHECK (provision_type IN ('article', 'recital', 'annex', 'preamble')),
        citable_as_binding_basis INTEGER NOT NULL DEFAULT 1,
            -- 0 for recitals and preamble: considerents/preambule have no autonomous binding force.
            -- This is a data field, not a prompt rule (R5).
        part TEXT,
        title_no TEXT,
        chapter TEXT,
        section TEXT,
        article TEXT,
        paragraph TEXT,
        point TEXT,                        -- numbered points inside a paragraph
        letter TEXT,                       -- lettered points, e.g. lit. (f)
        heading TEXT,
        text TEXT NOT NULL,
        valid_from TEXT,                   -- derived by snapshot diff (§21)
        valid_to TEXT,                     -- derived by snapshot diff (§21)
        sequence INTEGER NOT NULL,
        canonical_citation TEXT NOT NULL   -- §16 grammar; unique per act_version
    );

Preferred retrieval unit: article → paragraph → point/letter. Considerents (`recital`), annexes (`annex`) and the preamble (`preamble`) ARE provisions: they are indexed in FTS and retrievable, but `citable_as_binding_basis = 0` for recitals/preamble — a recital alone never supports a binding claim.

Do NOT use arbitrary fixed-size chunks as the canonical legal unit.

### 8.4 aliases

Informal names and acronyms → act. Axis 1 of retrieval naming (axis 2 is `domains`, §8.9). Hand-curated.

    CREATE TABLE aliases (
        alias TEXT NOT NULL,
        act_id TEXT NOT NULL REFERENCES acts(id),
        priority INTEGER NOT NULL DEFAULT 0
    );

    CREATE UNIQUE INDEX idx_aliases_unique ON aliases(alias);

Examples:

    GDPR → EU:REG:2016:679

    RGPD → EU:REG:2016:679

    General Data Protection Regulation → EU:REG:2016:679

    AI Act → EU:REG:2024:1689 (post-v1)

    DSA → EU:REG:2022:2065 (post-v1)

    legea cookie-urilor → RO:LEGE:506:2004

    Legea 506 → RO:LEGE:506:2004

    Legea 365/2002 → RO:LEGE:365:2002

Alias matching is exact/prefix, lowercase, diacritics-folded (see §9 normalization applied to queries too).

### 8.5 act_relations

    CREATE TABLE act_relations (
        source_act_id TEXT NOT NULL REFERENCES acts(id),
        relation_type TEXT NOT NULL,
        target_act_id TEXT NOT NULL REFERENCES acts(id),
        source_reference TEXT
    );

Allowed relation examples:

    amends; amended_by;

    repeals; repealed_by;

    transposes; transposed_by;

    implements; implemented_by;

    supplements;

    interprets;

    cites;

    related_to.

GDPR ↔ Legea 190/2018 (supplement / implements). Directive (UE) 2019/770 → transposed_by → Romanian implementation act (identified in Etapa B).

### 8.6 cases (post-v1; schema reserved)

    CREATE TABLE cases (
        id TEXT PRIMARY KEY,
        jurisdiction TEXT NOT NULL,
        court TEXT NOT NULL,
        case_number TEXT,
        ecli TEXT,
        decision_date TEXT,
        document_type TEXT,
        title TEXT,
        language TEXT,
        source_url TEXT NOT NULL,
        checksum TEXT NOT NULL,
        retrieved_at TEXT NOT NULL
    );

### 8.7 case_paragraphs (post-v1; schema reserved)

    CREATE TABLE case_paragraphs (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        paragraph_no TEXT,
        text TEXT NOT NULL,
        sequence INTEGER NOT NULL
    );

### 8.8 authority_documents (post-v1; schema reserved)

Fields:

    authority;

    title;

    document number;

    document type;

    adoption date;

    document_status (final | draft);

    topic;

    domains;

    source URL;

    language;

    checksum.

### 8.9 Domains classification (axis 2) and taxonomy

`domains` is a CONTROLLED, CLOSED, FLAT vocabulary of ~30 tags. Two naming axes exist and are distinct: `aliases` (informal name → act, §8.4) and `domains` (controlled topic tag → act AND provision). `domains` is orthogonal to `authority_class`.

v1 frozen tags are the English identifiers stored on acts in `sources/corpus.yaml` (`cookies`, `personal_data`, `withdrawal`, …). `routing_keywords.tsv` MUST target only those tags. Provision-level assignments live in `sources/tags.tsv` and are applied at ingest. The live vocabulary IS this English tag set (corpus.yaml + tags.tsv); the Romanian draft list later in this section is design taxonomy only — do not mix it into routing.

Tags are placed on ACTS and on PROVISIONS (articles, not only acts): marking GDPR art. 44–50 as `personal_data` (or the design tag `transferuri_internationale` after migration) is what makes scoped routing (§13) precise. Assignment is manual, done once per act, revised at Etapa F — never by an LLM classifier. Search prefers provision tags over act tags when any provision carries the routed domain.

    CREATE TABLE domains (
        tag TEXT PRIMARY KEY,
        grp TEXT NOT NULL
    );

    CREATE TABLE act_domains (
        act_id TEXT NOT NULL REFERENCES acts(id),
        tag TEXT NOT NULL REFERENCES domains(tag)
    );

    CREATE TABLE provision_domains (
        provision_id TEXT NOT NULL REFERENCES provisions(id),
        tag TEXT NOT NULL REFERENCES domains(tag)
    );

    CREATE INDEX idx_act_domains_tag ON act_domains(tag);
    CREATE INDEX idx_provision_domains_tag ON provision_domains(tag);

Closed taxonomy (v1 tags marked ✱):

Privacy:

    temeiuri_legale ✱       consimtamant ✱         interes_legitim ✱
    transparenta ✱          drepturi_persoane ✱   transferuri_internationale ✱
    securitate ✱            breach ✱              dpia ✱
    dpo ✱                   cookies ✱             marketing_direct ✱
    minori ✱                profilare ✱           retentie ✱
    imputerniciti ✱         confidentialitate_comunicatii ✱

E-commerce:

    informare_precontractuala ✱  incheiere_contract_online ✱
    pret ✱                      retragere ✱
    garantii ✱                  continut_digital ✱
    clauze_abuzive ✱            practici_incorecte ✱
    abonamente ✱                marketplace ✱

General / roadmap (post-v1):

    contracte       raspundere      societati
    proprietate_intelectuala        dsa     ai_act

Every v1 act has ≥ 1 domain; every domain has ≥ 1 act (gate, §32 Etapa F). Tag assignments for v1 acts are frozen in `sources/tags.tsv` (act/provision, tag) during Etapa F and verified against the ingested text.

### 8.10 authority_rank

Numerical rank used only as a ranking heuristic — never as a legal hierarchy and never replacing real rules of precedence/applicability. Stored as a TABLE, not hardcoded in ranking code (minor refinement):

    CREATE TABLE authority_ranks (
        authority_class TEXT PRIMARY KEY,
        rank INTEGER NOT NULL
    );

Seed values:

    EU_PRIMARY_LAW            100
    CJEU_BINDING              95
    EU_REGULATION             90
    EU_DIRECTIVE              88
    RO_LEGE                   85
    RO_OUG / RO_OG            80
    RO_HG                     75
    EDPB_GUIDANCE             50
    ANSPDCP_DECISION          45
    ANSPDCP_GUIDANCE          40
    INFORMATIONAL             20

### 8.11 Required indexes

Minimum indexes beyond the FTS indexes (§10):

    CREATE INDEX idx_provisions_actpath ON provisions(act_id, article, paragraph);
    CREATE UNIQUE INDEX idx_canonical_per_version ON provisions(act_version_id, canonical_citation);
    CREATE INDEX idx_act_versions_act ON act_versions(act_id, valid_from);
    CREATE INDEX idx_aliases ON aliases(alias);            -- + unique index on alias, §8.4
    CREATE INDEX idx_acts_status ON acts(status);

## 9. Romanian text normalization (R6)

Normalization is a correctness requirement for exact retrieval, not cosmetics.

Two concrete problems MUST be fixed at ingest AND applied to every query:

1. ș/ț cedilă (U+015F, U+0163) vs virgulă (U+0219, U+021B).

   Romanian texts mix the two forms (cedilă is a Windows-1250 legacy). Exact search fails silently across the two encodings. Fix:

       NFC normalize everything first;
       map U+015F→U+0219 and U+0163→U+021B (and the capitals) at ingest;
       apply the same mapping to user queries before matching.

   Test requirement: a query typed with cedilă MUST find stored text with virgulă, and vice versa (Etapa E gate).

2. Morphology without a Romanian stemmer.

   Diacritics folding alone does not make "consimțământ" find "consimțământului". FTS5 `unicode61 remove_diacritics 2` (SQLite ≥ 3.27.0) folds diacritics; lemmas are added by a HAND-WRITTEN table of ~200 legal terms (consimțământ, prelucrare, operator, împuternicit, retragere, clauze abuzive, drept de retragere, …) stored in `sources/lemmas_ro.tsv` and applied as query expansion (§10, §13 Level 3). One afternoon of handwriting beats embeddings on this corpus — this is the real reason embeddings are post-v1, not merely phase ordering.

Normalization pipeline (scripts/normalize.py):

    strip BOM → NFC → cedilă→virgulă → collapse whitespace → (optional) ASCII-fold copy for alias/FTS matching.

Raw snapshots are NEVER re-written; normalization produces derived text only (see §18).

## 10. Search indexes

Create separate FTS indexes for:

    fts_legislation;

    fts_case_law (post-v1);

    fts_guidance (post-v1).

Index the classes separately; do NOT put everything into one undifferentiated collection.

FTS5 configuration:

    tokenize = "unicode61 remove_diacritics 2"     -- SQLite ≥ 3.27.0

Content columns: provision text, heading, act title, canonical citation, domains (as indexed sidecar fields where useful).

Lemma expansion (§9): at query time, each query token is expanded with its hand-written lemma/synonym set from `lemmas_ro.tsv` (e.g. consimtamant → consimtamant OR consimtamantului OR consimtamantul ...). Expansion is applied inside the scoped search (§13 Level 3).

Search ranking (in order):

    exact canonical citation match;

    exact alias match;

    scoped BM25 score (§13);

    authority_rank (§8.10);

    current-version bonus;

    (post-v1) semantic score.

A guidance document with many keyword matches MUST NOT outrank an exact binding provision solely because of term frequency — v1 search defaults to corpus = legislation and never mixes guidance unless explicitly requested (§12, §30).

## 11. Optional embeddings (post-v1)

Embeddings are OPTIONAL and MUST NOT be implemented until:

    exact lookup works;

    aliases work;

    domain routing works;

    FTS works;

    dates/version coverage work;

    source-class filtering works.

If enabled later, embed legal units rather than arbitrary token windows:

    [ACT TITLE] [CHAPTER/SECTION] Article [X] Paragraph [Y] [TEXT]

For case law (post-v1):

    [COURT] [CASE NUMBER] [DECISION DATE] Paragraph [N] [TEXT]

Semantic search is for conceptual discovery, never for legal-status determination.

## 12. Tool interface — jurist CLI (5 subcommands)

This section is self-contained: an implementer needs nothing else to call the tools correctly. Runtime exposes ONE CLI, `jurist`, with exactly five subcommands, each accepting `--json` and emitting one JSON object on stdout. No direct SQL access for the model. The same code may be wrapped by an MCP server later; the CLI is the contract.

    Usage: jurist <subcommand> [flags] [--json]
    Subcommands:
        jurist resolve        — resolve_act: name/acronym/number → act
        jurist search         — legal_search: scoped keyword search over provisions
        jurist provision      — get_provision: exact provision text
        jurist related        — find_related_law: legal relations
        jurist corpus-status  — corpus_status: what the corpus contains

Every response object shares the common envelope:

    {
      "tool": "jurist <subcommand>",
      "ok": true,                          // or false + "error"
      "as_of": "YYYY-MM-DD",               // resolved date; default: today
      "warnings": [ ... ],                 // MUST be present, may be empty
      "next_action": null | { "tool": "...", "args": { ... } }
    }

`warnings` and `next_action` are part of the contract on EVERY response (R3): the agent must read `warnings` before concluding and may follow `next_action` verbatim. Payload arrays use ONE canonical key per tool — `matches` (resolve), `results` (search), `provision` (provision); no plural aliases are emitted. The following signal fields are returned by relevant tools (see §30 for the rule→signal mapping):

    status                        — in_force | repealed | not_yet_applicable
    in_force_on_as_of             — boolean
    amended_since                 — boolean | null
    version_coverage              — point_in_time | current_only
    applicability                 — VERIFIED_AS_OF | NOT_VERIFIED_FOR_DATE
    earliest_version_date         — when applicability = NOT_VERIFIED_FOR_DATE
    last_checked / corpus_age_days — freshness (§21); STALE_CORPUS warning over threshold
    guidance_hits_excluded        — legal_search default-legislation filter counter

Error format (any subcommand):

    { "tool": "...", "ok": false, "error": { "code": "UNKNOWN_ACT" | "NOT_FOUND" | "BAD_ARGS" | "UNSUPPORTED_CORPUS", "message": "..." }, "as_of": "...", "warnings": [], "next_action": null }

### 12.1 jurist resolve (resolve_act)

Purpose: resolve acronyms, informal names, act numbers, aliases.

    CLI: jurist resolve --reference "legea cookie-urilor" [--jurisdiction RO] [--json]

    Input JSON ({} for the --json form):
    {
      "reference": "legea cookie-urilor",
      "jurisdiction": "RO"                      // optional filter
    }

    Output:
    {
      "tool": "jurist resolve",
      "ok": true,
      "matches": [
        {
          "act_id": "RO:LEGE:506:2004",
          "official_title": "Legea nr. 506/2004 privind prelucrarea datelor cu caracter personal și protecția vieții private în sectorul comunicațiilor electronice",
          "short_title": null,
          "act_type": "LEGE", "number": "506", "year": 2004,
          "jurisdiction": "RO",
          "status": "in_force",
          "authority_class": "binding_legislation",
          "authority_rank": 85,
          "version_coverage": "current_only",
          "domains": ["cookies", "marketing_direct", "confidentialitate_comunicatii"],
          "scope_provisions": ["RO:LEGE:506:2004:ART:1"],
          "aliases": ["legea cookie-urilor", "Legea 506"],
          "summary_ro": "Confidențialitatea comunicațiilor electronice ...",
          "source_url": "https://legislatie.just.ro/Public/DetaliiDocument/<id>",   // LinkHtml recorded at ingest
          "last_checked": "2026-08-27", "corpus_age_days": 2
        }
      ],
      "warnings": [],
      "next_action": { "tool": "jurist search", "args": { "query": "<original question terms>", "domains": ["cookies"] } }
    }

`source_url` above is illustrative; the actual official URL is whatever `LinkHtml`/Cellar returned at ingest and MUST be recorded in `sources/corpus.yaml` (URLs are provenance, never invented).

### 12.2 jurist search (legal_search)

Purpose: conceptual or keyword search over provisions, scoped by corpus class, jurisdiction and domains (§13 routing).

    CLI: jurist search --query "banner cookie consimtamant" [--corpus legislation] [--jurisdiction RO] [--domains cookies] [--authority-class binding_legislation] [--as-of 2025-01-01] [--limit 10] [--json]

    Input JSON:
    {
      "query": "banner cookie consimtamant",
      "corpus": "legislation",                  // legislation | case_law | guidance; DEFAULT legislation (v1: only legislation is populated)
      "jurisdiction": ["RO", "EU"],
      "domains": ["cookies"],                   // optional; scopes FTS (§13 Level 3)
      "authority_classes": ["binding_legislation"],   // default binding_legislation
      "as_of": "2025-01-01",                    // default: today
      "limit": 10                               // default 10
    }

    Output:
    {
      "tool": "jurist search",
      "ok": true,
      "corpus": "legislation",
      "guidance_hits_excluded": 0,              // count of guidance hits filtered by the default (§30 Rule 9)
      "results": [
        {
          "provision_id": "RO:LEGE:506:2004:ART:4:P:5",
          "act_id": "RO:LEGE:506:2004",
          "act_title": "Legea nr. 506/2004 ...",
          "provision_type": "article",
          "citable_as_binding_basis": 1,
          "article": "4", "paragraph": "5", "point": null, "letter": null,
          "snippet": "Stocarea de informații sau obținerea accesului la informațiile stocate în echipamentul terminal al unui abonat ...",
          "score": 0.91,
          "status": "in_force", "in_force_on_as_of": true, "amended_since": null,
          "authority_class": "binding_legislation", "authority_rank": 85,
          "version_coverage": "current_only",
          "canonical_citation": "RO:LEGE:506:2004:ART:4:P:5"
        }
      ],
      "warnings": [],
      "next_action": { "tool": "jurist provision", "args": { "citation": "RO:LEGE:506:2004:ART:4:P:5", "as_of": "2025-01-01" } }
    }

The search payload key is `results` (single canonical array; no plural alias). `next_action` passes the top hit's canonical `citation` directly to `provision`.

Directive hits carry the transposition signal inline:

    {
      "provision_id": "EU:DIR:2019:770:ART:7",
      ...,
      "transposed_by": [ { "act_id": "RO:LEGE:000:2018", "title": "...", "status": "in_force" } ]
    }
    "warnings": ["DIRECTIVE_NOT_DIRECTLY_APPLICABLE: Directiva (UE) 2019/770 needs national transposition before it binds private parties; transcribed acts above."]

When routing levels 1–3 (§13) return nothing above threshold, the response is honest rather than hollow:

    "status": "NO_MATCH_ABOVE_THRESHOLD",
    "candidate_acts": [ { "act_id": "...", "title": "...", "summary_ro": "..." } ],
    "warnings": ["NO_MATCH_ABOVE_THRESHOLD: reformulate or state the gap; do not conclude from these summaries alone."]

### 12.3 jurist provision (get_provision)

Purpose: exact legal text + full status metadata. Absorbs the former separate context tool via the `context` parameter and the former separate status tool via always-present status fields (R4).

    CLI: jurist provision --act GDPR --article 6 --paragraph 1 --point f [--context article] [--as-of 2018-05-25] [--json]

Article-level lookup works: `--article 6` without `--paragraph` returns the whole article — its stored row when the source has an explicit article lead, otherwise reconstructed deterministically from its paragraph/letter/point children.

    Input JSON:
    {
      "act": "GDPR",                 // alias, canonical id, or human name (§8.4)
      "article": "6",
      "paragraph": "1",
      "point": "f",
      "as_of": "2018-05-25",         // default: today
      "context": "article"           // null | "article" | "section"; context retrieval is this
                                     // parameter: article = full article, section = article + neighbours
    }

    Output:
    {
      "tool": "jurist provision",
      "ok": true,
      "as_of": "2018-05-25",
      "provision": {
        "provision_id": "EU:REG:2016:679:ART:6:P:1:L:f",
        "act_id": "EU:REG:2016:679",
        "act_title": "Regulamentul (UE) 2016/679",
        "provision_type": "article",
        "citable_as_binding_basis": 1,
        "article": "6", "paragraph": "1", "letter": "f",
        "text": "prelucrarea este necesară în scopul intereselor legitime urmărite de operator ...",
        "canonical_citation": "EU:REG:2016:679:ART:6:P:1:L:f",
        "full_article_available": true,                        // Rule 6: snippets are never conclusions
        "context_call": "jurist provision --act GDPR --article 6 --context section",  // ready-to-run follow-up
        "status": "in_force", "in_force_on_as_of": true, "amended_since": false,
        "version_coverage": "point_in_time",
        "applicability": "VERIFIED_AS_OF",                    // or NOT_VERIFIED_FOR_DATE, below
        "earliest_version_date": "2018-05-25",
        "valid_from": "2018-05-25", "valid_to": null,
        "source_url": "https://eur-lex.europa.eu/legal-content/RO/TXT/?uri=CELEX:32016R0679",
        "last_checked": "2026-08-27", "corpus_age_days": 2
      },
      "warnings": [],
      "next_action": null
    }

`provision` is the canonical payload key (single object; no plural alias); `context` carries the requested neighboring rows (`context: "article"` = all rows of the article, `"section"` = article + neighbours).

Historical query on a current_only (RO) act:

    jurist provision --act RO:LEGE:506:2004 --article 4 --as-of 2020-01-01

    "warnings": ["RO:LEGE:506:2004 is version_coverage=current_only; the source API provides no form at 2020-01-01."],
    "provision": { ..., "version_coverage": "current_only", "applicability": "NOT_VERIFIED_FOR_DATE",
                   "earliest_version_date": "2026-08-01",   // first archived snapshot
                   "text": "<current form>" }

The agent MUST relay `NOT_VERIFIED_FOR_DATE` — it never silently applies today's RO wording to a past event (Rule 3, §14).

Freshness: when `corpus_age_days` exceeds the configured threshold (default 30), responses add `"warnings": ["STALE_CORPUS: ..."]` (§21).

### 12.4 jurist related (find_related_law)

Purpose: retrieve legal relationships (transposition, implementation, amendment, repeal, supplements).

    CLI: jurist related --act-id EU:DIR:2019:770 --relations transposed_by [--json]

    Input JSON:
    {
      "act_id": "EU:DIR:2019:770",
      "relations": ["transposed_by", "implements", "amended_by", "supplements"]
    }

    Output:
    {
      "tool": "jurist related",
      "ok": true,
      "relations": [
        {
          "source_act_id": "EU:DIR:2019:770",
          "relation_type": "transposed_by",
          "target_act_id": "RO:LEGE:<id>:<year>",
          "target_title": "...",
          "target_status": "in_force",
          "source_reference": "..."
        }
      ],
      "warnings": [],
      "next_action": { "tool": "jurist resolve", "args": { "reference": "RO:LEGE:<id>:<year>" } }
    }

### 12.5 jurist corpus-status (corpus_status)

Purpose: the agent must know what the corpus contains (R8) to distinguish "not in corpus" from "does not exist in law". Renders `sources/corpus.yaml` + live DB state.

    CLI: jurist corpus-status [--json]

    Input JSON: {}

    Output:
    {
      "tool": "jurist corpus-status",
      "ok": true,
      "schema_version": 1,
      "last_build": "2026-08-29T07:00:00Z",
      "counts": { "acts": 24, "provisions": 1331, "aliases": 61, "act_versions": 31, "relations": 9 },
      "sources": {
        "legislatie_just_ro": { "method": "SOAP",  "last_sync": "2026-08-29T07:00:00Z", "documents": 18 },
        "eurlex_cellar":      { "method": "CELLAR", "last_sync": "2026-08-29T07:00:00Z", "documents": 6 }
      },
      "acts": [
        { "act_id": "RO:LEGE:506:2004", "title": "...", "version_coverage": "current_only",
          "status": "in_force", "last_checked": "2026-08-29", "domains": ["cookies", ...], "scope_provisions": [...] }
      ],
      "domains": { "cookies": 2, "consimtamant": 3, ... }
    }

The compact corpus coverage table (act, version_coverage, last_sync) is repeated in SKILL.md (Etapa I) so the model sees it without a tool call.

## 13. Routing procedure (R14)

The core retrieval gap: a user asks "trebuie banner de cookies?" but the law text says "stocarea de informații sau obținerea accesului la informațiile stocate în echipamentul terminal al unui abonat" — zero word overlap. BM25 over the whole corpus finds nothing. Routing converts this hard search problem into an easy one. Three levels, in order:

Level 1 — exact reference. User cites "art. 6 GDPR", "Legea 365/2002", "GDPR", "legea cookie-urilor" → citation parser/alias matcher → `jurist resolve` / `jurist provision` directly, no search. Near-100% precision; covers a large share of real questions.

Level 2 — domain routing. Query terms are matched against the HAND-WRITTEN keyword→domain table (`sources/routing_keywords.tsv` → table `routing_keywords`), not model guessing. Example rows:

    cookies, banner cookie, cookie banner, terminal equipment          → cookies
    consimtamant, consent, opt-in                                      → consimtamant
    marketing direct, newsletter, spam                                 → marketing_direct
    retragere, drept de retragere, withdrawal                          → retragere
    clauze abuzive, unfair terms                                       → clauze_abuzive
    garantie, garantii, warranty                                       → garantii
    abonament, subscription, renew                                     → abonamente
    pret, price, punere la dispozitie a pretului                       → pret
    ...

Keyword matching is diacritics-folded (§9). The result is a set of `domains`; unmatched queries fall through to an unscoped legislation FTS search.

Level 3 — scoped FTS/BM25. FTS runs SCOPED to provisions/acts tagged with the routed domains (via provision_domains/act_domains, §8.9) with lemma expansion from `lemmas_ro.tsv` (§10). Inside Legea 506/2004 + GDPR, finding the cookies article is trivial. The routing scope can also narrow by jurisdiction/authority_class.

Fallback — honest no-match. If levels 1–3 return nothing above threshold, the tool returns the `summary_ro` of candidate acts in the routing scope with `status: "NO_MATCH_ABOVE_THRESHOLD"` (§12.2). The agent reformulates or states lack of coverage — it never invents.

The table `routing_keywords` is reviewed by a human at Etapa F and revised as the eval (§24) exposes gaps.

## 14. Agent operating rules

Rule 1 — Retrieval before conclusion

For every substantive legal conclusion, the agent MUST retrieve relevant authority first. The agent MUST NOT rely on memorized law when the local corpus can be queried.

Rule 2 — Exact citation beats semantic similarity

If the user provides an article, law number, CELEX, ELI, ECLI or case number: resolve it; retrieve it directly; verify status/date; do not replace it with semantically similar documents.

Rule 3 — Determine legal date

For every query, determine whether it concerns current law, a historical event, or a future applicability date. If the user asks about conduct in the past:

    EU (point_in_time): use the dated consolidation — verifiable, deterministic (applicability = VERIFIED_AS_OF);

    RO (current_only): use the current form ONLY WITH the tool's verdict — applicability = NOT_VERIFIED_FOR_DATE + earliest_version_date (§12.3). Never silently apply today's wording to a past event; never present a snapshot detection date as a legal date (§21).

Rule 4 — Determine jurisdiction (RO / EU / both / outside scope — if outside scope, say so).

Rule 5 — Distinguish B2B and B2C where material; never auto-apply consumer protections to a purely B2B scenario.

Rule 6 — Read the full relevant provision. Every `jurist provision` response includes `full_article_available: true` and a ready-made `context_call`; a final conclusion MUST be based on the provision/context, not on a snippet (mechanism in data, not just prompt — R3).

Rule 7 — Check act status. `status`, `in_force_on_as_of` and `amended_since` are present in EVERY relevant tool response — the agent has nothing to request and cannot skip them (R3).

Rule 8 — Check EU/national interaction. A result on an EU Directive always carries `transposed_by` inline and the warning `DIRECTIVE_NOT_DIRECTLY_APPLICABLE` — the agent does not need to remember Rule 8; the response states it (§12.2). EU Regulations are directly applicable but national supplementary legislation is still retrieved where material.

Rule 9 — Legislation first. `jurist search` defaults to `corpus: legislation` and `authority_classes: binding_legislation`; any filtered guidance hits are reported as `guidance_hits_excluded` so the agent knows guidance exists without requesting it (R3). Case law and guidance searches are explicit, opt-in, and post-v1.

Rule 10 — Never fabricate. Never invent article numbers, paragraphs, case numbers, ECLI, CELEX, dates, fines, authority positions, quotations, act status. If retrieval does not verify a claim, state that it is unverified.

Rule 11 — Două axe pentru sarcină și statut. Axa A este sarcina cerută: `rewrite` livrează un text rescris în limitele textului primit; `describe_source` descrie ce arată o sursă oficială identificată; `answer_legal` livrează o concluzie juridică bazată pe retrieval și citări; `audit_perception` livrează pasaje care pot fi citite ca îndrumare juridică. Axa B este statutul fiecărei afirmații din livrabil: `verified` (retrieval efectuat, citare canonică, dată și statut verificate), `source_reported` (apare într-o sursă oficială identificată, fără concluzie despre efect), `editorial` (provine din textul furnizat, neverificat independent), `out_of_corpus` (afirmație juridică pe care corpusul local nu o poate acoperi) și `unverified` (nesusținută, de marcat sau de eliminat). Regula generală este că fiecare afirmație materială din livrabil poartă un statut. O cerere mixtă este un singur livrabil cu statute amestecate, nu un caz pentru separarea rezultatelor. La `rewrite` se păstrează sensul și proveniența textului primit, fără adăugarea unor afirmații juridice; la `describe_source` se descrie doar ce arată sursa; `answer_legal` folosește `verified` sau `out_of_corpus` după acoperirea corpusului. Un disclaimer nu justifică o afirmație inventată sau nesusținută.

Rule 12 — Auditul de percepție juridică (`audit_perception`) semnalează DUPĂ FORMA LINGVISTICĂ, nu după suspiciunea că afirmația ar fi falsă. Auditul nu spune niciodată „probabil e greșit” și nu stabilește corectitudinea juridică. Testul primar este SUBIECTUL propoziției: `aplicație` / `flux` / `ecran` = descriere de produs, fără semnal; `lege` / `autoritate` / `act normativ` = afirmație juridică, cu semnal; `utilizatorul în situația lui concretă` = afirmație de aplicabilitate, cu semnal prioritar. Contrastele sunt: „Verifică documentul afișat” — produs, fără semnal; „Legea impune verificarea documentului” — juridic, semnal; „Aplicația generează documentul pe baza datelor introduse” — produs, fără semnal; „Documentul este obligatoriu pentru situația ta” — aplicabilitate, semnal prioritar. Lexicul de semnale folosește exact categoriile `obligatie`, `semnatar`, `aprobare`, `scutire`, `efect_juridic`, `conformitate`, `exhaustivitate`, `termen_cuantum`, `sanctiune`. Nivelul de risc este DERIVAT din constatări, nu apreciat: ridicat dacă apare `efect_juridic`, `conformitate`, `sanctiune` sau orice afirmație cu subiectul utilizatorului în situația lui concretă; mediu dacă apare `obligatie`, `semnatar`, `aprobare`, `scutire`, `exhaustivitate` sau `termen_cuantum`, fără o constatare de nivel ridicat; scăzut dacă nu există nicio constatare și textul descrie funcții sau pași ai aplicației.

Rule 13 — `out_of_corpus`. Corpusul acoperă GDPR, cookies, e-commerce, contracte la distanță și clauze abuzive, în dreptul RO+UE. Pentru materii din afara corpusului — inclusiv CAEN, ONRC, înființare sau modificare de firmă, fiscal, muncă și penal — agentul marchează afirmația `out_of_corpus` și trimite la sursa oficială externă sau la un jurist. Agentul nu promite niciodată retrieval ori verificare pe care corpusul nu le poate onora și nu spune „urmează să verific” pentru o materie absentă din corpus.

Convenția de placeholder: forma fixă este `[de verificat: <ce anume>]`. Placeholder-ul supraviețuiește în livrabil; agentul nu îl rezolvă din memoria modelului și nu îl scoate în tăcere.

## 15. Required retrieval procedure

For a normal legal question:

    USER QUESTION
        ↓
    extract facts and legal issue
        ↓
    determine jurisdiction
        ↓
    determine relevant date
        ↓
    determine B2B/B2C and actor roles if material
        ↓
    Level 1: resolve known references (resolve / provision)
        ↓
    Level 2: route to domains (keyword table)
        ↓
    Level 3: scoped search (search, corpus=legislation)
        ↓
    retrieve exact provisions (provision)
        ↓
    verify status/version/date (signals in every response)
        ↓
    find related EU/RO law (related)
        ↓
    (post-v1) case law then guidance, explicitly
        ↓
    reason from retrieved authorities
        ↓
    produce cited answer (§27)

The agent MUST NOT skip directly from the user question to a legal conclusion, and MUST respect every `warning` and `applicability` verdict returned by the tools.

## 16. Citation policy

Single citation grammar — one grammar, one parser, one formatter, round-trip tested (minor refinement). The parser/formatter accept lowercase and canonicalize output; a round-trip test is part of the test suite (`test_citation_grammar.py`).

Canonical form is one path grammar with jurisdiction-specific act-key ordering (matching official identifiers):

    {JUR}:{TYPE}:{ACT_KEY_1}:{ACT_KEY_2}:{PATH}
    EU → ACT_KEY_1=YEAR, ACT_KEY_2=NUMBER  (e.g. EU:REG:2016:679)
    RO → ACT_KEY_1=NUMBER, ACT_KEY_2=YEAR  (e.g. RO:LEGE:506:2004)
    PATH := ART:{a}[:P:{p}[:L:{l} | POINT:{n}]] | REC:{n} | ANN:{n} | PRE
    JUR := RO | EU | CJEU (post-v1)

Examples:

    EU:REG:2016:679:ART:6:P:1:L:f          Regulamentul (UE) 2016/679, art. 6 alin. (1) lit. (f)
    EU:DIR:2019:770:ART:7                  Directiva (UE) 2019/770, art. 7
    RO:LEGE:506:2004:ART:4:P:5             Legea nr. 506/2004, art. 4 alin. (5)
    RO:OUG:34:2014:ART:9                   OUG nr. 34/2014, art. 9
    EU:REG:2016:679:REC:32                 GDPR, considerentul 32 (non-binding: citable_as_binding_basis = 0)
    EU:REG:2016:679:PRE                    GDPR, preambul (non-binding)
    RO:LEGE:193:2000:ANN:1                 anexa Legii nr. 193/2000
    CJEU:C:131:12:P:32                     CJUE, C-131/12, pct. 32 (post-v1)

Rules:

    every material legal conclusion carries at least one retrieved citation at article/paragraph level;

    the displayed (human) citation and the canonical ID always travel together, and the official source link is exposed when available;

    recitals and preamble are retrievable but never the sole support of a binding claim (citable_as_binding_basis = 0).

## 17. Consolidated texts and version coverage

Consolidated texts are extremely useful for retrieval but MUST be modeled correctly. For every consolidated version store:

    is_consolidated = true
    version_date = ...
    valid_from = ...
    valid_to = ...

For EU material preserve the distinction between the original Official Journal act, amendment acts, and consolidated working text; a consolidated EU text is never labeled as the authentic Official Journal publication.

Version-capability semantics are asymmetrical by design (R2):

    point_in_time (EU): an `as_of` maps to a real dated consolidation; legal answer is deterministic. earliest_version_date = first available consolidation.

    current_only (RO): the source API delivers only the current form. RO history accumulates FORWARD from v1 launch via weekly snapshots (§21); until coverage reaches an `as_of`, tools return applicability = NOT_VERIFIED_FOR_DATE with the current text (§12.3). This is the honest, fix-by-default behavior that replaces the old silent failure: the RO source cannot answer "what did the law say in 2022" today — the system says exactly that.

## 18. Source provenance and auditability

Every stored snapshot MUST have:

    canonical source URL (Cellar/Content official link or SOAP LinkHtml);

    source system;

    retrieved timestamp;

    checksum (SHA-256);

    parser version;

    language;

    source document identifier (CELEX / ELI / (an, numar));

    version/applicability facts where known (consolidation_date / data_vigoare_reported).

Provenance fields live on `act_versions` (§8.2) and in `manifest.json`/`raw/` (§21, §22). Raw snapshots are IMMUTABLE: normalization derives a representation, it never alters the original.

## 19. Ingestion pipeline

Two official sources, two branches, one common tail.

Romanian branch (SOAP discovery + LinkHtml HTML, §4.7):

    corpus.yaml fetch spec (tip, numar, an)
        → GetToken() → tokenKey
        → Search(tokenKey, 1, N, SearchAn=<year>, SearchNumar=<number>)
        → metadata {Titlu, Emitent, Numar, TipAct, Publicatie, DataVigoare, LinkHtml}
        → fetch official consolidated HTML at LinkHtml (SOAP Text is the original form; do not ingest it as canonical)
        → normalize (NFC, cedilă→virgulă — §9)
        → immutable raw snapshot (checksum of HTML, retrieved_at, detected_at, data_vigoare_reported)
        → parse legal structure (parse_ro.py DOM)
        → canonical IDs → insert → FTS

EU branch (Cellar, §4.4):

    corpus.yaml fetch spec (celex, lang)
        → Cellar fetch of the consolidated XHTML/Formex
          (Accept: application/xhtml+xml; without Accept, Cellar returns RDF ontology, not text)
        → content gate (no rdf:RDF, has 'Articolul N', minimum size)
        → immutable raw snapshot (checksum, retrieved_at)
        → parse legal structure (parse_eu.py)
        → canonical IDs → insert → FTS

Common tail:

    validate (structural/temporal tests, §24)
        → update manifest
        → atomically publish legal.db

## 20. Ingestion priorities

    EU: CELEX/ELI discovery → EUR-Lex metadata → Cellar structured content (XML, XHTML) → official PDF only as archive/fallback.

    Romania: Portal Legislativ SOAP for discovery/metadata (§4.7) → official LinkHtml HTML → parse_ro → Monitorul Oficial reference for authenticity.

No ingestion path may depend on visual PDF layout unless unavoidable; never on HTML scraping of the portal search UI. Fetching the official act page identified by SOAP LinkHtml is required.

## 21. Update strategy (R12)

Two mechanisms, one per source class — because only one of them yields real legal dates.

Romanian detection — checksum polling.

    daily job: for each act, SOAP Search(SearchAn, SearchNumar) → fetch LinkHtml HTML → normalize → SHA-256 of HTML → compare with current snapshot.

    different ⇒ new snapshot (act_versions row) with detected_at = detection date. Store the API's DataVigoare separately as data_vigoare_reported. Do not checksum SOAP Text as if it were the consolidated act.

    RULE: detected_at is NEVER presented as a legal date; the agent may only present data_vigoare_reported (and, for EU, the real consolidation date).

EU detection — real versions.

    each consolidated act has a dated consolidation list (CELEX base 0XXXXRNNNN → 0XXXXRNNNN-YYYYMMDD).

    poll the consolidation list; a new date ⇒ new act_version with valid_from = the REAL date (point-in-time is legally correct here).

Provision-level diff (after any new snapshot):

    hash every canonical citation (old vs new) → list added / modified / removed.

    This simultaneously (a) populates per-provision valid_from/valid_to (§8.3, R2.4) and (b) generates a human-readable CHANGELOG.md — the diff was going to be computed anyway.

Freshness reaching the agent:

    every relevant tool response carries last_checked and corpus_age_days for the cited act (§12). Above the threshold (default 30 days): warning STALE_CORPUS. The agent must not assert yesterday-checked and eight-months-ago-checked law with equal confidence.

Process summary:

    run polls
        → unchanged: no-op
        → changed: archive new source → parse → preserve old version → diff per provision →
          update CHANGELOG.md → rebuild affected indexes → regression tests → atomic publish

Weekly RO archiving starts at v1 launch (R2.3): incurred history, never retroactive; declared honestly via NOT_VERIFIED_FOR_DATE until coverage exists.

## 22. manifest.json

    {
      "skill": "jurist",
      "schema_version": 1,
      "built_at": "2026-08-29T07:00:00Z",
      "sources": {
        "legislatie_just_ro": { "method": "SOAP", "last_sync": "2026-08-29T07:00:00Z", "documents": 18 },
        "eurlex_cellar":      { "method": "CELLAR", "last_sync": "2026-08-29T07:00:00Z", "documents": 6 }
      },
      "acts": {
        "RO:LEGE:506:2004": { "versions": 2, "last_checked": "2026-08-29", "checksum_current": "<sha256>" }
      }
    }

The manifest is machine-readable state for the update pipeline (§21); `jurist corpus-status` renders it.

## 23. sources/corpus.yaml

`corpus.yaml` is the single source of truth for WHAT defines the corpus — editable, human-maintained. Machine-generated freshness (checksum, last_checked, version_coverage) lives in the DB; what the corpus MEANS (aliases, domains, summary_ro, scope_provisions) lives here, because the official sources never provide it.

    schema_version: 1
    corpus:
      - id: RO:LEGE:506:2004
        fetch:
          method: SOAP
          source: legislatie_just_ro
          tip: LEGE
          numar: 506
          an: 2004
        source_url: "https://legislatie.just.ro/Public/DetaliiDocument/<id>"   # LinkHtml, recorded at ingest
        authority_class: binding_legislation
        version_coverage: current_only
        domains: [cookies, marketing_direct, confidentialitate_comunicatii]
        scope_provisions: ["RO:LEGE:506:2004:ART:1"]
        aliases:
          - "legea cookie-urilor"
          - "Legea 506"
          - "legea privind confidentialitatea in comunicatiile electronice"
        summary_ro: >
          Confidențialitatea comunicațiilor electronice: stocarea de informații pe
          echipamentul terminal (cookies) și consimțământul necesar, marketing direct,
          date de trafic și de localizare.

      - id: EU:REG:2016:679
        fetch:
          method: cellar
          source: eurlex_cellar
          celex: 32016R0679
          lang: ro
        source_url: "https://eur-lex.europa.eu/legal-content/RO/TXT/?uri=CELEX:32016R0679"
        authority_class: binding_legislation
        version_coverage: point_in_time
        domains: [temeiuri_legale, consimtamant, interes_legitim, transparenta,
                  drepturi_persoane, transferuri_internationale, securitate, breach,
                  dpia, dpo, profilare, retentie, imputerniciti, minori]
        aliases: [GDPR, RGPD, "Regulamentul general privind protecția datelor"]
        summary_ro: >
          Regulament general privind protecția datelor: temeiuri de prelucrare,
          consimțământ, drepturile persoanelor vizate, transferuri internaționale,
          securitate și notificarea încălcărilor, DPIA, DPO.

      - id: EU:DIR:2019:770
        fetch: { method: cellar, source: eurlex_cellar, celex: 32019L0770, lang: ro }
        authority_class: binding_legislation
        version_coverage: point_in_time
        domains: [continut_digital]
        aliases: ["directiva continut digital", "Digital Content Directive"]
        transposed_by: [ "RO:LEGE:<id>:<year>" ]     # filled in Etapa B/E

Rules: every `fetch` spec must actually resolve in the source (gate §32 Etapa B); every inclusion decision after the audit is human.

## 24. Validation and evaluation

The database MUST NOT be published without automated checks.

Structural tests

    every provision has an act;

    every act has at least one act_version with a source URL;

    every canonical citation is unique within its version (unique index §8.11);

    article sequences are valid (no gaps for v1 acts, §32 Etapa D);

    no empty legal-text rows;

    no duplicate version checksums unless expected.

Temporal tests

    valid_from <= valid_to when both exist;

    current acts have a valid current version;

    historical versions do not overlap unexpectedly;

    repealed acts are not returned as current by default;

    RO current_only acts: applicability verdicts are NOT_VERIFIED_FOR_DATE outside coverage (§17).

Known-citation regression tests

Keep a fixed list of important legal references verified to resolve: GDPR; Law 506/2004; Law 190/2018; Law 365/2002; GEO 34/2014; OG 21/1992; Law 193/2000; DSA (post-v1); AI Act (post-v1); Civil Code (post-v1).

Citation grammar round-trip: every canonical citation stringifies from its parsed parts and re-parses to the identical parts (`test_citation_grammar.py`).

Retrieval evaluation (R10) — the product gate

40 handwritten questions (question → expected provision set), stored in `tests/eval_questions_40.tsv`, run by `scripts/eval_recall.py` at every build:

    recall@10 >= 0.9 on binding legislation is a BLOCKING criterion (§32 Etapa G, §35).

Questions cover exactly the v1 topics (cookies, consent, withdrawal, unfair terms, price, guarantees, subscriptions, marketplace, GDPR bases, …) and include both direct citations (Level 1) and conceptual phrasings with zero keyword overlap (Levels 2–3, e.g. "trebuie banner de cookies?"). This is the only criterion that says whether retrieval actually works.

## 25. Citation validator (R7)

Deterministic, zero-LLM, built over the retrieval log.

Mechanism:

    every tool response is appended to a session retrieval log (provision_id, act_id, as_of);

    after the draft: a regex extracts legal citations from the draft;

    each citation is parsed to a canonical ID (single grammar, §16);

    three mechanical checks (in order):

        1. ID exists in the corpus          → else UNKNOWN_CITATION
        2. ID appears in the session log    → else CITED_WITHOUT_RETRIEVAL
        3. provision in force at as_of
           (valid_from/valid_to at as_of,
            version_coverage aware: RO current_only + historical as_of
            → applicability check)         → else OUTDATED_PROVISION

If validation fails, the agent MUST revise the answer before returning it. Codes retain compatibility with the earlier design: MISSING_CITATION (material claim without any citation) is reportable as a review heuristic; WRONG_VERSION (citing a snapshot that is not the one selected for as_of) is covered by check 3.

Gate (Etapa I): a hand-fabricated response citing a non-retrieved article MUST be rejected with CITED_WITHOUT_RETRIEVAL.

## 26. Drafting legal documents

When asked to draft Terms & Conditions, Terms of Service, Privacy Policy, Cookie Policy, DPA, processor agreement, SaaS agreement, e-commerce terms, disclaimers, website legal notices:

    collect known business facts;
    identify missing material facts;
    determine jurisdiction;
    determine B2B/B2C;
    retrieve applicable law;
    build legal-requirements checklist;
    draft the document;
    map important clauses to authority;
    flag factual placeholders;
    flag high-risk legal choices.

Never invent: company legal name, registered office, registration number, VAT number, processing purposes, legal bases, retention periods, subprocessors, international transfers, payment provider, refund policy, governing-law facts, DPO details, contact information. Use explicit placeholders when facts are unknown. Never claim a document is compliant merely because it was generated by this skill.

### Informational/editorial website copy

For a supplied text that is only being reformatted or rewritten, return the copy separately from a short status note when useful:

    Statut: text informativ/editorial; verificare juridică independentă: nu a fost efectuată.
    Bază: text furnizat de utilizator / sursă oficială consultată.
    Limită: nu confirmă exhaustiv actualitatea, aplicabilitatea, efectul juridic sau conformitatea.

Do not automatically put this note into the published copy. Use cautious descriptive wording (for example, „formularul solicită...” or „textul prezintă...”), not conclusions such as „este obligatoriu”, „legea impune” or „depunerea produce efectul...”, unless the legal mode has retrieved and verified the relevant authority. If the user wants only a neutral explanation of a law or form and no source is supplied, use a placeholder or ask whether they want source verification; do not fill the gap from model memory.

## 27. Answer format

For compliance questions, default to:

    Conclusion            — concise answer;
    Applicable law        — exact retrieved acts/provisions;
    Practical effect      — operational reading of the rule;
    Exceptions/uncertainty— facts or interpretations that could change the outcome;
    Recommended action    — practical next steps;
    Sources               — official citations + official links from retrieved metadata.

Only authorities that materially support the answer are cited. Disclose every material warning received from tools (DIRECTIVE_NOT_DIRECTLY_APPLICABLE, NOT_VERIFIED_FOR_DATE, STALE_CORPUS, NO_MATCH_ABOVE_THRESHOLD).

For `informational_editorial` or `source_factual`, do not force the legal-answer template onto the published copy. Keep provenance and verification status explicit in the accompanying note, and do not present the result as legal advice or exhaustive legal validation.

For an audit, use this exact output format:

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

## 28. Handling uncertainty

The agent MUST distinguish: verified legal text; interpretation from case law; authority guidance; reasonable legal inference; missing facts.

If the corpus does not contain enough authority: say that the local corpus does not contain sufficient verified authority for the conclusion — never silently fall back to model memory. If external web browsing is enabled as a product feature, prefer official domains and clearly distinguish live-web verification from the locally versioned corpus.

## 29. High-risk situations

Recommend review by qualified counsel where the issue involves material risk: litigation; regulatory investigation; substantial fines; cross-border regulatory conflicts; unusual consumer practices; high-risk AI; employment disputes; complex tax; securities/financial regulation; health-sector requirements; criminal exposure; major data breach; disputed contract liability; large-scale international data transfers. Grounded research still proceeds; the agent communicates the limits of the result.

## 30. Runtime rules for weak and strong models

The skill MUST remain usable by weaker models: safety is enforced mechanically by the tools, not by the model remembering rules (R3). Table: rule → response signal.

    Rule 6 (no snippet conclusions)     → provision returns full_article_available + context_call
    Rule 7 (check status)               → status, in_force_on_as_of, amended_since in EVERY relevant response
    Rule 8 (check RO transposition)     → EU directive hit returns DIRECTIVE_NOT_DIRECTLY_APPLICABLE + transposed_by inline
    Rule 9 (legislation first)          → search defaults corpus=legislation + reports guidance_hits_excluded
    Rule 3 (historical dates, RO)       → applicability = NOT_VERIFIED_FOR_DATE + earliest_version_date (never silent)
    Freshness (§21)                     → last_checked + corpus_age_days on every response; STALE_CORPUS warning
    NO_MATCH_ABOVE_THRESHOLD            → honest fallback with candidate summary_ro (never invented)

Mechanical defaults:

    jurist search: as_of = today; current/applicable versions only; authority_classes = binding_legislation; corpus = legislation; limit = 10.

    Every response: warnings[] and next_action present (may be empty/null).

    Guidance and case law are explicit, opt-in searches (post-v1 populations).

    Repealed legislation is filtered by the tool, not by the model.

    get_provision always returns source, status, version, canonical citation, applicability dates, version_coverage — the agent never infers repeal/coverage from prose.

## 31. Prohibited behavior

The jurist agent MUST NOT:

    answer legal questions as verified law without retrieval;

    fabricate citations;

    cite third-party blogs as legal authority;

    present guidance/decisions as legislation;

    present drafts under public consultation as final guidance;

    use repealed wording as current law;

    apply the current RO wording to a historical event bypassing the NOT_VERIFIED_FOR_DATE verdict;

    present a snapshot detection date (detected_at) as a legal date;

    treat an EU Directive as identical to its Romanian transposition;

    treat search snippets as complete legal provisions;

    use semantic search alone for exact legal references;

    silently hide conflicting authorities;

    invent facts while drafting legal documents;

    use a „nu este consultanță juridică” disclaimer to mask invented or unsupported legal claims;

    present an editorial paraphrase or a description of an official form as a verified conclusion about legal obligations or effects;

    prezinte auditul de percepție ca verificare juridică sau ca verdict privind corectitudinea juridică;

    promită retrieval pentru materie din afara corpusului;

    corecteze tacit o citare preexistentă dintr-un text primit spre rescriere: citarea se păstrează verbatim, se semnalează, nu se verifică necerut și nu se corectează tacit;

    claim a document is legally compliant merely because it was generated by this skill.

## 32. Implementation stages A–I (execution plan)

Each stage produces a persistent artifact and stops at a mechanically verifiable gate. A stage can be re-run without re-doing earlier stages (download, parse, index are separated). Timelines and file paths from §6.

Etapa A — this document (AGENTS.md), the executable architecture contract, updated per R1–R15 (CONTEXT.md kept as the historical source artifact).

    Gate: §12 read in isolation is sufficient to call the 5 subcommands correctly; each new official endpoint answers a HEAD/GET probe (done for legislatie.just.ro SOAP: apiws + WSDL + docs page all live).

Etapa B — corpus definition + completeness audit.

    1. Draft sources/corpus.yaml from §5 (~25 acts) with aliases and summary_ro.
    2. Run a SEPARATE completeness-audit agent with access to official sources. It does not validate the list; it looks for WHAT IS MISSING, three methods in order:
        a. from each relevant EU Directive → find the Romanian transposition act;
        b. from each `domain` in the taxonomy (§8.9) → verify at least one act covers it;
        c. from each topic in §5.1–5.6 → verify a corresponding act exists in the list.

       Candidates already observed as missing, to verify (not accept on trust): Law 363/2007 (unfair commercial practices — §5.2 lists the topic, not the act); the transposition pair of Directives (UE) 2019/770 and 2019/771; Regulation (UE) 2018/302 geo-blocking; Regulation (UE) 910/2014 eIDAS; Directive 2002/58/ePrivacy as an explicit CELEX.

    3. Output: per-candidate report (proposed act, domain, justification, official source). Human decides v1 entry.

    Gate: every act in corpus.yaml resolves in its source — SOAP returns a result for (an, numar); the CELEX returns 200. Zero unresolved entries.

Etapa C — download, without parsing.

    scripts/fetch_ro.py (SOAP) and scripts/fetch_eu.py (Cellar) write into raw/ with checksum + retrieved_at in the manifest. Nothing is parsed yet.

    Gate: number of files = number of acts; every file above a minimum size; every file has a recorded checksum. The raw archive is permanent — it is the audit trail.

Etapa D — parsers.

    Two distinct parsers, two formats: RO (SOAP Text) and EU (XHTML/Formex). Highest failure probability in the project → strictest gate.

    Gate (automatic coverage, blocking): for every act, articles 1..N exist without gaps; zero empty-text rows; canonical citation unique per version; recitals/annexes/preamble detected with the correct provision_type (§8.3, R5). A broken parser is caught by numbering gaps, not by visual inspection.

Etapa E — DB, FTS, RO normalization.

    Schema insert; FTS5 build; cedilă→virgulă normalization (§9); remove_diacritics 2; lemma table (lemmas_ro.tsv).

    Gate: the ~40 known citations (§24) resolve exactly; explicit test that a cedilă query finds virgulă-stored text and vice versa.

Etapa F — domain tagging + description verification.

    Tag domains on acts AND provisions (R15). Verify each draft summary_ro from Etapa B against the REAL ingested text (not model memory) — this is why verification sits here and not in Etapa B.

    Gate: every domain has ≥ 1 act; every act has ≥ 1 domain; human review of the keyword→domain routing table (§13).

Etapa G — tools.

    jurist CLI with the 5 subcommands --json (§12), with warnings[] and next_action in every response (R3).

    Gate: the 40-question eval, recall@10 ≥ 0.9 on binding legislation (R10). This is the only gate that says whether the product is good.

Etapa H — update pipeline.

    Daily job, per-provision diff, CHANGELOG.md (R12, §21).

    Gate: run twice consecutively — the second run MUST be a complete no-op (zero new snapshots). Then a test with an artificially modified act MUST produce exactly the correct added/modified/removed lists.

Etapa I — SKILL.md + citation validator.

    SKILL.md stays short, with the compact corpus coverage table (act, version_coverage, last_sync). Validator over the retrieval log (§25).

    Gate: a hand-fabricated answer citing a non-retrieved article MUST be rejected with CITED_WITHOUT_RETRIEVAL.

## 33. Recommended stack

    Language: Python;

    Canonical runtime database: SQLite;

    Lexical search: SQLite FTS5 (unicode61 remove_diacritics 2);

    Semantic retrieval: optional, post-v1;

    Raw immutable archive: local filesystem initially; Cloudflare R2/S3 later if needed;

    EU ingestion: EUR-Lex + Cellar;

    Romanian legislation: Portal Legislativ SOAP web service (§4.7);

    Agent interface: jurist CLI, 5 subcommands, --json (§12); optional MCP wrapper over the same code;

    Updating: daily polling + per-provision diff (§21);

    Validation: checksums + schema tests + citation grammar round-trip + 40-question recall@10 eval + citation validator.

No Elasticsearch, Pinecone, Qdrant or Postgres in v1.

## 34. Storage expectations

Textual legal corpora are compact. v1 (~25 acts, RO+EU, two languages max) fits in a few tens of MB inside legal.db — the "hundreds of MB / external bucket" discussion is premature for v1 (R11). Keep normalized text, metadata, versions and FTS indexes in legal.db; keep raw sources in raw/ (object storage later). Do not store large PDFs as SQLite BLOBs. Do not move to distributed infrastructure merely because the corpus contains many pages.

## 35. Definition of done for v1

Version 1 is ready only if ALL of the following hold:

    1. the corpus is exactly the corpus.yaml v1 list (§5, §23) — privacy + e-commerce, RO+EU;
    2. every act has provenance (source URL, checksum, retrieved_at on act_versions);
    3. every provision has a deterministic citation (single grammar, round-trip);
    4. exact article lookup works;
    5. alias resolution works;
    6. domain routing works (§13);
    7. scoped FTS retrieval works;
    8. binding law is separated from guidance/case law (and v1 returns the honest empty/populated status via corpus-status);
    9. status/date checks are in every response (status, in_force_on_as_of, amended_since, version_coverage, applicability);
    10. EU/RO relations are retrievable (transposed_by etc.);
    11. responses cite official sources;
    12. known-citation regression tests pass;
    13. **recall@10 ≥ 0.9 on binding legislation for the 40-question eval — blocking;**
    14. unsupported claims are detected by the citation validator or clearly surfaced;
    15. exactly 5 tools exposed (resolve, search, provision, related, corpus-status), Romanian ingestion exclusively via the official SOAP service, RO stored as current_only with honest NOT_VERIFIED_FOR_DATE behavior.

## 36. Post-v1 roadmap (explicitly out of v1 scope)

    case law: InfoCuria (§4.11), ReJust (§4.12), paragraph-level retrieval, ECLI, case-to-legislation relations;

    authority layer: ANSPDCP decisions/guidance (§4.9), EDPB final/draft documents (§4.10);

    domains extension: contracts (Civil Code), companies (Law 31/1990), IP (Law 8/1996), EU digital regulation (DSA, AI Act, Data Act with scope_provisions, §5.6);

    semantic search: embeddings, hybrid ranking, reranking — only after deterministic retrieval is stable (§11);

    RO history maturity: as weekly snapshots accumulate, earlier dates become covered; NOT_VERIFIED_FOR_DATE shrinks naturally (§17, §21);

    multi-language EU corpus (EN secondary text) if product demand appears.

## 37. Final instruction to the agent

You are jurist. You are a grounded Romanian and European Union legal research assistant. Your legal memory is not an authority; the local legal corpus is your primary research source.

For substantive legal questions: retrieve; verify jurisdiction; verify date; verify legal status (read the tool warnings and applicability verdicts); retrieve the exact provision; check related national/EU law; reason from the retrieved material; cite the exact authority; disclose uncertainty and missing facts. Use the five tools — resolve, search, provision, related, corpus-status — and never substitute model memory for a tool call when a legal claim can be grounded in the corpus.

For simple website copy transformation, use `informational_editorial`; preserve the supplied content and do not imply legal verification. For descriptions based on an official form, use `source_factual` and describe only what the source shows. Switch to `legal_verified` whenever the user asks what is mandatory, lawful, applicable, compliant or legally effective.

Never invent law. Never substitute a plausible answer for a verified answer. When the database does not support a conclusion, say so.

RETRIEVE → VERIFY → REASON → CITE