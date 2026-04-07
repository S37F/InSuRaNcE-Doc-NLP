# prompt.md — Phase-wise Cursor Prompts for PolicyLens

> **How to use this file:**
> Copy each Phase prompt into Cursor's chat (CMD+L or Composer).
> Complete and verify each phase before moving to the next.
> Do NOT skip phases — each phase depends on the previous one.

---

## ✅ PRE-FLIGHT CHECKLIST (Do this before Phase 1)

Before giving Cursor any prompt, ensure:
- [ ] Python 3.11+ is installed
- [ ] A virtual environment is created: `python -m venv venv && source venv/bin/activate`
- [ ] You have an Anthropic API key ready
- [ ] `CONTEXT.md` and `rules.md` are in the project root
- [ ] You've told Cursor: *"Read CONTEXT.md and rules.md before writing any code. Follow rules.md strictly in all files."*
---

---

## PHASE 1 — Project Scaffold & Environment Setup

### Goal
Create the complete folder structure, config files, and environment setup. No business logic yet.

### Cursor Prompt

```
Read CONTEXT.md and rules.md first.

Set up the complete PolicyLens project scaffold:

1. Create the exact folder structure defined in CONTEXT.md Section 7. Add __init__.py to every package folder.

2. Create requirements.txt with all packages from rules.md Section 13 (pinned versions).

3. Create .env.example with all variables from CONTEXT.md Section 12.

4. Create .streamlit/config.toml with:
   - theme: base = "light", primaryColor = "#1B4F72", backgroundColor = "#FFFFFF", secondaryBackgroundColor = "#EBF5FB", textColor = "#1C2833"
   - layout: wide = true

5. Create .streamlit/secrets.toml.example showing the ANTHROPIC_API_KEY placeholder.

6. Create config/settings.py with:
   - DOC_TYPE_KEYWORDS dict (from CONTEXT.md Section 3)
   - ENTITY_SCHEMA dict (all fields per doc type from CONTEXT.md Section 4)
   - RISK_FLAG_RULES dict (from CONTEXT.md Section 5)
   - All threshold constants (COVERAGE_LIMIT_THRESHOLD, DEDUCTIBLE_RATIO_THRESHOLD, EXPIRY_WARNING_DAYS) loaded from environment variables with sensible defaults

7. Create app.py that:
   - Sets page config (wide layout, title "PolicyLens", insurance shield favicon emoji)
   - Initialises ALL session state keys from CONTEXT.md Section 11 with their default values
   - Sets up logging as defined in rules.md Section 11
   - Shows a sidebar with app name, tagline, and page navigation links
   - Shows a homepage with app description and a "Get Started" call to action

8. Create a Makefile with targets: install, download-model, run, clean.
   - install: pip install -r requirements.txt
   - download-model: python -m spacy download en_core_web_lg
   - run: streamlit run app.py

Follow rules.md for all file conventions. No business logic yet.
```

### ✅ Phase 1 Verification
- `streamlit run app.py` launches without errors
- Sidebar and homepage render correctly
- `make install && make download-model` completes successfully

---

---

## PHASE 2 — PDF Extraction & Document Classification

### Goal
Build the PDF text extraction module and the rule-based document type classifier.

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Build core/pdf_extractor.py and core/doc_classifier.py.

--- core/pdf_extractor.py ---
Create a function:
    extract_pdf(file_obj: BinaryIO) -> dict

This function must:
- Accept a file object (from st.file_uploader)
- Use pdfplumber to extract text page by page
- Return a dict with:
  {
    "full_text": str,          # All pages joined with newline
    "pages": List[str],        # Per-page text list
    "page_count": int,
    "filename": str            # From file_obj.name
  }
- Raise ValueError if no text is extractable (e.g. scanned image-only PDF)
- Wrap in try/except pdfplumber.PDFSyntaxError and generic Exception
- Include full Google-style docstring
- Use the logger from logging.getLogger(__name__)

--- core/doc_classifier.py ---
Create a function:
    classify_document(full_text: str) -> str

This function must:
- Use DOC_TYPE_KEYWORDS from config/settings.py
- Perform case-insensitive keyword matching against the full_text
- Return one of: "policy", "certificate", "endorsement", "claim", "unknown"
- Score each type by keyword hit count and return the highest scoring type
- Return "unknown" if no type scores above 0
- Include full docstring and logging

Write a quick test block at the bottom of each file under `if __name__ == "__main__":` that prints sample output using a hardcoded text snippet.

Follow rules.md strictly.
```

### ✅ Phase 2 Verification
- `python core/pdf_extractor.py` runs without error
- `python core/doc_classifier.py` correctly classifies a sample text snippet
- No Streamlit imports in these files

---

---

## PHASE 3 — spaCy NER Pipeline

### Goal
Build the spaCy-based fast entity extractor with custom insurance-domain rules.

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Build core/nlp_pipeline.py.

Create a function:
    extract_entities_spacy(full_text: str, doc_type: str) -> dict

Requirements:
1. Load the spaCy model using a module-level cached loader (NOT @st.cache_resource — this is a pure Python module). Use a simple singleton pattern with a global variable.

2. Build a custom EntityRuler pipeline component with patterns for:
   - POLICY_NUMBER: regex patterns like "POL-\d+", "Policy No[.:]\s*\w+", "P\d{6,}"
   - PREMIUM_AMOUNT: patterns matching currency + number e.g. "₹\s*[\d,]+", "\$[\d,]+", "USD\s*[\d,]+"
   - COVERAGE_LIMIT: patterns near keywords "limit", "sum insured", "coverage amount"
   - DEDUCTIBLE: patterns near keywords "deductible", "excess"
   - CLAIM_NUMBER: patterns like "CLM-\d+", "Claim No[.:]\s*\w+"
   - ENDORSEMENT_NUMBER: patterns like "END-\d+", "Endorsement No[.:]\s*\w+"

3. Use spaCy's built-in NER for:
   - ORG → maps to insurer_name, insured_name, certificate_holder
   - PERSON → maps to adjuster_name, claimant_name
   - DATE → maps to policy_start_date, policy_end_date, effective_date, expiry_date, date_of_loss
   - MONEY → fallback for premium, limits if custom ruler misses

4. Apply doc_type-aware field mapping:
   - Use ENTITY_SCHEMA from config/settings.py to know which fields apply to which doc_type
   - Only return fields relevant to the detected doc_type

5. Normalise all extracted values:
   - Monetary values → float (strip ₹, $, USD, commas) using utils/formatters.py
   - Dates → "YYYY-MM-DD" string using utils/formatters.py
   - Unknown fields → None (not empty string)

6. Return a dict matching the schema for the given doc_type. Missing fields should be None.

Also build utils/formatters.py with:
    normalise_currency(value: str) -> float | None
    normalise_date(value: str) -> str | None   # returns "YYYY-MM-DD" or None

Both functions must handle malformed input gracefully and return None on failure.

Include docstrings and logging on all functions.
Follow rules.md.
```

### ✅ Phase 3 Verification
- Run `python core/nlp_pipeline.py` with sample insurance text
- Monetary values return as floats
- Dates return in YYYY-MM-DD format
- Missing fields return None, not empty strings

---

---

## PHASE 4 — Claude API Extraction & Risk Engine

### Goal
Build the LLM-based extractor for complex fields and the risk flagging engine.

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Build core/llm_extractor.py and core/risk_engine.py.

--- core/llm_extractor.py ---

Create:
    get_claude_client() -> anthropic.Anthropic

    extract_entities_llm(full_text: str, doc_type: str, spacy_result: dict) -> dict

Requirements for extract_entities_llm:
1. Load API key using the combined dotenv + st.secrets pattern from rules.md Section 5.
2. Use model: claude-sonnet-4-20250514, max_tokens: 2048, temperature: 0
3. Build a system prompt that:
   - Defines the role: "You are an expert insurance document analyser."
   - Lists the exact JSON schema for the given doc_type (pull from config/settings.py ENTITY_SCHEMA)
   - States: "Return ONLY a valid JSON object. No explanation, no markdown fences, no preamble."
   - Instructs Claude to fill only the fields that spaCy left as null (pass spacy_result as context)
4. User message: the full_text (truncated to 12,000 characters if longer, with a note appended)
5. Parse Claude's response using the safe_parse_json() function defined in rules.md Section 6
6. Merge Claude's result with spacy_result: spaCy values take priority, Claude fills nulls only
7. Wrap the entire API call in try/except for anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError
8. On any failure, log the error and return spacy_result unchanged (graceful degradation)

--- core/risk_engine.py ---

Create:
    compute_risk_flags(extracted_fields: dict, doc_type: str, filename: str) -> List[dict]

Each flag in the returned list must be:
    {
        "filename": str,
        "flag_name": str,
        "severity": str,    # "High" | "Medium" | "Low"
        "details": str      # Human-readable explanation
    }

Implement ALL flag rules from CONTEXT.md Section 5.
Use thresholds from config/settings.py (never hardcode numbers).
Use python-dateutil to parse dates for expiry comparison against today's date.
Return an empty list if no flags are triggered.
Include docstrings and logging.
Follow rules.md.
```

### ✅ Phase 4 Verification
- Run `python core/llm_extractor.py` with sample text — Claude fills missing fields
- Run `python core/risk_engine.py` with sample extracted fields — flags are returned correctly
- A policy with an expiry date 15 days from today should trigger 🔴 "Policy Expiring Soon"
- An empty coverage limit should trigger 🟠 "Missing Critical Fields"

---

---

## PHASE 5 — Chat Engine

### Goal
Build the document Q&A chat module using Claude with conversation memory.

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Build core/chat_engine.py.

Create:
    answer_question(
        question: str,
        full_text: str,
        chat_history: List[dict],
        doc_type: str
    ) -> str

Requirements:
1. Load Claude client using the same get_claude_client() from core/llm_extractor.py (import it, don't duplicate)
2. System prompt must:
   - Define role: "You are a specialist insurance document analyst."
   - State: "Answer questions based ONLY on the document text provided. If the answer is not in the document, say so clearly."
   - Include the doc_type so Claude knows context (e.g. "This is a Certificate of Insurance.")
3. Build the messages array:
   - First message: user sends the full_text as context block: "Here is the document:\n\n{full_text}\n\nPlease confirm you have read it."
   - Second message: assistant response "Understood. I have read the document. What would you like to know?"
   - Then append the last 10 turns from chat_history (role: user/assistant)
   - Finally append the new question as the latest user message
4. Cap total input to 15,000 characters of full_text — truncate with a trailing note if needed
5. max_tokens: 1024, temperature: 0.3
6. Return the assistant's text reply as a plain string
7. Wrap in try/except — on failure return: "I encountered an error processing your question. Please try again."

Include full docstring. Follow rules.md.
```

### ✅ Phase 5 Verification
- Run `python core/chat_engine.py` with sample document text and a question
- Claude responds based only on document content
- Asking about something not in the document returns a clear "not found" response

---

---

## PHASE 6 — Streamlit Pages (Upload + Results)

### Goal
Build the Upload page (single + batch) and the Results page (extracted fields table + risk flags).

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Build pages/1_Upload.py and pages/2_Results.py.

--- pages/1_Upload.py ---

Build the upload interface:
1. Page title: "📄 Upload Documents"
2. Two tabs: "Single Document" and "Batch Upload"
3. Single tab:
   - st.file_uploader accepting PDF only, single file
   - On upload: call extract_pdf(), classify_document(), extract_entities_spacy(), extract_entities_llm(), compute_risk_flags()
   - Show st.progress bar during processing steps with step labels
   - On success: store result in st.session_state["extracted_results"] and st.session_state["uploaded_docs"]
   - Show st.success with filename and detected document type
   - Show a "View Results →" button that navigates to page 2

4. Batch tab:
   - st.file_uploader accepting multiple PDFs
   - On upload: show list of filenames with status icons (⏳ pending)
   - "Process All" button triggers processing loop
   - Use st.progress() + st.status() for each file
   - Update st.session_state["processing_status"] per file: "pending" → "done" or "error"
   - After all done: show summary — X processed successfully, Y failed
   - Failed files show st.warning with filename and error message

5. All processing wrapped in try/except with user-facing st.error on failure

--- pages/2_Results.py ---

Build the results display:
1. Page title: "📊 Results"
2. If no results in session state: show st.info("No documents processed yet.") with link to Upload page
3. Document selector: st.selectbox listing all processed filenames
4. For selected document show:
   a. "Document Info" section:
      - Document type badge (styled with st.markdown and color)
      - Filename, page count
   b. "Extracted Fields" section:
      - st.dataframe showing field names and values (2 columns: Field, Value)
      - Highlight None/missing values in red using pandas Styler
      - Do NOT use st.table — use st.dataframe with use_container_width=True
   c. "Risk Flags" section:
      - If no flags: green st.success("No risk flags detected ✅")
      - If flags: display each flag as st.warning (Medium) or st.error (High) with flag name and details
      - Show a summary count: "X High, Y Medium flags"
5. Bottom of page: "Go to Chat →" and "Export →" navigation buttons

Follow rules.md for all Streamlit conventions.
No business logic in these pages — only call functions from core/ and utils/.
```

### ✅ Phase 6 Verification
- Upload a real PDF and verify the full pipeline runs end to end
- Results page shows extracted fields table and risk flags
- Batch upload processes multiple files with progress indication
- A failed file shows warning without crashing the app

---

---

## PHASE 7 — Chat Page & Export Page

### Goal
Build the interactive document Q&A chat interface and the export functionality.

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Build pages/3_Chat.py and pages/4_Export.py and utils/export.py.

--- pages/3_Chat.py ---

Build the chat interface:
1. Page title: "💬 Chat with Document"
2. If no documents processed: st.info with link to upload page
3. Document selector at top: st.selectbox of processed filenames
4. Display chat history for selected document from st.session_state["chat_history"]
   - Render each message using st.chat_message("user") and st.chat_message("assistant")
5. st.chat_input at bottom: "Ask a question about this document..."
6. On submit:
   - Append user message to chat history immediately and re-render
   - Show st.spinner("Thinking...") while calling answer_question()
   - Append assistant response to chat history
   - Use st.rerun() to refresh the display
7. "Clear Chat" button in sidebar that resets chat_history for current document
8. Show document type and filename in the sidebar for context

--- utils/export.py ---

Build:
    export_to_excel(results: List[dict], flags: List[dict]) -> BytesIO
    export_to_csv(results: List[dict]) -> str

For export_to_excel:
- Create a BytesIO buffer (never write to disk)
- Use pandas ExcelWriter with openpyxl engine
- Sheet 1 "Extracted Data": one row per document, columns from flattened field dict
  - List fields (exclusions etc.) joined as semicolon-separated string
  - None values shown as empty cell
- Sheet 2 "Risk Flags": columns: Filename, Flag Name, Severity, Details
- Sheet 3 "Summary": 
  - Total documents processed
  - Flag counts by severity
  - Export timestamp (ISO format)
  - App version: "PolicyLens v1.0"
- Column headers: Title Case with spaces
- Return the BytesIO buffer seeked to position 0

For export_to_csv:
- Flatten results list to a pandas DataFrame
- Return as CSV string (df.to_csv(index=False))

--- pages/4_Export.py ---

Build the export page:
1. Page title: "⬇️ Export Results"
2. If no results: st.info with link to upload page
3. Show a summary table of all processed documents (filename, doc type, flag count)
4. Two download buttons side by side using st.columns:
   - "Download Excel (.xlsx)" using st.download_button with export_to_excel()
   - "Download CSV (.csv)" using st.download_button with export_to_csv()
5. Both buttons use BytesIO/string directly — never write to disk

Follow rules.md strictly.
```

### ✅ Phase 7 Verification
- Chat with a processed document — responses reference document content
- Multi-turn conversation works (second question shows context from first)
- Excel download produces file with 3 correct sheets
- CSV download produces flat file with all extracted fields

---

---

## PHASE 8 — Polish, Error Hardening & Streamlit Cloud Deployment

### Goal
Harden the app for production, add final UI polish, and deploy to Streamlit Cloud.

### Cursor Prompt

```
Read CONTEXT.md and rules.md before writing code.

Perform production hardening and deployment preparation:

1. GRACEFUL ERROR CARDS
   In pages/1_Upload.py, wrap the entire processing pipeline in a try/except.
   On any unexpected error, show an error card using st.expander with:
   - Title: "⚠️ Processing Error — {filename}"
   - Content: error type, error message, and "Please check the file is a valid, text-based PDF."
   Never show a Python traceback to the user.

2. INPUT VALIDATION
   In pages/1_Upload.py, before processing:
   - Check file size < 20MB, else show st.warning and skip
   - Check file extension is .pdf (case-insensitive), else skip
   - Check extracted full_text is not empty, else show warning and skip

3. HOMEPAGE IMPROVEMENT (app.py)
   Update the homepage to show:
   - A hero section with the PolicyLens logo (emoji-based), tagline, and a 3-column feature overview
   - Feature cards: "🔍 Smart Extraction", "🚨 Risk Flags", "💬 Document Chat"
   - A "Supported Document Types" section listing all 4 types
   - Processing statistics if any documents are in session state (e.g. "3 documents analysed, 2 flags detected")

4. SIDEBAR ENHANCEMENT
   Update sidebar in app.py:
   - Show document count from session_state
   - Show a mini risk summary if results exist (total High/Medium flags)
   - Add a "Clear All Data" button that resets all session state keys to defaults

5. STREAMLIT CLOUD DEPLOYMENT PREP
   Create the following files:
   
   a. packages.txt (empty or with any system deps if needed)
   
   b. setup.sh:
      #!/bin/bash
      pip install -r requirements.txt
      python -m spacy download en_core_web_lg
   
   c. .streamlit/secrets.toml.example:
      ANTHROPIC_API_KEY = "your_key_here"
      COVERAGE_LIMIT_THRESHOLD = "100000"
      DEDUCTIBLE_RATIO_THRESHOLD = "0.10"
      EXPIRY_WARNING_DAYS = "30"
   
   d. README.md with:
      - Project overview (2 paragraphs)
      - Setup instructions (local dev)
      - Streamlit Cloud deployment steps
      - Environment variables table
      - Folder structure reference
      - Tech stack badges (markdown)

6. FINAL CHECKS
   Review every page file and ensure:
   - No page renders without a check for empty session state
   - All st.file_uploader widgets have type=["pdf"] restriction
   - All st.dataframe calls have use_container_width=True
   - All external calls (Claude, spaCy) are inside try/except blocks

Follow rules.md strictly.
```

### ✅ Phase 8 Verification
- App handles a non-PDF upload gracefully (shows warning, doesn't crash)
- App handles a scanned/image PDF gracefully (shows warning, doesn't crash)
- Push to GitHub and connect to Streamlit Cloud
- Add ANTHROPIC_API_KEY in Streamlit Cloud → Settings → Secrets
- App deploys and works end to end in cloud environment

---

---

## 🏁 FINAL CHECKLIST

After all 8 phases:

- [ ] Single PDF upload → extract → results → chat → export works end to end
- [ ] Batch upload → all files processed → bulk export works
- [ ] Risk flags fire correctly for expiring/expired policies
- [ ] Chat remembers conversation history within a session
- [ ] Excel export has 3 sheets: Extracted Data, Risk Flags, Summary
- [ ] App does not crash on malformed PDFs
- [ ] No API keys in source code
- [ ] spaCy model loads once (cached), not on every interaction
- [ ] Deployed to Streamlit Cloud and publicly accessible
- [ ] README.md is complete and accurate

---

## 📌 QUICK REFERENCE — Key Files

| File | Purpose |
|---|---|
| `config/settings.py` | All constants, schemas, thresholds |
| `core/pdf_extractor.py` | PDF → raw text |
| `core/doc_classifier.py` | Detect document type |
| `core/nlp_pipeline.py` | spaCy entity extraction |
| `core/llm_extractor.py` | Claude API entity extraction |
| `core/risk_engine.py` | Risk flag computation |
| `core/chat_engine.py` | Document Q&A via Claude |
| `utils/export.py` | Excel + CSV export |
| `utils/formatters.py` | Date + currency normalisation |
| `pages/1_Upload.py` | Upload UI |
| `pages/2_Results.py` | Results + flags UI |
| `pages/3_Chat.py` | Chat UI |
| `pages/4_Export.py` | Export UI |
