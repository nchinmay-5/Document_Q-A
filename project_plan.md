# Production RAG Document Analytics Platform — Project Plan

## 1. Project Objective

Build a **minimal, production-oriented document Q&A platform** focused primarily on demonstrating strong understanding of:

- document ingestion
- chunking
- embeddings
- hybrid retrieval
- reranking
- query rewriting
- grounded generation
- citations
- RAG evaluation
- observability

The project should avoid spending unnecessary time on frontend, authentication, custom infrastructure, or reinventing standard components.

The guiding principle is:

> **Spend engineering effort on retrieval quality, evaluation, and RAG architecture. Use simple/pre-built solutions everywhere else.**

---

# 2. Final MVP Scope

The system will support the following flow:

```text
Document Upload
      ↓
Async Ingestion
      ↓
Parsing
      ↓
Structure-Aware Chunking
      ↓
Metadata Enrichment
      ↓
Embeddings
      ↓
Elasticsearch Index
      ↓

User Question
      ↓
Query Rewriting
      ↓
┌───────────────┬───────────────┐
│ Dense Search  │ BM25 Search   │
└───────┬───────┴───────┬───────┘
        ↓               ↓
          RRF Fusion
              ↓
      Cross-Encoder Reranker
              ↓
           Top Chunks
              ↓
        Context Builder
              ↓
             LLM
              ↓
     Answer + Citations
              ↓
      Evaluation + Tracing
```

---

# 3. Technology Stack

## Backend

Use:

- Django
- Django REST Framework

Django will handle:

- users
- documents
- database models
- API endpoints
- basic authentication

No custom authentication system is required.

---

## Database

Use:

- PostgreSQL

Store:

- users
- documents
- processing status
- document metadata
- chat/query records
- evaluation runs
- traces

---

## Async Processing

Use:

- Celery
- Redis

Celery will process documents in the background.

Redis will act as the Celery broker/backend.

Do not build a custom job queue.

---

## Document Parsing

Use existing libraries wherever possible.

Preferred:

- Docling for PDF/document extraction
- python-docx if required for DOCX
- standard Python file handling for TXT

Do not implement PDF parsing from scratch.

Initial supported formats:

```text
PDF
DOCX
TXT
```

OCR can be added later as an optional extension.

---

## Embeddings

Use an existing embedding model through:

- Sentence Transformers

Recommended starting model:

```text
BAAI/bge-small-en-v1.5
```

or another lightweight BGE/E5 embedding model.

Avoid training any embedding model.

---

## Retrieval

Use:

- Elasticsearch

Elasticsearch will provide:

```text
BM25
+
dense vector retrieval
+
metadata filtering
```

FAISS may optionally be used as the dense-only baseline during evaluation.

It does not need to be part of the main serving architecture.

---

## Reranking

Use an existing cross-encoder reranker.

Example:

```text
BGE reranker
```

Do not train a reranker.

---

## Generation

Use either:

- gemini API
- LiteLLM
- local Ollama model

Keep the LLM provider abstracted behind a small wrapper.

---

## Evaluation

Use:

- custom retrieval metrics
- RAGAS where useful
- optional LLM-as-a-judge evaluation

Implement simple retrieval metrics yourself because they are straightforward and demonstrate understanding:

```text
Recall@K
MRR
```

Do not reinvent faithfulness evaluation if RAGAS already provides it.

---

## Frontend

Use:

- Streamlit

Frontend should remain extremely minimal.

The frontend exists only to demonstrate the backend and RAG workflow.

Do not spend time building polished React interfaces.

---

# 4. Authentication

Authentication is **not a project focus**.

Use Django's built-in user model.

Basic functionality:

```text
Register
Login
Logout
```

Use either:

- Django session authentication

or:

- simple DRF token authentication

No:

- OAuth
- social login
- email verification
- password recovery workflows
- refresh-token architecture
- role hierarchy

The only important requirement is:

> Each user should retrieve only their own documents.

---

# 5. Frontend Scope

Only three screens are needed.

## Screen 1 — Documents

Functions:

- upload document
- list uploaded documents
- show status

Example:

```text
File                 Status

HR_policy.pdf         Ready
Finance.pdf           Processing
Policy.docx           Failed
```

also allow deletion.

Nothing more is needed.

---

## Screen 2 — Q&A

Simple interface:

```text
Question input
      ↓
Answer
      ↓
Sources
```

Example:

```text
Employees receive 20 days of annual leave. [1]

Sources

[1] HR_policy.pdf — Page 12
```

&#x20;show retrieved chunks in an evaluation/debug screen.

---

## Screen 3 — Evaluation / Debug

This is the important screen.

Display:

```text
Original Query
Rewritten Query

Dense Results
BM25 Results

RRF Results

Reranker Scores

Final Chunks

Latency

Evaluation Metrics
```

This screen should demonstrate the technical depth of the project.

---

# 6. Suggested Project Structure

Keep responsibilities clearly separated.

```text
document-rag/

├── manage.py
├── requirements.txt
├── docker-compose.yml
├── README.md
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
│
├── users/
│   ├── models.py
│   ├── serializers.py
│   └── views.py
│
├── documents/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── services.py
│
├── ingestion/
│   ├── parser.py
│   ├── cleaner.py
│   ├── chunker.py
│   ├── embeddings.py
│   └── tasks.py
│
├── retrieval/
│   ├── dense.py
│   ├── bm25.py
│   ├── fusion.py
│   ├── filters.py
│   └── retriever.py
│
├── reranking/
│   └── reranker.py
│
├── generation/
│   ├── query_rewriter.py
│   ├── context_builder.py
│   ├── llm.py
│   └── prompts.py
│
├── evaluation/
│   ├── dataset.py
│   ├── retrieval_metrics.py
│   ├── generation_metrics.py
│   └── runner.py
│
├── tracing/
│   ├── models.py
│   └── tracer.py
│
├── qa/
│   ├── views.py
│   ├── serializers.py
│   └── service.py
│
├── ui/
│   └── app.py
│
└── tests/
```

Avoid creating unnecessary abstractions.

Each file should have one obvious responsibility.

---

# 7. Phase 1 — Basic Application Setup

Goal:

Create the minimal application foundation.

Implement:

- Django project
- PostgreSQL connection
- basic User model
- simple login/register
- Document model
- document upload API
- Streamlit upload page

Document model:

```text
Document

id
user
filename
file_path
status
content_hash
created_at
updated_at
```

Possible statuses:

```text
UPLOADED
PROCESSING
READY
FAILED
```

At the end of this phase:

```text
User
 ↓
Upload PDF
 ↓
Document stored
 ↓
Status displayed
```

Do not implement RAG yet.

---

# 8. Phase 2 — Async Document Ingestion

Add:

```text
Celery
Redis
```

Upload workflow:

```text
POST /documents
      ↓
Save document
      ↓
Create Document record
      ↓
Queue Celery task
      ↓
Return immediately
```

Worker:

```text
Document
 ↓
Parsing
 ↓
Chunking
 ↓
Embedding
 ↓
Indexing
```

Status changes:

```text
UPLOADED
   ↓
PROCESSING
   ↓
READY
```

or:

```text
FAILED
```

Keep retry logic simple using Celery's existing retry support.

---

# 9. Phase 3 — Parsing and Cleaning

Create:

```text
ingestion/parser.py
```

Interface:

```python
parse_document(path) -> ParsedDocument
```

The rest of the application should not care whether the file is:

```text
PDF
DOCX
TXT
```

Return a common representation such as:

```python
{
    "pages": [
        {
            "page_number": 1,
            "text": "...",
            "headings": [...]
        }
    ]
}
```

Use libraries rather than building parsers manually.

Cleaning should only handle practical issues such as:

- repeated whitespace
- empty sections
- broken lines
- unnecessary control characters

Do not create complex NLP-based cleaning.

---

# 10. Phase 4 — Chunking

Initial implementation:

**structure-aware recursive chunking**

Use existing text splitting utilities where possible.

Suggested:

```text
400–700 tokens
10–15% overlap
```

Preserve:

```text
document_id
page_number
section
chunk_index
user_id
```

Example chunk:

```json
{
  "chunk_id": "doc12_chunk7",
  "document_id": 12,
  "page": 8,
  "section": "Eligibility",
  "text": "Applicants must..."
}
```

Do not spend too much time creating a custom chunking algorithm initially.

Later evaluation can compare chunk sizes or strategies.

---

# 11. Phase 5 — Embedding and Elasticsearch Indexing

Create a simple wrapper:

```text
ingestion/embeddings.py
```

Responsibilities:

```text
text → embedding
batch text → embeddings
```

Use batching.

Store chunks in Elasticsearch containing:

```text
chunk_id
document_id
user_id
text
embedding
page
section
```

At this stage, implement only dense vector retrieval first.

Test:

```text
Question
 ↓
Query embedding
 ↓
Top K chunks
```

This becomes the baseline RAG system.

---

# 12. Phase 6 — Basic RAG Generation

Implement:

```text
generation/context_builder.py
generation/llm.py
generation/prompts.py
```

Flow:

```text
Question
 ↓
Dense Retrieval
 ↓
Top 5 Chunks
 ↓
Context Builder
 ↓
LLM
 ↓
Answer
```

Context:

```text
SOURCE 1
Document: HR.pdf
Page: 12

...

SOURCE 2
...
```

Require the model to answer only using supplied evidence.

At this stage, the first complete RAG system exists.

This becomes the **baseline** against which later improvements are evaluated.

---

# 13. Phase 7 — BM25 Retrieval

Add:

```text
retrieval/bm25.py
```

Elasticsearch already supports lexical search.

Do not implement BM25 mathematically yourself.

Retrieve:

```text
Top 30 BM25 results
```

Now there are two retrievers:

```text
dense.py
bm25.py
```

Each should expose a similar interface.

---

# 14. Phase 8 — Hybrid Retrieval

Implement:

```text
retrieval/fusion.py
```

Use:

**Reciprocal Rank Fusion**

Input:

```text
Dense top 30
BM25 top 30
```

Output:

```text
Hybrid top 20
```

RRF itself is simple enough to implement directly.

Do not create an overly generic ranking framework.

The pipeline becomes:

```text
Query

  ├── Dense
  │
  └── BM25

      ↓

     RRF

      ↓

Top candidates
```

---

# 15. Phase 9 — Metadata Filtering

Add filtering before search.

Minimum filter:

```text
user_id
```

This guarantees multi-user isolation.

Additional filters can optionally include:

```text
document_id
date
document_type
```

Do not build complex RBAC.

---

# 16. Phase 10 — Cross-Encoder Reranking

Add:

```text
reranking/reranker.py
```

Input:

```text
query
+
top 20 hybrid candidates
```

Output:

```text
top 5 ranked candidates
```

Use an existing reranker model.

No training required.

Final retrieval flow:

```text
Dense Top 30
      +
BM25 Top 30
      ↓
     RRF
      ↓
Top 20
      ↓
Cross Encoder
      ↓
Top 5
```

---

# 17. Phase 11 — Query Rewriting

Add:

```text
generation/query_rewriter.py
```

Keep the logic simple.

Input:

```text
question
+
recent conversation history
```

Output:

```text
standalone retrieval query
```

Example:

```text
"What about his salary?"
```

becomes:

```text
"What salary is reported for Rahul in his payslip?"
```

Store both:

```text
original_query
rewritten_query
```

Do not build an agent to do this.

One LLM call is sufficient.

---

# 18. Phase 12 — Citation-Backed Generation

Context builder assigns identifiers:

```text
SOURCE_1
SOURCE_2
SOURCE_3
```

The LLM returns references using these identifiers.

Backend maps:

```text
SOURCE_1
```

to:

```text
document
page
section
chunk
```

Final UI:

```text
Employees receive 20 annual leave days. [1]

[1] HR_policy.pdf, Page 12
```

Keep citation generation deterministic where possible.

---

# 19. Phase 13 — Evaluation Dataset

Use a combination of a **small project-specific golden evaluation set** and, optionally, an existing public QA/RAG dataset.

For the project-specific evaluation set, create:

```
evaluation/data/eval.json
```

Generate candidate question-answer pairs from the documents already indexed in the system using an LLM, then manually validate them before adding them to the final evaluation set.

Each item should contain:

```
{
  "question": "...",
  "expected_answer": "...",
  "relevant_chunk_ids": [...]
}
```

Target approximately:

```
40–60 validated questions
```

Include:

- semantic questions
- exact keyword / ID lookups
- paraphrased questions
- conversational questions
- multi-document questions
- questions with no available answer

The project-specific golden set will be used to evaluate the actual chunking, retrieval, reranking, and generation pipeline.

A public dataset may optionally be used for additional benchmarking, but it should not replace evaluation on the project's own indexed documents.

---

# 20. Phase 14 — Retrieval Evaluation

Implement directly:

```text
Recall@5
Recall@10
MRR
```

Create evaluation configurations:

```text
dense
BM25
hybrid
hybrid + reranker
```

Run each against the same evaluation dataset.

Save results.

Example:

```text
Configuration        Recall@5      MRR

Dense                 ...
BM25                  ...
Hybrid                ...
Hybrid + Reranker     ...
```

The purpose is not to produce impressive numbers.

The purpose is to prove which architecture performs better on the project's dataset.

---

# 21. Phase 15 — Generation Evaluation

Use existing libraries where useful.

Evaluate:

```text
faithfulness
answer relevance
citation correctness
```

Use RAGAS for suitable metrics instead of recreating them.

Add some manually reviewed examples to ensure automated metrics make sense.

---

# 22. Phase 16 — Tracing and Debugging

Create a lightweight trace for each query.

Store:

```text
trace_id
user_id
original_query
rewritten_query

dense_results
BM25_results
RRF_results
reranker_scores

final_chunks

answer
citations

retrieval_latency
reranking_latency
generation_latency
```

Do not build a custom distributed tracing platform.

A database record and simple debug page are enough.

---

# 23. Phase 17 — Evaluation Dashboard

Use Streamlit.

Display:

```text
Retrieval configuration
Recall@K
MRR
Faithfulness
Answer relevance
Average latency
```

Also allow selecting one test query and inspecting:

```text
Dense results
BM25 results
RRF ranking
Reranker ranking
Final answer
```

This is one of the most important demo features.

---

# 24. Phase 18 — Duplicate Detection

Calculate:

```text
SHA-256(file)
```

before processing.

If the same user uploads the exact same document again:

```text
skip duplicate ingestion
```

Use Python's standard hashing library.

No custom deduplication system is needed.

---

# 25. Phase 19 — Document Updates

Keep versioning basic.

When a document is replaced:

```text
Deactivate/delete old chunks
        ↓
Process new document
        ↓
Index new chunks
```

No complex historical version-management UI is required.

---

# 26. Phase 20 — Dockerization

Create:

```text
docker-compose.yml
```

Services:

```text
django
celery
redis
postgres
elasticsearch
streamlit
```

Goal:

```bash
docker compose up
```

should start the application.

Do not introduce Kubernetes.

---

# 27. What We Should Explicitly Avoid

To keep the project focused, do not initially implement:

- React frontend
- complex CSS
- OAuth
- email verification
- password reset flows
- custom PDF parsers
- custom embedding models
- custom reranker training
- custom vector database
- custom BM25 implementation
- GraphRAG
- multi-agent systems
- MCP
- Kubernetes
- sophisticated role management
- custom OCR
- microservices
- event-driven distributed architecture
- dozens of file types

The project should demonstrate **RAG engineering**, not framework complexity.

---

# 28. Development Philosophy

Use mature libraries and framework abstractions whenever they provide a reliable implementation, including for core RAG components.

The focus should be on correctly **designing, configuring, combining, evaluating, and debugging** the RAG system rather than implementing standard algorithms from scratch.

Preferred implementations:

```
Authentication
→ Django

REST APIs
→ Django REST Framework

Async jobs
→ Celery

Queue / broker
→ Redis

Parsing
→ Docling

Document representation / loading
→ LangChain where useful

Chunking
→ LangChain text splitters

Embeddings
→ Sentence Transformers / LangChain wrappers

Lexical retrieval
→ Elasticsearch BM25

Vector retrieval
→ Elasticsearch kNN

Metadata filtering
→ Elasticsearch filters

RAG pipeline orchestration
→ LangChain / LCEL

Prompt templates
→ LangChain

Reranking
→ pretrained cross encoder

LLM access
→ LangChain / LiteLLM

Generation evaluation
→ RAGAS

Frontend
→ Streamlit
```

Keep project-specific code structured into clear components for:

```
retrieval configuration
hybrid retrieval orchestration
RRF / fusion configuration
reranker integration
metadata access filtering
context construction
citation/source mapping
evaluation experiment execution
retrieval metrics
query tracing
comparison of RAG configurations
```

If a reliable library already provides one of these operations, use it rather than recreating it unnecessarily.

Even when using a library, the implementation should keep the main RAG stages explicit:

```
retrieve
   ↓
fuse
   ↓
rerank
   ↓
build context
   ↓
generate
   ↓
evaluate
```

Avoid high-level abstractions that hide the complete retrieval and generation pipeline when that would make evaluation or debugging difficult.

---

# 29. Recommended Build Order

The safest build order is:

```text
1. Django + document upload

2. Celery ingestion

3. Parsing

4. Chunking

5. Embeddings

6. Elasticsearch dense retrieval

7. Basic RAG answer

---------- BASELINE COMPLETE ----------

8. BM25

9. Hybrid RRF

10. Reranking

11. Metadata filtering

12. Query rewriting

13. Citations

---------- PRODUCTION RAG COMPLETE ----------

14. Evaluation dataset

15. Retrieval metrics

16. Generation evaluation

17. Tracing

18. Evaluation dashboard

---------- RESUME VERSION COMPLETE ----------

19. Deduplication

20. Document updates

21. Docker cleanup

22. Tests + README
```

This order is important because there should always be a working system.

Avoid trying to implement every component before testing end-to-end.

---

# 30. Definition of Done

The project is resume-ready when the following scenario works:

```text
User logs in

        ↓

Uploads multiple documents

        ↓

Documents process asynchronously

        ↓

Status becomes READY

        ↓

User asks question

        ↓

Query may be rewritten

        ↓

Dense + BM25 retrieval

        ↓

RRF fusion

        ↓

Cross-encoder reranking

        ↓

Top evidence provided to LLM

        ↓

Grounded answer

        ↓

Clickable/source-visible citations

        ↓

Trace records full retrieval process
```

And the evaluation page can demonstrate:

```text
Dense baseline
vs
BM25
vs
Hybrid
vs
Hybrid + Reranker
```

using real:

```text
Recall@K
MRR
Faithfulness
Answer relevance
Latency
```

---

# 31. Main Project Priority

Engineering effort should roughly be distributed as:

```text
Retrieval + reranking          30%
Evaluation                    25%
Ingestion + chunking          20%
Generation + citations        10%
Tracing                       10%
Frontend + authentication      5%
```

That keeps development aligned with the actual purpose of the project:

> **Demonstrating production-level understanding of RAG retrieval, grounding, evaluation, and system design rather than building another document chatbot.**
