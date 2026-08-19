"""
Tests for Darius v2.0 — planning, evaluation, DAG execution, compressed context.

Run with: python -m pytest AI/darius/tests/test_darius_v2.py -v
Or standalone: python AI/darius/tests/test_darius_v2.py

Note: smolagents and litellm are only available inside the Docker container.
Tests mock these at the module level for local execution.
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# Set required env vars before importing modules
os.environ.setdefault("POSTGRES_DSN", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
os.environ.setdefault("MCP_URL", "http://localhost:9000")
os.environ.setdefault("DARIUS_MAX_EVAL_RETRIES", "3")
os.environ.setdefault("SEARXNG_URL", "http://localhost:8080")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Mock external packages that aren't in local venv (only in Docker)
_mock_smolagents = MagicMock()
_mock_smolagents.Tool = MagicMock
_mock_smolagents.ToolCallingAgent = MagicMock
_mock_smolagents.LiteLLMModel = MagicMock
sys.modules.setdefault("smolagents", _mock_smolagents)

_mock_litellm = MagicMock()
sys.modules.setdefault("litellm", _mock_litellm)

# Mock httpx if not available
try:
    import httpx
except ImportError:
    sys.modules["httpx"] = MagicMock()

# Mock psycopg2 if not available
try:
    import psycopg2
except ImportError:
    sys.modules["psycopg2"] = MagicMock()
    sys.modules["psycopg2.extras"] = MagicMock()
    sys.modules["psycopg2.extensions"] = MagicMock()

# Mock orchestrator modules (not in import path for unit tests)
sys.modules.setdefault("orchestrator", MagicMock())
sys.modules.setdefault("orchestrator.memory", MagicMock())
sys.modules.setdefault("orchestrator.template_engine", MagicMock())
sys.modules.setdefault("agents", MagicMock())
sys.modules.setdefault("agents.steering_loader", MagicMock())
sys.modules.setdefault("config", MagicMock())
sys.modules.setdefault("config.settings", MagicMock())


class TestPlanner(unittest.TestCase):
    """Tests for AI.darius.planner"""

    def test_simple_task_skips_planning(self):
        """Simple tasks should return single step without LLM call."""
        from AI.darius.planner import plan_task, _is_complex_task

        # Short task — should not be complex
        self.assertFalse(_is_complex_task("fix the login button"))

        # Plan should return single step without calling LLM
        with patch("AI.darius.planner.completion") as mock_llm:
            steps = plan_task("fix the login button")
            mock_llm.assert_not_called()

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["id"], "step_1")
        self.assertIn("agent", steps[0])
        self.assertEqual(steps[0]["depends_on"], [])

    def test_complex_task_triggers_planning(self):
        """Multi-domain tasks should trigger LLM planning."""
        from AI.darius.planner import _is_complex_task

        self.assertTrue(_is_complex_task(
            "Build a new dashboard page with React frontend and FastAPI backend endpoint"
        ))
        self.assertTrue(_is_complex_task(
            "Create the component and then deploy it to production"
        ))

    def test_plan_task_with_llm_response(self):
        """Planning should parse valid LLM JSON response."""
        from AI.darius.planner import plan_task

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"id": "step_1", "agent": "frontend", "task": "Build React page", "depends_on": []},
            {"id": "step_2", "agent": "backend", "task": "Create API endpoint", "depends_on": []},
            {"id": "step_3", "agent": "deploy", "task": "Deploy both", "depends_on": ["step_1", "step_2"]},
        ])
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        with patch("AI.darius.planner.completion", return_value=mock_response):
            with patch("AI.darius.memory.log_trace"):
                steps = plan_task(
                    "Build a React dashboard page and a FastAPI backend endpoint then deploy",
                    "melanin-tech-website"
                )

        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["agent"], "frontend")
        self.assertEqual(steps[1]["agent"], "backend")
        self.assertEqual(steps[2]["depends_on"], ["step_1", "step_2"])

    def test_plan_task_handles_invalid_json(self):
        """Planning should gracefully handle malformed LLM output."""
        from AI.darius.planner import plan_task

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not JSON at all"

        with patch("AI.darius.planner.completion", return_value=mock_response):
            steps = plan_task(
                "Build a React page and a backend API then deploy everything",
                "default"
            )

        # Should fall back to single darius step
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["agent"], "darius")

    def test_plan_caps_at_8_steps(self):
        """Planner should cap output at 8 steps."""
        from AI.darius.planner import plan_task

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"id": f"step_{i}", "agent": "code", "task": f"Step {i}", "depends_on": []}
            for i in range(12)
        ])
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=200)

        with patch("AI.darius.planner.completion", return_value=mock_response):
            with patch("AI.darius.memory.log_trace"):
                steps = plan_task(
                    "Build frontend and backend and deploy and test and document and review and optimize and monitor and alert and log and cache and backup",
                    "default"
                )

        self.assertLessEqual(len(steps), 8)


class TestEvaluator(unittest.TestCase):
    """Tests for AI.darius.evaluator"""

    def test_guardrail_violations_fail_immediately(self):
        """Blocked patterns should cause immediate failure."""
        from AI.darius.evaluator import evaluate_output

        result = evaluate_output(
            task="Delete the old database",
            output="```bash\nrm -rf /var/data\nDROP TABLE users;\n```",
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["score"], 0.0)
        self.assertIn("Guardrail violation", result["feedback"])

    def test_valid_code_output_passes_structural_check(self):
        """Properly formatted code blocks should pass structural validation."""
        from AI.darius.evaluator import _check_structural_validity

        output = """```tsx
// src/components/Dashboard.tsx
import React from 'react'

export default function Dashboard() {
  return <div className="p-4">Dashboard</div>
}
```"""
        valid, issues = _check_structural_validity(output)
        self.assertTrue(valid)
        self.assertEqual(issues, [])

    def test_missing_file_path_fails_structural_check(self):
        """Code blocks without file paths should fail structural check."""
        from AI.darius.evaluator import _check_structural_validity

        output = """```tsx
import React from 'react'

export default function Dashboard() {
  return <div>Dashboard</div>
}
```"""
        valid, issues = _check_structural_validity(output)
        self.assertFalse(valid)
        self.assertIn("Code blocks missing file path comments on first line", issues)

    def test_todo_patterns_fail_completeness(self):
        """Outputs with TODO/placeholder patterns should fail completeness."""
        from AI.darius.evaluator import _check_completeness

        output = """```python
# app/api/routes.py
def get_users():
    # TODO: implement this
    pass
```"""
        complete, issues = _check_completeness(output)
        self.assertFalse(complete)

    def test_max_retries_with_slack_notification(self):
        """evaluate_with_retries should notify Slack after max failures."""
        from AI.darius.evaluator import evaluate_with_retries, MAX_RETRIES

        call_count = {"n": 0}

        def mock_retry_fn(task, feedback):
            call_count["n"] += 1
            return "still bad output without code blocks"

        with patch("AI.darius.evaluator.notify_rejection") as mock_notify:
            with patch("AI.darius.evaluator._llm_evaluate", return_value=None):
                final_output, passed = evaluate_with_retries(
                    task="Build a React component",
                    output="no code here",
                    retry_fn=mock_retry_fn,
                    task_id="test-123",
                    step_index=1,
                )

        self.assertFalse(passed)
        # Should have retried MAX_RETRIES - 1 times (first eval + retries)
        self.assertEqual(call_count["n"], MAX_RETRIES - 1)
        # Should have notified Slack
        mock_notify.assert_called_once()

    def test_passing_output_skips_retries(self):
        """Good output should pass immediately without retries."""
        from AI.darius.evaluator import evaluate_with_retries

        good_output = """```tsx
// src/components/Widget.tsx
import React from 'react'

export function Widget() {
  return <div className="widget">Content</div>
}
```"""

        def mock_retry_fn(task, feedback):
            raise Exception("Should not be called")

        mock_llm_result = {"score": 0.9, "pass": True, "feedback": "", "issues": []}

        with patch("AI.darius.evaluator._llm_evaluate", return_value=mock_llm_result):
            final_output, passed = evaluate_with_retries(
                task="Build a Widget component",
                output=good_output,
                retry_fn=mock_retry_fn,
                task_id="test-pass",
                step_index=0,
            )

        self.assertTrue(passed)
        self.assertEqual(final_output, good_output)


class TestDAGExecutor(unittest.TestCase):
    """Tests for AI.darius.executor"""

    def test_topological_levels_parallel(self):
        """Steps without dependencies should be grouped into the same level."""
        from AI.darius.executor import _topological_levels

        steps = [
            {"id": "step_1", "agent": "frontend", "task": "A", "depends_on": []},
            {"id": "step_2", "agent": "backend", "task": "B", "depends_on": []},
            {"id": "step_3", "agent": "deploy", "task": "C", "depends_on": ["step_1", "step_2"]},
        ]

        levels = _topological_levels(steps)
        self.assertEqual(len(levels), 2)
        self.assertEqual(len(levels[0]), 2)  # step_1 and step_2 in parallel
        self.assertEqual(len(levels[1]), 1)  # step_3 after both
        self.assertEqual(levels[1][0]["id"], "step_3")

    def test_topological_levels_sequential(self):
        """Sequential dependencies should produce one-step-per-level."""
        from AI.darius.executor import _topological_levels

        steps = [
            {"id": "step_1", "agent": "code", "task": "A", "depends_on": []},
            {"id": "step_2", "agent": "code", "task": "B", "depends_on": ["step_1"]},
            {"id": "step_3", "agent": "code", "task": "C", "depends_on": ["step_2"]},
        ]

        levels = _topological_levels(steps)
        self.assertEqual(len(levels), 3)
        for level in levels:
            self.assertEqual(len(level), 1)

    def test_topological_handles_circular_deps(self):
        """Circular dependencies should not deadlock — force execution."""
        from AI.darius.executor import _topological_levels

        steps = [
            {"id": "step_1", "agent": "code", "task": "A", "depends_on": ["step_2"]},
            {"id": "step_2", "agent": "code", "task": "B", "depends_on": ["step_1"]},
        ]

        levels = _topological_levels(steps)
        # Should still produce levels (force-break circular dep)
        self.assertGreater(len(levels), 0)
        total_steps = sum(len(level) for level in levels)
        self.assertEqual(total_steps, 2)

    def test_execute_dag_with_mock_agents(self):
        """DAG execution should call agents and collect results."""
        from AI.darius.executor import execute_dag
        import httpx as _httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "args": {"proposal": "```tsx\n// src/App.tsx\nexport default function App() { return <div/> }\n```"}
        }
        mock_response.raise_for_status = MagicMock()

        steps = [
            {"id": "step_1", "agent": "frontend", "task": "Build app", "depends_on": []},
        ]

        with patch("AI.darius.executor.httpx.post", return_value=mock_response):
            with patch("AI.darius.executor._evaluate_step_output", side_effect=lambda step, output, **kw: output):
                with patch("AI.darius.memory.log_trace"):
                    results = execute_dag(steps, project="test", evaluate=True)

        self.assertIn("step_1", results)
        self.assertIn("App.tsx", results["step_1"])


class TestContext(unittest.TestCase):
    """Tests for AI.darius.context"""

    def test_maybe_compress_below_threshold(self):
        """Should not compress when below turn threshold."""
        from AI.darius.context import maybe_compress

        with patch("AI.darius.memory.get_session_turn_count", return_value=3):
            with patch("AI.darius.memory.get_last_summary_turn", return_value=0):
                with patch("AI.darius.context.completion") as mock_llm:
                    maybe_compress("test-session")
                    mock_llm.assert_not_called()

    def test_maybe_compress_triggers_at_threshold(self):
        """Should compress when unsummarized turns reach threshold."""
        from AI.darius.context import maybe_compress

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary of the last 5 turns."

        mock_turns = [
            {"role": "user", "content": f"Turn {i}"} for i in range(5)
        ] + [
            {"role": "assistant", "content": f"Response {i}"} for i in range(5)
        ]

        with patch("AI.darius.memory.get_session_turn_count", return_value=5):
            with patch("AI.darius.memory.get_last_summary_turn", return_value=0):
                with patch("AI.darius.memory.load_session", return_value=mock_turns):
                    with patch("AI.darius.context.completion", return_value=mock_response):
                        with patch("AI.darius.memory.save_context_summary") as mock_save:
                            maybe_compress("test-session")
                            mock_save.assert_called_once()

    def test_build_context_assembles_parts(self):
        """build_context should assemble summaries + recent turns."""
        from AI.darius.context import build_context

        mock_summaries = [
            {"summary": "Previously built the auth system", "turn_start": 1, "turn_end": 5},
        ]
        mock_recent = [
            {"role": "user", "content": "Add password reset"},
            {"role": "assistant", "content": "Done."},
        ]

        with patch("AI.darius.memory.recall_context_summaries", return_value=mock_summaries):
            with patch("AI.darius.memory.load_session", return_value=mock_recent):
                with patch("orchestrator.memory.recall", return_value=[]):
                    context = build_context("test-session", "Add email verification")

        self.assertIn("auth system", context)
        self.assertIn("password reset", context)


class TestMemory(unittest.TestCase):
    """Tests for AI.darius.memory trace functions (unit-level, no DB)."""

    def test_log_trace_signature(self):
        """log_trace should accept all expected parameters without error."""
        from AI.darius.memory import log_trace

        # Mock the DB connection
        with patch("AI.darius.memory._get_conn") as mock_conn:
            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

            # Should not raise
            log_trace(
                task_id="test-001",
                phase="plan",
                session_id="session-1",
                step_index=0,
                tool_name="planner",
                tool_args={"task": "test"},
                tool_result="result",
                evaluation_score=0.85,
                evaluation_feedback="looks good",
                revision_attempt=0,
                model="claude-haiku",
                tokens_in=100,
                tokens_out=50,
                latency_ms=200,
                status="success",
            )


class TestIntegration(unittest.TestCase):
    """Integration tests — verifies the full flow wiring."""

    def test_run_task_simple(self):
        """Simple task should plan (single step) → execute via smolagents → save."""
        from AI.darius.agent import run_task

        mock_agent = MagicMock()
        mock_agent.run.return_value = "Task completed successfully."

        with patch("AI.darius.agent.build_agent", return_value=mock_agent):
            with patch("AI.darius.agent.build_context", return_value=""):
                with patch("AI.darius.agent.plan_task", return_value=[
                    {"id": "step_1", "agent": "darius", "task": "test", "depends_on": []}
                ]):
                    with patch("AI.darius.agent.log_trace"):
                        with patch("AI.darius.memory.save_turn"):
                            with patch("AI.darius.agent.maybe_compress"):
                                result = run_task("hello", session_id="test")

        self.assertEqual(result, "Task completed successfully.")
        mock_agent.run.assert_called_once()

    def test_run_task_multi_step(self):
        """Multi-step plan should route through DAG executor."""
        from AI.darius.agent import run_task

        multi_plan = [
            {"id": "step_1", "agent": "frontend", "task": "Build UI", "depends_on": []},
            {"id": "step_2", "agent": "backend", "task": "Build API", "depends_on": []},
        ]

        with patch("AI.darius.agent.build_context", return_value=""):
            with patch("AI.darius.agent.plan_task", return_value=multi_plan):
                with patch("AI.darius.agent.execute_dag", return_value={"step_1": "UI done", "step_2": "API done"}):
                    with patch("AI.darius.agent.log_trace"):
                        with patch("AI.darius.memory.save_turn"):
                            with patch("AI.darius.agent.maybe_compress"):
                                result = run_task("Build full stack feature", session_id="test")

        self.assertIn("step_1", result)
        self.assertIn("step_2", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
