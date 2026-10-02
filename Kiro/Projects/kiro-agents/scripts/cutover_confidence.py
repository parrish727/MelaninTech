#!/usr/bin/env python3
"""
Cutover Confidence — one combined view for the Anthropic -> open-weight migration.

Runs BOTH eval tracks and fuses them per candidate into a single cutover
confidence:

  1. Free-text task quality      (scripts/ab_eval.py)      — LOB golden sets
  2. Typed-decision parity        (scripts/system_one_eval.py) — System One golden set
                                                              (accuracy + Brier + ECE)

Rationale: the migration must preserve BOTH how Darius writes/answers (free text)
AND how it makes narrow, machine-consumed decisions (System One). A model can be
great at prose but poorly calibrated on typed judgements, or vice-versa. The
combined score weights both so a candidate is only "cutover-ready" when it holds
parity on both axes.

Combined confidence (per candidate):
    combined = FREE_TEXT_WEIGHT * free_text_conf + SYSTEM_ONE_WEIGHT * system_one_conf
Default weights favor typed decisions slightly, since that is where open-weight
models most directly replace Anthropic inside deterministic software.

Runs offline with --mock. Emits a single console table + JSON + Markdown.

Usage:
    python scripts/cutover_confidence.py --mock
    python scripts/cutover_confidence.py
    python scripts/cutover_confidence.py --free-text-weight 0.5 --system-one-weight 0.5
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.ab_eval as ab
import scripts.system_one_eval as so

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("cutover_confidence")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "eval" / "reports"

DEFAULT_FREE_TEXT_WEIGHT = 0.45
DEFAULT_SYSTEM_ONE_WEIGHT = 0.55


def run_free_text(mock: bool, lob: str | None, candidates: set[str] | None, timeout: int) -> dict:
    """Invoke ab_eval's internals and return {candidate_name: confidence|None}."""
    cfg = ab.load_candidate_config()
    lob_cases = ab.load_golden_sets(lob=lob)
    b = cfg["baseline"]
    baseline = ab.ModelClient(b["name"], b["provider"], b["model"], timeout=timeout, mock=mock)
    judge = ab.ModelClient("judge", cfg["judge"]["provider"], cfg["judge"]["model"], timeout=timeout, mock=mock)
    ok, reason = baseline.preflight()
    if not ok:
        logger.warning(f"[free-text] baseline unavailable: {reason}")
        return {"_baseline_ok": False, "_reason": reason}
    baseline_run = ab.run_model_over_cases(baseline, lob_cases, judge, use_judge=True)
    out = {"_baseline_ok": True, "_baseline_overall": baseline_run["overall"]}
    for c in cfg["candidates"]:
        if candidates and c["name"] not in candidates:
            continue
        client = ab.ModelClient(c["name"], c["provider"], c["model"], timeout=timeout, mock=mock)
        ok, reason = client.preflight()
        if not ok:
            out[c["name"]] = {"status": "skipped", "reason": reason}
            continue
        run = ab.run_model_over_cases(client, lob_cases, judge, use_judge=True)
        parity = ab.compute_parity(baseline_run, run)
        out[c["name"]] = {"status": "ran", "confidence": parity["cutover_confidence"],
                          "overall": run["overall"], "errors": run["errors"]}
    return out


def run_system_one(mock: bool, candidates: set[str] | None, timeout: int) -> dict:
    """Invoke system_one_eval's internals and return {candidate_name: confidence|None}."""
    cases = so.load_golden()
    cfg = so.load_candidates()
    bspec = cfg["baseline"]
    bprov, reason = so.make_provider(bspec["name"], bspec["provider"], bspec["model"], mock, timeout)
    if bprov is None:
        logger.warning(f"[system-one] baseline unavailable: {reason}")
        return {"_baseline_ok": False, "_reason": reason}
    baseline_run = so.run_model(bprov, cases)
    out = {"_baseline_ok": True, "_baseline_accuracy": baseline_run["accuracy"]}
    for c in cfg["candidates"]:
        if candidates and c["name"] not in candidates:
            continue
        prov, reason = so.make_provider(c["name"], c["provider"], c["model"], mock, timeout)
        if prov is None:
            out[c["name"]] = {"status": "skipped", "reason": reason}
            continue
        run = so.run_model(prov, cases)
        conf, _ = so.system_one_confidence(run, baseline_run)
        out[c["name"]] = {"status": "ran", "confidence": conf,
                          "accuracy": run["accuracy"], "brier": run["brier"],
                          "ece": run["ece"], "errors": run["errors"]}
    return out


def combined_label(conf: float) -> str:
    if conf >= 96:
        return "CUTOVER-READY"
    if conf >= 85:
        return "SHADOW-READY"
    if conf >= 60:
        return "PROMISING"
    return "NOT READY"


def fuse(ft: dict, s1: dict, ft_w: float, s1_w: float) -> list[dict]:
    names = [k for k in set(list(ft) + list(s1)) if not k.startswith("_")]
    rows = []
    for name in sorted(names):
        f = ft.get(name, {})
        s = s1.get(name, {})
        f_ran = f.get("status") == "ran"
        s_ran = s.get("status") == "ran"
        f_conf = f.get("confidence") if f_ran else None
        s_conf = s.get("confidence") if s_ran else None

        # Combine only over available axes; renormalize weights across present ones.
        parts, weights = [], []
        if f_conf is not None:
            parts.append(f_conf); weights.append(ft_w)
        if s_conf is not None:
            parts.append(s_conf); weights.append(s1_w)
        if parts:
            wsum = sum(weights)
            combined = round(sum(p * w for p, w in zip(parts, weights)) / wsum, 1)
            status = "ran"
        else:
            combined = None
            status = "skipped"

        rows.append({
            "candidate": name,
            "status": status,
            "free_text_confidence": f_conf,
            "free_text_reason": f.get("reason") if not f_ran else None,
            "system_one_confidence": s_conf,
            "system_one_reason": s.get("reason") if not s_ran else None,
            "system_one_accuracy": s.get("accuracy") if s_ran else None,
            "system_one_ece": s.get("ece") if s_ran else None,
            "combined_confidence": combined,
            "readiness": combined_label(combined) if combined is not None else "NOT MEASURABLE",
        })
    rows.sort(key=lambda r: (r["combined_confidence"] is not None, r["combined_confidence"] or -1), reverse=True)
    return rows


def print_report(rows, ft, s1, ft_w, s1_w, mode):
    print(f"\n{'=' * 78}")
    print("  DARIUS CUTOVER CONFIDENCE — free-text quality + typed-decision parity")
    print(f"  Weights: free-text {ft_w:.0%} | system-one {s1_w:.0%}   Mode: {mode}")
    if ft.get("_baseline_ok"):
        print(f"  Free-text baseline overall: {ft.get('_baseline_overall', 0):.1%}")
    if s1.get("_baseline_ok"):
        print(f"  System One baseline accuracy: {s1.get('_baseline_accuracy', 0):.1%}")
    print(f"{'=' * 78}")
    print(f"  {'candidate':28s} {'free-text':>10s} {'sys-one':>9s} {'combined':>9s}  readiness")
    print(f"  {'-' * 74}")
    for r in rows:
        ft_s = f"{r['free_text_confidence']:.1f}%" if r["free_text_confidence"] is not None else "  skip"
        s1_s = f"{r['system_one_confidence']:.1f}%" if r["system_one_confidence"] is not None else " skip"
        cb_s = f"{r['combined_confidence']:.1f}%" if r["combined_confidence"] is not None else "   n/a"
        print(f"  {r['candidate']:28s} {ft_s:>10s} {s1_s:>9s} {cb_s:>9s}  [{r['readiness']}]")
    print(f"{'=' * 78}\n")


def write_markdown(rows, ft, s1, ft_w, s1_w, mode, path):
    L = [
        "# Darius Cutover Confidence — Combined View",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Mode: {mode}",
        f"- Weights: free-text {ft_w:.0%}, System One {s1_w:.0%}",
        f"- Free-text baseline overall: {ft.get('_baseline_overall', 0):.1%}" if ft.get("_baseline_ok") else "- Free-text baseline: unavailable",
        f"- System One baseline accuracy: {s1.get('_baseline_accuracy', 0):.1%}" if s1.get("_baseline_ok") else "- System One baseline: unavailable",
        "",
        ("Combined = weighted mean of the two confidence tracks (weights renormalized "
        "over whichever tracks ran). A candidate is only *cutover-ready* when both "
        "free-text quality and typed-decision parity hold."),
        "",
        "| Candidate | Free-text | System One | S1 acc | S1 ECE | Combined | Readiness |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ft_s = f"{r['free_text_confidence']:.1f}%" if r["free_text_confidence"] is not None else "skip"
        s1_s = f"{r['system_one_confidence']:.1f}%" if r["system_one_confidence"] is not None else "skip"
        acc = f"{r['system_one_accuracy']:.0%}" if r["system_one_accuracy"] is not None else "—"
        ece = f"{r['system_one_ece']:.3f}" if r["system_one_ece"] is not None else "—"
        cb = f"{r['combined_confidence']:.1f}%" if r["combined_confidence"] is not None else "n/a"
        L.append(f"| {r['candidate']} | {ft_s} | {s1_s} | {acc} | {ece} | {cb} | {r['readiness']} |")
    L += ["", "Labels: ≥96% CUTOVER-READY · ≥85% SHADOW-READY · ≥60% PROMISING · else NOT READY.",
          "", "## Path to 96%",
          "1. Resolve GPU hardware (#71) so local candidates run at production latency.",
          ("2. Grow BOTH golden sets — free-text LOB cases and System One typed decisions "
          "(sample-sufficiency caps both confidences on small sets)."),
          ("3. Close per-track gaps: a model strong on prose but weak/ill-calibrated on typed "
          "decisions is not cutover-ready — target the weaker axis."),
          "4. Shadow-run the top candidate in parallel with Claude and confirm sustained parity.",
          ""]
    path.write_text("\n".join(L))


def main() -> int:
    ap = argparse.ArgumentParser(description="Combined Darius cutover confidence")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--lob", default=None, help="Restrict free-text eval to one LOB")
    ap.add_argument("--candidates", default=None, help="Comma-separated candidate names")
    ap.add_argument("--free-text-weight", type=float, default=DEFAULT_FREE_TEXT_WEIGHT)
    ap.add_argument("--system-one-weight", type=float, default=DEFAULT_SYSTEM_ONE_WEIGHT)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--output-dir", default=str(REPORTS_DIR))
    args = ap.parse_args()

    cand = set(args.candidates.split(",")) if args.candidates else None
    mode = "mock" if args.mock else "live"

    logger.info("Running free-text A/B track...")
    ft = run_free_text(args.mock, args.lob, cand, args.timeout)
    logger.info("Running System One typed-decision track...")
    s1 = run_system_one(args.mock, cand, args.timeout)

    if not ft.get("_baseline_ok") and not s1.get("_baseline_ok"):
        logger.error("Both baselines unavailable — set ANTHROPIC_API_KEY or use --mock.")
        return 2

    rows = fuse(ft, s1, args.free_text_weight, args.system_one_weight)
    print_report(rows, ft, s1, args.free_text_weight, args.system_one_weight, mode)

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "weights": {"free_text": args.free_text_weight, "system_one": args.system_one_weight},
        "free_text_track": ft,
        "system_one_track": s1,
        "combined": rows,
    }
    (out / f"cutover_confidence_{ts}.json").write_text(json.dumps(report, indent=2))
    write_markdown(rows, ft, s1, args.free_text_weight, args.system_one_weight, mode,
                   out / f"cutover_confidence_{ts}.md")
    logger.info(f"Wrote {out}/cutover_confidence_{ts}.json and .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
