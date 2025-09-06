# AI-Powered Communication Assistant

End-to-end assistant to fetch support emails, prioritize them, extract info, generate AI replies (RAG), and manage via a simple dashboard.

## Features
- IMAP email fetching (subject filter: Support/Query/Request/Help)
- Sentiment & priority classification (OpenAI if available, otherwise heuristics)
- Information extraction: phone, alt email, brief summary
- RAG: lightweight retrieval from `docs/kb` files
- AI draft responses (OpenAI GPT with empathetic tone)
- Priority-first queue view
- Streamlit dashboard with analytics
- SQLite storage

## Quick Start

### 1) Clone & Env
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Edit `.env`:
```
IMAP_HOST=imap.gmail.com
IMAP_USER=youremail@gmail.com
IMAP_PASS=your_app_password
OPENAI_API_KEY=sk-...
DB_PATH=backend/assistant.db
API_BASE=http://localhost:8000
```

Enable IMAP in your email. For Gmail, use an App Password if 2FA is on.

### 2) Run Backend (Flask)
```bash
export FLASK_APP=backend/app.py
python -m backend.app
# runs on http://localhost:8000
```

### 3) Run Frontend (Streamlit)
```bash
API_BASE=http://localhost:8000 streamlit run frontend/dashboard.py
```

### 4) Workflow
- Click **Initialize DB**
- Click **Fetch from IMAP**
- Select an email → **Generate AI Draft Reply** → Edit → **Send** (simulated)  

## Notes
- Actual SMTP sending can be added in `/send` endpoint.
- If `OPENAI_API_KEY` is missing, the system falls back to rules.
- Add your product FAQs in `docs/kb/*.md` to power RAG.
