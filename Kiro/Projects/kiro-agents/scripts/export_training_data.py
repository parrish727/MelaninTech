#!/usr/bin/env python3
"""
Training Data Export — extracts approved traces from darius_traces for fine-tuning.

Exports pairs of (task, reasoning_chain, tool_calls, final_output) from traces
where the output was approved. This becomes the training dataset for the self-hosted
Darius model.

Formats:
  - JSONL (for fine-tuning with Hugging Face / Axolotl)
  - Conversation format (for chat-style fine-tuning)

Usage:
  python3 scripts/export_training_data.py --format jsonl --output training_data.jsonl
  python3 scripts/export_training_data.py --format conversation --output training_conv.jsonl
  python3 scripts/export_training_data.py --since 2026-07-01 --min-score 0.8
"""
import os
import sys
import json
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("training_export")

_DSN = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")


def get_conn():
    import psycopg2
    return psycopg2.connect(_DSN)


def export_traces(since: str = None, min_score: float = 0.7, limit: int = 10000) -> list[dict]:
    """
    Extract training-quality traces from darius_traces.

    Filters:
      - Only completed tasks (phase = 'complete')
      - Only approved outputs (status = 'success' or 'pass')
      - Optional: minimum evaluation score
      - Optional: since date

    Returns list of training examples.
    """
    conn = get_conn()
    from psycopg2.extras import RealDictCursor

    query = """
        SELECT t.task_id, t.session_id, t.phase, t.step_index,
               t.tool_name, t.tool_args, t.tool_result,
               t.evaluation_score, t.evaluation_feedback,
               t.model, t.tokens_in, t.tokens_out, t.latency_ms,
               t.status, t.created_at
        FROM darius_traces t
        WHERE t.status IN ('success', 'pass')
    """
    params = []

    if since:
        query += " AND t.created_at >= %s"
        params.append(since)

    if min_score:
        query += " AND (t.evaluation_score IS NULL OR t.evaluation_score >= %s)"
        params.append(min_score)

    query += " ORDER BY t.task_id, t.created_at LIMIT %s"
    params.append(limit)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

    conn.close()
    return rows


def group_by_task(rows: list[dict]) -> list[dict]:
    """Group trace rows into complete task chains."""
    tasks = {}
    for row in rows:
        task_id = row["task_id"]
        if task_id not in tasks:
            tasks[task_id] = {
                "task_id": task_id,
                "session_id": row["session_id"],
                "model": row["model"],
                "phases": [],
            }
        tasks[task_id]["phases"].append(row)

    # Filter to tasks that have at least a plan + complete phase
    complete_tasks = []
    for task_id, task in tasks.items():
        phases = [p["phase"] for p in task["phases"]]
        if "plan" in phases and "complete" in phases:
            complete_tasks.append(task)

    return complete_tasks


def format_jsonl(tasks: list[dict]) -> list[str]:
    """
    Format as JSONL training pairs.
    Each line: {"input": task_description, "reasoning": planning_output, "output": final_result}
    """
    lines = []
    for task in tasks:
        plan_phase = next((p for p in task["phases"] if p["phase"] == "plan"), None)
        complete_phase = next((p for p in task["phases"] if p["phase"] == "complete"), None)

        if not plan_phase or not complete_phase:
            continue

        # Extract task from plan args
        plan_args = plan_phase.get("tool_args")
        if isinstance(plan_args, str):
            try:
                plan_args = json.loads(plan_args)
            except Exception:
                plan_args = {}

        task_text = plan_args.get("task", "") if plan_args else ""
        plan_result = plan_phase.get("tool_result", "")
        final_result = complete_phase.get("tool_result", "")

        if not task_text:
            continue

        entry = {
            "input": task_text,
            "reasoning": plan_result[:5000],
            "output": final_result[:10000],
            "model": task.get("model", "unknown"),
            "evaluation_score": next(
                (p.get("evaluation_score") for p in task["phases"] if p.get("evaluation_score")), None
            ),
            "task_id": task["task_id"],
        }
        lines.append(json.dumps(entry))

    return lines


def format_conversation(tasks: list[dict]) -> list[str]:
    """
    Format as conversation-style training data (system/user/assistant turns).
    Compatible with Axolotl, LLaMA-Factory, etc.
    """
    lines = []
    for task in tasks:
        plan_phase = next((p for p in task["phases"] if p["phase"] == "plan"), None)
        complete_phase = next((p for p in task["phases"] if p["phase"] == "complete"), None)

        if not plan_phase or not complete_phase:
            continue

        plan_args = plan_phase.get("tool_args")
        if isinstance(plan_args, str):
            try:
                plan_args = json.loads(plan_args)
            except Exception:
                plan_args = {}

        task_text = plan_args.get("task", "") if plan_args else ""
        final_result = complete_phase.get("tool_result", "")

        if not task_text or not final_result:
            continue

        # Build tool call chain
        tool_calls = []
        for phase in task["phases"]:
            if phase.get("tool_name") and phase["phase"] == "execute":
                tool_calls.append({
                    "tool": phase["tool_name"],
                    "args": phase.get("tool_args", {}),
                    "result_preview": (phase.get("tool_result", ""))[:500],
                })

        conversation = {
            "system": "You are Darius, an AI orchestration agent. You plan tasks, use tools, and produce high-quality results.",
            "conversations": [
                {"role": "user", "content": task_text},
                {"role": "assistant", "content": final_result[:10000]},
            ],
            "metadata": {
                "task_id": task["task_id"],
                "model": task.get("model"),
                "tool_calls": tool_calls[:10],
            },
        }
        lines.append(json.dumps(conversation))

    return lines


def main():
    parser = argparse.ArgumentParser(description="Export Darius training data")
    parser.add_argument("--format", choices=["jsonl", "conversation"], default="jsonl")
    parser.add_argument("--output", default="training_data.jsonl")
    parser.add_argument("--since", help="Only export traces after this date (YYYY-MM-DD)")
    parser.add_argument("--min-score", type=float, default=0.7, help="Minimum evaluation score")
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()

    logger.info(f"Exporting training data (format={args.format}, min_score={args.min_score})")

    rows = export_traces(since=args.since, min_score=args.min_score, limit=args.limit)
    logger.info(f"Raw traces: {len(rows)}")

    tasks = group_by_task(rows)
    logger.info(f"Complete task chains: {len(tasks)}")

    if args.format == "jsonl":
        lines = format_jsonl(tasks)
    else:
        lines = format_conversation(tasks)

    with open(args.output, "w") as f:
        f.write("\n".join(lines))

    logger.info(f"Exported {len(lines)} training examples to {args.output}")
    logger.info(f"File size: {os.path.getsize(args.output) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
