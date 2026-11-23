# SHAPE Demo Video — Build Guide

**Group 3 | ITAI2376-14562**  
Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas

---

## What's in this folder

| File | Purpose |
|---|---|
| `narration_script.txt` | Full narration script with per-clip timing markers |
| `generate_voiceover.py` | Converts script → per-clip `.wav` files (gTTS or pyttsx3) |
| `render_demo.py` | Blender VSE automation — assembles clips + audio → final MP4 |
| `assets/` | Place all source clips, stills, and music here before rendering |
| `output/` | Rendered MP4 appears here after blender runs |

---

## End-to-End Workflow

### Step 1 — Record your screen clips (4 clips)

Run each notebook and record your screen (OBS, QuickTime, or Kazam on Pi).

| Notebook | Output filename |
|---|---|
| `01_SHAPE_Intro_Overview.ipynb` | `screen_capture_nb1.mp4` |
| `02_Why_We_Built_SHAPE.ipynb` | `screen_capture_nb2.mp4` |
| `03_Fieldwork_Use_Case.ipynb` | `screen_capture_nb3.mp4` |
| `04_Code_Walkthrough_Pitch.ipynb` | `screen_capture_nb4.mp4` |

Place all `.mp4` files in `demo/assets/`.

### Step 2 — Prepare still images

| File | What it is |
|---|---|
| `title_card.png` | Opening credits (make in Canva, PowerPoint, or GIMP) |
| `pi_photo.jpg` | Photo of a Raspberry Pi (or royalty-free stock) |
| `montage.mp4` | 40-second pitch montage (or swap for a still image) |
| `end_card.png` | Closing credits still |
| `bg_music.mp3` | Ambient background music (royalty-free, e.g. from Pixabay) |

### Step 3 — Generate voiceover audio

```bash
# Online (gTTS — better voice quality):
pip install gtts pydub
python demo/generate_voiceover.py

# Fully offline (pyttsx3 — robotic but no internet needed):
pip install pyttsx3 pydub
python demo/generate_voiceover.py --offline
```

This creates `voice_CLIP_*.wav` files in `demo/assets/` — one per clip,
pre-padded to the exact clip duration so audio and video stay in sync.

### Step 4 — Render with Blender

```bash
# Install Blender (free): https://www.blender.org/download/
# Then render headless:
blender --background --python demo/render_demo.py
```

The final video is saved to:
```
demo/output/FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4
```

---

## Demo Video Structure

| Clip | Timestamps | Content |
|---|---|---|
| Opening Credits | 0:00 – 0:12 | Group member names, fade to SHAPE logo |
| Act 1: Intro | 0:12 – 1:00 | What is SHAPE, architecture overview |
| Act 2: Why | 1:00 – 1:55 | The problem, our decision, cost chart |
| Act 3: Device | 1:55 – 2:30 | Raspberry Pi hardware, fieldwork scenario |
| Act 4: Live Demo | 2:30 – 3:30 | Notebooks 3+4 running: sensor task, self-healing, RL |
| Act 5: Code | 3:30 – 4:10 | Brief code walkthrough, tools, safety, RL |
| Act 6: Pitch | 4:10 – 4:50 | The pitch — who needs SHAPE and why |
| Closing Credits | 4:50 – 5:00 | Fade out |

---

## Troubleshooting

**"Asset not found" warning in Blender**  
→ The script replaces missing clips with a dark blue placeholder. Add the asset to `demo/assets/` and re-run.

**Voice is too fast / too slow**  
→ Edit `generate_voiceover.py`: change `engine.setProperty("rate", 160)` for pyttsx3,  
  or manually re-record the clip at a comfortable pace and drop it in `demo/assets/`.

**Video and voice are out of sync**  
→ The `fit_to_duration()` function in `generate_voiceover.py` pads/trims each WAV to  
  match its clip window exactly. If sync is still off, adjust `CLIP_TIMING` in both  
  `generate_voiceover.py` and `render_demo.py` to match your actual recording lengths.

**Blender version issues**  
→ Script targets Blender 3.6+. Run `blender --version` to check.
