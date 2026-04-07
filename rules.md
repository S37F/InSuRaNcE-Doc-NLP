# rules.md — Cursor Coding Rules for PolicyLens

These rules must be followed in EVERY file Cursor generates or modifies.
Do not deviate unless explicitly instructed in the phase prompt.

---

## 1. Language & Style

- Python 3.11+ only
- Follow PEP 8 strictly
- Use type hints on ALL function signatures
- Use f-strings for string formatting (no `.format()` or `%`)
- Maximum line length: 100 characters
- Use `snake_case` for variables and functions
- Use `PascalCase` for class names
- Use `UPPER_SNAKE_CASE` for constants in `config/settings.py`

---

## 2. File & Module Rules

- Every folder must have an `__init__.py`
- One responsibility per file — do not mix extraction logic with UI logic
- No business logic inside `pages/` files — pages only call functions from `core/` and `utils/`
- All constants (thresholds, keywords, schemas) live in `config/settings.py` only
- Never import from `pages/` into `core/` or `utils/`

---

## 3. Docstrings

Every function must have a Google-style docstring:

```python
def extract_text(pdf_path: str) -> dict:
    """Extracts raw text from a PDF file using pdfplumber.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        A dict with keys 'full_text' (str) and 'pages' (List[str]).

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF has no extractable text.
    """
```

---

## 4. Error Handling

- Wrap ALL external calls (Claude API, pdfplumber, spaCy) in try/except
- Never use bare `except:` — always catch specific exceptions
- Log errors using Python's `logging` module (not `print`)
- In Streamlit pages: display errors using `st.error()`, never `st.write()` for errors
- On Claude API failure: show `st.error("LLM extraction failed. Showing partial results.")` and continue with spaCy-only results
- On PDF parse failure: show `st.warning("Could not extract text from this file.")` and skip that file

```python
# Correct pattern
try:
    result = claude_client.messages.create(...)
except anthropic.APIConnectionError as e:
    logging.error(f"Claude API connection error: {e}")
    st.error("Could not connect to Claude API. Check your API key.")
    return {}
except anthropic.RateLimitError as e:
    logging.error(f"Claude API rate limit: {e}")
    st.warning("Rate limit hit. Retrying in 10 seconds...")
    time.sleep(10)
```

---

## 5. API Key & Secrets Management

- NEVER hardcode API keys in any file
- Local dev: load via `python-dotenv`

```python
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
```

- Streamlit Cloud: load via `st.secrets`

```python
import streamlit as st
api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
```

- Always use the combined pattern above so the app works both locally and on Streamlit Cloud

---

## 6. Claude API Rules

- Model: always use `claude-sonnet-4-20250514` — never change this without updating CONTEXT.md
- max_tokens: 2048 for extraction calls, 1024 for chat replies
- Temperature: 0 for extraction (deterministic), 0.3 for chat
- Extraction calls must instruct Claude to return ONLY valid JSON — no prose, no markdown fences
- Always parse Claude's response with a safe JSON parser:

```python
import json, re

def safe_parse_json(text: str) -> dict:
    """Strips markdown fences and parses JSON safely."""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logging.error(f"Failed to parse Claude JSON: {text[:200]}")
        return {}
```

- Chat history passed to Claude must be capped at last 10 turns to avoid context overflow

---

## 7. spaCy Rules

- Load model once using `@st.cache_resource`:

```python
@st.cache_resource
def load_nlp_model():
    return spacy.load("en_core_web_lg")
```

- Custom entity patterns must be defined in `core/nlp_pipeline.py` using `EntityRuler`
- Never run spaCy on more than 1,000,000 characters per document — truncate with a warning
- spaCy is for fast first-pass extraction only — Claude fills gaps

---

## 8. Streamlit Rules

- Use `st.session_state` for ALL cross-page state — never use global variables
- Initialise all session state keys at app startup in `app.py`:

```python
defaults = {
    "uploaded_docs": [],
    "extracted_results": [],
    "active_doc_index": 0,
    "chat_history": {},
    "processing_status": {},
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val
```

- Use `@st.cache_data` for PDF extraction (keyed by file hash, not filename)
- Use `st.progress()` + `st.status()` for batch processing loops
- Never use `st.experimental_*` APIs — use stable APIs only
- Page layout: always `st.set_page_config(layout="wide")`
- Sidebar: navigation and settings only — no results displayed in sidebar

---

## 9. Data & Type Rules

- All extracted fields stored as Python dicts matching the schema in CONTEXT.md
- Monetary values: always normalise to `float` — strip currency symbols and commas
- Dates: always normalise to `YYYY-MM-DD` string format using `dateutil.parser`
- Boolean fields (e.g., `additional_insured`): store as Python `bool`, not string
- Lists (e.g., `exclusions`): store as `List[str]`, never as a single comma-separated string
- Missing/unextracted fields: store as `None`, never as empty string `""`

---

## 10. Export Rules

- Excel export must use `openpyxl` via `pandas.ExcelWriter`
- Excel file must have 3 sheets:
  - `"Extracted Data"` — one row per document, all fields as columns
  - `"Risk Flags"` — one row per flag, columns: Filename, Flag Name, Severity, Details
  - `"Summary"` — document count, flag counts by severity, processing timestamp
- CSV export: flat file of extracted data only (no flags sheet)
- Column headers in exports: Title Case with spaces (not snake_case)
- Provide download via `st.download_button` — never write files to disk on Streamlit Cloud

---

## 11. Logging

- Use Python's built-in `logging` module — not `print`
- Set up logging in `app.py`:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
```

- Each module uses its own logger: `logger = logging.getLogger(__name__)`

---

## 12. Testing Conventions (for future phases)

- Every function in `core/` must be independently testable (no Streamlit dependencies)
- Use `pytest` for unit tests
- Test files go in `tests/` directory mirroring `core/` structure
- Mock Claude API calls in tests using `unittest.mock`

---

## 13. requirements.txt Rules

- Pin major versions, allow minor updates:

```
streamlit>=1.32.0,<2.0.0
pdfplumber>=0.10.0,<1.0.0
spacy>=3.7.0,<4.0.0
anthropic>=0.25.0,<1.0.0
pandas>=2.0.0,<3.0.0
openpyxl>=3.1.0,<4.0.0
python-dotenv>=1.0.0,<2.0.0
python-dateutil>=2.8.0,<3.0.0
```

- Add spaCy model as a `packages.txt` or post-install step — NOT as a pip package in requirements.txt
- Include a `setup.sh` or `Makefile` with `python -m spacy download en_core_web_lg`

---

## 14. What Cursor Must NEVER Do

- Never generate placeholder/stub functions without a TODO comment explaining what's missing
- Never skip error handling on API or file I/O operations
- Never use `st.write()` to display structured data — use `st.dataframe()` or `st.table()`
- Never put raw API keys in any file, even in comments
- Never create a new session state key inside a page without first declaring it in `app.py`
- Never use synchronous sleep in Streamlit without a user-visible waiting message
- Never return `None` from an extraction function silently — always log what failed and why
