# Insurance Claims Intelligence — Week 3

Local **single-agent claim process** built on Week 2 **Agentic Hybrid RAG**. One LangGraph agent runs a claim through **Filing → Classification → Investigation → Report → Human Review**, with **Keenable** web search (weather + market parts/labor) and **preliminary vs facility** estimate comparison.

The system **never** approves, denies, settles, or pays claims.

| Doc | Purpose |
| --- | --- |
| [docs/PROJECT_REPORT.docx](docs/PROJECT_REPORT.docx) | Project report (overview, data, prompts, iterations, learnings) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [docs/WEEK3_AGENTIC.md](docs/WEEK3_AGENTIC.md) | Week 3 agentic notes |
| [docs/WEEK3_DEMO_SCRIPTS.docx](docs/WEEK3_DEMO_SCRIPTS.docx) | Short demo recording scripts |
| [SETUP_WINDOWS.md](SETUP_WINDOWS.md) | Windows setup & troubleshooting |

## Quick start

```powershell
Copy-Item backend\.env.example backend\.env
# Set Nebius, Pinecone, Keenable keys

cd backend
uv sync
uv run python scripts\generate_data.py
uv run python scripts\ingest_docs.py
cd ..
.\dev.ps1
```

| URL | View |
| --- | --- |
| http://127.0.0.1:5173 | Adjuster Desk |
| http://127.0.0.1:5173/workflow | Live Workflow (debug) |
| http://127.0.0.1:8000/api/health | API health |

Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/WEEK3_AGENTIC.md](docs/WEEK3_AGENTIC.md)
