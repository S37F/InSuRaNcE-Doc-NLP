# CONTEXT.md — Insurance Document Intelligence Tool

## 1. Project Overview

**App Name:** PolicyLens
**Type:** Production-grade Streamlit web application
**Purpose:** Automatically extract structured entities from commercial insurance documents (PDFs), flag risks, enable document Q&A via chat, and export results to Excel/CSV.

This tool is built for internal production use at an insurance brokerage. It must handle real, messy PDFs reliably, surface actionable insights, and be maintainable by an intermediate Python developer.

---

## 2. Core User Flows

1. **Single Upload** → User uploads one PDF → system extracts entities → shows results table + risk flags → user can chat with the document → export to Excel/CSV
2. **Batch Upload** → User uploads multiple PDFs → system processes all → shows unified results table with per-document rows → bulk export

---

## 3. Supported Document Types

The app must detect document type automatically and apply the correct extraction schema.

| Document Type             | Key Identifier Phrases |
|---------------------------|------------------------|
| Policy Document           | "policy number", "insuring agreement", "declarations" |
| Certificate of Insurance  | "certificate holder", "this is to certify", "acord" |
| Endorsement               | "endorsement number", "it is agreed", "forms part of" |
| Claims Document           | "claim number", "date of loss", "claimant" |

---

## 4. Entity Schema (per document type)

### Policy Document
| Field | Type |
|---|---|
| Insured Name | String |
| Policy Number | String |
| Insurer Name | String |
| Coverage Type | String |
| Premium Amount | Float |
| Coverage Limit | Float |
| Deductible | Float |
| Policy Start Date | Date |
| Policy End Date | Date |
| Exclusions | List[String] |
| Named Endorsements | List[String] |

### Certificate of Insurance
| Field | Type |
|---|---|
| Certificate Holder | String |
| Insured Name | String |
| Insurer Name | String |
| Policy Number | String |
| Coverage Type | String |
| Coverage Limit | Float |
| Effective Date | Date |
| Expiry Date | Date |
| Additional Insured | Boolean |

### Endorsement
| Field | Type |
|---|---|
| Endorsement Number | String |
| Policy Number | String |
| Effective Date | Date |
| Description | String |
| Additional Premium | Float |
| Amended Clause | String |

### Claims Document
| Field | Type |
|---|---|
| Claim Number | String |
| Claimant Name | String |
| Date of Loss | Date |
| Loss Description | String |
| Reserve Amount | Float |
| Claim Status | String (Open/Closed/Pending) |
| Adjuster Name | String |

---

## 5. Risk Flag Rules

Risk flags are computed AFTER extraction. Each flag has a severity level.

| Flag | Condition | Severity |
|---|---|---|
| Policy Expiring Soon | End/Expiry date within 30 days | 🔴 High |
| Policy Already Expired | End/Expiry date in the past | 🔴 High |
| Low Coverage Limit | Coverage Limit < ₹10,00,000 (or $100,000) | 🟡 Medium |
| High Deductible | Deductible > 10% of Coverage Limit | 🟡 Medium |
| Missing Critical Fields | Any required field is null/empty | 🟠 High |
| No Exclusions Listed | Exclusions field is empty | 🟡 Medium |
| Claim Status Open | Claim Status == "Open" | 🟡 Medium |
| Unrecognised Document Type | Doc type could not be classified | 🔴 High |

---

## 6. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| UI Framework | Streamlit | >=1.32.0 |
| PDF Extraction | pdfplumber | >=0.10.0 |
| NLP / NER | spaCy | >=3.7.0 |
| spaCy Model | en_core_web_lg | latest |
| LLM (extraction + chat) | Anthropic Claude API | claude-sonnet-4-20250514 |
| Anthropic SDK | anthropic | >=0.25.0 |
| Data Handling | pandas | >=2.0.0 |
| Excel Export | openpyxl | >=3.1.0 |
| Env Management | python-dotenv | >=1.0.0 |
| Deployment | Streamlit Cloud | — |

---

## 7. Folder Structure

```
policylens/
├── app.py                        # Streamlit entry point (navigation + session init)
├── requirements.txt
├── .env.example                  # Template for local dev env vars
├── .streamlit/
│   ├── config.toml               # Theme, layout settings
│   └── secrets.toml.example      # Template for Streamlit Cloud secrets
├── config/
│   └── settings.py               # Constants: field schemas, risk thresholds, doc type keywords
├── core/
│   ├── __init__.py
│   ├── pdf_extractor.py          # pdfplumber: raw text + page extraction
│   ├── doc_classifier.py         # Rule-based document type detection
│   ├── nlp_pipeline.py           # spaCy NER: custom rules + patterns
│   ├── llm_extractor.py          # Claude API: structured field extraction via prompt
│   ├── risk_engine.py            # Risk flag computation logic
│   └── chat_engine.py            # Claude API: document Q&A with context window
├── utils/
│   ├── __init__.py
│   ├── export.py                 # Excel + CSV export functions
│   ├── formatters.py             # Date parsing, currency normalisation
│   └── validators.py             # Field validation helpers
└── pages/
    ├── 1_Upload.py               # Upload UI (single + batch)
    ├── 2_Results.py              # Extracted fields table + risk flags
    ├── 3_Chat.py                 # Q&A chat interface per document
    └── 4_Export.py               # Export controls (Excel/CSV)
```

---

## 8. Data Flow

```
PDF Upload (single or batch)
        │
        ▼
pdf_extractor.py        → Raw text per page, full doc text
        │
        ▼
doc_classifier.py       → Document type (Policy / COI / Endorsement / Claim)
        │
        ▼
nlp_pipeline.py         → spaCy NER: fast extraction of dates, monetary values,
                          org names, person names using custom rule patterns
        │
        ▼
llm_extractor.py        → Claude API fills in complex/ambiguous fields
                          that spaCy misses (exclusions, descriptions, status)
        │
        ▼
risk_engine.py          → Applies flag rules against extracted fields
        │
        ▼
Streamlit UI            → Results table, risk flags, chat, export
        │
        ▼
chat_engine.py          → User Q&A: full doc text injected into Claude context
        │
        ▼
export.py               → Excel (.xlsx) or CSV download
```

---

## 9. Extraction Strategy (Hybrid)

**spaCy handles:**
- Dates (policy start, end, effective dates)
- Monetary values (premium, limits, deductibles, reserves)
- Organisation names (insurer, insured, certificate holder)
- Person names (adjuster, claimant)

**Claude API handles:**
- Coverage type classification
- Exclusions list (requires reading full paragraphs)
- Claim status
- Endorsement descriptions
- Any field spaCy returns as null

This hybrid approach minimises API costs while maximising accuracy.

---

## 10. Claude API Usage

### Model
`claude-sonnet-4-20250514`

### Extraction Prompt Pattern
Each LLM extraction call sends:
- A system prompt defining the JSON output schema
- The full document text as user message
- Instruction to return ONLY valid JSON, no preamble

### Chat Pattern
Each Q&A message sends:
- System prompt: "You are an insurance document analyst. Answer questions based only on the document provided."
- Full document text as context block
- Conversation history (last 10 turns)
- User's latest question

### API Key Management
- Local dev: `ANTHROPIC_API_KEY` in `.env`
- Streamlit Cloud: stored in `st.secrets["ANTHROPIC_API_KEY"]`
- Never hardcoded anywhere in source code

---

## 11. Session State Keys (Streamlit)

```python
st.session_state["uploaded_docs"]       # List of {filename, raw_text, pages}
st.session_state["extracted_results"]   # List of {filename, doc_type, fields, flags}
st.session_state["active_doc_index"]    # Int: which doc is active in chat/results
st.session_state["chat_history"]        # Dict[filename → List[{role, content}]]
st.session_state["processing_status"]   # Dict[filename → "pending"|"done"|"error"]
```

---

## 12. Environment Variables

```env
# .env.example
ANTHROPIC_API_KEY=your_key_here
COVERAGE_LIMIT_THRESHOLD=100000
DEDUCTIBLE_RATIO_THRESHOLD=0.10
EXPIRY_WARNING_DAYS=30
```

---

## 13. Streamlit Cloud Deployment Notes

- All secrets go in Streamlit Cloud → App Settings → Secrets (TOML format)
- `requirements.txt` must include `en_core_web_lg` as a spaCy model download
- Add `packages.txt` if any system-level dependency is needed
- Use `@st.cache_resource` for spaCy model loading
- Use `@st.cache_data` for PDF extraction results

---

## 14. Constraints & Non-Negotiables

- No hardcoded API keys or thresholds in source files — all via config/env
- All Claude API calls must have try/except with user-facing error messages
- spaCy model must be loaded once using `@st.cache_resource`
- Batch processing must show a per-file progress bar
- Exported Excel must have separate sheets: "Extracted Data", "Risk Flags", "Summary"
- App must not crash on a malformed or non-insurance PDF — show a graceful error card instead
- All monetary values normalised to float (strip ₹, $, commas)
- All dates normalised to ISO 8601 format (YYYY-MM-DD)
