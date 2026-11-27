"""
shape_viz_bridge.py — Live Trace bridge between SHAPEAgent and the HTML visualizer.

Usage in NB01 (after the visualizer is displayed):

    from shape_viz_bridge import stream_to_viz
    stream_to_viz(agent, "Write a palindrome checker and test it.")

Each Thought / Action / Observation / Final Answer step is pushed into the
visualizer's Live Trace log via postMessage to the iframe, using IPython's
display system.

Group 3 — ITAI2376-14562
"""
from __future__ import annotations
import json, re, textwrap
from typing import Any


# ── IPython / Colab display helpers ──────────────────────────────────────────

def _push(event_type: str, label: str, text: str) -> None:
    """Inject one log entry into the visualizer via a <script> display call."""
    try:
        from IPython.display import display, Javascript
        payload = json.dumps({"type": event_type, "label": label, "text": text})
        js = f"""
(function() {{
  var frames = document.querySelectorAll('iframe');
  for (var i = 0; i < frames.length; i++) {{
    try {{
      frames[i].contentWindow.postMessage({payload}, '*');
    }} catch(e) {{}}
  }}
  // Also try direct call if visualizer is in same document (IFrame display)
  if (typeof window.addLog === 'function') {{
    var p = {payload};
    window.addLog(p.type, p.label, p.text);
  }}
}})();
"""
        display(Javascript(js))
    except Exception:
        pass  # graceful no-op outside IPython


def _push_stat(iters: int, tools: int, phase: str, status: str) -> None:
    try:
        from IPython.display import display, Javascript
        js = f"""
(function() {{
  function applyStats(w) {{
    if (!w) return;
    var s = w.document || w;
    ['statIter','statTools','statStep','statStatus'].forEach(function(id, i) {{
      var el = (s.getElementById || s.querySelector.bind(s))('#' + id);
      if (el) el = s.getElementById ? s.getElementById(id) : el;
      if (el) el.textContent = [{iters}, {tools}, {json.dumps(phase)}, {json.dumps(status)}][i];
    }});
  }}
  document.querySelectorAll('iframe').forEach(function(f) {{
    try {{ applyStats(f.contentWindow); }} catch(e) {{}}
  }});
}})();
"""
        display(Javascript(js))
    except Exception:
        pass


# ── postMessage listener injection ───────────────────────────────────────────

def _inject_listener() -> None:
    """
    Inject a window.addEventListener('message') handler into the visualizer
    so it can receive log entries pushed from the kernel.
    """
    try:
        from IPython.display import display, Javascript
        js = """
(function() {
  function setupListener(w) {
    if (!w || w.__shapeListening) return;
    w.__shapeListening = true;
    w.addEventListener('message', function(evt) {
      var d = evt.data;
      if (!d || !d.type || !d.label) return;
      if (typeof w.addLog === 'function') {
        w.addLog(d.type, d.label, d.text || '');
      }
      // update stats if present
      if (d.stats && typeof w.updateStats === 'function') {
        var s = d.stats;
        w.updateStats(s.iters, s.tools, s.phase, s.status);
      }
    });
  }
  document.querySelectorAll('iframe').forEach(function(f) {
    try { setupListener(f.contentWindow); } catch(e) {}
  });
  // also wire up the top window (IFrame display in local Jupyter)
  setupListener(window);
})();
"""
        display(Javascript(js))
    except Exception:
        pass


# ── Verbose output parser ─────────────────────────────────────────────────────

_THOUGHT_RE  = re.compile(r'^\[Step \d+\]', re.MULTILINE)
_ACTION_RE   = re.compile(r'Action\s*:\s*(\S+)', re.IGNORECASE)
_INPUT_RE    = re.compile(r'Action Input\s*:\s*(.+)', re.IGNORECASE | re.DOTALL)
_FINAL_RE    = re.compile(r'Final Answer\s*:\s*(.+)', re.IGNORECASE | re.DOTALL)
_OBS_RE      = re.compile(r'^Observation\s*:\s*(.+)', re.IGNORECASE | re.MULTILINE)


def _classify_step(text: str) -> list[dict]:
    """
    Turn one verbose step block into one or more log events for the visualizer.
    Returns a list of {type, label, text} dicts.
    """
    events = []
    text = text.strip()

    if not text:
        return events

    # Observation line (from HumanMessage("Observation: …"))
    obs_m = _OBS_RE.search(text)
    if obs_m and text.lstrip().startswith('Observation'):
        events.append({"type": "obs", "label": "Observation",
                       "text": obs_m.group(1).strip()[:300]})
        return events

    # LLM step block
    final_m  = _FINAL_RE.search(text)
    action_m = _ACTION_RE.search(text)

    # Thought line(s)
    thought_lines = []
    for line in text.splitlines():
        if line.strip().startswith('Thought:'):
            thought_lines.append(line.strip())
    if thought_lines:
        events.append({"type": "thought", "label": "Thought",
                       "text": ' '.join(thought_lines)[:200]})

    if final_m:
        answer = final_m.group(1).strip()[:300]
        events.append({"type": "final", "label": "Final Answer", "text": answer})
    elif action_m:
        tool = action_m.group(1).strip()
        inp_m = _INPUT_RE.search(text)
        inp   = inp_m.group(1).strip()[:120] if inp_m else ''
        events.append({"type": "action", "label": f"Action: {tool}",
                       "text": f"tool={tool}\ninput={inp}"})

    return events


# ── Main bridge function ──────────────────────────────────────────────────────

def stream_to_viz(agent: Any, query: str) -> str:
    """
    Run agent.run(query) with verbose=True and stream each step into the
    HTML visualizer via IPython postMessage.

    Returns the final answer string (same as agent.run()).
    """
    import io, sys

    _inject_listener()

    # Announce the query
    _push("live", "Query", query)
    _push("thought", "InputGuard", "Checking query…")

    # Temporarily capture stdout (verbose agent prints to stdout)
    old_verbose = agent.config.get("verbose", False)
    agent.config["verbose"] = True

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    answer = "[SHAPE] No response."
    iters = 0
    tool_calls = 0

    try:
        answer = agent.run(query)
    finally:
        sys.stdout = old_stdout
        agent.config["verbose"] = old_verbose

    raw_output = captured.getvalue()

    # Parse and push each step block
    # Verbose format: "\n[Step N]\n<text>\n"
    blocks = re.split(r'\n\[Step \d+\]\n', '\n' + raw_output)
    for block in blocks:
        if not block.strip():
            continue
        events = _classify_step(block)
        for ev in events:
            if ev["type"] == "action":
                tool_calls += 1
            if ev["type"] in ("thought", "action"):
                iters_disp = max(1, iters)
            _push(ev["type"], ev["label"], ev["text"])
        # count LLM forward passes
        if re.search(r'Action\s*:|Final Answer\s*:', block, re.IGNORECASE):
            iters += 1

    # Push final answer
    _push("final", "Final Answer", answer[:400])
    _push_stat(iters, tool_calls, "Done", "✓ Complete")

    # Print final answer to notebook cell output too
    print("\n" + "="*60)
    print("FINAL ANSWER")
    print("="*60)
    print(answer)

    return answer
