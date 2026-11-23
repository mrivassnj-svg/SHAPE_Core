"""
SHAPE CLI — interactive terminal interface
Run with:  python main.py
           python main.py --config config.yaml

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from shape.agent import build_agent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s  %(name)s — %(message)s",
)

BANNER = r"""
 ____  _   _    _    ____  _____
/ ___|| | | |  / \  |  _ \| ____|
\___ \| |_| | / _ \ | |_) |  _|
 ___) |  _  |/ ___ \|  __/| |___
|____/|_| |_/_/   \_\_|   |_____|

Self-Healing Autonomous Programming Engine
Running offline on Raspberry Pi — Powered by Ollama + CodeLlama
Group 3 | ITAI2376-14562
Type 'help' for commands, 'quit' to exit.
"""

HELP_TEXT = """
Commands
--------
  help           Show this help message.
  status         Show agent feedback/RL statistics.
  reset          Clear conversation memory.
  quit / exit    Exit SHAPE.

Anything else is treated as a coding request.

After each response you will be asked to rate it 1–5.
Your ratings train the RL feedback loop to improve future responses.
"""


def load_config(path: str | None) -> dict:
    if path and Path(path).exists():
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    # Defaults — works out of the box on Pi with Ollama installed
    return {
        "model": "codellama",
        "ollama_url": "http://localhost:11434",
        "temperature": 0.2,
        "context_window": 4096,
        "memory_window": 6,
        "max_iterations": 8,
        "executor_timeout": 10,
        "feedback_path": "data/feedback.jsonl",
        "workspace_dir": "workspace",
        "doc_index_path": "data/doc_index",
        "docs_dir": "data/docs",
        "doc_top_k": 3,
        "verbose": False,
    }


def ask_feedback(agent, user_input: str, answer: str) -> None:
    """Prompt the user for a 1–5 rating and record it."""
    while True:
        raw = input("\n[Rate this response 1–5, or press Enter to skip] ").strip()
        if raw == "":
            return
        if raw.isdigit() and 1 <= int(raw) <= 5:
            agent.collect_feedback(user_input, answer, int(raw))
            print("[SHAPE] Thanks — feedback recorded.")
            return
        print("  Please enter a number between 1 and 5.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SHAPE — coding agent CLI")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--verbose", action="store_true", help="Show agent reasoning steps")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.verbose:
        config["verbose"] = True
        logging.getLogger().setLevel(logging.INFO)

    print(BANNER)
    print("Connecting to Ollama… ", end="", flush=True)
    try:
        agent = build_agent(config)
        print("OK\n")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] Could not start agent: {exc}")
        print("Make sure Ollama is running:  ollama serve")
        sys.exit(1)

    while True:
        try:
            user_input = input("SHAPE> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("quit", "exit"):
            print("Goodbye.")
            break

        elif lower == "help":
            print(HELP_TEXT)
            continue

        elif lower == "reset":
            agent.reset_session()
            print("[SHAPE] Session memory cleared.\n")
            continue

        elif lower == "status":
            stats = agent.feedback.summary()
            print(f"\n[SHAPE RL Status]")
            print(f"  Records in window : {stats['records']}")
            print(f"  Average score     : {stats['avg_score']}")
            print(f"  Policy hint       : {stats['policy']}\n")
            continue

        # --- coding request ---
        print("\n[SHAPE] Thinking…\n")
        answer = agent.run(user_input)
        print(f"\n{answer}\n")
        ask_feedback(agent, user_input, answer)
        print()


if __name__ == "__main__":
    main()
