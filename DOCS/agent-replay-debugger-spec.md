# PROJECT NAME [IMPORTANT]

> Statica Trace

# Agent Replay Debugger — Design Document

## 1. Problem statement

When an AI agent fails in production (wrong tool call, bad retrieval, hallucinated output, dropped context), the only thing most teams have is a log line. They can't see the exact prompt, retrieved context, and tool state at the moment of failure, and they can't test a fix without re-running the entire multi-step chain from scratch. Existing observability tools (LangSmith, Langfuse) show traces well but are built for LangChain-first teams and don't focus on the "edit this one step and re-run it" workflow. Teams using CrewAI, LlamaIndex, AutoGen, raw SDK loops, or JS agent stacks have even less.

## 2. Goal

Build a hosted tool that:

1. Captures full execution traces from as many AI agent stacks as possible with minimal setup.
2. Lets a developer open a failed run, see exactly what the model saw at each step, edit any part of that step (prompt, retrieved context, tool inputs, params), and re-run just that step against the live API.
3. Shows a diff between the original output and the replayed output.

## 3. Non-goals (skip these, do not build)

- Full agent-building/orchestration platform. We are a debugging layer, not a framework.
- Databricks/MLflow-specific integration. Databricks already has native tracing; not a gap worth building for.
- Deep evaluation/scoring suites (that's a different product). We only need pass/fail and diff, not scoring rubrics.
- Building bespoke adapters for every single framework by hand. Use the tiered approach below instead.

## 4. Target integrations (broadest reach approach)

To cover "most AI solutions" without writing a custom adapter for every framework, use a **two-tier capture strategy**:

**Tier 1 — deep support (full replay capability)**
These get first-class SDK integrations that capture enough structured detail (editable messages, tool schemas, retrieved docs) to support real replay:

- LangChain / LangGraph (Python) — via a custom `BaseCallbackHandler`
- Raw OpenAI SDK (Python + JS) — via a wrapped client
- Raw Anthropic SDK (Python + JS) — via a wrapped client

**Tier 2 — broad support (trace viewing, replay where possible)**
These get ingested generically through an OpenTelemetry (OTel) bridge instead of custom adapters, since most of them already emit or can emit OTel GenAI semantic-convention spans (via libraries like OpenLLMetry/Traceloop):

- CrewAI
- LlamaIndex
- AutoGen
- Vercel AI SDK (JS/TS)
- LiteLLM
- Google Gemini SDK
- Any other framework the user has already instrumented with OpenTelemetry GenAI conventions

This means: build 3 real adapters by hand (LangChain/LangGraph, OpenAI, Anthropic), and get everything else almost for free by accepting standard OTLP (OpenTelemetry Protocol) trace exports on a generic ingest endpoint. This is the single highest-leverage decision in this whole doc, it's what lets one person cover a huge surface area of frameworks.

## 5. High-level architecture

```
[LangChain/LangGraph]  [Raw OpenAI/Anthropic SDK]      [Everything else via OTel]
        |                        |                              |
   Capture SDK              Capture SDK                  OTLP exporter (generic)
        |                        |                              |
        +------------------------+------------------------------+
                                 |
                          Ingest API (FastAPI)
                                 |
                          Trace store (Postgres)
                                 |
                     Replay engine  <-->  Frontend (React)
```

## 6. Core data model (universal trace schema)

Every capture path (custom SDK or OTel bridge) must normalize into this shape before storage. This is the most important file in the whole project, get this right first.

```json
{
	"trace_id": "uuid",
	"project_id": "uuid",
	"source": "langchain | langgraph | openai | anthropic | otel",
	"started_at": "iso8601",
	"ended_at": "iso8601",
	"status": "success | error",
	"spans": [
		{
			"span_id": "uuid",
			"parent_span_id": "uuid | null",
			"type": "llm_call | tool_call | retrieval | agent_step",
			"name": "string",
			"started_at": "iso8601",
			"ended_at": "iso8601",
			"input": {
				"messages": [
					{
						"role": "system|user|assistant|tool",
						"content": "string"
					}
				],
				"model": "string",
				"params": { "temperature": 0.0, "max_tokens": 0 },
				"tools": [{ "name": "string", "schema": {} }],
				"retrieved_context": [
					{ "source": "string", "content": "string", "score": 0.0 }
				]
			},
			"output": {
				"content": "string",
				"tool_calls": [{ "name": "string", "arguments": {} }]
			},
			"error": { "message": "string", "type": "string" }
		}
	]
}
```

Notes for whoever (or whatever AI) builds this:

- `spans` is a flat list with `parent_span_id` links, not a nested tree. Build the tree client-side for display. Flat storage is much easier to query and insert.
- `retrieved_context` only applies to RAG-style spans, omit if not applicable.
- Every span that is `type: llm_call` is a replay candidate. Tool/retrieval spans are shown for context but are not directly replayable in v1.

## 7. Python package

Package name suggestion: `agentreplay` (check PyPI availability before committing).

### 7.1 Folder structure

```
agentreplay/
  agentreplay/
    __init__.py
    client.py          # handles auth + sending traces to the backend
    langchain.py        # LangChain/LangGraph callback handler
    openai_wrapper.py   # wraps openai.Client
    anthropic_wrapper.py # wraps anthropic.Client
    otel_exporter.py    # OTLP span exporter that forwards to our ingest endpoint
    schema.py           # pydantic models matching section 6
    buffer.py           # local queue + batching + retry on send failure
  tests/
  pyproject.toml
  README.md
```

### 7.2 What each file needs to do

**`client.py`**

- Reads API key from env var `AGENTREPLAY_API_KEY` or constructor arg.
- Exposes `AgentReplayClient(api_key=...)` with a `.send(trace)` method.
- Batches traces client-side (don't fire an HTTP request per span, buffer and flush every N seconds or every N traces).
- Never blocks the user's main agent code on network failure. All sends must be fire-and-forget with local retry/backoff, swallow errors after N attempts and log a warning instead of raising.

**`langchain.py`**

- Implements `AgentReplayCallbackHandler(BaseCallbackHandler)`.
- Hook into: `on_llm_start`, `on_llm_end`, `on_llm_error`, `on_tool_start`, `on_tool_end`, `on_tool_error`, `on_chain_start`, `on_chain_end`, `on_chain_error`.
- Build up a trace in memory across the callback lifecycle, keyed by LangChain's `run_id`, and send the whole trace on chain completion.
- Must work with both classic LangChain chains and LangGraph graphs (LangGraph uses the same callback system under the hood).
- Usage should be exactly this simple for the end user:
    ```python
    from agentreplay.langchain import AgentReplayCallbackHandler
    chain.invoke(input, config={"callbacks": [AgentReplayCallbackHandler()]})
    ```

**`openai_wrapper.py`**

- Wraps `openai.OpenAI` client so `client.chat.completions.create(...)` transparently captures input messages, params, and output, then forwards to `client.py`, without changing the return value or behavior for the caller.
- Usage:
    ```python
    from agentreplay.openai_wrapper import wrap
    client = wrap(openai.OpenAI())
    ```

**`anthropic_wrapper.py`**

- Same pattern as `openai_wrapper.py` but for `anthropic.Anthropic().messages.create(...)`.

**`otel_exporter.py`**

- Implements a standard OTel `SpanExporter` that maps incoming OTel GenAI semantic-convention spans onto the schema in section 6, then forwards via `client.py`.
- This is what gives Tier 2 coverage. Document that any user with OpenLLMetry/Traceloop or similar already instrumenting CrewAI, LlamaIndex, AutoGen, etc. can just point their existing OTel exporter at our endpoint (or use this exporter class) and traces show up with zero extra integration work.

**`schema.py`**

- Pydantic models mirroring section 6 exactly. Every other file should build these models and call `.model_dump()` before sending, never send raw dicts.

**`buffer.py`**

- Simple in-memory queue with a background thread that flushes on a timer. Keep this dumb and reliable, this is not the place for cleverness. If it's confusing to vibe-code correctly, fall back to synchronous send with a short timeout instead of building a queue; correctness beats cleverness here.

### 7.3 JS/TS package (v2, after Python MVP validates)

Same structure, ported to TypeScript, targeting the Vercel AI SDK and raw OpenAI/Anthropic JS clients. Don't build this until the Python version has real users, since it doubles maintenance surface for no proven demand yet.

## 8. Backend

### 8.1 Stack

- FastAPI (Python) for the API.
- Postgres for storage (Supabase is a good option if you want hosted Postgres + auth without standing up your own infra).
- No message queue needed for v1, direct writes are fine at expected volume.

### 8.2 Database schema

```sql
create table projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  api_key text unique not null,
  created_at timestamptz default now()
);

create table traces (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id),
  source text not null,
  status text not null,
  started_at timestamptz,
  ended_at timestamptz,
  raw jsonb not null,       -- full trace payload as received, section 6 shape
  created_at timestamptz default now()
);

create index idx_traces_project on traces(project_id, created_at desc);
create index idx_traces_status on traces(project_id, status);

create table replays (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid references traces(id),
  span_id text not null,
  edited_input jsonb not null,
  output jsonb,
  created_at timestamptz default now()
);
```

Keep `raw` as a single JSONB blob rather than fully normalizing spans into their own rows for v1. Query patterns are simple enough (fetch by project, fetch by trace id) that you don't need relational span storage yet, and it removes a lot of migration/ORM complexity from a vibe-coded build.

### 8.3 API endpoints

```
POST   /v1/ingest              # receives a trace payload (section 6 shape), stores it
GET    /v1/traces              # list traces for the authenticated project, filter by status, paginate
GET    /v1/traces/{id}         # full trace detail including all spans
POST   /v1/replay              # body: { trace_id, span_id, edited_input } -> calls the live model, returns output
GET    /v1/projects/me         # returns project info for the authenticated API key
POST   /v1/projects            # create a project, returns a new API key (for signup flow)
```

### 8.4 Auth

- Simple API key in an `Authorization: Bearer <key>` header for both SDK ingestion and frontend API calls.
- No need for OAuth/user accounts in v1, one API key per project is enough to validate the idea. Add proper user accounts (email/password or magic link) only once you have paying users who need multiple projects or team access.

### 8.5 Replay engine

- `POST /v1/replay` takes a `trace_id` + `span_id` + `edited_input` (the modified messages/params/tools for that one span), reconstructs the exact call that would have been made (same model, same tool schema unless the user edited it), fires it directly at the provider's API (OpenAI/Anthropic, based on which the original span used), and returns the new output alongside the original for diffing.
- This endpoint needs the end user's own LLM provider API key to make the replay call. Store it encrypted per-project (or make the user pass it per-request and never persist it, which is simpler and safer for v1, just require it as a header on each replay call).
- No need to replay multi-step chains in v1. Single-step replay is the core value prop, keep it scoped there.

## 9. Frontend

No UI component library specified here on purpose, pick your own. This section only covers functional requirements per page.

### 9.1 Pages

**Login / API key setup**

- On first visit, generate or let the user paste a project API key.
- Show the install snippet for whichever SDK they picked (LangChain callback / OpenAI wrapper / OTel exporter), copy-pasteable, with their real API key already filled in.

**Trace list**

- Table or list of recent traces: timestamp, source (LangChain/OpenAI/etc.), status (success/error), duration.
- Filter by status (show failures first by default, that's the primary debugging use case).
- Click a row to open trace detail.

**Trace detail**

- Vertical timeline of spans in the trace, indented by parent/child relationship.
- Each span shows: type, name, duration, and a status indicator (error spans visually distinct).
- Clicking a span expands it to show full input (messages, retrieved context, tool schema, params) and output.

**Replay panel**

- Opens when a span is selected for replay (only `llm_call` spans are replayable).
- Editable text areas for: system prompt, each message, retrieved context blocks, model params.
- A "replay" button that calls `POST /v1/replay` and shows a loading state.
- Once complete, show a side-by-side or inline diff between original output and replayed output.

**Settings**

- Show/regenerate API key.
- (v2) Provider API key management for replay if you choose to persist it instead of passing per-request.

### 9.2 State and data

- Fetch trace list and trace detail from the backend endpoints in section 8.3.
- No need for real-time updates (polling or websockets) in v1, a manual refresh is fine.
- Keep all replay edits as local component state until the user hits replay, don't autosave drafts in v1.

## 10. Build order (do this in sequence, don't jump ahead)

1. Write `schema.py` (section 6/7.2) first. Every other piece depends on this being right.
2. Build the backend ingest endpoint (`POST /v1/ingest`) and the `traces` table. Test it by posting a hand-written JSON payload with `curl` before writing any SDK code.
3. Build the LangChain callback handler (`langchain.py`) and confirm a real LangChain chain run shows up correctly in the database.
4. Build the trace list and trace detail frontend pages against the real ingested data.
5. Build the replay endpoint and replay panel UI. This is the core differentiator, don't rush it.
6. Add the OpenAI and Anthropic raw SDK wrappers.
7. Add the OTel exporter bridge for Tier 2 framework coverage.
8. Add the signup flow (create project, get API key) so this can be used by someone other than you.
9. Polish: error states, empty states, loading states across the frontend.
10. (v2, only after validating demand) JS/TS SDK, proper user accounts, persisted provider keys, team access.

## 11. Deployment

- Backend: any container host works, Fly.io or Railway are low-effort options for a solo-built API.
- Database: Supabase Postgres or a managed Postgres instance from the same host as the backend.
- Frontend: Vercel or Netlify, static build with API calls to the backend.
- Keep infra minimal until you have real usage, don't over-engineer scaling for a product with zero users yet.

## 12. Validation checkpoint

Before building past step 3 in the build order, get at least a few real people (from the LangChain Discord, r/LangChain, Indie Hackers) to actually send you a real failing trace and confirm the replay workflow would have helped them. If nobody bites at that stage, it's much cheaper to redirect than after the frontend and OTel bridge are built too.
