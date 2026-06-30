#!/usr/bin/env python3
"""
Vault Sync — pulls secrets from Vaultwarden → writes .env
Includes a kill switch that disconnects the pipeline on anomalous activity.

Usage:
    python3 scripts/vault_sync.py          # Normal sync
    python3 scripts/vault_sync.py --lock   # Engage kill switch (revoke .env)
    python3 scripts/vault_sync.py --unlock # Restore .env from vault
    python3 scripts/vault_sync.py --status # Check kill switch state
"""
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
LOCK_FILE = BASE_DIR / ".env.locked"
BACKUP_FILE = BASE_DIR / ".env.backup"
KILL_SWITCH_FILE = BASE_DIR / ".kill_switch"
LOG_FILE = BASE_DIR / "logs" / "vault_sync.log"

VAULT_URL = os.environ.get("VAULT_URL", "https://emerald.melanin-tech.com")


def log(msg: str):
    """Append to sync log."""
    LOG_FILE.parent.mkdir(exist_ok=True)
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(entry)
    print(entry.strip())


def is_locked() -> bool:
    """Check if kill switch is engaged."""
    return KILL_SWITCH_FILE.exists()


def engage_kill_switch(reason: str = "Manual lock"):
    """
    KILL SWITCH — immediately disconnects secrets from all services.
    1. Backs up current .env
    2. Replaces .env with empty file (containers lose secrets on next restart)
    3. Creates lock file to prevent sync
    4. Logs the event
    """
    if is_locked():
        log("⚠️  Kill switch already engaged")
        return

    # Backup current .env
    if ENV_FILE.exists():
        BACKUP_FILE.write_text(ENV_FILE.read_text())

    # Wipe .env — containers will fail to authenticate on restart
    ENV_FILE.write_text("# KILL SWITCH ENGAGED — secrets revoked\n# Reason: {}\n# Time: {}\n# To restore: python3 scripts/vault_sync.py --unlock\n".format(reason, datetime.now().isoformat()))

    # Create lock file
    KILL_SWITCH_FILE.write_text(json.dumps({
        "engaged_at": datetime.now().isoformat(),
        "reason": reason,
    }))

    log(f"🚨 KILL SWITCH ENGAGED — Reason: {reason}")
    log("   .env wiped, services will lose secrets on next restart")
    log("   To restore: python3 scripts/vault_sync.py --unlock")


def disengage_kill_switch():
    """Restore .env from backup and remove lock."""
    if not is_locked():
        log("Kill switch is not engaged")
        return

    if BACKUP_FILE.exists():
        ENV_FILE.write_text(BACKUP_FILE.read_text())
        BACKUP_FILE.unlink()
        log("✅ Kill switch disengaged — .env restored from backup")
    else:
        log("⚠️  No backup found — run sync to regenerate .env from vault")

    KILL_SWITCH_FILE.unlink()


def sync_from_vault():
    """Pull secrets from Vaultwarden and write .env (placeholder — requires bw CLI auth)."""
    if is_locked():
        log("❌ Sync blocked — kill switch is engaged")
        sys.exit(1)

    log("🔄 Vault sync started")

    # Check if bw CLI is available and logged in
    try:
        result = subprocess.run(["bw", "status"], capture_output=True, text=True, timeout=10)
        status = json.loads(result.stdout) if result.stdout else {}
        if status.get("status") != "unlocked":
            log("❌ Bitwarden CLI not unlocked. Run: bw login && bw unlock")
            sys.exit(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log("❌ Bitwarden CLI (bw) not found. Install: brew install bitwarden-cli")
        sys.exit(1)

    # Export all items as env vars
    try:
        result = subprocess.run(
            ["bw", "list", "items", "--search", ""],
            capture_output=True, text=True, timeout=30
        )
        items = json.loads(result.stdout) if result.stdout else []
    except Exception as e:
        log(f"❌ Failed to fetch from vault: {e}")
        sys.exit(1)

    # Build .env from vault items (Secure Notes with name=value in notes)
    env_lines = ["# Auto-generated from Vaultwarden — DO NOT EDIT MANUALLY",
                 f"# Synced: {datetime.now().isoformat()}",
                 f"# Source: {VAULT_URL}",
                 ""]

    for item in items:
        if item.get("type") == 2:  # Secure Note
            name = item.get("name", "")
            notes = item.get("notes", "")
            if name and notes and not name.startswith("TEST"):
                env_lines.append(f"{name}={notes}")

    # Write .env
    ENV_FILE.write_text("\n".join(env_lines) + "\n")
    log(f"✅ Synced {len(items)} items from vault → .env ({len(env_lines)-4} secrets)")


def status():
    """Print current state."""
    if is_locked():
        data = json.loads(KILL_SWITCH_FILE.read_text())
        print(f"🔴 LOCKED — Kill switch engaged at {data['engaged_at']}")
        print(f"   Reason: {data['reason']}")
    else:
        print("🟢 UNLOCKED — Vault sync active")
        if ENV_FILE.exists():
            lines = [l for l in ENV_FILE.read_text().splitlines() if l and not l.startswith("#")]
            print(f"   .env has {len(lines)} secrets")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--sync"

    if cmd == "--lock":
        reason = " ".join(sys.argv[2:]) or "Manual lock"
        engage_kill_switch(reason)
    elif cmd == "--unlock":
        disengage_kill_switch()
    elif cmd == "--status":
        status()
    elif cmd == "--sync":
        sync_from_vault()
    else:
        print(__doc__)
