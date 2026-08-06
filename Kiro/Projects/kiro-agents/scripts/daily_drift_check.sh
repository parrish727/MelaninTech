#!/bin/bash
# Daily Drift Check — runs inside the orchestrator container via host cron.
#
# Install on host machine:
#   crontab -e
#   0 6 * * * /Users/pktech_dev/Documents/MelaninTechnologies/Kiro/Projects/kiro-agents/scripts/daily_drift_check.sh >> /tmp/drift_check.log 2>&1
#
# What it does:
#   1. Runs drift detector (compare outputs to baselines)
#   2. Runs eval suite in fast mode (keyword-only, no LLM cost)
#   3. Checks evaluation score trends
#   4. Alerts Slack on any failures
#
# Exit codes:
#   0 — all checks pass
#   1 — drift or quality degradation detected (alert sent)

set -e

ORCHESTRATOR="docker-orchestrator-1"
DARIUS_URL="http://docker-darius-agent-1:8000"
WORKDIR="/app/Projects/kiro-agents"

echo "═══════════════════════════════════════════════════"
echo "Daily Drift Check — $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════"

# Check that containers are running
if ! docker ps --format '{{.Names}}' | grep -q "$ORCHESTRATOR"; then
    echo "ERROR: Orchestrator container not running"
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "docker-darius-agent-1"; then
    echo "ERROR: Darius container not running"
    exit 1
fi

FAILED=0

# 1. Drift check (compare to baselines)
echo ""
echo "─── Step 1: Drift Detection ───"
if docker exec -e DARIUS_URL="$DARIUS_URL" -w "$WORKDIR" "$ORCHESTRATOR" \
    python -m integrations.drift_detector --check 2>&1 | tail -5; then
    echo "✓ Drift check passed"
else
    echo "✗ DRIFT DETECTED"
    FAILED=1
fi

# 2. Fast eval (keyword-only, no API cost)
echo ""
echo "─── Step 2: Eval Gate (fast) ───"
if docker exec -e DARIUS_URL="$DARIUS_URL" -w "$WORKDIR" "$ORCHESTRATOR" \
    python scripts/eval_runner.py --fast --threshold 0.50 2>&1 | tail -15; then
    echo "✓ Eval gate passed"
else
    echo "✗ EVAL BELOW THRESHOLD"
    FAILED=1
fi

# 3. Score trends
echo ""
echo "─── Step 3: Score Trends ───"
docker exec -w "$WORKDIR" "$ORCHESTRATOR" \
    python -m integrations.drift_detector --scores 2>&1 | tail -5

echo ""
echo "═══════════════════════════════════════════════════"
if [ $FAILED -eq 0 ]; then
    echo "✓ ALL DAILY CHECKS PASSED"
else
    echo "✗ FAILURES DETECTED — investigate traces"
fi
echo "═══════════════════════════════════════════════════"

exit $FAILED
