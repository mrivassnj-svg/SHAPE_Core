# SHAPE — Self-Healing Autonomous Programming Engine

**Group 3 | ITAI2376-14562**

| Name | Role |
|---|---|
| Michael Rivas | Lead Developer / Architecture |
| Cherluk Sumdin | RL Feedback Module / Testing |
| Olubukola Kukoyi | Tools Integration / Documentation |
| Taki Eddine Boubekri | Safety Module / Raspberry Pi Setup |

---

## What is SHAPE?

SHAPE is an **offline AI coding agent** that runs entirely on a **Raspberry Pi 4**
(or any Linux machine). It uses:

- **LangChain** (ReAct agent pattern) for reasoning and tool orchestration
- **Ollama** running **CodeLlama 7B** locally — no internet, no API keys required
- **Four integrated tools**: code executor, linter, file manager, and doc search
- A **reinforcement learning feedback loop** that improves responses over time
  based on user ratings (1–5 stars)

---

## Architecture

```
User Input
    │
    ▼
┌─────────────┐
│  InputGuard │  ← Safety screening (blocked patterns, out-of-scope)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  ReAct Agent (LangChain + Ollama / CodeLlama 7B)     │
│                                                       │
│  Thought → Action → Observation → … → Final Answer   │
│                                                       │
│  Tools available:                                     │
│    • code_executor  (run Python in sandbox)           │
│    • linter         (pyflakes static analysis)        │
│    • file_manager   (read/write workspace files)      │
│    • doc_search     (offline FAISS doc index)         │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│   Output     │  ← Returned to CLI
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  FeedbackMemory  │  ← User rates 1–5 → rolling avg → policy hint
│  (RL loop)       │    next run() injects hint into prompt
└──────────────────┘
```

---

## Raspberry Pi Setup

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull codellama   # ~3.8 GB — downloads once
ollama serve            # starts on port 11434
```

### 2. Clone & install SHAPE

```bash
git clone https://github.com/mrivassnj-svg/SHAPE_Core.git
cd SHAPE_Core
pip install -r requirements.txt
```

### 3. (Optional) Build offline doc index

Place `.md` documentation files in `data/docs/`, then:

```bash
python -m shape.tools.doc_search --build
```

### 4. Run SHAPE

```bash
python main.py
# or with verbose reasoning:
python main.py --verbose
# or with custom config:
python main.py --config config.yaml
```

---

## Configuration (`config.yaml`)

| Key | Default | Description |
|---|---|---|
| `model` | `codellama` | Ollama model name |
| `ollama_url` | `http://localhost:11434` | Ollama API base URL |
| `temperature` | `0.2` | LLM temperature (lower = more deterministic) |
| `context_window` | `4096` | Token context window |
| `memory_window` | `6` | Conversation turns kept in memory |
| `max_iterations` | `8` | Max ReAct loop iterations |
| `executor_timeout` | `10` | Code execution timeout (seconds) |
| `feedback_path` | `data/feedback.jsonl` | RL feedback history file |
| `workspace_dir` | `workspace` | Sandboxed file workspace |
| `doc_index_path` | `data/doc_index` | FAISS index directory |
| `docs_dir` | `data/docs` | Source docs for index building |

---

## Project Structure

```
SHAPE_Core/
├── main.py                  # CLI entry point
├── config.yaml              # Runtime configuration
├── requirements.txt
├── setup.sh                 # Raspberry Pi one-shot setup script
├── shape/
│   ├── __init__.py
│   ├── agent.py             # Core ReAct agent
│   ├── feedback.py          # RL feedback loop
│   ├── safety.py            # Input guard / safety screening
│   └── tools/
│       ├── __init__.py
│       ├── code_executor.py # Sandboxed Python execution
│       ├── linter.py        # pyflakes static analysis
│       ├── file_manager.py  # Workspace file I/O
│       └── doc_search.py    # Offline FAISS doc search
├── data/
│   ├── docs/                # Place .md doc files here
│   ├── doc_index/           # Auto-generated FAISS index
│   └── feedback.jsonl       # RL feedback history
└── workspace/               # Agent's sandboxed file workspace
```

---

## Example Session

```
SHAPE>  Write a function that checks if a string is a palindrome and test it.

[SHAPE] Thinking…

Here is the function:

    def is_palindrome(s: str) -> bool:
        s = s.lower().replace(" ", "")
        return s == s[::-1]

    # Tests
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello")   == False
    assert is_palindrome("A man a plan a canal Panama") == True
    print("All tests passed.")

[Rate this response 1–5, or press Enter to skip] 5
[SHAPE] Thanks — feedback recorded.
```

---

## Deliverables

| File | Description |
|---|---|
| `FN_Report_MichaelRivas_Group3_ITAI2376_14562.pdf` | Project report |
| `FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4` | Demo video |
| `FN_Proposal_MichaelRivas_Group3_ITAI2376_14562.pdf` | Project proposal |

---

*SHAPE — built for ITAI2376, Group 3. Runs entirely offline on a Raspberry Pi.*
