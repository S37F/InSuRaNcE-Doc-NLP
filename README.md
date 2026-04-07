# PolicyLens

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-ff4b4b)
![spaCy](https://img.shields.io/badge/spaCy-3.7%2B-09a3d5)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude%20Sonnet%204-5c4dff)
![Pandas](https://img.shields.io/badge/Pandas-2.0%2B-130654)

PolicyLens is a Streamlit application for extracting structured intelligence from insurance PDFs.
It combines rule-based parsing, spaCy NER, and Claude-powered completion to generate consistent
fields that can be reviewed, flagged for risk, queried in chat, and exported for reporting.

The app is designed for real-world operational use in brokerage and underwriting workflows. It
supports single and batch uploads, document-type-aware schemas, graceful failure handling for
noisy inputs, and export-ready outputs in Excel and CSV formats.

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies and download the spaCy model.
3. Configure environment variables.
4. Run Streamlit.

```bash
python -m venv venv
source venv/bin/activate  # Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download en_core_web_lg
cp .env.example .env
streamlit run app.py
```

## Streamlit Cloud Deployment

1. Push this repository to GitHub.
2. In Streamlit Cloud, create a new app from the repo with `app.py` as entrypoint.
3. In app settings, add secrets from `.streamlit/secrets.toml.example`.
4. Ensure dependencies install from `requirements.txt` and run `setup.sh` if needed.
5. Deploy and verify upload, extraction, chat, and export flows.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | None | Anthropic API key for LLM extraction and chat |
| `COVERAGE_LIMIT_THRESHOLD` | No | `100000` | Minimum acceptable coverage limit for risk flagging |
| `DEDUCTIBLE_RATIO_THRESHOLD` | No | `0.10` | Maximum deductible-to-limit ratio before flagging |
| `EXPIRY_WARNING_DAYS` | No | `30` | Days-to-expiry threshold for expiring-soon flag |

## Folder Structure

```text
policylens/
├── app.py
├── requirements.txt
├── .env.example
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── config/
│   └── settings.py
├── core/
│   ├── pdf_extractor.py
│   ├── doc_classifier.py
│   ├── nlp_pipeline.py
│   ├── llm_extractor.py
│   ├── risk_engine.py
│   └── chat_engine.py
├── utils/
│   ├── export.py
│   ├── formatters.py
│   └── validators.py
└── pages/
    ├── 1_Upload.py
    ├── 2_Results.py
    ├── 3_Chat.py
    └── 4_Export.py
```
