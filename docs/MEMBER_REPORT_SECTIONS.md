# SHAPE — Individual Member Report Sections
**Group 3 | ITAI2376-14562**  
For inclusion in `FN_Report_MichaelRivas_Group3_ITAI2376_14562.pdf`

Each member must be represented in three areas per assignment rubric:
1. Design contribution
2. Coding contribution  
3. Reflection

---

## Cherluk Sumdin

### Design Contribution
Cherluk was responsible for the reinforcement learning feedback architecture. She designed the reward mechanism — the 1–5 star rating system that feeds a rolling average window into prompt policy hints. She also defined the minimum threshold (5 records) before hints activate, and the three-tier policy response (poor / average / good) that adjusts agent behavior. This design decision ensured the RL loop was lightweight enough to run on the Pi without any external RL infrastructure.

### Coding Contribution
Cherluk authored `shape/feedback.py` — the `FeedbackMemory` class that:
- Persists feedback records to a JSONL file so learning survives session restarts
- Maintains a 20-turn rolling deque in memory
- Computes rolling average scores and maps them to policy hint strings
- Exposes a `summary()` method used by the CLI `status` command

She also ran and verified Notebook 1 (`01_SHAPE_Intro_Overview.ipynb`), confirming the agent initializes correctly and the first ReAct demo runs end-to-end.

### Reflection
Working on the RL feedback module taught me that reinforcement learning doesn't have to mean training neural networks. By treating user ratings as a reward signal and injecting policy hints into the prompt, we achieved real behavioral improvement with simple Python. The hardest part was deciding when the hint should activate — too early and it produces noise, too late and it misses correction opportunities. I settled on 5 records as a reasonable threshold after testing with simulated rating sequences.

---

## Olubukola Kukoyi

### Design Contribution
Olu led the tool integration design — deciding which four tools the agent would have access to and how each one interfaces with LangChain's tool-calling API. She defined the sandboxing constraints for the code executor (10-second timeout, isolated workspace directory), the pyflakes integration for the linter, the workspace-scoped file manager, and the FAISS-based offline document search. She also authored the cost comparison analysis that became a core slide in the demo video.

### Coding Contribution
Olu authored all four tool modules in `shape/tools/`:
- `code_executor.py` — sandboxed Python subprocess runner with timeout and workspace isolation
- `linter.py` — pyflakes static analysis wrapper returning structured results
- `file_manager.py` — read/write operations scoped to the `workspace/` directory
- `doc_search.py` — offline FAISS semantic search over local markdown documentation

She also ran and verified Notebook 2 (`02_Why_We_Built_SHAPE.ipynb`), confirming the cost chart generates correctly and hardware specs reflect the Pi 5 configuration.

### Reflection
Building the tool integration showed me how much of an agent's value comes from its tools rather than the LLM itself. CodeLlama 7B on its own produces reasonable code — but it also hallucinates and misses bugs. The moment we added the linter as a mandatory pre-execution step, the self-healing loop clicked into place. The agent stopped trusting its own output and started verifying it. That shift — from generation to generation-plus-verification — is what makes SHAPE useful rather than just impressive.

---

## Taki Eddine Boubekri

### Design Contribution
Taki designed the safety architecture and the three-tier hardware system. For safety, he identified the two categories of threat — harmful requests (destructive shell commands, malware generation, injection attacks) and out-of-scope requests (medical/legal advice, creative writing) — and designed the InputGuard regex pattern library to handle both. For hardware, he designed the UART protocol between the Pico 2 and Zero 2 W (CSV telemetry format, JSON command format) and the GPIO wiring diagram for the sensor node.

### Coding Contribution
Taki authored `shape/safety.py` — the `InputGuard` class with 8 blocked security patterns, 3 out-of-scope patterns, and an 8,000-character input length cap. He also authored the full Pico 2 firmware (`hardware/pico2/`) in MicroPython: `main.py`, `sensors.py`, `keys.py`, `st7789.py`, and `boot.py`. He ran and verified Notebook 3 (`03_Fieldwork_Use_Case.ipynb`), confirming the sensor simulation, self-healing demo, safety block, and RL feedback all produce correct output.

### Reflection
Writing the safety module forced me to think adversarially — not just "what does the agent do?" but "what could someone make it do?" The regex pattern library is not perfect; a determined user could probably find edge cases. But for a classroom coding agent, it covers the realistic threat surface. The more interesting challenge was the out-of-scope filtering — deciding where "coding help" ends and "general assistant" begins. We drew a clear line: if it's not about writing, debugging, or understanding code, SHAPE politely refuses and says why.

---

## Michael Rivas

### Design Contribution
Michael led the overall system architecture and integration. He designed the three-tier hardware topology (Pico 2 → Zero 2 W → Pi 5), the ReAct agent loop using LangGraph's `create_react_agent`, the sliding-window conversation memory system, and the HTTP API that the Zero 2 W uses to query the Pi 5 agent. He also defined the 8-step reasoning cycle documented in the `core/` tutoring engine and coordinated the handoff protocol between team members.

### Coding Contribution
Michael authored:
- `shape/agent.py` — the `SHAPEAgent` class wiring LangGraph ReAct + Ollama + tools + feedback
- `main.py` — the CLI entry point with REPL loop, feedback prompting, and status command
- `hardware/pi5/api_server.py` — HTTP API exposing the SHAPE agent to the Zero 2 W over local Wi-Fi
- `hardware/zero2w/main_zero2w.py` — the field terminal state machine on the Zero 2 W
- `hardware/zero2w/serial_bridge.py` — UART bridge between Pico 2 and Pi 5
- `demo/make_video.py` and `demo/render_slides.py` — the full slide-based demo video generator
- `core/orchestrator.py` — the OpenAI-based tutoring engine used in team notebooks

He ran and verified Notebook 4 (`04_Code_Walkthrough_Pitch.ipynb`) and compiled the final report.

### Reflection
Leading the integration on a multi-tier hardware project taught me that the hardest problems are not the AI ones — they are the plumbing ones. Getting the Pico 2 to reliably send CSV over UART, the Zero 2 W to relay it over Wi-Fi, and the Pi 5 to process it through a full ReAct loop — all within acceptable latency for a fieldwork scenario — required careful attention to failure modes at every boundary. The most important design decision we made was giving the Zero 2 W a response cache: when the Pi 5 is unreachable, the terminal falls back to the last known answer rather than failing silently. That single decision is what makes the system usable in genuinely degraded network conditions.
