# SHAPE — Final Submission Status
**Group 3 | ITAI2376-14562**

---

## Deliverables

| File | Status | Location |
|---|---|---|
| Demo video | ✅ | `demo/output/FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4` |
| Project report | ✅ | `docs/FN_Report_MichaelRivas_Group3_ITAI2376_14562.pdf` |
| Notebook 1 | ✅ | `notebooks/01_SHAPE_Introduction.ipynb` |
| Notebook 2 | ✅ | `notebooks/02_SHAPE_ReAct_Engine.ipynb` |
| Notebook 3 | ✅ | `notebooks/03_SHAPE_Tools_Environment.ipynb` |
| Notebook 4 | ✅ | `notebooks/04_SHAPE_Evaluation_Demo.ipynb` |
| Interactive visualizer | ✅ | `notebooks/shape_react_visualizer.html` |
| Unit tests (32 passing) | ✅ | `tests/` |

---

## Notebook Chapter Map

| Notebook | Rubric coverage |
|---|---|
| 01 — Introduction & Architecture | Input processing, project option, 3-tier hardware, 10-step data flow |
| 02 — Agent & ReAct Engine | Memory, ReAct loop, output generation, 8-step cap |
| 03 — Tools & Environment | Two external tools, error handling, safety, sensor validation |
| 04 — Evaluation & Demo | RL before/after, reward trend, metrics, single-click full demo |

---

## Package Structure (shape/ v2.0.0)

```
shape/
├── agent.py        SHAPEAgent + build_agent()
├── parser.py       parse_llm_output()
├── memory.py       make_history(), trimmed_messages()
├── prompts.py      REACT_SYSTEM template
├── rewards.py      FeedbackMemory (RL loop)
├── safety.py       InputGuard
├── sensors.py      SensorReading, parse_csv_line()
└── tools/
    ├── code_executor.py
    ├── linter.py
    ├── file_manager.py
    └── doc_search.py
```

---

## Member Contributions

| Member | Primary modules | Notebooks verified |
|---|---|---|
| Michael Rivas | `shape/agent.py`, `main.py`, `hardware/pi5/api_server.py` | NB04 |
| Cherluk Sumdin | `shape/rewards.py` (RL feedback loop) | NB01 |
| Olubukola Kukoyi | `shape/tools/` (all 4 tools) | NB03 |
| Taki Eddine Boubekri | `shape/safety.py`, `hardware/pico2/` (firmware) | NB02 |
