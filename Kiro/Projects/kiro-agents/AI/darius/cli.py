"""
Darius CLI — interactive terminal entrypoint.
Usage:
  python -m AI.darius.cli                         # new session (smart routing)
  python -m AI.darius.cli --session <id>          # resume session
  python -m AI.darius.cli --task "..."            # one-shot
  python -m AI.darius.cli --replay <id>           # replay session from start
  python -m AI.darius.cli --replay <id> --from 2  # replay from turn 2
  python -m AI.darius.cli --engine delta          # force engine (delta/swarm/legacy)
  python -m AI.darius.cli --improve               # run self-improvement cycle
"""
import argparse
import sys
import uuid
import logging
import io
import contextlib
import json

logging.basicConfig(level=logging.ERROR)
logging.getLogger("smolagents").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

from AI.darius.memory import list_sessions

BANNER = """
╔══════════════════════════════════════════╗
║  D A R I U S — Melanin Technologies      ║
║  AI Coding Agent  v3.0                   ║
║                                          ║
║  Engines: delta | swarm | auto | legacy  ║
╚══════════════════════════════════════════╝
Commands: 'exit', 'sessions', 'improve', 'engine <name>'
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


def _run_with_engine(task: str, session_id: str, engine: str) -> str:
    """Execute a task using the specified engine."""
    if engine == "legacy":
        from AI.darius.agent import run_task
        return run_task(task, session_id=session_id)

    elif engine == "delta":
        from AI.darius.swarm.executor import DeltaExecutor
        from AI.darius.context import build_context
        context = ""
        try:
            context = build_context(session_id, task) or ""
        except Exception:
            pass
        executor = DeltaExecutor(task_id=session_id)
        result = executor.run(task=task, context=context)
        usage = result.get("token_usage", {})
        header = f"[delta | {result.get('step_count', 0)} steps | {usage.get('input', 0)+usage.get('output', 0)} tokens | ${usage.get('cost', 0):.3f}]"
        return f"{header}\n\n{result.get('final_output', '')}"

    elif engine == "swarm":
        from AI.darius.swarm.swarm import AgentSwarm
        from AI.darius.context import build_context
        context = ""
        try:
            context = build_context(session_id, task) or ""
        except Exception:
            pass
        swarm = AgentSwarm(task_id=session_id)
        result = swarm.execute(task=task, context=context)
        usage = result.get("token_usage", {})
        agents = result.get("agents", [])
        agent_summary = ", ".join(f"{a.get('role','?')}" for a in agents)
        header = f"[swarm | {len(agents)} agents ({agent_summary}) | {usage.get('input', 0)+usage.get('output', 0)} tokens | ${usage.get('cost', 0):.3f}]"
        return f"{header}\n\n{result.get('final_output', '')}"

    elif engine == "auto":
        from AI.darius.swarm.selector import select_engine, classify_task
        selected = select_engine(task)
        classification = classify_task(task)
        print(f"  [auto] classified as '{classification}' → engine '{selected}'")
        return _run_with_engine(task, session_id, selected)

    else:
        return f"Unknown engine: {engine}. Options: auto, delta, swarm, legacy"


def _run_improve():
    """Run the self-improvement cycle."""
    from AI.darius.swarm.analyzer import analyze
    from AI.darius.swarm.refiner import SkillRefiner

    print("Running improvement cycle (14d analysis)...")
    insights = analyze(days=14)
    summary = insights.get("summary", {})
    print(f"\n  Executions: {summary.get('total_executions', 0)}")
    print(f"  Success rate: {summary.get('success_rate', 0)}%")
    print(f"  Avg latency: {summary.get('avg_latency_ms', 0)}ms")
    print(f"  Total tokens: {summary.get('total_tokens', 0):,}")

    refiner = SkillRefiner()
    proposals = refiner.refine(insights)
    print(f"\n  Proposals: {len(proposals)}")

    recs = insights.get("recommendations", [])
    if recs:
        print("\n  Recommendations:")
        for r in recs:
            print(f"    • {r}")

    if proposals:
        print(f"\n{refiner.format_proposals()}")


def main():
    parser = argparse.ArgumentParser(description="Darius AI Coding Agent v3")
    parser.add_argument("--session", help="Resume a session by ID")
    parser.add_argument("--task", help="Run a single task and exit")
    parser.add_argument("--replay", help="Replay a session by ID")
    parser.add_argument("--from", dest="from_turn", type=int, default=0, help="Replay from this turn number")
    parser.add_argument("--engine", choices=["auto", "delta", "swarm", "legacy"], default="auto", help="Execution engine (default: auto)")
    parser.add_argument("--improve", action="store_true", help="Run self-improvement cycle")
    args = parser.parse_args()

    # Improvement mode
    if args.improve:
        _run_improve()
        return

    # Replay mode
    if args.replay:
        from AI.darius.agent import replay_session
        print(f"Replaying session: {args.replay} from turn {args.from_turn}")
        results = replay_session(args.replay, from_turn=args.from_turn)
        for i, r in enumerate(results):
            print(f"\n--- Turn {args.from_turn + i + 1} ---\n{r}")
        return

    session_id = args.session or str(uuid.uuid4())[:8]
    engine = args.engine

    # One-shot mode
    if args.task:
        with _suppress_stdout():
            result = _run_with_engine(args.task, session_id, engine)
        print(result)
        return

    # Interactive mode
    print(BANNER)
    print(f"Session: {session_id} | Engine: {engine}\n")

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
            print("\n".join(sessions[-10:]) if sessions else "No sessions found.")
            continue
        if task.lower() == "improve":
            _run_improve()
            continue
        if task.lower().startswith("engine "):
            new_engine = task.split(" ", 1)[1].strip()
            if new_engine in ("auto", "delta", "swarm", "legacy"):
                engine = new_engine
                print(f"  Switched to engine: {engine}")
            else:
                print(f"  Unknown engine. Options: auto, delta, swarm, legacy")
            continue

        if _is_conversational(task):
            print("\nHey! I'm Darius v3 — your AI coding agent. Engines: delta (efficient), swarm (parallel), auto (smart routing). What would you like to build?\n")
            continue

        print()
        with _suppress_stdout():
            result = _run_with_engine(task, session_id, engine)
        print(f"{result}\n")


if __name__ == "__main__":
    main()
