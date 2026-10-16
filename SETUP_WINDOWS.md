# Windows setup — Insurance Claims Intelligence

Step-by-step guide for running this app locally on Windows PowerShell.

**No Docker.** External services: **Nebius Token Factory** + **Pinecone** only.

For a short overview, see [README.md](README.md).

---

## Prerequisites

Install and verify before continuing:

| Requirement | How to check |
| --- | --- |
| Windows 10/11 | — |
| [uv](https://docs.astral.sh/uv/) | `uv --version` |
| Python 3.11+ | uv can install this for you |
| Node.js 18+ | `node -v` and `npm -v` |
| Nebius API key | [Token Factory](https://tokenfactory.nebius.com/) |
| Pinecone API key | Pinecone console |

Optional: if PowerShell blocks scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## Setup checklist

Do these once (or after a clean clone).

### 1. Open the project root

```powershell
cd "<path-to>\week 2 Project"
```

You should see `dev.ps1`, `backend\`, and `frontend\` in this folder.

### 2. Install Python dependencies (uv)

```powershell
cd backend
uv sync
```

This creates `backend\.venv` and installs packages from `pyproject.toml`.

**Alternative (pip):** if you prefer a classic venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Prefer `uv` for day-to-day use — `dev.ps1` expects it.

### 3. Configure credentials

Still in `backend\`:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set at least:

| Variable | What to put |
| --- | --- |
| `NEBIUS_API_KEY` | Your Nebius key |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/` |
| `NEBIUS_CHAT_MODEL` | A **tool-calling** chat model from your Nebius catalog (example: `openai/gpt-oss-120b`) |
| `NEBIUS_EMBED_MODEL` | Embedding model (example: `Qwen/Qwen3-Embedding-8B`) |
| `PINECONE_API_KEY` | Your Pinecone key |
| `PINECONE_INDEX` | Index name, e.g. `claims-intelligence` |

Do **not** invent model IDs. Use IDs that appear in your Nebius console or the [model catalog](https://tokenfactory.nebius.com/model-catalog.md).

Use the **same** embedding model for ingest and runtime queries.

### 4. Generate synthetic data

From `backend\`:

```powershell
uv run python scripts\generate_data.py
```

Creates policies, claims, documents, and evaluation fixtures under `backend\data\`.

### 5. Build search indexes

**Option A — full Hybrid RAG (recommended for demos)**  
Needs valid Nebius + Pinecone credentials:

```powershell
uv run python scripts\ingest_docs.py
```

This will:

1. Chunk policy Markdown files  
2. Build the local BM25 index under `data\indexes\`  
3. Discover embedding dimensions from Nebius  
4. Create the Pinecone index if missing (cosine)  
5. Upsert vectors into the `policy-docs` namespace  

**Option B — BM25 only (offline)**  
No cloud keys required; dense/Pinecone retrieval will not work until you run Option A:

```powershell
uv run python scripts\build_bm25_only.py
```

### 6. (Optional) Run tests

```powershell
uv run pytest -q
uv run python scripts\evaluate.py
```

Unit tests do not need cloud keys. Evaluation may call live models depending on the script path.

---

## Run the app

### One command (API + UI)

From the **project root** (not `backend\`):

```powershell
cd "<path-to>\week 2 Project"
.\dev.ps1
```

What `dev.ps1` does:

- Checks for `uv`, `node`, and `npm`
- Syncs Python deps (unless you pass `-SkipSync`)
- Installs frontend `npm` deps if `frontend\node_modules` is missing
- Frees ports **8000** and **5173** if something is still listening
- Starts API + UI via `scripts\run_app.py`

| Service | URL |
| --- | --- |
| UI | http://127.0.0.1:5173 |
| API health | http://127.0.0.1:8000/api/health |
| OpenAPI / Swagger | http://127.0.0.1:8000/docs |

Stop: `Ctrl+C` in that terminal.

Skip sync on later starts:

```powershell
.\dev.ps1 -SkipSync
```

### Separate terminals

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
```

Or manually:

```powershell
# Terminal 1 — backend (from backend\)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — frontend (from frontend\)
npm install
npm run dev
```

Vite proxies `/api` to the backend.

---

## First demo (CLM-1001)

1. Open http://127.0.0.1:5173  
2. Confirm status lights are green: **Backend**, **Nebius**, **Pinecone**, **BM25**  
3. Select claim **CLM-1001**  
4. Keep the default investigation question (or pick an example)  
5. Click **Run Investigation**  
6. Watch the React Flow canvas update from live SSE events  
7. Click nodes to inspect tool input/output  
8. Open **Investigation Report** in the bottom panel  

**Portfolio mode:** set claim to **None** and ask book-level questions (e.g. how many active policies). That path uses `query_portfolio_data`, not policy RAG.

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| `uv` / `npm` / `node` not found | Install the tool and reopen PowerShell |
| Nebius status red | Check `NEBIUS_API_KEY` and `NEBIUS_BASE_URL` in `backend\.env` |
| Tool-calling / tools error | Pick a chat model that supports function/tool calling |
| Pinecone status red | Check `PINECONE_API_KEY` and that ingest completed |
| Pinecone dimension mismatch | Use a **new** `PINECONE_INDEX` name that matches your embed model, then re-run `ingest_docs.py` |
| BM25 status red / empty | Run `uv run python scripts\ingest_docs.py` or `build_bm25_only.py` from `backend\` |
| Port already in use | Run `.\dev.ps1` again (it frees 8000/5173), or stop the old process |
| CORS errors | Use `http://127.0.0.1:5173` or `http://localhost:5173`; ensure `CORS_ORIGINS` in `.env` includes that origin |
| SSE / canvas not updating | Confirm the investigate POST succeeded; in DevTools Network, look for `/api/runs/.../events` |
| Execution policy blocks `.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

---

## Security notes

- Never commit `backend\.env`
- API keys stay on the backend — the browser never sees them
- The system never auto-approves, denies, settles, or pays claims
