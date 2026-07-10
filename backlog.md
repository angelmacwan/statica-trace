# Statica Trace — Implementation Backlog

> **Product**: Statica Trace — An agent replay debugger that captures full AI agent execution traces and lets developers edit and re-run individual steps to debug failures.
>
> **Definition of Done**: All checkboxes below are checked off. The entire product is shippable.

---

## Legend

- `[ ]` — Not started
- `[x]` — Done

---

## Testing Philosophy

All Python code is tested with **pytest**. All Python code is formatted with **black** and linted with **ruff** — CI fails on any violation.

**Mocking strategy**: Tests use the real library (e.g. real `langchain`, real `openai` SDK, real `anthropic` SDK) but mock the outbound HTTP calls using `pytest-httpx`, `respx`, or `unittest.mock.patch` so no test ever hits a live API. This means we test our integration logic with the actual library internals (callbacks, client lifecycle, response parsing) without external dependencies.

**Frontend** uses **Vitest** for unit/component tests and **Playwright** for end-to-end browser tests.

**System tests** (Module 7) run the real backend locally in the background against a dedicated test database (SQLite/Postgres) and run full flows end-to-end natively without Docker.

---

## Module 0 — Tooling & Test Infrastructure

### Sprint 0.1 — Python Tooling Setup

- [x] **0.1.1 — Configure ruff and black for Python**

    **Description**: Set up `ruff` and `black` as the standard formatting and linting tools for all Python code in the repo. Both must be enforced in CI so no unformatted or lint-failing code can be merged.

    **Acceptance Criteria**:
    - `pyproject.toml` (or `ruff.toml`) contains ruff configuration: selected rule sets (at minimum `E`, `F`, `I`, `UP`), line length matching black's default (88).
    - `black` is configured in `pyproject.toml` with line length 88.
    - A `make lint` (or equivalent script) runs both `ruff check .` and `black --check .` and exits non-zero on any violation.
    - CI pipeline step runs this check and fails the build on any violation.
    - All existing Python files pass both tools on first run (or are fixed before this item is closed).

- [x] **0.1.2 — Configure pytest and shared test fixtures**

    **Description**: Set up pytest as the test runner for all Python code. Create the shared fixtures and factory helpers that all other test modules will rely on: sample trace builders, mock HTTP responses, a test database client.

    **Acceptance Criteria**:
    - `pytest` and `pytest-cov` are listed as dev dependencies in `pyproject.toml`.
    - `conftest.py` at the repo root (or per-package) defines shared fixtures including: `sample_trace()`, `sample_llm_call_span()`, `sample_tool_call_span()`, `sample_rag_span()` — each returning valid Pydantic model instances.
    - A `make test` (or equivalent) command runs the full test suite.
    - `pytest.ini` or `[tool.pytest.ini_options]` in `pyproject.toml` sets `testpaths`, `addopts = --tb=short --cov`, and coverage threshold (minimum 80%).
    - CI pipeline runs tests and fails if coverage drops below threshold.
    - `pytest-httpx` or `respx` is installed for HTTP mocking in SDK tests.

### Sprint 0.2 — Frontend Tooling Setup

- [x] **0.2.1 — Configure Vitest for frontend unit and component tests**

    **Description**: Set up Vitest as the frontend test runner. Configure it with jsdom for component testing and add the initial test utilities.

    **Acceptance Criteria**:
    - `vitest` and `@testing-library/react` (or equivalent for the chosen framework) installed as dev dependencies.
    - `vitest.config.ts` (or equivalent) configured with jsdom environment.
    - A `npm run test` command runs the Vitest suite.
    - A `npm run test:coverage` command runs with coverage reporting; minimum 70% branch coverage enforced.
    - CI pipeline runs frontend tests and fails on failure or coverage drop.
    - A trivial smoke test exists and passes (e.g. renders a `<Button>` component and asserts it's in the DOM).

- [x] **0.2.2 — Configure Playwright for end-to-end browser tests**

    **Description**: Set up Playwright as the E2E test framework for the frontend. Configure it to run against a local dev server or a staging environment.

    **Acceptance Criteria**:
    - `@playwright/test` installed as a dev dependency.
    - `playwright.config.ts` configured with at least Chromium as a target browser.
    - `npm run test:e2e` command runs the Playwright suite against a locally started dev server.
    - A trivial smoke test exists: navigates to `/` and asserts the page title is correct.
    - CI pipeline step runs Playwright tests (can be gated to run only on PRs that touch frontend code).

---

## Module 1 — Foundation & Data Model

### Sprint 1.1 — Core Schema

- [x] **1.1.1 — Define Pydantic trace schema (`schema.py`)**

    **Description**: Create the canonical Pydantic data models that represent the universal trace schema. Every capture path (custom SDK adapters and OTel bridge) must normalize into this shape before storage. This is the single most critical file in the project — all other modules depend on it being correct.

    **Acceptance Criteria**:
    - `schema.py` defines Pydantic models exactly matching the universal trace schema in the spec (trace, span, input, output, error, retrieved context).
    - Models include: `Trace`, `Span`, `SpanInput`, `SpanOutput`, `SpanError`, `Message`, `RetrievedContext`, `ToolDefinition`, `ToolCall`.
    - `source` field is an enum: `langchain | langgraph | openai | anthropic | otel`.
    - `type` field on spans is an enum: `llm_call | tool_call | retrieval | agent_step`.
    - `spans` is a flat list with `parent_span_id` references (not a nested tree).
    - All models use `.model_dump()` cleanly and serialize/deserialize without data loss.
    - File passes `ruff` and `black` checks.

### Sprint 1.2 — Schema Unit Tests

- [x] **1.2.1 — Unit tests for `schema.py`**

    **Description**: Write a thorough pytest test suite for all Pydantic models in `schema.py`. Tests should cover valid construction, serialization round-trips, validation errors on bad input, and all optional field combinations.

    **Acceptance Criteria**:
    - Tests live in `tests/test_schema.py`.
    - Covers: constructing each model with all required fields, `.model_dump()` produces the correct dict shape.
    - Covers: round-trip `Trace.model_validate(trace.model_dump())` is lossless for both simple and complex traces.
    - Covers: `source` enum rejects an unknown string value with a `ValidationError`.
    - Covers: `type` enum on spans rejects an unknown value.
    - Covers: `retrieved_context` can be omitted entirely and the model is still valid.
    - Covers: a span with `parent_span_id = None` is valid (root span).
    - Covers: a `Trace` with zero spans is valid.
    - Covers: a `Trace` with 50 spans serializes and deserializes without data loss.
    - 100% line coverage on `schema.py`.
    - All tests pass `ruff` and `black`.

---

## Module 2 — Backend

### Sprint 2.1 — Database & Project Setup

- [x] **2.1.1 — Initialize Postgres database and run migrations**

    **Description**: Set up the Postgres database (Supabase or managed Postgres) and apply the initial schema migration. This creates the `projects`, `traces`, and `replays` tables as specified in the design doc.

    **Acceptance Criteria**:
    - `projects`, `traces`, and `replays` tables exist and match the SQL schema exactly.
    - Indexes on `traces(project_id, created_at desc)` and `traces(project_id, status)` are present.
    - `traces.raw` is a JSONB column that can store the full trace payload.
    - Migration is idempotent (safe to re-run).
    - Database connection is managed via environment variables (not hardcoded credentials).

- [x] **2.1.2 — Project creation and API key generation (`POST /v1/projects`)**

    **Description**: Implement the endpoint that creates a new project record in the database and returns a unique API key. This is the entry point for the signup flow, allowing a new user to get their API key without needing an existing account.

    **Acceptance Criteria**:
    - `POST /v1/projects` accepts a JSON body with a `name` field.
    - Returns a project object including a newly generated `api_key` (UUID or securely random string).
    - `api_key` is stored in the `projects` table with a unique constraint.
    - Duplicate project names are allowed (only `api_key` must be unique).
    - Returns HTTP 201 on success, 400 on invalid input.

- [x] **2.1.3 — API key authentication middleware**

    **Description**: Implement the authentication layer for the FastAPI backend. All protected endpoints must validate the `Authorization: Bearer <key>` header against the `projects` table and attach the resolved `project_id` to the request context.

    **Acceptance Criteria**:
    - A FastAPI dependency reads the `Authorization: Bearer <key>` header.
    - Valid API key resolves and injects the `project_id` into the request.
    - Invalid or missing key returns HTTP 401.
    - The middleware is applied to all endpoints except `POST /v1/projects`.
    - No API key is ever logged in plaintext.

- [x] **2.1.4 — Get project info (`GET /v1/projects/me`)**

    **Description**: Implement the endpoint that returns the authenticated project's metadata. Used by the frontend to display the current project name and confirm API key validity.

    **Acceptance Criteria**:
    - `GET /v1/projects/me` returns the project's `id`, `name`, and `created_at`.
    - Does **not** return the `api_key` in the response body.
    - Returns HTTP 200 with project data on valid auth.
    - Returns HTTP 401 on invalid or missing key.

### Sprint 2.2 — Trace Ingestion

- [x] **2.2.1 — Trace ingest endpoint (`POST /v1/ingest`)**

    **Description**: Implement the main ingest endpoint that receives a full trace payload (matching the schema from Module 1), validates it, and stores it as a JSONB blob in the `traces` table. This is the endpoint all SDKs and the OTel bridge will POST to.

    **Acceptance Criteria**:
    - `POST /v1/ingest` accepts a JSON body matching the `Trace` Pydantic model.
    - Payload is validated against the schema; returns HTTP 422 on schema mismatch.
    - Valid trace is stored in the `traces` table with correct `project_id`, `source`, `status`, `started_at`, `ended_at`, and the full payload in `raw`.
    - Returns HTTP 202 on success (accepted for storage).
    - A manually crafted `curl` POST with a valid JSON payload produces a row in the database.
    - Handles missing optional fields gracefully (e.g. no `retrieved_context`).

### Sprint 2.3 — Trace Retrieval

- [x] **2.3.1 — List traces endpoint (`GET /v1/traces`)**

    **Description**: Implement the endpoint that returns a paginated list of traces for the authenticated project. Supports filtering by status so failed runs appear first.

    **Acceptance Criteria**:
    - `GET /v1/traces` returns traces for the authenticated `project_id` only.
    - Response includes: `trace_id`, `source`, `status`, `started_at`, `ended_at`, `duration_ms`.
    - Supports `?status=error|success` query param filter.
    - Default sort: `created_at DESC` (newest first).
    - Supports `?limit=` and `?offset=` pagination params (default limit: 50).
    - A project cannot see another project's traces.

- [x] **2.3.2 — Trace detail endpoint (`GET /v1/traces/{id}`)**

    **Description**: Implement the endpoint that returns the full trace detail for a single trace, including all spans. Used by the frontend to render the trace timeline and span inspector.

    **Acceptance Criteria**:
    - `GET /v1/traces/{id}` returns the full trace payload including all spans.
    - Returns HTTP 404 if the trace does not belong to the authenticated project.
    - Spans are returned as a flat list with `parent_span_id` links (tree is built client-side).
    - Response time is acceptable for traces with up to 50 spans.

### Sprint 2.4 — Replay Engine

- [x] **2.4.1 — Replay endpoint (`POST /v1/replay`)**

    **Description**: Implement the replay engine endpoint. It accepts a `trace_id`, `span_id`, and `edited_input` (modified messages, params, tools for that one span), reconstructs the original LLM call with the edits applied, fires it at the provider's live API, and returns the new output alongside the original output for diffing.

    **Acceptance Criteria**:
    - `POST /v1/replay` accepts `{ trace_id, span_id, edited_input }` in the request body.
    - Fetches the original span from the stored trace by `trace_id` + `span_id`.
    - Detects the provider (OpenAI or Anthropic) from the original span's data.
    - Accepts the user's provider API key via a request header (e.g. `X-Provider-Api-Key`) — key is **never** persisted.
    - Constructs and fires the exact call to the provider API using the `edited_input`.
    - Returns a response containing: `original_output` (from stored trace) and `replayed_output` (from live call).
    - Stores the replay attempt in the `replays` table (`trace_id`, `span_id`, `edited_input`, `output`).
    - Only `llm_call` span types are replayable; returns HTTP 400 for other types.
    - Returns HTTP 404 if `trace_id` or `span_id` is not found.
    - Returns a clear error if the provider API key is missing or rejected by the provider.

### Sprint 2.5 — Backend Unit & Integration Tests

- [x] **2.5.1 — Unit tests for auth middleware**

    **Description**: Write pytest tests for the API key authentication dependency in isolation, without spinning up a real database. Use a mock project store or SQLite in-memory database.

    **Acceptance Criteria**:
    - Tests live in `tests/backend/test_auth.py`.
    - Covers: valid API key resolves the correct `project_id`.
    - Covers: missing `Authorization` header returns 401.
    - Covers: `Authorization: Bearer invalid-key` returns 401.
    - Covers: malformed header (not Bearer scheme) returns 401.
    - All branches covered; 100% coverage on the auth module.
    - Tests run without a real Postgres instance (use dependency override or SQLite).

- [x] **2.5.2 — Integration tests for `POST /v1/ingest`**

    **Description**: Write pytest integration tests for the ingest endpoint using FastAPI's `TestClient` and a real test database (SQLite in-memory or a separate test Postgres schema). Tests use the real endpoint stack but with the database isolated per test.

    **Acceptance Criteria**:
    - Tests live in `tests/backend/test_ingest.py`.
    - Covers: posting a valid minimal trace returns HTTP 202 and a row appears in the DB.
    - Covers: posting a trace with all optional fields (retrieved_context, tools) stores correctly.
    - Covers: posting a malformed payload returns HTTP 422 with a meaningful error.
    - Covers: posting without a valid API key returns HTTP 401.
    - Covers: two projects' traces are stored independently and cannot be accessed across projects.
    - Database is reset between tests (transaction rollback or per-test schema).

- [x] **2.5.3 — Integration tests for `GET /v1/traces` and `GET /v1/traces/{id}`**

    **Description**: Write pytest integration tests for the trace retrieval endpoints, seeding the database with fixture traces and asserting correct filtering, pagination, and isolation.

    **Acceptance Criteria**:
    - Tests live in `tests/backend/test_traces.py`.
    - Covers: list endpoint returns only the authenticated project's traces.
    - Covers: `?status=error` filter returns only error traces; `?status=success` returns only success traces.
    - Covers: pagination (`?limit=2&offset=0`) returns the correct page; `?offset=2` returns the next page.
    - Covers: default sort is newest first (verified by `created_at` ordering).
    - Covers: detail endpoint returns the full `raw` payload including all spans.
    - Covers: detail endpoint returns 404 for a trace belonging to another project.
    - Covers: detail endpoint returns 404 for a nonexistent trace ID.

- [x] **2.5.4 — Integration tests for `POST /v1/replay`**

    **Description**: Write pytest integration tests for the replay endpoint. The outbound call to the provider API (OpenAI / Anthropic) is mocked using `pytest-httpx` or `respx` — real `httpx` or `requests` calls are intercepted and a fake response is returned. The actual replay engine logic (constructing the provider call, parsing the response) is exercised end-to-end except for the network hop.

    **Acceptance Criteria**:
    - Tests live in `tests/backend/test_replay.py`.
    - Covers: valid replay request for an OpenAI span — mocked OpenAI API returns a fake completion, endpoint returns `original_output` vs `replayed_output`.
    - Covers: valid replay request for an Anthropic span — mocked Anthropic API returns a fake message.
    - Covers: edited_input overrides are applied (changed system prompt appears in the mocked outbound request).
    - Covers: missing `X-Provider-Api-Key` header returns a clear error.
    - Covers: mocked provider API returning 401 surfaces a clear error response (not a 500 crash).
    - Covers: replaying a `tool_call` span returns HTTP 400.
    - Covers: replay record is written to the `replays` table.
    - Provider API calls are fully mocked — no real network traffic.

---

## Module 3 — Python Capture SDK (`agentreplay`)

### Sprint 3.1 — SDK Foundation

- [x] **3.1.1 — Python package scaffolding and `client.py`**

    **Description**: Initialize the `agentreplay` Python package with its full folder structure and implement `client.py`, the core networking layer that handles auth and sends traces to the backend ingest endpoint. All other SDK modules depend on this client.

    **Acceptance Criteria**:
    - Package folder structure matches the spec: `agentreplay/`, `client.py`, `langchain.py`, `openai_wrapper.py`, `anthropic_wrapper.py`, `otel_exporter.py`, `schema.py`, `buffer.py`, `tests/`, `pyproject.toml`, `README.md`.
    - `AgentReplayClient(api_key=...)` reads key from constructor arg or `AGENTREPLAY_API_KEY` env var.
    - `.send(trace)` method serializes the trace and POSTs to `POST /v1/ingest`.
    - On network failure, the client retries with backoff up to N attempts, then logs a warning instead of raising.
    - Sends are **non-blocking** — they never stall the caller's main thread.
    - Packaged with `pyproject.toml` and installable via `pip install .`.
    - All files pass `ruff` and `black`.

- [x] **3.1.2 — Send buffer and batching (`buffer.py`)**

    **Description**: Implement the local in-memory queue and background flush mechanism. Traces should be batched and sent periodically rather than one HTTP request per span, to minimize overhead on the user's agent code.

    **Acceptance Criteria**:
    - `buffer.py` provides a queue that accumulates trace payloads.
    - A background thread (or equivalent) flushes the queue every N seconds OR when N traces are queued (whichever comes first).
    - Flush failure does not raise an exception to the caller — it logs a warning and drops after max retries.
    - If flushing is too complex to implement reliably, falls back to a synchronous send with a short timeout (correctness over cleverness, per spec).
    - On process exit, attempts a final flush.

### Sprint 3.2 — Tier 1 Adapters

- [x] **3.2.1 — LangChain / LangGraph callback handler (`langchain.py`)**

    **Description**: Implement `AgentReplayCallbackHandler`, a `BaseCallbackHandler` subclass that hooks into the LangChain callback lifecycle to capture a full trace across a chain or graph run, then sends it via `client.py` on completion.

    **Acceptance Criteria**:
    - `AgentReplayCallbackHandler` extends `BaseCallbackHandler`.
    - Hooks implemented: `on_llm_start`, `on_llm_end`, `on_llm_error`, `on_tool_start`, `on_tool_end`, `on_tool_error`, `on_chain_start`, `on_chain_end`, `on_chain_error`.
    - Trace is assembled in memory keyed by LangChain's `run_id`; full trace is sent on chain completion.
    - Works with both classic LangChain chains and LangGraph graphs.
    - Integration usage is exactly: `chain.invoke(input, config={"callbacks": [AgentReplayCallbackHandler()]})`.
    - A real LangChain chain run produces a correctly structured trace in the database.
    - Captured spans include: messages, model name, params, tool schemas (if tool-calling), and output.

- [x] **3.2.2 — OpenAI SDK wrapper (`openai_wrapper.py`)**

    **Description**: Implement the `wrap()` function that transparently wraps an `openai.OpenAI` client so that all `chat.completions.create()` calls are automatically captured as traces, without changing any return values or behavior for the caller.

    **Acceptance Criteria**:
    - `from agentreplay.openai_wrapper import wrap; client = wrap(openai.OpenAI())` is the complete usage.
    - All `client.chat.completions.create(...)` calls are intercepted.
    - Captured data: input messages, model, temperature, max_tokens, tools (if present), full output.
    - Return value to the caller is **identical** to an unwrapped call.
    - Errors from the OpenAI API are re-raised unchanged; the span is captured with `status: error`.
    - A real call through the wrapped client produces a correctly structured trace in the database.

- [x] **3.2.3 — Anthropic SDK wrapper (`anthropic_wrapper.py`)**

    **Description**: Implement the same transparent wrapping pattern as `openai_wrapper.py` but for the `anthropic.Anthropic().messages.create(...)` call path.

    **Acceptance Criteria**:
    - `from agentreplay.anthropic_wrapper import wrap; client = wrap(anthropic.Anthropic())` is the complete usage.
    - All `client.messages.create(...)` calls are intercepted.
    - Captured data: input messages, model, temperature, max_tokens, tools (if present), full output — mapped to the universal schema.
    - Return value to the caller is **identical** to an unwrapped call.
    - Errors from the Anthropic API are re-raised unchanged; the span is captured with `status: error`.
    - A real call through the wrapped client produces a correctly structured trace in the database.

### Sprint 3.3 — Tier 2 OTel Bridge

- [x] **3.3.1 — OpenTelemetry span exporter (`otel_exporter.py`)**

    **Description**: Implement a standard OTel `SpanExporter` that maps incoming OTel GenAI semantic-convention spans (as emitted by OpenLLMetry/Traceloop and compatible libraries) to the universal trace schema, then forwards them via `client.py`. This is the Tier 2 coverage mechanism for frameworks like CrewAI, LlamaIndex, AutoGen, LiteLLM, Vercel AI SDK, and Google Gemini SDK.

    **Acceptance Criteria**:
    - `AgentReplayOTelExporter` implements the `opentelemetry.sdk.trace.export.SpanExporter` interface.
    - Maps OTel GenAI semantic convention attributes to the universal trace schema fields.
    - Can be used as a drop-in exporter: `TracerProvider(exporter=AgentReplayOTelExporter(api_key=...))`.
    - Alternatively, users can point their existing OTLP exporter at the backend ingest endpoint directly (documented in README).
    - A CrewAI or LlamaIndex run instrumented with OpenLLMetry produces a visible trace in the database via this exporter.
    - README documents the Tier 2 setup path clearly.

### Sprint 3.4 — SDK Unit Tests

- [x] **3.4.1 — Unit tests for `client.py` and `buffer.py`**

    **Description**: Write pytest unit tests for the networking client and buffer. The outbound HTTP POST to the ingest endpoint is mocked — no real server needed.

    **Acceptance Criteria**:
    - Tests live in `tests/sdk/test_client.py` and `tests/sdk/test_buffer.py`.
    - **`client.py`** covers:
        - API key read from constructor arg.
        - API key read from `AGENTREPLAY_API_KEY` env var when constructor arg is absent.
        - `.send()` makes a POST to `/v1/ingest` with correct `Authorization` header and serialized body (mocked HTTP).
        - Network failure: client retries N times, then logs a warning and does not raise.
        - `.send()` does not block the calling thread (assert wall-clock time below a threshold with mocked slow response).
    - **`buffer.py`** covers:
        - Enqueue adds item to queue.
        - Flush is triggered when queue size reaches threshold (without waiting for timer).
        - Flush is triggered on timer expiry even if threshold not reached.
        - Flush failure does not raise — warning is logged.
        - Final flush is attempted on process exit.
    - All HTTP calls mocked; no real network traffic.

- [x] **3.4.2 — Unit tests for `langchain.py` (with real LangChain, mocked LLM)**

    **Description**: Write pytest tests for `AgentReplayCallbackHandler` using **real LangChain library code** but with a mocked LLM (LangChain's `FakeListLLM` or a mock that returns a canned response). The handler is invoked through an actual LangChain chain so the full callback lifecycle is exercised. The outbound send to the backend is also mocked.

    **Acceptance Criteria**:
    - Tests live in `tests/sdk/test_langchain.py`.
    - Use real `langchain` and `langchain_core` imports — no mocking of LangChain internals.
    - Use `FakeListLLM` or equivalent to avoid real LLM API calls.
    - Covers: running a simple chain with the handler attached produces a `Trace` object with at least one `llm_call` span.
    - Covers: span `input.messages` contains the correct prompt messages.
    - Covers: span `output.content` contains the fake LLM response.
    - Covers: an LLM error during the chain produces a span with `status: error` and an `error` field.
    - Covers: a chain with a tool call produces both an `llm_call` span and a `tool_call` span.
    - Covers: the assembled `Trace` is sent to the backend via `client.send()` (backend send is mocked).
    - Covers: handler does not alter the chain's return value.
    - No real OpenAI/Anthropic/etc. API calls.

- [x] **3.4.3 — Unit tests for `openai_wrapper.py` (with real OpenAI SDK, mocked HTTP)**

    **Description**: Write pytest tests for the OpenAI wrapper using the **real `openai` Python SDK** but intercepting its outbound HTTP calls with `pytest-httpx` or `respx`. This exercises the SDK's internal request building and response parsing together with our wrapping logic.

    **Acceptance Criteria**:
    - Tests live in `tests/sdk/test_openai_wrapper.py`.
    - Use real `openai.OpenAI()` client — do not mock the SDK class itself.
    - Intercept HTTP calls at the transport level (e.g. `respx` or `pytest-httpx`).
    - Covers: `wrap(openai.OpenAI())` returns a client that behaves identically to an unwrapped one (same return type, same response content).
    - Covers: after a `chat.completions.create(...)` call, a `Trace` with one `llm_call` span is captured with correct messages, model, params, and output.
    - Covers: tool definitions passed to `create()` appear in the span's `input.tools`.
    - Covers: when the mocked HTTP returns an error response, the exception is re-raised to the caller unchanged, and the span is recorded with `status: error`.
    - Covers: the backend send is also mocked; asserts the trace is sent with correct content.
    - No real OpenAI API calls; no real network traffic.

- [x] **3.4.4 — Unit tests for `anthropic_wrapper.py` (with real Anthropic SDK, mocked HTTP)**

    **Description**: Write pytest tests for the Anthropic wrapper following the exact same pattern as `3.4.3` but for the `anthropic` SDK.

    **Acceptance Criteria**:
    - Tests live in `tests/sdk/test_anthropic_wrapper.py`.
    - Use real `anthropic.Anthropic()` client — do not mock the SDK class itself.
    - Intercept HTTP calls at the transport level.
    - Covers: `wrap(anthropic.Anthropic())` returns a client that behaves identically (same return type, same response).
    - Covers: after a `messages.create(...)` call, a `Trace` with one `llm_call` span is captured with correct messages, model, params, and output mapped to the universal schema.
    - Covers: tool definitions appear in the span's `input.tools`.
    - Covers: API error response re-raised to caller; span captured with `status: error`.
    - Covers: the backend send is mocked; asserts correct trace content.
    - No real Anthropic API calls; no real network traffic.

- [x] **3.4.5 — Unit tests for `otel_exporter.py` (with real OpenTelemetry SDK)**

    **Description**: Write pytest tests for the OTel exporter using the **real `opentelemetry-sdk`** library to emit spans and routing them through the exporter. The exporter's outbound send to the backend is mocked.

    **Acceptance Criteria**:
    - Tests live in `tests/sdk/test_otel_exporter.py`.
    - Use real `opentelemetry.sdk.trace` and `opentelemetry.trace` imports.
    - Configure a `TracerProvider` with `AgentReplayOTelExporter` as the exporter.
    - Covers: a span emitted with GenAI semantic convention attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.prompt`, `gen_ai.completion`) is correctly mapped to a `Trace` with one `llm_call` span.
    - Covers: `source` field is set to `otel`.
    - Covers: span timing (`started_at`, `ended_at`) is correctly translated from OTel nanosecond timestamps to ISO8601.
    - Covers: a span with an error status sets `status: error` on the captured span.
    - Covers: the assembled trace is sent via the backend client (mocked).
    - No real network traffic.

---

## Module 4 — Frontend

### Sprint 4.1 — Design System & App Shell

- [x] **4.1.1 — Tailwind config and design token setup**

    **Description**: Configure Tailwind CSS with the full design token set from the design system doc. This includes the semantic color palette, custom font families, extended radius scale, and custom shadow tokens. This must be done first so all components can be built consistently.

    **Acceptance Criteria**:
    - `tailwind.config.js` extends the theme with all semantic color tokens: full `surface` scale, `primary`, `primary-container`, `secondary`, `secondary-container`, `tertiary-fixed`, `tertiary-fixed-dim`, `on-primary`, `on-surface`, `on-surface-variant`, `outline`, `error`, `success`.
    - Font families configured: `font-sans` → Inter, `font-headline` → Manrope.
    - Google Fonts (Inter + Manrope) loaded in the app's `<head>`.
    - Custom border radius tokens added: `rounded-2.5xl` (1.75rem), `rounded-3.5xl` (2rem).
    - Custom shadow tokens added: `shadow-ambient-sm`, `shadow-ambient-lg`, `shadow-brand`, `shadow-hero`.
    - Custom breakpoints added if needed: `tablet` (860px), `wide` (1180px).
    - A quick visual smoke-test page (not shipped) confirms all tokens render correctly.

- [x] **4.1.2 — App shell: sidebar navigation and layout**

    **Description**: Build the persistent app shell that wraps all authenticated pages. Includes the sidebar navigation and the main content area. Navigation items link to: Traces, Settings.

    **Acceptance Criteria**:
    - Sidebar is fixed/sticky on the left, full viewport height, `w-60`, `bg-surface-container-low`.
    - Brand name displayed at the top of the sidebar using `font-headline`.
    - Nav items follow the design system pattern: inactive state (`text-secondary`), active state (`text-primary bg-surface-container-lowest shadow-ambient-sm`).
    - Smooth hover transition on nav items.
    - Main content area takes up remaining width.
    - Layout is responsive: sidebar collapses or is hidden below the `tablet` breakpoint.

### Sprint 4.2 — Auth & Onboarding Pages

- [x] **4.2.1 — Login / API key setup page**

    **Description**: Build the first-visit onboarding page where a new user can create a project (triggering `POST /v1/projects`) or paste an existing API key. After setup, the page displays the integration install snippet with the user's real API key pre-filled and a copy-to-clipboard button.

    **Acceptance Criteria**:
    - Page has two modes: "Create project" (name input + submit) and "I already have a key" (paste key + confirm).
    - "Create project" calls `POST /v1/projects`, stores the returned API key in local storage, and shows the success state.
    - Install snippet section shows three tabs: LangChain, OpenAI, OTel — each with the correct code snippet and the user's real API key already substituted in.
    - Copy-to-clipboard button works on each snippet.
    - API key is masked in the UI (show first/last 4 chars), with a "reveal" toggle.
    - Page follows the auth page layout from the design system doc (two-column or single-column centered form).

### Sprint 4.3 — Trace List Page

- [x] **4.3.1 — Trace list page**

    **Description**: Build the main trace list page that shows all traces for the current project in a table, with filtering and the ability to click into a trace for detail.

    **Acceptance Criteria**:
    - Fetches data from `GET /v1/traces` on mount.
    - Table columns: Timestamp, Source (LangChain / OpenAI / OTel / etc.), Status (success/error chip), Duration.
    - Status column uses colored chips: error state uses `bg-error-container text-error`, success uses `bg-secondary-container text-on-secondary-container`.
    - Default sort is newest first; failed traces shown first or accessible via filter toggle.
    - Filter control: "All", "Errors only", "Success only" — filters via `?status=` query param.
    - Empty state: helpful message with a link back to the setup page when no traces exist.
    - Loading state: skeleton rows or spinner while fetching.
    - Clicking a row navigates to the trace detail page.
    - Table follows the design system table pattern with header gradient tint and row hover.

### Sprint 4.4 — Trace Detail & Span Inspector

- [x] **4.4.1 — Trace detail page with span timeline**

    **Description**: Build the trace detail page that renders the full span timeline for a selected trace. Spans are shown as a vertical tree (built client-side from the flat list using `parent_span_id` links), indented by depth, with error spans visually distinct.

    **Acceptance Criteria**:
    - Fetches data from `GET /v1/traces/{id}` on mount.
    - Renders a vertical timeline of spans, indented by parent/child relationship.
    - Each span row shows: type icon, span name, duration, and status indicator.
    - Error spans are visually distinct (e.g. red left border or `error` color treatment).
    - Clicking a span expands it inline to show the full input (messages, retrieved context if present, tool schema if present, model params) and output.
    - `llm_call` spans show a "Replay" button to open the replay panel.
    - Non-`llm_call` spans (tool_call, retrieval, agent_step) show their data but no replay button.
    - Breadcrumb or back button navigates to the trace list.
    - Loading and error states handled.

### Sprint 4.5 — Replay Panel

- [x] **4.5.1 — Replay panel UI and diff view**

    **Description**: Build the replay panel that opens when a user clicks "Replay" on an `llm_call` span. The panel provides editable fields for the span's inputs, a replay action that calls the backend, and a diff view comparing the original and replayed outputs.

    **Acceptance Criteria**:
    - Replay panel opens as a side panel or modal when "Replay" is clicked on an `llm_call` span.
    - Editable fields: system prompt (textarea), each user/assistant message (textarea per message), retrieved context blocks (textarea per block, if present), model params (temperature, max_tokens as number inputs).
    - All editable fields are pre-populated with the original span's input data.
    - A text input or field for the user's provider API key (required to fire the replay; never sent to or stored by the backend beyond the single request).
    - "Replay" button calls `POST /v1/replay` with the edited inputs.
    - Loading state shown while replay is in progress; button disabled during this time.
    - On success: side-by-side or inline diff between original output and replayed output, with differences highlighted.
    - On error: clear inline error message (e.g. provider key rejected, span not replayable).
    - All replay edits are local component state — no autosave.

### Sprint 4.6 — Settings Page

- [x] **4.6.1 — Settings page**

    **Description**: Build the settings page that lets the user view their API key and project info.

    **Acceptance Criteria**:
    - Displays project name and project ID (fetched from `GET /v1/projects/me`).
    - Displays the API key in masked form (first/last 4 chars) with a "reveal" toggle.
    - "Copy" button copies the API key to clipboard.
    - Clean, minimal layout following the design system card and form patterns.

### Sprint 4.7 — Frontend Unit & Component Tests

- [x] **4.7.1 — Unit tests for span tree builder utility**

    **Description**: The trace detail page builds a parent/child tree from a flat `spans` list. Write Vitest unit tests for this pure function, which is the most logic-heavy piece of frontend code.

    **Acceptance Criteria**:
    - Tests live in `src/__tests__/spanTree.test.ts` (or equivalent).
    - Covers: flat list with one root span and two children produces correct tree.
    - Covers: spans with missing `parent_span_id` are treated as root nodes.
    - Covers: deeply nested spans (3+ levels) are correctly ordered.
    - Covers: empty spans array produces empty tree.
    - Covers: a span whose `parent_span_id` references a nonexistent span is placed at root level (graceful handling).
    - 100% branch coverage on the tree-builder function.

- [x] **4.7.2 — Component tests for the trace list table**

    **Description**: Write Vitest + Testing Library component tests for the trace list table, mocking the API fetch layer with MSW (Mock Service Worker) or a similar tool.

    **Acceptance Criteria**:
    - Tests live in `src/__tests__/TraceList.test.tsx` (or equivalent).
    - API calls mocked — no real backend needed.
    - Covers: loading state renders a skeleton or spinner.
    - Covers: after data loads, table rows match the mocked trace list (timestamp, source, status, duration).
    - Covers: error state (mocked API failure) renders an error banner.
    - Covers: empty state (mocked empty list) renders the empty state UI.
    - Covers: `?status=error` filter is applied when "Errors only" is selected.
    - Covers: clicking a row triggers navigation to the correct trace detail URL.

- [x] **4.7.3 — Component tests for the replay panel**

    **Description**: Write Vitest + Testing Library component tests for the replay panel component, covering the edit-and-submit flow.

    **Acceptance Criteria**:
    - Tests live in `src/__tests__/ReplayPanel.test.tsx` (or equivalent).
    - Covers: panel renders with all fields pre-populated from the span's input data.
    - Covers: editing the system prompt textarea updates local state correctly.
    - Covers: editing a message textarea updates the correct message in local state.
    - Covers: "Replay" button is disabled while a replay is in progress (loading state).
    - Covers: on successful replay (mocked API response), the diff view renders with both original and replayed outputs.
    - Covers: on API error (mocked failure), an inline error message is displayed.
    - Covers: the provider API key field is present and its value is included in the mocked outbound request.

### Sprint 4.8 — Frontend E2E Tests (Playwright)

- [x] **4.8.1 — E2E: onboarding and project creation flow**

    **Description**: Write a Playwright test that navigates through the full onboarding flow: creating a project, receiving an API key, and viewing the install snippet.

    **Acceptance Criteria**:
    - Test runs against a local dev server with a mocked or test backend.
    - Covers: navigating to `/` shows the onboarding page.
    - Covers: entering a project name and submitting creates a project (API mocked) and shows the success state with an API key.
    - Covers: the install snippet tab for LangChain is visible and contains the substituted API key.
    - Covers: the copy button copies the snippet to clipboard (or asserts the button is present and clickable).

- [x] **4.8.2 — E2E: trace list and trace detail navigation**

    **Description**: Write a Playwright test that navigates the trace list, applies a filter, and opens a trace detail page.

    **Acceptance Criteria**:
    - Test runs against a local dev server with a mocked or test backend seeded with fixture traces.
    - Covers: trace list page loads and displays at least one trace row.
    - Covers: clicking "Errors only" filter updates the table to show only error traces.
    - Covers: clicking a trace row navigates to the trace detail page.
    - Covers: trace detail page shows the span timeline with at least one span.
    - Covers: clicking a span expands it to show input and output details.

- [x] **4.8.3 — E2E: replay panel flow**

    **Description**: Write a Playwright test that opens the replay panel on an `llm_call` span, edits the system prompt, submits a replay, and verifies the diff view renders.

    **Acceptance Criteria**:
    - Test runs against a local dev server with a mocked backend.
    - Covers: clicking "Replay" on an `llm_call` span opens the replay panel.
    - Covers: system prompt textarea is pre-populated with the original prompt.
    - Covers: editing the system prompt and submitting a replay call (mocked API response) renders the diff view.
    - Covers: diff view contains both "original" and "replayed" output sections.

---

## Module 5 — Polish & Production Readiness

### Sprint 5.1 — Frontend Polish

- [x] **5.1.1 — Empty states across all pages**

    **Description**: Ensure every page and data-heavy component has a well-designed empty state so the app never shows a broken or blank screen when there is no data.

    **Acceptance Criteria**:
    - Trace list: empty state with icon, message ("No traces yet"), and link to the setup/onboarding snippet.
    - Trace detail: empty state if a trace has no spans.
    - All empty states use the design system's surface colors and typography.
    - Empty states include a helpful action or next step — not just text.

- [x] **5.1.2 — Loading states across all pages**

    **Description**: Add consistent loading feedback for all async data fetches across the app.

    **Acceptance Criteria**:
    - Trace list: skeleton loading rows or a spinner while `GET /v1/traces` is in flight.
    - Trace detail: spinner or skeleton while `GET /v1/traces/{id}` is in flight.
    - Replay panel: button shows loading/spinner state while `POST /v1/replay` is in flight; button is disabled during this time.
    - No layout shift when data loads in.

- [x] **5.1.3 — Error states and API error handling**

    **Description**: Add error handling so the app degrades gracefully when API calls fail (network error, 401, 404, 500).

    **Acceptance Criteria**:
    - Failed `GET /v1/traces` shows an error banner with a retry button.
    - Failed `GET /v1/traces/{id}` shows an error message (404 specifically shows "Trace not found").
    - 401 on any request redirects to or shows a message on the login/API key page.
    - Replay errors (e.g. bad provider key) show a clear inline error in the replay panel — not a generic crash.
    - No unhandled promise rejections or console errors in the happy path.

### Sprint 5.2 — Deployment

- [x] **5.2.1 — Backend deployment (Fly.io or Railway)** (Documented for Linode VPS)

    **Description**: Deploy the FastAPI backend to a container host or VPS. Connect it to the production Postgres database.

    **Acceptance Criteria**:
    - Backend is reachable at a stable public URL.
    - Environment variables (database URL, any secrets) are configured via the host's secret management — not hardcoded.
    - All six API endpoints return correct responses on the live URL.
    - Health check endpoint (`GET /healthz` or equivalent) returns HTTP 200.
    - HTTPS enforced.

- [x] **5.2.2 — Database deployment (Supabase or managed Postgres)** (Documented PostgreSQL on VPS)

    **Description**: Provision and configure the production Postgres database. Apply all migrations. Ensure the backend can reach it.

    **Acceptance Criteria**:
    - Production Postgres instance is provisioned and accessible only from the backend host.
    - All migrations applied; all tables and indexes exist.
    - Database connection pool configured for expected v1 load.
    - Backups enabled.

- [x] **5.2.3 — Frontend deployment (Vercel or Netlify)** (Documented and updated Vite production build)

    **Description**: Deploy the frontend as a static build. Configure the API base URL to point to the production backend.

    **Acceptance Criteria**:
    - Frontend is reachable at a stable public URL.
    - API base URL is configured via a build-time environment variable (not hardcoded).
    - All pages load correctly on the production URL.
    - HTTPS enforced.
    - No CORS errors between frontend origin and backend.

---

## Module 6 — Validation Gate

### Sprint 6.1 — Early User Validation

- [ ] **6.1.1 — Share build with early users and gather replay feedback**

    **Description**: Before investing in the JS/TS SDK, OTel bridge polish, or team features, validate that real developers find the replay workflow useful. Per the spec, reach out in LangChain Discord, r/LangChain, and Indie Hackers.

    **Acceptance Criteria**:
    - At least 3 external developers (not the builder) have sent a real failing trace to the system.
    - At least 1 developer has confirmed that the replay workflow helped them identify or fix a real bug.
    - Feedback is documented (written notes, DM screenshot, or short form response).
    - Any critical UX blockers discovered are added as new work items in this backlog.
    - A clear go/no-go decision is made for v2 features based on this evidence.

---

## Module 7 — Full System Tests

> These tests treat the entire product as a black box. They spin up the real backend natively (running as a local process in the background) connected to a dedicated test database (such as a local SQLite file or native PostgreSQL), and drive flows from the SDK or HTTP client all the way through to the database. They are the final quality gate before any release.

### Sprint 7.1 — System Test Infrastructure

- [ ] **7.1.1 — Native system test runner and environment**

    **Description**: Create a system test runner script or Makefile target (`make system-test`) that starts the FastAPI backend natively as a background process (pointing to a dedicated test database, e.g., an isolated SQLite database file or a local native Postgres instance), waits for it to be healthy, runs the system test suite, and reliably tears down the background server on completion.

    **Acceptance Criteria**:
    - A `make system-test` (or equivalent script) starts the FastAPI backend using `uvicorn` in the background with `DATABASE_URL` set to an isolated test database (e.g., `sqlite+aiosqlite:///./statica_trace_system_test.db`).
    - The test runner automatically waits for the backend port (e.g. 8000) to be open/healthy before launching tests.
    - The test runner applies database tables and indexes to the test database prior to running tests.
    - Running `make system-test` runs the entire system test suite using `pytest tests/system`.
    - The runner ensures the background uvicorn process is terminated (teardown) when tests finish, even if tests fail (e.g., using a bash `trap` or Python script wrapper).
    - CI pipeline runs this command natively; failures block merge.
    - Test database is isolated from dev and production databases.

- [ ] **7.1.2 — System test shared fixtures and helpers**

    **Description**: Create the shared pytest fixtures and helper utilities used across all system tests. Includes a client that speaks to the live test server and seed helpers that create projects, ingest traces, and clean up after each test.

    **Acceptance Criteria**:
    - `conftest.py` in the system test directory defines:
        - `test_server_url` fixture returning the base URL of the running test backend.
        - `api_client(api_key)` fixture: an `httpx.Client` with the `Authorization` header pre-set.
        - `create_project()` helper: calls `POST /v1/projects`, returns `(project_id, api_key)`.
        - `ingest_trace(api_key, trace)` helper: calls `POST /v1/ingest` with a given trace.
        - Database teardown: each test cleans up its own project/traces via a fixture scope (session or function level).
    - All helpers pass `ruff` and `black`.

### Sprint 7.2 — System Test Suites

- [ ] **7.2.1 — System test: project creation and auth flow**

    **Description**: End-to-end system test covering project creation and API key authentication across the live backend and real database.

    **Acceptance Criteria**:
    - Tests live in `tests/system/test_auth_flow.py`.
    - Covers: `POST /v1/projects` creates a project and returns a valid API key stored in the DB.
    - Covers: `GET /v1/projects/me` with the returned key returns the correct project name.
    - Covers: `GET /v1/projects/me` with an invalid key returns 401.
    - Covers: two separate projects created in the same test cannot access each other's data.
    - Tests run against the live natively running test environment (real database, real FastAPI).

- [ ] **7.2.2 — System test: SDK → ingest → retrieval pipeline**

    **Description**: End-to-end system test that uses the real `agentreplay` Python SDK (with the real `openai` library and mocked HTTP to the OpenAI API) to capture a trace, send it to the live backend, and confirm it appears correctly via the retrieval endpoints.

    **Acceptance Criteria**:
    - Tests live in `tests/system/test_ingest_pipeline.py`.
    - Uses the real `agentreplay` SDK (not a direct HTTP call).
    - OpenAI API outbound calls are mocked at the transport level.
    - Covers: wrapping an `openai.OpenAI()` client and making a `chat.completions.create()` call causes a trace to appear in `GET /v1/traces`.
    - Covers: the trace detail (`GET /v1/traces/{id}`) contains the exact messages sent to the mocked OpenAI API.
    - Covers: `source` field is `openai`.
    - Covers: a LangChain chain run with `AgentReplayCallbackHandler` also produces a correctly structured trace with `source: langchain`.
    - Covers: status is `error` when the SDK captures an exception from the LLM call.

- [ ] **7.2.3 — System test: replay engine end-to-end**

    **Description**: End-to-end system test for the replay flow. A trace is ingested into the live backend, then a replay is requested via `POST /v1/replay`. The provider API (OpenAI/Anthropic) is mocked at the test environment level.

    **Acceptance Criteria**:
    - Tests live in `tests/system/test_replay_flow.py`.
    - Covers: ingest a trace with an `llm_call` span → call `POST /v1/replay` with `edited_input` (modified system prompt) → response contains `original_output` and `replayed_output`.
    - Covers: the outbound call in the replay engine uses the edited messages (verified via mock assertion on the intercepted request body).
    - Covers: the replay record is persisted in the `replays` table.
    - Covers: replaying a `tool_call` span returns HTTP 400.
    - Covers: missing provider API key header returns a clear error (not a 500).
    - Provider API is mocked — no real OpenAI/Anthropic traffic.

- [ ] **7.2.4 — System test: multi-project data isolation**

    **Description**: End-to-end system test that verifies strict data isolation between projects — one project can never read or replay another project's traces.

    **Acceptance Criteria**:
    - Tests live in `tests/system/test_isolation.py`.
    - Creates two separate projects with separate API keys.
    - Ingests one trace per project.
    - Covers: Project A's `GET /v1/traces` does not return Project B's trace.
    - Covers: Project A's `GET /v1/traces/{id}` with Project B's trace ID returns 404.
    - Covers: Project A's `POST /v1/replay` referencing Project B's `trace_id` returns 404.
    - All assertions use the live backend and real database.

- [ ] **7.2.5 — System test: OTel bridge pipeline**

    **Description**: End-to-end system test that uses the `AgentReplayOTelExporter` with the real `opentelemetry-sdk` to emit spans and confirms they appear correctly in the live backend.

    **Acceptance Criteria**:
    - Tests live in `tests/system/test_otel_pipeline.py`.
    - Uses real `opentelemetry-sdk` — configure a `TracerProvider` with `AgentReplayOTelExporter` pointing to the test backend.
    - Emit a span with GenAI semantic convention attributes.
    - Covers: the trace appears in `GET /v1/traces` with `source: otel`.
    - Covers: the span's messages and model are correctly mapped from OTel attributes.
    - Covers: span timing is correctly translated.
    - No outbound calls to any real AI provider.

---

## Module 8 — v2 Features (Post-Validation Only)

> ⚠️ **Do not build these until Module 6 validation is complete and confirms demand.**

### Sprint 8.1 — JS/TS SDK

- [ ] **8.1.1 — JS/TS package: OpenAI and Anthropic wrappers**

    **Description**: Port the Python OpenAI and Anthropic wrappers to TypeScript. Target Vercel AI SDK users and raw OpenAI/Anthropic JS client users.

    **Acceptance Criteria**:
    - TypeScript package published to NPM.
    - `wrap(new OpenAI())` and `wrap(new Anthropic())` work identically to their Python counterparts.
    - Full traces appear in the database from a Node.js script using the JS wrappers.
    - README covers the JS/TS setup path.

- [ ] **8.1.2 — JS/TS SDK unit tests (with real SDKs, mocked HTTP)**

    **Description**: Write Vitest unit tests for the JS/TS wrappers following the same philosophy as the Python SDK tests — use real library code, mock HTTP at the transport level.

    **Acceptance Criteria**:
    - Tests use real `openai` and `@anthropic-ai/sdk` npm packages.
    - HTTP intercepted with `msw` or `nock`.
    - Covers same cases as Python SDK tests (3.4.3 and 3.4.4) ported to TypeScript.
    - `npm run test` runs and passes.

### Sprint 8.2 — User Accounts & Team Access

- [ ] **8.2.1 — Proper user accounts (email/magic link auth)**

    **Description**: Add real user account management so multiple people can share a project. Add email/magic link authentication.

    **Acceptance Criteria**:
    - Users can sign up and log in via email (magic link or password).
    - Multiple users can belong to a project.
    - API keys remain associated with projects, not individual users.
    - Session management (JWT or session cookie) replaces raw API key auth for frontend calls.

### Sprint 8.3 — Persisted Provider Keys

- [ ] **8.3.1 — Encrypted provider API key storage per project**

    **Description**: Allow users to store their OpenAI/Anthropic API keys in the app so they don't have to paste them per replay request.

    **Acceptance Criteria**:
    - Provider API keys are stored encrypted at rest (AES-256 or equivalent).
    - Key is never returned in plaintext via any API response.
    - Replay endpoint uses the stored key if no per-request key is provided.
    - Settings page UI allows add/update/delete of provider keys per project.

---

_Build order: tooling setup (M0) → schema + schema tests (M1) → backend + backend tests (M2) → SDK + SDK tests (M3) → frontend + frontend tests (M4) → polish (M5) → deploy (M5.2) → system tests pass (M7) → validate with users (M6) → v2 (M8)._
