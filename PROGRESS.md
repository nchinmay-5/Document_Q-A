# Build Progress

Implementation log for [project_plan.md](project_plan.md). One section per
phase: what was built, the decisions worth knowing, and how it was verified.

**Scope delivered: Phases 1–12** (the complete production retrieval pipeline:
hybrid retrieval, metadata filtering, cross-encoder reranking, query rewriting
and verified citations). Phases 13–20 — evaluation dataset, retrieval and
generation metrics, tracing, dashboard, deduplication, document updates, full
Dockerisation — are not implemented; the seams left for them are noted below.

Dates: Phases 1–9 on 2026-08-13, Phases 10–12 on 2026-09-04 ·
Platform: Windows 11, Python 3.12

**Structure pass (after Phase 9)** — 15 files were removed without changing
behaviour: Django boilerplate that only restated global settings (`apps.py`
files, an empty `users/models.py`, `asgi.py`), and fragments that belonged with
their owner rather than in a file of their own. The parser package folded into
one `parser.py`, the ingestion data contracts moved next to the code that
creates them, `pipeline.py` merged into `tasks.py`, the Elasticsearch client
joined `index.py`, and the three per-app `urls.py` became one route table in
`config/urls.py`. Every stage that carries architectural meaning — the retrieval
retrievers, the fusion step, the generation stages — stayed separate.

Re-verified after the change: 51 tests pass, `manage.py check` is clean, URL
resolution is unchanged, and a full end-to-end run (upload → ingest → ask in all
three modes → filters → delete) reproduced the results below exactly.

---

## Environment notes

| Item | Value |
| --- | --- |
| Python env | project-local `.venv` |
| Postgres | container, published on host port **5433** (a locally installed Postgres already owns 5432) |
| Redis | container, host port 6379 |
| Elasticsearch | container 8.15.0, host port 9200, single node, security disabled |
| Embeddings | `BAAI/bge-small-en-v1.5`, 384 dims, local |
| Reranker | `BAAI/bge-reranker-base` cross-encoder, local (`identity` backend in tests) |
| LLM | Ollama `qwen3:4b-instruct` (already present on this machine) |

Two machine-specific notes, both handled in `.env`:

- Host port **5433** for Postgres, because a locally installed Postgres service already listens on 5432 and was answering connections meant for the container.
- `HF_HUB_DISABLE_XET=1`, because Hugging Face's Xet transfer path stalled at 0 bytes on this network; the plain CDN download works (~700 KB/s).

---

## Phase 1 — Application foundation

**Built**

- `config/` — env-driven settings (`settings.py`, typed readers in `env.py`), all routes in `urls.py`, WSGI entry point.
- `users/` — register, login, logout on DRF token auth.
- `documents/` — `Document` model (`UPLOADED → PROCESSING → READY/FAILED`), upload/list/retrieve/delete API, `services.py` for lifecycle operations.
- `docker-compose.yml` — Postgres, Redis, Elasticsearch with health checks.
- `ui/` — Streamlit shell plus the Documents screen.

**Decisions**

- **Token auth, not sessions.** The Streamlit client holds a token trivially; sessions would need cookie handling for no benefit.
- **Every setting comes from the environment** through `config/env.py`, so no code changes are needed between local runs and containers.
- **Per-user isolation is one rule in one place**: `DocumentViewSet.get_queryset()` filters on `request.user`. Retrieval enforces the same rule separately (Phase 9).
- **`content_hash` is computed at upload** (streamed SHA-256) even though deduplication is Phase 18 — the field the later phase needs is already populated.
- Uploads are validated (extension, size) in the serializer before anything touches disk.

**Verified** — `tests/test_documents_api.py`: upload creates the record with hash and type, unsupported extensions and oversized files are rejected, listing returns only the caller's documents, another user gets 404 on read and delete, anonymous access gets 401.

---

## Phase 2 — Async ingestion

**Built**

- `config/celery.py` + `config/__init__.py` exposing the Celery app.
- `ingestion/tasks.py` — `run_ingestion()`, the stage sequence, plus the `ingest_document` Celery task that wraps it with status transitions, retries and error capture.

**Decisions**

- **The pipeline is a plain function, the task is a thin wrapper.** `run_ingestion(document)` can be called from a shell with no broker running, which is what makes ingestion debuggable and testable; the task around it adds only status transitions and retry policy.
- **Retries use Celery's own support** (`autoretry_for`, `retry_backoff`, `max_retries=2`). The document is marked `FAILED` only after the last retry, so a transient Elasticsearch hiccup does not surface as a failed document.
- The failure message is stored on the document (truncated) and shown in the UI.
- A deleted document mid-flight is handled explicitly rather than raising.

**Verified** — end-to-end run below: uploads returned immediately with `UPLOADED`, the worker moved each document to `PROCESSING` and then `READY`.

---

## Phase 3 — Parsing and cleaning

**Built**

- `ingestion/parser.py` — the `Page`/`ParsedDocument` contracts, heading heuristics, the pypdf / python-docx / plain-text handlers, and `parse_document(path)` dispatching on extension.
- `ingestion/cleaner.py` — whitespace, control characters, hyphenated line breaks, wrapped lines.

**Decisions**

- **Docling was not used.** It pulls a large torch-based stack for material gain the project does not need yet. The parser interface is the swap point: adding Docling means one new handler function and one dictionary entry — no caller changes.
- **DOCX returns a single page.** A .docx has no pages until it is rendered, so inventing page numbers would put fabricated data in citations. DOCX structure instead comes from real Word heading styles, which are more reliable than PDF text heuristics.
- **Headings are detected during parsing, cleaning happens after.** Cleaning joins wrapped lines, which would otherwise destroy the line structure headings are inferred from.
- Cleaning is deliberately mechanical — no NLP, per the plan.

**Verified** — `tests/test_parser.py` and `tests/test_cleaner.py`: PDF parsed page-by-page with headings, DOCX heading styles recognised, TXT form feeds treated as page breaks, unsupported extensions rejected, prose not misread as a heading; control characters stripped, `reim-\nbursement` rejoined, paragraph breaks preserved, empty pages dropped.

---

## Phase 4 — Structure-aware chunking

**Built** — `ingestion/chunker.py`: splits each page at its headings, then splits each section with LangChain's `RecursiveCharacterTextSplitter`.

**Decisions**

- **Structure first, size second.** Splitting at headings before recursive splitting keeps a chunk from straddling two sections, and gives every chunk a meaningful `section` value for filtering and citations.
- **2400 chars / 300 overlap** ≈ 600 tokens with 12.5% overlap, inside the plan's 400–700 token and 10–15% overlap targets. Both are settings, so chunk-size experiments later need no code change.
- `chunk_id` is deterministic (`doc12_chunk7`) and used as the Elasticsearch document `_id`, which makes re-indexing idempotent.
- Every chunk carries `document_id`, `user_id`, `page`, `section`, `chunk_index`.

**Verified** — `tests/test_chunker.py`: metadata present on every chunk, sections taken from headings, default section when a page has none, long sections split into several chunks that respect the size limit.

---

## Phase 5 — Embeddings and Elasticsearch indexing

**Built**

- `ingestion/embeddings.py` — `EmbeddingBackend` protocol + `SentenceTransformerBackend`, selected by `get_embedding_backend()`.
- `retrieval/index.py` — the Elasticsearch chunk store: client singleton, index mapping, `ensure_index`, `delete_document_chunks`, `count_document_chunks`.
- `ingestion/indexer.py` — batch embed + bulk index.
- `retrieval/dense.py` — kNN search.

**Decisions**

- **Elasticsearch is the only chunk store.** Postgres keeps documents and status; duplicating chunk text in a relational table would add a write path with no reader.
- **The model loads lazily and once** (`lru_cache` + deferred import). Django and Celery start instantly, and the unit suite never imports torch.
- **Vectors are normalised and the mapping uses cosine similarity** — the pairing BGE expects. The query side gets BGE's instruction prefix; the passage side does not.
- **A hosted embedding backend is one class away.** `_BACKENDS` is the single registration point, which is what "BGE now, Gemini later" needs.
- `refresh=True` on bulk indexing means a document is searchable the moment it reports `READY` — no polling race in the UI.
- Ingestion deletes a document's existing chunks before writing new ones, so re-ingestion cannot leave stale vectors (the mechanism Phase 19 will reuse).

**Verified** — end-to-end run below: chunk counts in Postgres match the Elasticsearch document count, and dense-only retrieval answers a paraphrased question.

---

## Phase 6 — Grounded generation (baseline)

**Built**

- `generation/prompts.py` — system prompt, answer template, fixed no-evidence answer.
- `generation/context_builder.py` — numbered `SOURCE n` blocks + the source map behind them.
- `generation/llm.py` — `LLMClient` protocol with Gemini, Ollama and stub providers.
- `qa/service.py`, `qa/views.py`, `qa/serializers.py` — `POST /api/qa/ask/`.
- `ui/screens/qa_screen.py` — question, answer, expandable sources.

**Decisions**

- **The source map is built, not parsed.** `context_builder` assigns numbers and keeps each number's document, page, section and chunk id, so mapping `[2]` back to a citation is deterministic — the groundwork Phase 12 needs.
- **No evidence means no LLM call.** When retrieval returns nothing the service returns a fixed answer, which is both honest and free.
- **Three providers, one interface.** Gemini and Ollama for real use; `stub` keeps the test suite and offline development free of keys and model downloads.
- **Filenames are resolved in one query** and passed into the context builder, so the retrieval layer stays free of Django model imports.
- Answers carry per-stage latency, which the debug screen shows and Phase 16 tracing can persist unchanged.

**Verified** — `tests/test_context_builder.py` and `tests/test_qa_service.py`: source numbering and rendering, source cap, character budget, unknown-document fallback; answers grounded in retrieved sources, filters always scoped to the asking user, no-evidence path skips generation. Plus the live run below.

---

## Phase 7 — BM25 retrieval

**Built** — `retrieval/bm25.py`: `multi_match` over `text` and `section` (boosted), with the same filters and the same return type as dense search.

**Decisions**

- **Identical signature to `dense.search`.** Fusion, the API and later evaluation configurations treat retrievers interchangeably; nothing branches on retriever type.
- Elasticsearch's BM25 is used as-is, per the plan's instruction not to implement scoring.
- The `section` field is boosted modestly (1.5) because heading text is a strong signal for policy-style documents.

**Verified** — live run below: the exact-code query (`FIN-2291`) retrieves the right chunk under `mode=bm25`.

---

## Phase 8 — Hybrid retrieval (RRF)

**Built**

- `retrieval/fusion.py` — Reciprocal Rank Fusion, ~20 lines.
- `retrieval/retriever.py` — `RetrievalConfig`, `RetrievalResult`, `retrieve()`.
- `ui/screens/debug_screen.py` — dense vs BM25 vs RRF vs final, with latencies.

**Decisions**

- **RRF, not score blending.** Ranks avoid having to normalise BM25 scores against cosine similarities, and there is no weight to tune.
- **`RetrievalResult` keeps every stage**, not just the winners. That is what makes the debug screen possible and what Phase 16 will persist; a pipeline that returned only final chunks would be undebuggable.
- **`RetrievalConfig` is the unit of comparison** Phase 14 needs (`dense`, `bm25`, `hybrid`, later `hybrid + reranker`) — one frozen dataclass, validated on construction, defaults from settings, overridable per request.
- Per-stage timings are recorded in the same place the stages run.
- No generic ranking framework, per the plan.

**Verified** — `tests/test_fusion.py` and `tests/test_retriever.py`: RRF scores follow `1/(k+rank)`, a chunk found by both retrievers outranks one found by either, results deduplicated and truncated; dense mode skips BM25 and vice versa, hybrid runs both and fuses, `final_k` truncates, unknown modes rejected. Plus the live three-mode comparison below.

---

## Phase 9 — Metadata filtering

**Built** — `retrieval/filters.py`: `SearchFilters` → Elasticsearch filter clauses; optional `document_ids`, `content_types`, `created_after` exposed on the ask API.

**Decisions**

- **`user_id` is a required constructor argument.** Isolation is not a filter someone can forget: a `SearchFilters` cannot be constructed without it, and `qa.service` builds it from `request.user` rather than from request data. A caller can narrow their search, never widen it.
- **Filter clauses, not queries** — Elasticsearch filters do not affect scoring, so filtering cannot distort relevance.
- Empty lists are treated as "no filter" so an empty UI selection does not silently return nothing.
- `describe()` gives a serialisable form for debug output and future traces.
- No RBAC, per the plan.

**Verified** — `tests/test_filters.py` and `tests/test_qa_service.py`: user clause always present, `SearchFilters()` without a user raises, optional filters translated correctly, empty lists skipped, optional filters forwarded from the service. Plus the cross-user isolation check in the live run.

---

## Phase 10 — Cross-encoder reranking

**Built**

- `reranking/reranker.py` — `RerankerBackend` protocol, `CrossEncoderBackend`
  (BGE reranker, lazily loaded), `IdentityReranker` for offline work, and
  `rerank(query, chunks, top_k)`.
- `retrieval/retriever.py` — `rerank` / `rerank_k` on `RetrievalConfig`, a
  `reranked_results` stage on `RetrievalResult`, and `rerank_ms` timing.

**Decisions**

- **Reranking is a flag on the config, not a fourth mode.** `mode` says how
  candidates are *found*; reranking says how they are *ordered* afterwards.
  Making it a mode would have needed `dense_rerank`, `bm25_rerank` and
  `hybrid_rerank` entries for what is one orthogonal switch — and Phase 14 has to
  compare exactly those combinations. `RetrievalConfig.label`
  (`hybrid+reranker`) names the resulting configuration in one place.
- **It runs after fusion, over the fused top 20.** Cross-encoding is far more
  expensive per candidate than kNN, so it only ever sees a short list; running it
  before fusion would mean scoring 60 candidates to throw most of them away.
- **Same backend shape as embeddings** — protocol, deferred import, `lru_cache`,
  a `_BACKENDS` registry. The model loads once per process and the unit suite
  never imports torch.
- **`identity` is a real backend, not a mock.** It preserves the incoming order
  with well-formed descending scores, so offline runs exercise the same code path
  production does; `config/settings_test.py` selects it.
- The reranker reuses `RetrievedChunk.with_score`, so the pipeline still passes
  one type between every stage.

**Verified** — `tests/test_reranker.py` plus new cases in
`tests/test_retriever.py`: candidates reorder by cross-encoder score, `top_k`
truncates, an empty candidate list never loads the model, the identity backend
returns a descending ranking, an unknown backend raises; the reranker receives
what RRF produced, its output becomes the final chunks, `rerank=False` leaves the
fused order untouched, and `label` names the configuration.

Against a real model (`cross-encoder/ms-marco-MiniLM-L-6-v2`, standing in for
`bge-reranker-base` to keep the check to a 90 MB download) on three chunks and
the query *"How many days of annual leave do employees get?"*:

| Chunk | Reranker score |
| --- | --- |
| "Employees receive 20 days of paid annual leave each year." | **9.77** |
| "Expense claims must be submitted within 30 days…" | −5.70 |

The annual-leave chunk was second in the input order and moved to first, while
the "30 days" chunk — the lexical trap BM25 scores highly for *days* — was pushed
down. That reordering is the entire reason the stage exists.

---

## Phase 11 — Query rewriting

**Built**

- `generation/query_rewriter.py` — `RewrittenQuery` and
  `rewrite_query(question, history)`.
- `generation/prompts.py` — rewriting system prompt and template.
- `qa/service.py` rewrites first and retrieves with the result; `history` is
  accepted by the ask API and by the Streamlit Q&A screen, which now keeps a
  conversation.

**Decisions**

- **A first question skips the LLM call entirely.** With no history there is
  nothing to resolve, so rewriting would spend a round trip to return its input.
  `reason` records why rewriting ran or did not, which is what makes the debug
  screen honest.
- **A rewriter failure is not a request failure.** `LLMError` is caught and the
  original question is used. Retrieval on the raw question is a mild degradation;
  a 502 because a *helper* call failed is not.
- **The model's output is treated as untrusted.** Only the first line is kept,
  quotes are stripped, and an empty or overlong rewrite is rejected in favour of
  the original — a chatty model cannot turn a query into a paragraph of prose.
- **Retrieval sees the rewritten query, the user sees their own.** `AnswerResult`
  carries both, and the answer prompt still quotes the question as typed, so the
  answer addresses what was actually asked.
- Both queries are already on the result, which is the field Phase 16's trace
  record needs.

**Verified** — `tests/test_query_rewriter.py`: a follow-up is resolved using
history, a first question makes no LLM call, `QUERY_REWRITE_ENABLED=false` is
respected, a provider failure falls back to the original, a chatty multi-line
answer is trimmed to its first line, an overlong rewrite is rejected, and history
is limited to the configured number of turns. `tests/test_qa_service.py` adds the
integration check that retrieval receives the rewritten query while the result
still reports the original question.

---

## Phase 12 — Citation-backed generation

**Built**

- `generation/citations.py` — `Citation`, `CitedAnswer` and
  `resolve_citations(answer, sources)`.
- `qa/service.py` resolves citations after generation; the API returns them, and
  both Streamlit screens render the footnote list.
- `generation/prompts.py` — the system prompt now requires a citation on every
  factual sentence and forbids numbers that were not supplied.

**Decisions**

- **Resolution is a lookup, not an inference.** The context builder assigned each
  number to a chunk when it built the prompt (Phase 6), so `[2]` → document, page,
  section, chunk id is deterministic. The only model-dependent step is reading the
  markers it emitted.
- **Invented markers are removed from the answer, not merely ignored.** A `[7]`
  when six sources were supplied is a hallucinated citation; leaving it on screen
  would present it as verifiable. It is stripped from the text and reported under
  `debug.dropped_citations`, so the failure is measurable rather than invisible —
  which is what Phase 15's citation-correctness metric will count.
- **A partly valid group keeps its valid half.** `[1, 9]` with one source becomes
  `[1]`; discarding the whole marker would lose a correct citation.
- **`is_grounded` is derived, not asserted.** An answer with no surviving citation
  is flagged by the state of the evidence, not by asking the model.
- Only sources the answer actually cited become citations; the full retrieved set
  stays available separately, so the Q&A screen can show both.

**Verified** — `tests/test_citations.py`: markers resolve to document and page,
only cited sources become citations, `[1, 2]` is expanded, a repeated marker is
listed once, an invented marker is dropped from the answer and recorded, a group
keeps its valid numbers, and an uncited answer is left intact.
`tests/test_qa_service.py` adds the end-to-end case where a scripted model emits
one good and one invented marker.

---

## End-to-end verification (Phases 1–9)

Run on 2026-08-13 against the real stack: three healthy containers (Elasticsearch
green), Django dev server, Celery worker (`--pool=solo`), Streamlit, Ollama.

**Unit suite** — `pytest`: **51 passed**, on SQLite with the `stub` provider and
mocked retrievers (no Docker, no model download).

**Ingestion** (Phases 1–5) — uploads returned `201 UPLOADED` immediately; the
worker took each document to `READY`:

| Document | Pages | Chunks |
| --- | --- | --- |
| hr_policy.pdf | 3 | 5 |
| finance_policy.txt | 2 | 3 |
| security_policy.docx | 1 | 3 |

Elasticsearch `_count` = **11**, matching the sum of `chunk_count` in Postgres.
The first document took 162 s (BGE download and load); the next two took ~0.4 s
each, confirming the model is loaded once per worker.

**Retrieval and generation** (Phases 6–8) — "How much paid time off do permanent
staff receive each year?" (a paraphrase; the documents say "20 days of paid
annual leave"):

| Mode | Dense hits | BM25 hits | Retrieval | Answer |
| --- | --- | --- | --- | --- |
| bm25 | – | 3 | 69 ms | "Permanent staff receive 20 days of paid annual leave each year [1]." |
| hybrid | 11 | 3 | 119 ms (dense 93 + bm25 26 + fusion 0.15) | same answer, top source hr_policy.pdf p1 *Annual Leave* |

Both modes put `doc1_chunk0` first. On the exact-identifier query (`FIN-2291`),
BM25 returned exactly one chunk — the correct one, score 7.43 — and hybrid ranked
it first, which is the lexical/semantic complementarity the hybrid design exists
for. The unanswerable query ("dividend policy") returned the fixed refusal in all
three modes.

**Isolation** (Phase 9) — a second user (`bob`) sees no documents, and the same
question returns 0 dense hits, 0 BM25 hits and the refusal answer.

**Metadata filters** (Phase 9) — same question, different filters:

| Filter | Documents in final chunks |
| --- | --- |
| none | 1, 2, 3 |
| `document_ids=[2]` | 2 only |
| `content_types=["pdf"]` | 1 only |
| `content_types=["docx"] + created_after=2030` | none → refusal |

Deleting a document returned `204` and dropped Elasticsearch from 11 to 8 chunks
— exactly the deleted document's 3 — so no orphaned vectors remain.

**UI** — all three screens driven in a browser: sign-in, documents table with
status, Q&A ("Expense claims must be submitted within 30 days of the expense
being incurred [1]", 14.9 s including a cold model load), and the debug screen
showing Dense 8 / BM25 3 / RRF 8 / Final 8 with the latency table and the
configuration + filters actually used.

### Two problems the run exposed

**1. A provider failure was reported as a server crash.** The very first
generation call got HTTP 500 from Ollama (cold-loading a 2.5 GB model while torch
was still resident). The client reported only the status code, so the cause was
invisible, and DRF returned an HTML 500 page. Fixed: `LLMError` now carries
Ollama's response body, and `AskView` maps provider failures to **502** with a
readable `detail`. Covered by `tests/test_qa_api.py`.

**2. `qwen3:4b-instruct` refuses identifier-style questions.** "What is cost code
FIN-2291 used for?" returns the refusal even though the chunk containing
`FIN-2291` is ranked first. Reproduced with a single-source context and unchanged
across three prompt variants, so it is a model limitation, not a retrieval or
prompt bug — the same fact asked forward ("Which cost code do managers use to
approve claims?") is answered correctly with a citation. A larger local model or
`LLM_PROVIDER=gemini` is the practical fix. This is precisely the kind of failure
Phase 15's generation evaluation is meant to measure rather than eyeball.

---

## End-to-end verification (Phases 10–12)

Docker was not running on 2026-09-04, so Elasticsearch and Ollama were
unavailable and the live three-container run below was not repeated. Instead the
whole request path — `AskView` → service → rewriter → retriever → RRF → reranker
→ context builder → generation → citation resolution → serializer — was driven
through the real DRF test client with **only Elasticsearch and the LLM replaced**.

Request: *"What about contractors?"* with two turns of history and `rerank: true`.

| Field | Value |
| --- | --- |
| `query.original_query` | "What about contractors?" |
| `query.rewritten_query` | "How many annual leave days do contractors receive?" |
| `query.reason` | follow-up resolved |
| `retrieval.label` | `hybrid+reranker` |
| `answer` | "Contractors receive 20 days of paid annual leave. [1] Bonus is doubled." |
| `citations[0].label` | hr_policy.pdf, Page 2 |
| `debug.dropped_citations` | `[9]` |
| stages | dense 2 → BM25 1 → RRF 2 → reranked 2 → final 2 |
| timings | `rewrite_ms`, `dense_ms`, `bm25_ms`, `fusion_ms`, `rerank_ms`, `generation_ms`, `total_ms` all present |

The scripted model emitted `[1]` (valid) and `[9]` (invented); the answer that
reached the client had the invented marker removed and the fabrication recorded
in the debug payload.

**Unit suite** — `pytest`: **76 passed** (up from 51), still on SQLite with the
`stub` provider, the `identity` reranker and mocked retrievers.
`manage.py check` is clean.

Two things Phases 10–12 have *not* been verified against, both blocked by the
unavailable services rather than by the code:

- the reranker running on `bge-reranker-base` over real Elasticsearch candidates
  (the cross-encoder code path is verified, the specific model is not);
- query rewriting driven by a real provider — the rewriter's LLM call is covered
  only by scripted responses, so `qwen3:4b-instruct`'s actual rewriting quality
  is unmeasured.

A note on running the suite on this machine: pytest's default base temp directory
under `%LOCALAPPDATA%\Temp` is not writable from the agent shell, which errors the
five `tmp_path` tests in `test_parser.py`. Passing `--basetemp=<writable dir>`
runs all 76. This is an environment quirk, not a code change.

---

## Known limitations

- **DOCX page numbers are always 1** — page geometry does not exist until a .docx is rendered. Sections carry the structure instead.
- **Heading detection for PDF/TXT is heuristic** (short, title-like lines). A styled-layout parser such as Docling would improve it; the parser interface is where it plugs in.
- **The chunk index has no vector-dimension migration.** Changing `EMBEDDING_MODEL` to a model with different dimensions requires deleting the index so the mapping is recreated.
- **Citations are validated, not fact-checked.** A `[n]` marker is now verified to point at a source that was actually supplied, and invented markers are removed (Phase 12). Whether the cited chunk really supports the sentence is a faithfulness question, which Phase 15 measures.
- **Generation quality is capped by the local 4B model** — see finding 2 above. Retrieval is unaffected.
- **No evaluation harness yet** (Phases 13–15), so retrieval quality claims here are qualitative — including whether reranking helps on this corpus. Phase 14 compares `dense`, `bm25`, `hybrid` and `hybrid+reranker`, which `RetrievalConfig` can already express.
- **Reranking adds a second local model to the request path.** On CPU it costs one forward pass per candidate, so `RETRIEVAL_FINAL_K` is what bounds the latency; `RERANK_ENABLED=false` turns the stage off.
- **Query rewriting costs an extra LLM call on follow-up questions only.** With the local 4B model that is a real share of the response time; a smaller or hosted model for rewriting would be the fix.
- **Only infrastructure is containerised.** Django, Celery and Streamlit run from the local `.venv`; Phase 20 covers the rest.
