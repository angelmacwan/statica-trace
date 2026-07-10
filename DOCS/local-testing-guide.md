# 🧭 Statica Trace: Local Running & Testing Guide

This guide describes how to deploy **Statica Trace** locally, run the backend and frontend components, and test trace ingestion and replays using the Python SDK and direct API calls.

---

## 🏗️ 1. Architecture Overview

When running locally, the ecosystem consists of three parts:
1. **Backend Service** (FastAPI + SQLite): Listens on `http://localhost:8000`. It ingests traces, stores them in `statica_trace_dev.db`, and exposes replay management.
2. **Frontend UI** (Vite + React): Listens on `http://localhost:5173`. It connects to the backend to display timelines, details, and side-by-side diff replays.
3. **Agent Application / Scripts**: Uses the `agentreplay` Python SDK to capture and upload traces to the backend.

---

## ⚙️ 2. Local Setup & Installation

Ensure you have **Python >= 3.11** and **Node.js >= 18** installed.

### Step A: Backend Setup
1. **Activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Install dependencies in development/editable mode**:
   ```bash
   make install
   ```
3. **Start the backend development server**:
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```
   *The Swagger API documentation will automatically load at `http://127.0.0.1:8000/docs`.*

### Step B: Frontend Setup
1. **Navigate to the frontend folder**:
   ```bash
   cd frontend
   ```
2. **Install NPM dependencies**:
   ```bash
   npm install
   ```
3. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   *The UI dashboard will launch at `http://localhost:5173/`.*

---

## 🧪 3. Zero-Configuration Testing (Fast Path)

To test the system immediately without setting up actual OpenAI or Anthropic API credentials, you can ingest a synthetic trace that contains realistic RAG contexts, tool calls, and LLM spans.

### Step 1: Register a Local Project
The backend requires trace submissions to be authenticated via a project-specific API key. Register a new local test project:
```bash
curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Local Playground"}'
```
**Example Response:**
```json
{
  "id": "d396cb9f-a6bd-42e2-90a1-82dc3d6b1abf",
  "name": "Local Playground",
  "api_key": "1n1VNbbB9bUQhvTz9xF9dwAY7joHMZah2vI_FWW9mU8",
  "created_at": "2026-07-10T12:33:51.547950"
}
```
Copy the `"api_key"` from the response.

### Step 2: Run the Ingestion Test Script
We have provided a pre-configured script: [scripts/send_test_trace.py](file:///Users/angel/Documents/repo/scripts/send_test_trace.py). Run it using your project's API key:
```bash
python scripts/send_test_trace.py YOUR_API_KEY
```
*Alternatively, you can set the environment variable and run without arguments:*
```bash
export AGENTREPLAY_API_KEY="YOUR_API_KEY"
python scripts/send_test_trace.py
```

### Step 3: Inspect on the Frontend Dashboard
1. Open `http://localhost:5173/` in your browser.
2. In the top-right header configuration (or project selector), paste your project's **API Key** (`YOUR_API_KEY`) to authorize the dashboard.
3. You should see the ingested trace in the list.
4. Click on the trace to view the **nested timeline tree** (Root Agent Step -> Retrieval -> LLM Call -> Tool Call) and inspect inputs, parameters, and outputs.

---

## 🧠 4. Live SDK Integration Testing

If you want to capture traces from real agent runs, configure the SDK wrappers by passing environment variables.

Set the local destination for trace uploads:
```bash
export AGENTREPLAY_API_KEY="YOUR_API_KEY"
export AGENTREPLAY_ENDPOINT="http://localhost:8000/v1/ingest"
```

### Option A: Raw OpenAI SDK Wrapper
Wrap your standard OpenAI client. All chat completion calls are transparently tracked and uploaded in the background:
```python
import openai
from agentreplay.openai_wrapper import wrap

# Create the client and wrap it
raw_client = openai.OpenAI(api_key="your-openai-api-key")
client = wrap(raw_client)

# Calls are intercepted and recorded, returning normal API response types
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a friendly agent."},
        {"role": "user", "content": "Tell me a joke."}
    ],
    temperature=0.7
)
print(response.choices[0].message.content)
```
*Wrapper module code: [agentreplay/openai_wrapper.py](file:///Users/angel/Documents/repo/agentreplay/openai_wrapper.py)*

### Option B: Raw Anthropic SDK Wrapper
Wrap the Anthropic client:
```python
import anthropic
from agentreplay.anthropic_wrapper import wrap

raw_client = anthropic.Anthropic(api_key="your-anthropic-api-key")
client = wrap(raw_client)

message = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello Claude!"}]
)
print(message.content[0].text)
```
*Wrapper module code: [agentreplay/anthropic_wrapper.py](file:///Users/angel/Documents/repo/agentreplay/anthropic_wrapper.py)*

### Option C: LangChain & LangGraph Callback Handler
For frameworks built on LangChain or LangGraph, pass our callback handler to the invoke configuration:
```python
from agentreplay.langchain import AgentReplayCallbackHandler
from langchain_openai import ChatOpenAI

# Initialize handler
handler = AgentReplayCallbackHandler()

# Attach callback handler to runs
llm = ChatOpenAI(model="gpt-4o")
chain = prompt | llm

chain.invoke(
    {"input": "Hello world!"},
    config={"callbacks": [handler]}
)
```
*Callback handler code: [agentreplay/langchain.py](file:///Users/angel/Documents/repo/agentreplay/langchain.py)*

---

## 🔄 5. Testing the Step-Level Replay Engine

One of Statica Trace's core features is the ability to edit an LLM call prompt or parameter and re-run just that single step against the model provider.

1. Locate an `llm_call` span in the trace detail view of the frontend dashboard.
2. Click the **Replay** tab on the side panel.
3. Modify the System Prompt, User message, Temperature, or other parameters.
4. Enter your **OpenAI / Anthropic Provider Key** in the API Key input field in the replay panel.
   > [!IMPORTANT]
   > Provider API keys are passed to the backend via the `X-Provider-Api-Key` header solely for this synchronous call and are **never persisted** to the database or saved to disk.
5. Click **Run Replay**.
6. View the side-by-side visual diff showing differences in token length, response text content, and tool arguments.

---

## 🏁 6. Full Verification Pipeline

You can run the entire local verification pipeline (linting, backend tests, frontend unit tests, and frontend playwright E2E tests) using:
```bash
make ci
```
*Or run individual checks:*
- **Backend format check**: `make lint`
- **Backend tests with coverage**: `make test`
- **Frontend unit tests**: `cd frontend && npm run test`
- **Frontend E2E Playwright tests**: `cd frontend && npm run test:e2e`

*See helper commands defined in the [Makefile](file:///Users/angel/Documents/repo/Makefile).*
