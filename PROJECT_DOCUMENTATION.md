# PolicyLens — Comprehensive Project Documentation

Documentation generated from repository analysis (**PolicyLens** / `InSuRaNcE-Doc-NLP`). Several sections are **explicitly marked N/A** where the codebase does not implement those layers (there is **no REST API**, **no database**, and **no end-user JWT/session auth**—it is a **Streamlit monolith** with **Anthropic API key** configuration).

---

## 1. Tech stack

| Layer | Technology | Version / notes (from repo) |
|--------|------------|-----------------------------|
| **Language** | Python | README: **3.11+** (not pinned in a `pyproject.toml`; `requirements.txt` is the source of truth) |
| **UI / “frontend”** | Streamlit | `streamlit>=1.32.0,<2.0.0` |
| **PDF text extraction** | pdfplumber | `pdfplumber>=0.10.0,<1.0.0` (also uses `pdfminer`’s `PDFSyntaxError` from that stack) |
| **NLP** | spaCy | `spacy>=3.7.0,<4.0.0` |
| **spaCy model** | `en_core_web_lg` | Installed via `python -m spacy download en_core_web_lg` (`README.md`, `setup.sh`, `Makefile`) |
| **LLM API** | Anthropic Python SDK | `anthropic>=0.25.0,<1.0.0` |
| **LLM model ID** | Claude | `claude-sonnet-4-20250514` (constant `MODEL_NAME` in `core/llm_extractor.py`, reused by `core/chat_engine.py`) |
| **Data / tables** | pandas | `pandas>=2.0.0,<3.0.0` |
| **Excel export** | openpyxl | `openpyxl>=3.1.0,<4.0.0` (used as `engine="openpyxl"` in `utils/export.py`) |
| **Config / env** | python-dotenv | `python-dotenv>=1.0.0,<2.0.0` |
| **Date parsing** | python-dateutil | `python-dateutil>=2.8.0,<3.0.0` |
| **Deployment (documented)** | Streamlit Cloud | `README.md` (secrets pattern via `.streamlit/secrets.toml.example`) |
| **Dev tooling** | GNU Make, Bash | `Makefile`, `setup.sh` |
| **Testing** | *(declared via `.gitignore` only)* | `.pytest_cache/`, `.coverage`, `htmlcov/` ignored — **no test suite files present** in the repo |

**Not present in this codebase:** React/Vue, FastAPI/Flask/Django, PostgreSQL/MongoDB, Redis, Docker/Kubernetes manifests, CI workflow files under `.github/` (none found).

---

## 2. Backend concepts and key methods

This project is **not** a classical request/response HTTP backend. “Backend” behavior lives in **`core/`** and is invoked from **Streamlit pages**. Below are **concepts that are actually implemented**, with definitions tied to this repo.

### 2.1 Hybrid extraction (rules + spaCy + LLM)

| | |
|--|--|
| **What it is** | Combine fast deterministic parsing (PDF + spaCy/rules) with an LLM that only fills gaps. |
| **Why here** | Insurance PDFs are noisy; spaCy catches many entities, Claude fills `None` fields per `ENTITY_SCHEMA`. |
| **How it works** | `pages/1_Upload.py` → `_process_uploaded_file()` calls `extract_pdf` → `classify_document` → `extract_entities_spacy` → `extract_entities_llm` → `compute_risk_flags`. |
| **Where** | `pages/1_Upload.py` (`_process_uploaded_file`), `core/pdf_extractor.py`, `core/doc_classifier.py`, `core/nlp_pipeline.py`, `core/llm_extractor.py`, `core/risk_engine.py` |

### 2.2 PDF text extraction and error surfacing

| | |
|--|--|
| **What it is** | Turn PDF bytes into `full_text`, per-page strings, `page_count`, `filename`. |
| **Why here** | Everything downstream (classification, NLP, chat) needs searchable text. |
| **How it works** | `extract_pdf()` reads bytes, opens with pdfplumber, joins non-empty pages; raises `ValueError` if empty text; propagates/logs `PDFSyntaxError` and generic errors. |
| **Where** | `core/pdf_extractor.py` — `extract_pdf(file_obj: BinaryIO) -> dict[str, object]` |

### 2.3 Rule-based document type classification

| | |
|--|--|
| **What it is** | Keyword hit-count scoring to pick `policy`, `certificate`, `endorsement`, `claim`, or `unknown`. |
| **Why here** | Chooses which `ENTITY_SCHEMA` and extraction rules apply. |
| **How it works** | Lowercase full text → count keyword hits per type from `DOC_TYPE_KEYWORDS` → pick max; if score ≤ 0 return `unknown`. |
| **Where** | `config/settings.py` (`DOC_TYPE_KEYWORDS`), `core/doc_classifier.py` — `classify_document(full_text: str) -> str` |

### 2.4 spaCy NER + custom EntityRuler patterns

| | |
|--|--|
| **What it is** | A loaded `Language` pipeline with insurer-style patterns appended before built-in `ner`. |
| **Why here** | Improves recall for IDs, amounts, deductibles vs generic English NER alone. |
| **How it works** | Singleton `_get_nlp_model()` loads `en_core_web_lg`, `_add_entity_ruler()` registers regex/token patterns (`POLICY_NUMBER`, `COVERAGE_LIMIT`, …). `extract_entities_spacy()` runs the doc and maps spaCy labels to schema fields via `_set_first_available`, with regex/date/currency helpers. Large texts truncated at `MAX_CHARS` (1_000_000). |
| **Where** | `core/nlp_pipeline.py` — `_add_entity_ruler`, `_get_nlp_model`, `extract_entities_spacy(full_text, doc_type)` |

### 2.5 LLM “gap fill” extraction (Anthropic Messages API)

| | |
|--|--|
| **What it is** | Prompt Claude with schema + spaCy JSON + document text to output JSON for **null fields only**. |
| **Why here** | Structural fields (lists, exclusions, narrative clauses) often need semantic understanding. |
| **How it works** | `extract_entities_llm()` builds system prompt listing `ENTITY_SCHEMA` + current `spacy_result`, sends truncated user content (`_truncate_text`, `MAX_TEXT_CHARS = 12_000`), parses JSON via `safe_parse_json`, merges with `_merge_spacy_with_llm` (spaCy non-null wins). On API/config errors, returns `spacy_result` unchanged. |
| **Where** | `core/llm_extractor.py` — `get_claude_client()`, `extract_entities_llm(...)`, `safe_parse_json`, `_merge_spacy_with_llm` |

### 2.6 Risk scoring / rule engine over extracted entities

| | |
|--|--|
| **What it is** | Deterministic flags (expiry, limits, deductible ratio, missing fields, exclusions empty, claim open, unknown doc type). |
| **Why here** | Gives brokers/underwriters quick operational signals beyond raw extraction. |
| **How it works** | `compute_risk_flags()` uses thresholds from env (`COVERAGE_LIMIT_THRESHOLD`, `DEDUCTIBLE_RATIO_THRESHOLD`, `EXPIRY_WARNING_DAYS`), `ENTITY_SCHEMA`-aware `_missing_required_fields`, and emits dicts `{filename, flag_name, severity, details}` via `_build_flag`. Metadata for rules documented in `RISK_FLAG_RULES` (documentation map; evaluated logic is in code). |
| **Where** | `core/risk_engine.py` — `compute_risk_flags(extracted_fields, doc_type, filename)`; thresholds in `config/settings.py` |

### 2.7 Document-grounded chat (prompt-based QA, not a vector DB)

| | |
|--|--|
| **What it is** | Multi-turn QA where the **full document text** (truncated) is injected into Claude’s message list with instructions to stick to the document. |
| **Why here** | Lets users probe policies without manually rereading long PDFs. |
| **How it works** | `answer_question()` builds synthetic first user/assistant turns to “confirm” document read, appends `_sanitize_history` (last `MAX_CHAT_TURNS = 10` valid `user`/`assistant` turns), calls `client.messages.create` with `temperature=0.3`. Failures return `ERROR_MESSAGE`. |
| **Where** | `core/chat_engine.py` — `answer_question(question, full_text, chat_history, doc_type)` |

### 2.8 Streamlit session state as application memory

| | |
|--|--|
| **What it is** | Server-side per-session Python dicts holding uploads, results, chat, status. |
| **Why here** | No database; results must survive navigation between pages in one browser session. |
| **How it works** | `app.py` `DEFAULT_SESSION_STATE` + `init_session_state()`; `pages/1_Upload.py` `_ensure_session_state()` guard; `_store_result()` appends to `uploaded_docs`, `extracted_results`, marks `processing_status`. |
| **Where** | `app.py`, `pages/1_Upload.py` |

### 2.9 Upload validation (type and size)

| | |
|--|--|
| **What it is** | Pre-check `.pdf` extension and 20 MB max. |
| **Why here** | Avoids pointless LLM/API work and clearer UX. |
| **How it works** | `_validate_upload()` in upload page; batch path skips invalid files with warnings. |
| **Where** | `pages/1_Upload.py` — `_validate_upload(uploaded_file) -> tuple[bool, str]` |

### 2.10 Logging

| | |
|--|--|
| **What it is** | Standard library `logging` with INFO-level configuration at app entry. |
| **Why here** | Trace pipeline steps and external API issues. |
| **How it works** | `logging.basicConfig` in `app.py` `main()`; module loggers in `core/*` and `utils/formatters.py`. |
| **Where** | `app.py` (`main`), various `logger = logging.getLogger(__name__)` |

### 2.11 Configuration via environment variables

| | |
|--|--|
| **What it is** | Thresholds and API key read from process environment / Streamlit secrets. |
| **Why here** | Tune risk behavior per deployment without code changes. |
| **How it works** | `os.getenv` in `config/settings.py` for numeric thresholds; Anthropic key via `os.getenv` and `st.secrets` in `_get_api_key()`. |
| **Where** | `config/settings.py`, `core/llm_extractor.py` (`_get_api_key`, `get_claude_client`) |

### Concepts not implemented (so not listed as patterns in this repo)

Examples: **JWT**, **OAuth2**, **session cookies for app users**, **rate limiting middleware**, **Redis/cache**, **message queues**, **webhooks**, **WebSockets**, **SQL/ORM**, **CORS middleware** (not applicable to this app shape), **Helmet-style HTTP headers** (Streamlit serves the app; not configured here).

---

## 3. API inventory

### 3.1 REST / HTTP JSON APIs

**None.** There are **no** FastAPI/Flask/Starlette routers, **no** `@app.route` / `@router.get` style handlers, and **no** OpenAPI spec in the repository.

### 3.2 External APIs consumed

| Provider | Purpose | Call site |
|----------|---------|-----------|
| **Anthropic** | LLM extraction + chat | `anthropic.Anthropic` in `core/llm_extractor.py` (`client.messages.create`) and `core/chat_engine.py` (`client.messages.create`) |

### 3.3 Streamlit “routes” (multi-page app)

Streamlit maps files to paths; exact URL shape depends on Streamlit version and deployment. Pages in this repo:

| Method | Route (file) | Description | Auth | Request body | Response |
|--------|----------------|-------------|------|--------------|----------|
| GET | `app.py` | Home / landing | None in app | N/A | HTML UI |
| GET | `pages/1_Upload.py` | Upload & run pipeline | None in app | File upload (PDF) via widget | Renders status + session updates |
| GET | `pages/2_Results.py` | View fields & flags | None in app | N/A | HTML UI |
| GET | `pages/3_Chat.py` | Document Q&A | None in app | Chat input string | HTML UI |
| GET | `pages/4_Export.py` | Download Excel/CSV | None in app | N/A | File download buttons |

---

## 4. Architecture diagram (text)

**Data & control flow (single session):**

```
[Browser / Streamlit client]
        │
        ▼
[Streamlit runtime]
   ├─ app.py ........................ Home + sidebar + session init
   └─ pages/*.py .................... Upload / Results / Chat / Export
        │
        ├─ st.session_state .......... uploaded_docs, extracted_results,
        │                              active_doc_index, chat_history,
        │                              processing_status
        │
        ▼
[Processing pipeline — pages/1_Upload._process_uploaded_file]
   │
   ├─► [core.pdf_extractor.extract_pdf] ──► raw text + pages
   │
   ├─► [core.doc_classifier.classify_document] ──► doc_type
   │
   ├─► [core.nlp_pipeline.extract_entities_spacy] ──► partial fields
   │
   ├─► [core.llm_extractor.extract_entities_llm] ──► merged fields
   │         │
   │         └──► [Anthropic Messages API] (HTTPS, API key)
   │
   └─► [core.risk_engine.compute_risk_flags] ──► flags[]

[Chat path — pages/3_Chat]
   └──► [core.chat_engine.answer_question]
              └──► [Anthropic Messages API] (document text + history in prompt)

[Export path — pages/4_Export]
   └──► [utils.export.export_to_excel / export_to_csv]
              └──► [pandas + openpyxl] (in-memory bytes / CSV string)
```

**Auth flow (actual):**

```
[Deployer configures ANTHROPIC_API_KEY]
        │
        ├─► .env (local) ............... python-dotenv in _get_api_key()
        └─► Streamlit secrets (cloud) .. st.secrets["ANTHROPIC_API_KEY"]

[End user of the web app]
        └─► No application-level login in this codebase
```

---

## 5. Problem statement

| Question | Answer (from `README.md` + code) |
|----------|----------------------------------|
| **Real-world problem** | Brokers and underwriters spend heavy manual time reading insurance PDFs to pull structured facts, spot risk (expiry, limits, deductibles, gaps), and answer ad-hoc questions. |
| **Target user** | Operations staff in **brokerage / underwriting** workflows (also anyone needing structured outputs from COIs, endorsements, claims PDFs). |
| **Manual alternative** | Open each PDF, copy fields into spreadsheets, track renewals and limits by hand, and reread documents for each question. |
| **Core value proposition** | PolicyLens turns PDFs into **reviewable structured fields**, **automatic risk flags**, and **document-grounded Q&A**, with **Excel/CSV export**—combining spaCy/rules for speed with Claude where semantics matter. |

---

## 6. Authentication and authorization

| Topic | Detail |
|--------|--------|
| **App user auth** | **None implemented** — no JWT, OAuth, sessions, or API keys for callers of the Streamlit UI. Protection is **deployment-time** only (who can reach Streamlit Cloud / network). |
| **External API auth** | **Anthropic API key** — logical “service credential,” not end-user RBAC. |
| **Generation / storage / validation** | Key read by `_get_api_key()` from **`st.secrets`** (when running under Streamlit) or **`os.getenv("ANTHROPIC_API_KEY")`** after `load_dotenv()`. Missing key → `ValueError` in `get_claude_client()`. |
| **Roles / permissions** | **None** in code. |
| **“Auth middleware”** | **Not applicable** — there is **no middleware function** guarding HTTP routes. |

If you require a symbolic “signature” for documentation completeness: **`get_claude_client() -> anthropic.Anthropic`** — there is **no** `def require_auth(...):` pattern in this codebase.

---

## 7. Database design

| Topic | Detail |
|--------|--------|
| **Databases used** | **None**. No SQLite/Postgres/Mongo imports, no ORM, no connection strings. |
| **Persistence model** | **Streamlit `st.session_state`** only (in-memory for the session; lost on restart or new session). |
| **“Models”** | **`ENTITY_SCHEMA`**, **`DOC_TYPE_KEYWORDS`**, **`RISK_FLAG_RULES`** in `config/settings.py` are **Python dict schemas / metadata**, not DB tables. |
| **Relationships** | **N/A** (no relational store). Logical link: each `extracted_results` row ties to **`filename`**; `chat_history` is keyed by **`filename`**; **`uploaded_docs`** mirrors raw text keyed by **`filename`**. |
| **Migrations / seeding / indexing** | **None.** |

---

## 8. Error handling and logging

| Area | Behavior | Where |
|------|----------|--------|
| **Global HTTP error handler** | **None** — not an HTTP JSON API framework. |
| **UI-level errors** | Upload paths wrap `_process_uploaded_file` in `try/except`, set `processing_status[name]="error"`, show `type(exc).__name__` + message in expanders. | `pages/1_Upload.py` |
| **PDF errors** | Logs warning/error; re-raises `PDFSyntaxError`; raises `ValueError` for empty text. | `core/pdf_extractor.py` |
| **spaCy errors** | On model/processing failure, logs and returns empty or partial dict (see `extract_entities_spacy` except block returns `result`). | `core/nlp_pipeline.py` |
| **LLM extraction errors** | Catches `APIConnectionError`, `RateLimitError`, `APIStatusError`, `ValueError`, generic `Exception`; logs; **returns `spacy_result`** (graceful degradation). | `core/llm_extractor.py` |
| **Chat errors** | Broad `except Exception`; returns constant **`ERROR_MESSAGE`**. | `core/chat_engine.py` |
| **Client “error format”** | **Streamlit widgets** (`st.error`, `st.warning`, `st.info`) — **not** a unified JSON error schema. |
| **Logging library** | **`logging`** (stdlib), configured in `app.py` `main()`. |
| **Custom exception classes** | **None** defined in this repo. |

---

## 9. Security measures

| Measure | Present? | Evidence |
|---------|------------|----------|
| **Secrets not committed** | Yes | `.gitignore` ignores `.env`, `.streamlit/secrets.toml` |
| **API key via env / secrets** | Yes | `core/llm_extractor.py` (`_get_api_key`), `.env.example`, `.streamlit/secrets.toml.example` |
| **Upload validation** | Yes | PDF-only, 20 MB cap — `pages/1_Upload.py` `_validate_upload` |
| **Input trimming / chat history filter** | Partial | `core/chat_engine._sanitize_history` keeps only `user`/`assistant` with non-empty content; caps turns |
| **JSON hardening for LLM output** | Partial | `safe_parse_json` strips fenced blocks and catches `JSONDecodeError` |
| **SQL/NoSQL injection** | N/A | No database queries |
| **Rate limiting (app-level)** | No | Not implemented; Anthropic may return rate limit errors (handled in extraction path) |
| **Helmet / security headers** | Not configured | Streamlit server concerns; nothing in repo |
| **Field validation module** | Placeholder only | `utils/validators.py` is a TODO stub |
| **Error detail leakage** | Risk note | Upload UI shows raw exception messages to the user — fine for local use; consider sanitization in untrusted deployments |

---

## 10. Project structure

**Tree (depth ~3, repo root):**

```
.
├── app.py                 # Streamlit entry: session defaults, sidebar, home
├── README.md
├── requirements.txt
├── Makefile               # install, download-model, run, clean
├── setup.sh               # pip install + spaCy model (Streamlit Cloud / Linux)
├── .env.example           # Local env template
├── .gitignore
├── .streamlit/
│   ├── config.toml        # UI theme colors
│   └── secrets.toml.example
├── config/
│   ├── __init__.py
│   └── settings.py        # DOC_TYPE_KEYWORDS, ENTITY_SCHEMA, RISK_FLAG_RULES, thresholds
├── core/
│   ├── __init__.py
│   ├── pdf_extractor.py   # PDF → text
│   ├── doc_classifier.py  # Keyword classification
│   ├── nlp_pipeline.py    # spaCy + EntityRuler extraction
│   ├── llm_extractor.py   # Claude gap-fill + merge
│   ├── risk_engine.py     # Risk flags
│   └── chat_engine.py     # Claude Q&A
├── utils/
│   ├── __init__.py
│   ├── formatters.py      # normalise_currency, normalise_date
│   ├── export.py          # Excel/CSV builders
│   └── validators.py      # Placeholder (no logic yet)
└── pages/
    ├── __init__.py
    ├── 1_Upload.py        # Pipeline orchestration + batch
    ├── 2_Results.py       # DataFrame + flags UI
    ├── 3_Chat.py          # Chat UI + answer_question
    └── 4_Export.py        # Download buttons
```

**Folder purposes (summary):**

- **`app.py`**: Page config, logging setup, session initialization, navigation chrome.
- **`config/`**: Static schemas and tunable thresholds (`os.getenv`).
- **`core/`**: Domain logic — PDF, classification, NLP, LLM, risk, chat.
- **`utils/`**: Shared formatting and export; validators reserved for later.
- **`pages/`**: Streamlit multipage UI; each file is a user-facing step.
- **`.streamlit/`**: Theme and secrets example for hosted runs.

---

### Closing accuracy note

This documentation reflects **only what exists in the repository**: a **Streamlit + Python** tool with **spaCy**, **pdfplumber**, **pandas/openpyxl**, and **Anthropic**. If you add a REST API, database, or user auth later, sections **3**, **6**, **7**, and **8** would need to be extended accordingly.
