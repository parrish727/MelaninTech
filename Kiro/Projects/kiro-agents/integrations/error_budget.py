"""
Multi-Burn-Rate Error Budget Engine — Melanin Technologies SRE

Implements Google SRE multi-window burn-rate alerting:
  - Fast Burn (Critical): 14.4x burn rate over 1h window → page immediately
  - Slow Burn (Warning): 6x burn rate over 6h window → create ticket/notification

Key formula:
  Burn Rate = Error Rate / (1 - SLO Target)

This replaces the noisy threshold-based alerting that fires on every transient spike.
Only sustained burn rates trigger alerts — transient spikes are filtered out by the
multi-window approach.

Usage:
    from integrations.error_budget import ErrorBudgetEngine
    engine = ErrorBudgetEngine()

    # Run the full check cycle (call from HUD watchdog every 5 min)
    engine.run_check_cycle()

    # Get dashboard data
    dashboard = engine.get_dashboard_data()

    # Check if deploys should be blocked
    frozen = engine.is_feature_frozen()
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

logger = logging.getLogger("error_budget")

_DSN = os.environ.get("POSTGRES_DSN", "")
_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
_SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# ── Alert Tiers ───────────────────────────────────────────────────────────────

@dataclass
class AlertTier:
    name: str
    burn_rate_threshold: float  # Multiplier (e.g., 14.4x)
    short_window_hours: float   # Fast check window
    long_window_hours: float    # Sustained check window
    severity: str               # "critical" or "warning"
    action: str                 # What happens when triggered


# Standard multi-burn-rate tiers (per Google SRE book)
ALERT_TIERS = [
    AlertTier(
        name="fast_burn",
        burn_rate_threshold=14.4,
        short_window_hours=1.0,
        long_window_hours=5.0 / 60.0,  # 5-minute confirmation window
        severity="critical",
        action="page_oncall",
    ),
    AlertTier(
        name="slow_burn",
        burn_rate_threshold=6.0,
        short_window_hours=6.0,
        long_window_hours=1.0,  # 1-hour confirmation window
        severity="warning",
        action="create_ticket",
    ),
]

# Feature freeze threshold (percentage of budget remaining)
FEATURE_FREEZE_THRESHOLD = 20.0  # Freeze when < 20% budget remaining

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class SLODefinition:
    name: str
    target: float           # e.g., 0.995 for 99.5%
    window_days: int        # SLO window (typically 30)
    sli_type: str           # "availability", "latency", "error_rate"
    budget_total_minutes: float  # Total allowed bad minutes in window


@dataclass
class BurnRateResult:
    slo_name: str
    current_burn_rate: float
    budget_remaining_pct: float
    hours_to_exhaustion: Optional[float]
    alert_tier: Optional[str]       # "fast_burn", "slow_burn", or None
    alert_severity: Optional[str]   # "critical", "warning", or None
    window_error_rate: float
    is_firing: bool


# ── Engine ────────────────────────────────────────────────────────────────────

class ErrorBudgetEngine:
    """Multi-burn-rate error budget calculation and alerting engine."""

    def __init__(self):
        self._conn = None
        self._redis = None
        self._alerted_keys: set = set()  # Prevent duplicate alerts within cycle
        self._http = httpx.Client(timeout=10)

    # ── Public API ────────────────────────────────────────────────────────────

    def run_check_cycle(self):
        """
        Run the full burn-rate check cycle for all SLOs.
        Call this every 5 minutes from the HUD watchdog.
        """
        slos = self._load_slo_definitions()
        results = []

        for slo in slos:
            result = self._check_slo_burn_rate(slo)
            results.append(result)

            # Store result in DB for dashboard
            self._store_burn_rate_snapshot(result)

            # Fire alerts if thresholds breached
            if result.is_firing:
                self._fire_alert(result)

        # Check feature freeze condition
        self._check_feature_freeze(results)

        return results

    def get_dashboard_data(self) -> dict:
        """Get current burn rate + budget data for HUD dashboard."""
        slos = self._load_slo_definitions()
        data = {
            "slos": [],
            "feature_frozen": self.is_feature_frozen(),
            "overall_health": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
        }

        for slo in slos:
            result = self._check_slo_burn_rate(slo)
            data["slos"].append({
                "name": slo.name,
                "target": slo.target,
                "sli_type": slo.sli_type,
                "burn_rate": round(result.current_burn_rate, 2),
                "budget_remaining_pct": round(result.budget_remaining_pct, 1),
                "hours_to_exhaustion": round(result.hours_to_exhaustion, 1) if result.hours_to_exhaustion else None,
                "alert_tier": result.alert_tier,
                "alert_severity": result.alert_severity,
                "status": self._budget_status(result.budget_remaining_pct),
            })

            if result.alert_severity == "critical":
                data["overall_health"] = "critical"
            elif result.alert_severity == "warning" and data["overall_health"] != "critical":
                data["overall_health"] = "warning"

        return data

    def is_feature_frozen(self) -> bool:
        """Check if deploys should be blocked due to budget exhaustion."""
        r = self._get_redis()
        if r:
            try:
                return r.get("sre:feature_freeze") == "active"
            except Exception:
                pass

        # Fallback: check DB directly
        slos = self._load_slo_definitions()
        for slo in slos:
            result = self._check_slo_burn_rate(slo)
            if result.budget_remaining_pct < FEATURE_FREEZE_THRESHOLD:
                return True
        return False

    # ── Burn Rate Calculation ─────────────────────────────────────────────────

    def _check_slo_burn_rate(self, slo: SLODefinition) -> BurnRateResult:
        """Calculate current burn rate for an SLO across all alert tiers."""
        conn = self._get_conn()
        if not conn:
            return BurnRateResult(
                slo_name=slo.name, current_burn_rate=0, budget_remaining_pct=100,
                hours_to_exhaustion=None, alert_tier=None, alert_severity=None,
                window_error_rate=0, is_firing=False,
            )

        # Calculate error rate for the full SLO window (30d)
        full_window_error_rate = self._measure_error_rate(slo, hours=slo.window_days * 24)

        # Calculate budget remaining
        error_budget = 1.0 - slo.target  # e.g., 0.005 for 99.5% SLO
        budget_consumed_pct = (full_window_error_rate / error_budget) * 100 if error_budget > 0 else 0
        budget_remaining_pct = max(0, 100 - budget_consumed_pct)

        # Calculate current burn rate (using short windows)
        # Burn Rate = (error rate in window) / (error budget)
        current_burn_rate = 0
        firing_tier = None
        firing_severity = None

        for tier in ALERT_TIERS:
            short_window_rate = self._measure_error_rate(slo, hours=tier.short_window_hours)
            long_window_rate = self._measure_error_rate(slo, hours=tier.long_window_hours)

            # Burn rate = error_rate / error_budget
            if error_budget > 0:
                short_burn = short_window_rate / error_budget
                long_burn = long_window_rate / error_budget
            else:
                short_burn = 0
                long_burn = 0

            # Both windows must exceed threshold (multi-window confirmation)
            if short_burn >= tier.burn_rate_threshold and long_burn >= tier.burn_rate_threshold:
                current_burn_rate = max(current_burn_rate, short_burn)
                if firing_tier is None:  # Take highest severity
                    firing_tier = tier.name
                    firing_severity = tier.severity

            current_burn_rate = max(current_burn_rate, short_burn)

        # Hours to exhaustion at current burn rate
        hours_to_exhaustion = None
        if current_burn_rate > 0 and budget_remaining_pct > 0:
            budget_remaining_fraction = budget_remaining_pct / 100
            hours_to_exhaustion = (budget_remaining_fraction * slo.window_days * 24) / current_burn_rate

        return BurnRateResult(
            slo_name=slo.name,
            current_burn_rate=current_burn_rate,
            budget_remaining_pct=budget_remaining_pct,
            hours_to_exhaustion=hours_to_exhaustion,
            alert_tier=firing_tier,
            alert_severity=firing_severity,
            window_error_rate=full_window_error_rate,
            is_firing=firing_tier is not None,
        )

    def _measure_error_rate(self, slo: SLODefinition, hours: float) -> float:
        """Measure the error rate for a given SLO over a time window."""
        conn = self._get_conn()
        if not conn:
            return 0.0

        try:
            with conn.cursor() as cur:
                interval = f"{hours} hours"

                if slo.sli_type == "availability":
                    cur.execute(f"""
                        SELECT COUNT(*) as total,
                               COUNT(*) FILTER (WHERE status NOT IN ('success', 'credit_guard')) as errors
                        FROM llm_traces
                        WHERE created_at > NOW() - INTERVAL '{interval}'
                          AND COALESCE(task_preview, '') NOT LIKE '%%HUD timeout%%'
                    """)
                    total, errors = cur.fetchone()
                    if total == 0:
                        return 0.0
                    return errors / total

                elif slo.sli_type == "error_rate":
                    cur.execute(f"""
                        SELECT COUNT(*) as total,
                               COUNT(*) FILTER (WHERE status NOT IN ('success', 'credit_guard')
                                   AND COALESCE(task_preview, '') NOT LIKE '%%HUD timeout%%') as errors
                        FROM llm_traces
                        WHERE created_at > NOW() - INTERVAL '{interval}'
                    """)
                    total, errors = cur.fetchone()
                    if total == 0:
                        return 0.0
                    return errors / total

                elif slo.sli_type == "latency":
                    # For latency SLOs, "error" = requests exceeding the target
                    target_ms = slo.target * 1000 if slo.target < 1000 else slo.target
                    cur.execute(f"""
                        SELECT COUNT(*) as total,
                               COUNT(*) FILTER (WHERE latency_ms > {target_ms}) as slow
                        FROM llm_traces
                        WHERE created_at > NOW() - INTERVAL '{interval}'
                          AND status = 'success'
                          AND cached = FALSE
                          AND latency_ms < 60000
                    """)
                    total, slow = cur.fetchone()
                    if total == 0:
                        return 0.0
                    return slow / total

                return 0.0
        except Exception as e:
            logger.warning(f"Error measuring rate for {slo.name}: {e}")
            return 0.0

    # ── Alerting ──────────────────────────────────────────────────────────────

    def _fire_alert(self, result: BurnRateResult):
        """Fire an alert based on burn rate result."""
        alert_key = f"{result.slo_name}:{result.alert_tier}"

        # Deduplicate within check cycle
        if alert_key in self._alerted_keys:
            return
        self._alerted_keys.add(alert_key)

        # Check cooldown in Redis (don't re-alert within 30 min for critical, 2h for warning)
        r = self._get_redis()
        if r:
            cooldown_key = f"sre:alert_cooldown:{alert_key}"
            if r.get(cooldown_key):
                return
            cooldown_seconds = 1800 if result.alert_severity == "critical" else 7200
            r.setex(cooldown_key, cooldown_seconds, "1")

        if result.alert_severity == "critical":
            self._send_critical_alert(result)
        else:
            self._send_warning_alert(result)

    def _send_critical_alert(self, result: BurnRateResult):
        """Send critical (fast-burn) alert to Slack."""
        hours_left = f"{result.hours_to_exhaustion:.1f}h" if result.hours_to_exhaustion else "unknown"
        message = (
            f"🔴 *CRITICAL: Fast Burn on `{result.slo_name}`*\n"
            f"Burn rate: *{result.current_burn_rate:.1f}x* (threshold: 14.4x)\n"
            f"Budget remaining: *{result.budget_remaining_pct:.1f}%*\n"
            f"Estimated exhaustion: *{hours_left}*\n"
            f"_Action: Investigate immediately. Budget will exhaust in ~2 days at this rate._"
        )
        self._send_slack(message)
        logger.critical(f"FAST BURN: {result.slo_name} at {result.current_burn_rate:.1f}x burn rate")

    def _send_warning_alert(self, result: BurnRateResult):
        """Send warning (slow-burn) alert to Slack."""
        hours_left = f"{result.hours_to_exhaustion:.1f}h" if result.hours_to_exhaustion else "unknown"
        message = (
            f"🟡 *WARNING: Slow Burn on `{result.slo_name}`*\n"
            f"Burn rate: *{result.current_burn_rate:.1f}x* (threshold: 6x)\n"
            f"Budget remaining: *{result.budget_remaining_pct:.1f}%*\n"
            f"Estimated exhaustion: *{hours_left}*\n"
            f"_Action: Address within 24h. Budget will exhaust in ~5 days at this rate._"
        )
        self._send_slack(message)
        logger.warning(f"SLOW BURN: {result.slo_name} at {result.current_burn_rate:.1f}x burn rate")

    # ── Feature Freeze ────────────────────────────────────────────────────────

    def _check_feature_freeze(self, results: list[BurnRateResult]):
        """Activate/deactivate feature freeze based on budget remaining."""
        r = self._get_redis()
        if not r:
            return

        any_below_threshold = any(
            res.budget_remaining_pct < FEATURE_FREEZE_THRESHOLD
            for res in results
        )

        current_freeze = r.get("sre:feature_freeze") == "active"

        if any_below_threshold and not current_freeze:
            # Activate freeze
            r.set("sre:feature_freeze", "active")
            offending = [res.slo_name for res in results if res.budget_remaining_pct < FEATURE_FREEZE_THRESHOLD]
            self._send_slack(
                f"🛑 *FEATURE FREEZE ACTIVATED*\n"
                f"Error budget below {FEATURE_FREEZE_THRESHOLD}% for: {', '.join(offending)}\n"
                f"_All non-critical deploys are blocked until budget recovers._\n"
                f"_Focus: reliability work only._"
            )
            logger.critical(f"FEATURE FREEZE activated: {offending}")

        elif not any_below_threshold and current_freeze:
            # Deactivate freeze
            r.delete("sre:feature_freeze")
            self._send_slack(
                f"✅ *Feature Freeze Lifted*\n"
                f"All error budgets above {FEATURE_FREEZE_THRESHOLD}%. Deploys are unblocked."
            )
            logger.info("Feature freeze lifted — budgets recovered")

    # ── Storage ───────────────────────────────────────────────────────────────

    def _store_burn_rate_snapshot(self, result: BurnRateResult):
        """Store burn rate data for dashboard time-series."""
        conn = self._get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO error_budget_snapshots
                        (slo_name, burn_rate, budget_remaining_pct, hours_to_exhaustion,
                         alert_tier, alert_severity, error_rate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    result.slo_name, result.current_burn_rate, result.budget_remaining_pct,
                    result.hours_to_exhaustion, result.alert_tier, result.alert_severity,
                    result.window_error_rate,
                ))
            conn.commit()
        except Exception as e:
            logger.debug(f"Failed to store snapshot: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    def _ensure_tables(self):
        """Create the snapshot table if it doesn't exist."""
        conn = self._get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS error_budget_snapshots (
                        id SERIAL PRIMARY KEY,
                        slo_name TEXT NOT NULL,
                        burn_rate REAL NOT NULL,
                        budget_remaining_pct REAL NOT NULL,
                        hours_to_exhaustion REAL,
                        alert_tier TEXT,
                        alert_severity TEXT,
                        error_rate REAL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_budget_snapshots_slo_time
                    ON error_budget_snapshots(slo_name, created_at DESC)
                """)
            conn.commit()
        except Exception as e:
            logger.warning(f"Table creation failed: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_slo_definitions(self) -> list[SLODefinition]:
        """Load SLO definitions from the database."""
        conn = self._get_conn()
        if not conn:
            return []

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT name, target, window_hours FROM llm_slos")
                rows = cur.fetchall()

            slos = []
            for row in rows:
                name = row["name"]
                target_raw = float(row["target"])
                window_hours = int(row["window_hours"])

                # Determine SLI type from name
                if "availability" in name:
                    sli_type = "availability"
                    target = target_raw / 100  # Convert 99.5 → 0.995
                elif "error_rate" in name:
                    sli_type = "error_rate"
                    target = 1 - (target_raw / 100)  # Convert 2% error → 98% success
                elif "latency" in name:
                    sli_type = "latency"
                    target = target_raw  # Already in ms
                else:
                    continue  # Skip token budget — not user-facing SLI

                window_days = window_hours // 24

                slos.append(SLODefinition(
                    name=name,
                    target=target,
                    window_days=window_days,
                    sli_type=sli_type,
                    budget_total_minutes=(1 - target) * window_days * 24 * 60 if sli_type != "latency" else 0,
                ))

            return slos
        except Exception as e:
            logger.warning(f"Failed to load SLO definitions: {e}")
            return []

    def _budget_status(self, remaining_pct: float) -> str:
        """Convert budget remaining to a status label."""
        if remaining_pct <= 0:
            return "exhausted"
        elif remaining_pct < FEATURE_FREEZE_THRESHOLD:
            return "critical"
        elif remaining_pct < 50:
            return "warning"
        else:
            return "healthy"

    def _get_conn(self):
        """Get PostgreSQL connection."""
        if not _DSN:
            return None
        try:
            if self._conn is None or self._conn.closed:
                self._conn = psycopg2.connect(_DSN)
            if self._conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                try:
                    self._conn.rollback()
                except Exception:
                    self._conn = psycopg2.connect(_DSN)
            return self._conn
        except Exception:
            return None

    def _get_redis(self):
        """Get Redis connection."""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _send_slack(self, message: str):
        """Send a message to Slack."""
        if not _SLACK_TOKEN or not _SLACK_CHANNEL:
            logger.info(f"[no-slack] {message}")
            return
        try:
            self._http.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {_SLACK_TOKEN}", "Content-Type": "application/json"},
                json={"channel": _SLACK_CHANNEL, "text": message},
            )
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
