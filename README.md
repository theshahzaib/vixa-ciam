# ViXa Platform — CIAM Onboarding Flow

Developed by [Shahzaib Asif](mailto:shahzaib.asif024@gmail.com) while doing assessment work for **ViXa**. This repository contains:

A working implementation of the **ViXa Customer Identity & Access Management
(CIAM)** onboarding flow described in the architecture brief: an *identity-first,
event-driven* platform with a clean separation between CIAM and the **Ost
Infinity** system of record.

- **Backend:** Python + **FastAPI** (async, typed, auto-documented)
- **Frontend:** **React** (Vite) SPA consuming the FastAPI endpoints
- **Architecture fidelity:** every one of the brief's **eight tiers**, the
  **five-phase onboarding saga** with compensating actions, all **17 workflows**,
  the **anti-corruption layer**, the **event backbone with a dead-letter queue**,
  and the full **security/compliance** layer are implemented — not simplified.


## Repository layout

```
vixa-ciam/
├── REPORT.md              # Main deliverable: design report & recommendations
├── docs/                  # Architecture, API design, recommendations (deep dives)
├── backend/               # FastAPI service (the CIAM platform)
│   └── app/               # core, gateway, ciam, domains, acl, adapters, api/v1
├── frontend/              # React SPA (register wizard, login, products, admin)
└── docker-compose.yml     # Illustrative production wiring (Postgres/Redis/Kafka)
```

## Quickstart

The MVP runs with **zero infrastructure** — the PostgreSQL, Redis and Kafka
components are in-memory stand-ins behind clean interfaces (see the report for
how they map to production).

### 1. Backend

Virtual Environment (venv) users:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Conda users:

```bash
cd backend
conda create -n vixa python=3.12 -y
conda activate vixa
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

- API:        http://127.0.0.1:8000
- Swagger UI:  http://127.0.0.1:8000/docs  (interactive, auto-generated)

Run the test suite (drives the full saga end-to-end):

```bash
pytest -q
```

### 2. Frontend

```bash
cd frontend 
npm install
npm run dev
```

Open http://localhost:5173 # For frontend UI

---
Developed with ❤️ by Shahzaib Asif for ViXa's CIAM assessment.