# SHAPE — Individual Member Report Sections
**Group 3 | ITAI2376-14562**

Each member's contribution covers three areas per the assignment rubric:
design, coding, and reflection.

---

## Michael Rivas — Lead Developer / Architecture

### Design Contribution
Michael designed the overall three-tier hardware architecture (Pico 2 → Zero 2 W → Pi 5)
and the core ReAct agent loop. The key architectural decision was implementing a
prompt-based ReAct loop in pure Python rather than using LangGraph's `create_react_agent`,
because CodeLlama does not support Ollama's native tool-calling API (HTTP 400). This
required writing `shape/parser.py` — a custom `re.search` parser that extracts
Thought/Action/Final Answer from plain text completions and dispatches to tools manually.

### Coding Contribution
Michael authored:
- `shape/agent.py` — `SHAPEAgent`, `build_agent()`, `_build_llm()`, `_build_system_prompt()`
- `shape/parser.py` — `parse_llm_output()` (all 3 branches, 9 unit tests)
- `shape/memory.py` — `make_history()`, `trimmed_messages()`
- `shape/prompts.py` — `REACT_SYSTEM` template
- `shape/sensors.py` — `SensorReading`, `parse_csv_line()`, `validate_reading()`
- `main.py` — CLI entry point
- `hardware/pi5/api_server.py` — 6-endpoint HTTP API server with API key auth,
  auto-alert `/sensor` routing, and whisper.cpp `/transcribe` voice endpoint
- `notebooks/04_SHAPE_Evaluation_Demo.ipynb` — single-click full demo cell

### Reflection
The most technically challenging part was building a tool-dispatching agent without
any native tool-calling support from the LLM. Every other LangChain tutorial assumes
the model returns structured JSON tool calls. We had to teach the model to output
`Action: tool_name` / `Action Input: ...` via the system prompt, then parse that text
ourselves. When langchain-ollama upgraded and started passing tool schemas to Ollama
regardless (triggering HTTP 400), we had to rewrite `_setup_llm()` to pass a plain
message list with no tool bindings. The solution was cleaner than the original — but
finding it required reading LangChain's source code at 2am.

---

## Cherluk Sumdin — RL Feedback Module

### Design Contribution
Cherluk designed the reinforcement learning feedback architecture. The reward mechanism
uses a 1–5 star rating system that feeds a rolling average window into prompt policy hints.
She defined the minimum threshold (5 records before hints activate) and the three-tier
policy response (correction below 2.5, nudge 2.5–3.5, positive above 3.5) that adjusts
agent behavior between sessions. The design is lightweight enough to run on the Pi without
any external RL infrastructure — no model retraining, no optimizer, no GPU.

### Coding Contribution
Cherluk authored `shape/rewards.py` — the `FeedbackMemory` class:
- Persists feedback records to a JSONL file so learning survives Pi reboots
- Maintains a 20-turn rolling deque in memory
- Computes rolling average scores and maps them to policy hint strings
- Exposes `summary()` used by the CLI status command and Notebook 04

She ran and verified `notebooks/01_SHAPE_Introduction.ipynb`, confirming package
imports, the test suite (32 tests), and the sensor protocol demonstration.

### Reflection
Working on the RL feedback module taught me that reinforcement learning doesn't require
training neural networks. By treating user ratings as a reward signal and injecting policy
hints into the prompt, we achieved real behavioral improvement with simple Python. The
hardest decision was the activation threshold — too early and it produces noise, too late
and it misses correction opportunities. I settled on 5 records after testing with
simulated rating sequences in `notebooks/04_SHAPE_Evaluation_Demo.ipynb`.

---

## Olubukola Kukoyi — Tools Integration

### Design Contribution
Olu led tool integration — deciding which four tools the agent would have, and how each
interfaces with the ReAct loop. She defined the sandboxing constraints for the code
executor (10-second timeout, isolated workspace), the pyflakes integration for the linter,
the workspace-scoped file manager with path traversal protection, and the FAISS-based
offline document search with keyword fallback. She also designed the "lint before execute"
rule that appears in `shape/prompts.py:REACT_SYSTEM` — saving ~380 ms per ReAct step
by catching bugs at lint time (~45 ms) before the subprocess is spawned.

### Coding Contribution
Olu authored all four tool modules in `shape/tools/`:
- `code_executor.py` — sandboxed subprocess runner with timeout, output cap, stderr capture
- `linter.py` — pyflakes static analysis with structured error return
- `file_manager.py` — read/write/list scoped to `workspace/`, `_safe_path()` traversal block
- `doc_search.py` — FAISS semantic search with `all-MiniLM-L6-v2` + keyword fallback

She ran and verified `notebooks/02_SHAPE_ReAct_Engine.ipynb`, confirming the prompt
construction, parser branches, memory trimming, and full ReAct trace.

### Reflection
Building the tool integration showed me how much of an agent's value comes from its tools
rather than the LLM itself. The moment we added the linter as a mandatory pre-execution
step, the self-healing loop clicked. The agent stopped trusting its own output and started
verifying it. The path traversal protection in `file_manager.py` was a small but critical
detail — without it, the agent could theoretically be prompted to read sensitive files
outside the workspace. One `Path.resolve()` check prevents the whole class of attack.

---

## Taki Eddine Boubekri — Safety Module & Hardware

### Design Contribution
Taki designed the safety architecture and the full three-tier hardware system. For safety,
he identified two threat categories — harmful requests (destructive shell commands, malware,
injection attacks) and out-of-scope requests (medical/legal advice) — and designed the
`InputGuard` regex pattern library to handle both pre-LLM. For hardware, he designed the
UART protocol between the Pico 2 and Zero 2 W (CSV telemetry format, JSON command return
path) and the GPIO wiring for the sensor node (DHT22 on GP2, MQ-135 ADC on GP26).

### Coding Contribution
Taki authored:
- `shape/safety.py` — `InputGuard` with 8 blocked security patterns, 3 out-of-scope
  patterns, 8,000-char length cap, and runtime-extensible `extra_blocked_patterns`
- `hardware/pico2/main.py` — MicroPython firmware: 100 Hz event loop, 2-second sensor
  sampling, UART CSV transmit, JSON receive, 3-mode ST7789 display
- `hardware/pico2/sensors.py` — `SensorHub` class: DHT22 + MQ-135 ADC reads with
  consecutive-error tracking and health status
- `hardware/pico2/keys.py` — ABXY key handler with debounce
- `hardware/pico2/st7789.py` — ST7789 LCD driver for the Waveshare 1.3" HAT

He ran and verified `notebooks/03_SHAPE_Tools_Environment.ipynb`, confirming all tool
error paths, the safety block tests, and the sensor validation boundary cases.

### Reflection
Writing the safety module forced me to think adversarially. The regex pattern library is
not perfect — a determined user could find edge cases. But for a classroom coding agent,
it covers the realistic threat surface. The more interesting challenge was out-of-scope
filtering: deciding where "coding help" ends and "general assistant" begins. We drew a
clear line — if it's not about writing, debugging, or understanding code, SHAPE refuses
and explains why. The firmware work was the most satisfying: watching the Pico 2 LCD
update with live sensor readings and agent reward bars was the moment SHAPE stopped being
a software project and became a physical system.
