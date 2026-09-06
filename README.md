# RAG Document Analytics Platform

Document Q&A with hybrid retrieval: upload PDF/DOCX/TXT, ingest asynchronously,
and ask grounded questions answered only from your own documents.

Current state: **Phases 1–12** of [project_plan.md](project_plan.md) — the
complete production retrieval pipeline: hybrid search, cross-encoder reranking,
query rewriting and verified citations. See [PROGRESS.md](PROGRESS.md) for what
each phase delivered.

```
upload ──> parse ──> clean ──> chunk ──> embed ──> Elasticsearch
                                                        │
question + history ──> rewrite ──> filter ──┬──> dense kNN ──┐
                                            └──> BM25 ───────┴──> RRF
                                                                   │
                              answer + citations <── LLM <── cross-encoder rerank
```

## Stack

| Concern | Choice |
| --- | --- |
| API | Django 5 + DRF (token auth) |
| Metadata store | PostgreSQL |
| Async ingestion | Celery + Redis |
| Chunk store / retrieval | Elasticsearch 8 (BM25 + dense kNN + filters) |
| Embeddings | `BAAI/bge-small-en-v1.5` via sentence-transformers |
| Reranking | `BAAI/bge-reranker-base` cross-encoder (`identity` backend for offline dev) |
| Generation | Gemini or local Ollama (`stub` provider for offline dev) |
| UI | Streamlit |

## Setup

1. **Infrastructure** (Postgres, Redis, Elasticsearch):

```bash
docker compose up -d
```

Postgres is published on host port **5433** so it cannot collide with a locally
installed Postgres on 5432; Redis (6379) and Elasticsearch (9200) use their
usual ports.

2. **Python environment**:

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```

3. **Configuration** — copy `.env.example` to `.env` and set at least the LLM
   provider (`LLM_PROVIDER=ollama` with `ollama serve` running, or
   `LLM_PROVIDER=gemini` with `GEMINI_API_KEY`).

4. **Database**:

```bash
.venv/Scripts/python manage.py migrate
```

## Running

Three processes. On Windows the Celery worker needs the solo pool.

```bash
.venv/Scripts/python manage.py runserver
```

```bash
.venv/Scripts/celery -A config worker -l info --pool=solo
```

```bash
.venv/Scripts/streamlit run ui/app.py
```

Sample documents for a first run:

```bash
.venv/Scripts/python samples/build_samples.py
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register/` | create a user, returns a token |
| POST | `/api/auth/login/` | returns a token |
| POST | `/api/auth/logout/` | invalidates the token |
| GET | `/api/documents/` | list your documents and ingestion status |
| POST | `/api/documents/` | upload a document (multipart `file`) |
| DELETE | `/api/documents/{id}/` | delete a document and its indexed chunks |
| POST | `/api/qa/ask/` | ask a question |

Ask request body:

```json
{
  "question": "What about contractors?",
  "mode": "hybrid",
  "rerank": true,
  "history": [
    {"role": "user", "content": "How many annual leave days do employees get?"},
    {"role": "assistant", "content": "20 days. [1]"}
  ],
  "document_ids": [1, 2],
  "content_types": ["pdf"],
  "debug": true
}
```

`mode` is `dense`, `bm25` or `hybrid`; `rerank` toggles the cross-encoder, so
the four configurations the evaluation phases compare (`dense`, `bm25`,
`hybrid`, `hybrid+reranker`) are all reachable from one request.

`history` is optional. When present, the question is rewritten into a standalone
retrieval query; the response reports both under `query`.

The response carries `citations` — the `[n]` markers the answer actually used,
resolved to document, page and section. Markers pointing at sources that were
never supplied are removed from the answer and listed under
`debug.dropped_citations`.

`debug: true` adds the per-stage result lists (dense, BM25, RRF, reranked,
final) that the Evaluation/Debug screen renders.

## Tests

```bash
.venv/Scripts/python -m pytest
```

The suite runs on SQLite with the `stub` LLM provider and mocked retrievers, so
it needs no Docker services and no model downloads.

## Layout

```
config/       settings, URLs, Celery app
users/        register / login / logout
documents/    Document model, upload API, lifecycle services
ingestion/    parser (all formats), cleaner, chunker, embeddings, indexer, pipeline + Celery task
retrieval/    index (ES client + mapping), filters, dense, bm25, fusion, retriever
reranking/    cross-encoder reranker (the final ordering stage)
generation/   prompts, query rewriter, context builder, citations, LLM providers
qa/           ask endpoint and the question-answering service
ui/           Streamlit screens (documents, Q&A, debug)
tests/        unit and API tests
samples/      generator for sample PDF/DOCX/TXT documents
```
