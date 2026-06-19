# saipol

## Cursor Cloud specific instructions

### Repository state
- The `main` branch currently contains only `README.md`. The actual application
  (a Python tool named **colza-brief**) lives on feature branches (e.g.
  `cursor/create-colza-brief-*`) and has not been merged into `main` yet.
- When app code is present, expect `main.py`, `requirements.txt`, and
  `.env.example` at the repo root.

### What the app does
`main.py` (`colza-brief`) fetches oilseed commodity prices (rapeseed MATIF, soy
oil/meal) via `yfinance`, generates a French morning trading brief via the
Gemini API (`google-genai`), and emails it through Gmail.

### Environment
- Python 3.12 with a virtualenv at `.venv` (the update script creates it and
  installs `requirements.txt` when that file is present).
- System package `python3.12-venv` is required to create the venv (already
  available in the base image).
- Run the app with `.venv/bin/python main.py`. Activate the env with
  `source .venv/bin/activate` if preferred.

### Secrets / running notes (non-obvious)
- Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY`, `GMAIL_USER`,
  `GMAIL_APP_PASSWORD` (loaded via `python-dotenv`).
- Price fetching via `yfinance` works with **no** credentials, so it is the
  easiest way to smoke-test the environment. The Gemini brief and email steps
  require the secrets above.
- The `RS=F` (rapeseed MATIF) ticker intermittently returns no data from Yahoo
  Finance; the other tickers (`ZL=F`, `ZM=F`) are reliable for a smoke test.

### Tests / lint
- No automated test or lint configuration exists in the repo yet.
