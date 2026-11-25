# SHAPE Notebook Handoff Status
**Group 3 | ITAI2376-14562**  
Due: Dec 6, 2026 at 11:59pm

---

## Chain of Custody

```
Michael (distributes) → Cherluk → Olu → Taki → Michael (compiles report)
```

---

## Completion Status

| Step | Member | Notebook | Cells Run | Pi5/8GB Fixed | Handoff Cell Added | Submitted to Next |
|---|---|---|---|---|---|---|
| 1 | **Cherluk Sumdin** | `01_SHAPE_Intro_Overview.ipynb` | [ ] | ✅ Done | ✅ Done | [ ] |
| 2 | **Olubukola Kukoyi** | `02_Why_We_Built_SHAPE.ipynb` | [ ] | ✅ Done | ✅ Done | [ ] |
| 3 | **Taki Eddine Boubekri** | `03_Fieldwork_Use_Case.ipynb` | [ ] | n/a | ✅ Done | [ ] |
| 4 | **Michael Rivas** | `04_Code_Walkthrough_Pitch.ipynb` | [ ] | n/a | ✅ Done | — |

---

## What Each Member Needs to Do

### Cherluk Sumdin — NB1
1. Open `notebooks/01_SHAPE_Intro_Overview.ipynb`
2. Make sure Ollama is running: `ollama serve`
3. Run all cells top to bottom — confirm:
   - Ollama model list prints
   - Agent loads (`✅ SHAPE agent ready.`)
   - Fibonacci function is generated
4. Update `HANDOFF_STATUS.md`: mark your row `Cells Run ✅` and `Submitted ✅`
5. Send completed `.ipynb` to Olu

### Olubukola Kukoyi — NB2
1. Receive NB1 from Cherluk
2. Open `notebooks/02_Why_We_Built_SHAPE.ipynb`
3. Run all cells — confirm:
   - Cost comparison bar chart generates and saves to `docs/cost_comparison.png`
   - Hardware specs table prints with Pi 5 / 8 GB / $80
4. Update `HANDOFF_STATUS.md`: mark your row complete
5. Send completed `.ipynb` to Taki

### Taki Eddine Boubekri — NB3
1. Receive NB2 from Olu
2. Open `notebooks/03_Fieldwork_Use_Case.ipynb`
3. Run all cells — confirm:
   - Sensor CSV generated (`workspace/sensor_data.csv`, 20 rows)
   - Task 1 (data analysis + CO2 alert) runs and prints output
   - Task 2 (self-healing bug fix) agent corrects the broken code
   - Safety demo blocks the harmful request
   - RL demo prints policy hint after 5+ ratings
4. Update `HANDOFF_STATUS.md`: mark your row complete
5. Send completed `.ipynb` to Michael

### Michael Rivas — NB4 (Final)
1. Receive all 3 completed notebooks from Taki
2. Open `notebooks/04_Code_Walkthrough_Pitch.ipynb`
3. Run all cells — confirm:
   - ReAct verbose trace prints for C→F converter demo
   - All 4 tools listed with descriptions
   - Safety tests: 3 blocked, 2 pass
   - RL progression: 10 iterations, policy hint evolves
4. Mark all 4 rows complete in this file
5. Compile final report PDF

---

## Individual Report Sections
See `docs/MEMBER_REPORT_SECTIONS.md` for each member's pre-drafted:
- Design contribution
- Coding contribution
- Reflection

---

## Deliverables Checklist

| Item | Filename | Status |
|---|---|---|
| GitHub repo | github.com/mrivassnj-svg/SHAPE_Core | ✅ Live |
| Demo video | `FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4` | ✅ In repo |
| Project report | `FN_Report_MichaelRivas_Group3_ITAI2376_14562.pdf` | ⏳ In progress |
| Canvas submission | Text entry with GitHub link | ⏳ Due Dec 6 |
