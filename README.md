# Clarify

A communication aid for patients to articulate their feelings before a scheduled medical visit. Powered by Claude and a RAG pipeline. No patient data is stored.

## Setup

```bash
python -m venv venv
source venv/bin/activate
cp .env.example .env        # then add your real ANTHROPIC_API_KEY
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```
