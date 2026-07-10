# 🤖 AI Agent Integration & Instrumentation Guide

This guide details how different AI Agent frameworks and LLM SDKs integrate with **Statica Trace** to capture execution traces, and how the replay engine executes individual step overrides.

---

## 📖 Table of Contents
1. [🎯 Instrumentation Strategy](#-instrumentation-strategy)
2. [📊 Data Models & Trace Schema](#-data-models-&-trace-schema)
3. [🔌 Deep Support (Tier 1)](#-deep-support-tier-1)
4. [🌐 Broad Support via OpenTelemetry (Tier 2)](#-broad-support-via-opentelemetry-tier-2)
5. [🔄 Replay Mechanism & Engine](#-replay-mechanism-&-engine)

---

## 🎯 Instrumentation Strategy

Statica Trace implements a **two-tier capture strategy** designed to maximize framework compatibility with minimal custom adapter overhead:

```
[Agent Execution Lifecycle]
       │
       ├─► Tier 1: Custom SDK Interceptors (LangChain, OpenAI, Anthropic) ──► Complete Replay Payload
       │
       └─► Tier 2: OpenTelemetry GenAI Convention Spans (CrewAI, AutoGen) ──► Trace Ingestion Bridge
```

*   **Tier 1 (Deep Support)**: First-class SDK integrations that capture fully structured inputs (editable system messages, user prompts, parameters, tool schemas, and output tokens). This tier supports complete step-level editing and replay.
*   **Tier 2 (Broad Support)**: Collects spans generically via an OpenTelemetry (OTel) bridge utilizing GenAI semantic-convention schemas (e.g., via libraries like OpenLLMetry or Traceloop). This enables trace viewing out-of-the-box for CrewAI, LlamaIndex, AutoGen, Vercel AI SDK, and others.

---

## 📊 Data Models & Trace Schema

All client-side instrumentation must normalize execution data into the universal trace schema defined in [agentreplay/schema.py](file:///Users/angel/Documents/repo/agentreplay/schema.py).

### Trace Structure
A **Trace** represents a single complete run of an agent system (e.g., a multi-turn chat session or a graph execution). It consists of metadata and a flat list of Spans.

```json
{
  "trace_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "project_id": "3d508492-f08d-4f1a-b6ea-32c028c4ff2b",
  "source": "langchain",
  "started_at": "2026-07-10T11:45:00.000Z",
  "ended_at": "2026-07-10T11:45:04.200Z",
  "status": "success",
  "spans": [...]
}
```

### Spans
A **Span** represents a discrete unit of work within a trace. Spans are stored in a flat array, using `parent_span_id` to establish parent/child relationships that are rendered as a tree in the dashboard.

#### Span Types
Spans in Statica Trace support four primary types defined in [SpanType](file:///Users/angel/Documents/repo/agentreplay/schema.py):
1.  `llm_call`: A direct query to an LLM provider. **These are the only spans eligible for replay debugging.**
2.  `tool_call`: The execution of a local tool or function.
3.  `retrieval`: A database or vector lookup (provides source context for RAG).
4.  `agent_step`: A logical step inside an agent loop.

```json
{
  "span_id": "4a7b5d92-284f-4d36-8a71-f925b6826131",
  "parent_span_id": "0291e92d-e8cf-4822-ba74-d4b8e2172159",
  "type": "llm_call",
  "name": "chat_completion",
  "started_at": "2026-07-10T11:45:01.100Z",
  "ended_at": "2026-07-10T11:45:02.800Z",
  "input": {
    "model": "gpt-4o",
    "messages": [
      { "role": "system", "content": "You are a helpful assistant." },
      { "role": "user", "content": "Fetch the weather in San Francisco." }
    ],
    "params": { "temperature": 0.0, "max_tokens": 150 },
    "tools": [
      {
        "name": "get_weather",
        "schema": {
          "type": "object",
          "properties": {
            "location": { "type": "string" }
          }
        }
      }
    ]
  },
  "output": {
    "content": null,
    "tool_calls": [
      {
        "name": "get_weather",
        "arguments": { "location": "San Francisco, CA" }
      }
    ]
  },
  "error": null
}
```

---

## 🔌 Deep Support (Tier 1)

### 🦜 1. LangChain & LangGraph Callback Handler
The LangChain callback handler (`langchain.py`) implements LangChain's `BaseCallbackHandler`. It intercepts hook points (`on_llm_start`, `on_llm_end`, etc.) and correlates the events using LangChain's internal `run_id`.

**Usage:**
```python
from agentreplay.langchain import AgentReplayCallbackHandler
from langchain_openai import ChatOpenAI

# 1. Initialize callback handler
handler = AgentReplayCallbackHandler(api_key="your_statica_api_key")

# 2. Attach handler to run configs
llm = ChatOpenAI(model="gpt-4o")
chain = prompt | llm

chain.invoke(
    {"input": "Hello!"}, 
    config={"callbacks": [handler]}
)
```

### 🧠 2. Raw SDK Client Wrappers
For applications that call models directly, Statica Trace provides transparent client wrappers that intercept API calls to capture input parameters, prompts, and output structures.

#### OpenAI wrapper example:
```python
import openai
from agentreplay.openai_wrapper import wrap

# Wrap the client transparently
client = wrap(openai.OpenAI(api_key="your_openai_key"))

# Calls are intercepted and recorded, returning normal API response types
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

#### Anthropic wrapper example:
```python
import anthropic
from agentreplay.anthropic_wrapper import wrap

client = wrap(anthropic.Anthropic(api_key="your_anthropic_key"))

message = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

---

## 🌐 Broad Support via OpenTelemetry (Tier 2)

Statica Trace accepts standard OpenTelemetry protocol (OTLP) exports via the `AgentReplayOTelExporter`. When an agent framework (like CrewAI, LlamaIndex, or AutoGen) is instrumented with OTel GenAI conventions, spans are mapped to our schema and sent to the ingest endpoint.

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from agentreplay.otel_exporter import AgentReplayOTelExporter

# 1. Configure the exporter pointing to Statica Trace
exporter = AgentReplayOTelExporter(
    api_key="your_statica_api_key",
    endpoint="https://api.staticatrace.com/v1/ingest"
)

# 2. Add processor to TracerProvider
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
```

---

## 🔄 Replay Mechanism & Engine

When a developer clicks **"Replay"** in the frontend dashboard, a request is sent to the backend endpoint `/v1/replay` containing the modified parameters.

### Replay Execution Sequence
1.  **Request Handshake**: The frontend sends a request containing the trace ID, the target span ID, and the edited inputs (e.g. prompt, temperature, parameters), along with the developer's raw provider key in the header `X-Provider-Api-Key`.
2.  **Trace Lookup**: [backend/main.py](file:///Users/angel/Documents/repo/backend/main.py#L307) fetches the original trace from the database.
3.  **Span Isolation**: The engine extracts the target span from the trace payload and ensures that it is of type `llm_call`.
4.  **Provider Resolution**: [backend/replay_engine.py](file:///Users/angel/Documents/repo/backend/replay_engine.py#L52) parses the model string (e.g., `gpt-4o` vs `claude-3-5-sonnet`) or trace metadata to routing the call to OpenAI or Anthropic.
5.  **Parameter Merging**: The engine merges the original span's settings with the developer's overrides.
6.  **Outbound Invocation**: Reconstructed payloads are sent directly to the model provider (using `httpx.AsyncClient`).
7.  **Comparison**: The fresh API output is returned alongside the original outputs to display visual diffs on the frontend dashboard.
8.  **Audit Persistence**: The replay invocation parameters and output are saved in the `replays` table for historical audit.

> [!IMPORTANT]
> The `X-Provider-Api-Key` header is utilized solely for that synchronous HTTP call. The backend **never persists** the LLM provider key to any disk or database table, safeguarding API credentials.

---

## 🧹 Maintenance and Updates

> [!NOTE]
> The [README.md](file:///Users/angel/Documents/repo/README.md) and [agents.md](file:///Users/angel/Documents/repo/agents.md) files should update as the code changes. This just makes sure that the README and agents MD files remain updated at all times.

