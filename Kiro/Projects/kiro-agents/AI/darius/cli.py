"""
Darius CLI — interactive terminal entrypoint.
Usage:
  python -m AI.darius.cli                         # new session
  python -m AI.darius.cli --session <id>          # resume session
  python -m AI.darius.cli --task "..."            # one-shot
  python -m AI.darius.cli --replay <id>           # replay session from start
  python -m AI.darius.cli --replay <id> --from 2  # replay from turn 2
"""
import argparse
import sys
import uuid
import logging
import io
import contextlib

logging.basicConfig(level=logging.ERROR)
logging.getLogger("smolagents").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

from AI.darius.agent import run_task, replay_session
from AI.darius.memory import list_sessions

BANNER = """
╔══════════════════════════════════════════╗
║  D A R I U S — Melanin Technologies      ║
║  AI Coding Agent  v1.1                   ║
╚══════════════════════════════════════════╝
Type your task, 'exit' to quit, 'sessions' to list past sessions.
"""

_GREETINGS = {"hi", "hello", "hey", "yo", "sup", "hi darius", "hello darius", "hey darius"}


def _is_conversational(text: str) -> bool:
    return text.lower().strip().rstrip("!?.") in _GREETINGS


@contextlib.contextmanager
def _suppress_stdout():
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old


def main():
    parser = argparse.ArgumentParser(description="Darius AI Coding Agent")
    parser.add_argument("--session", help="Resume a session by ID")
    parser.add_argument("--task", help="Run a single task and exit")
    parser.add_argument("--replay", help="Replay a session by ID")
    parser.add_argument("--from", dest="from_turn", type=int, default=0, help="Replay from this turn number")
    args = parser.parse_args()

    # Replay mode
    if args.replay:
        print(f"Replaying session: {args.replay} from turn {args.from_turn}")
        results = replay_session(args.replay, from_turn=args.from_turn)
        for i, r in enumerate(results):
            print(f"\n--- Turn {args.from_turn + i + 1} ---\n{r}")
        return

    session_id = args.session or str(uuid.uuid4())[:8]

    if args.task:
        with _suppress_stdout():
            result = run_task(args.task, session_id=session_id)
        print(result)
        return

    print(BANNER)
    print(f"Session: {session_id}\n")

    while True:
        try:
            task = input("darius> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not task:
            continue
        if task.lower() == "exit":
            print("Goodbye.")
            break
        if task.lower() == "sessions":
            sessions = list_sessions()
            print("\n".join(sessions) if sessions else "No sessions found.")
            continue

        if _is_conversational(task):
            print("\nHey! I'm Darius, your AI coding agent by Melanin Technologies. What would you like to build or fix?\n")
            continue

        print()
        with _suppress_stdout():
            result = run_task(task, session_id=session_id)
        print(f"{result}\n")


if __name__ == "__main__":
    main()
