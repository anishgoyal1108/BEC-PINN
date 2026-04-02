#!/usr/bin/env python3
"""Quick anomaly detector for circulation.dat winding numbers at release time.

Checks every om_*_real subdirectory for two conditions:
  1. Mutual exclusivity — top and bottom winding numbers must round to
     different values (one ~0, the other ~1).
  2. Sanity — both raw values must be close to 0 or 1 (not negative,
     not 2+, etc.).
"""

import sys

sys.dont_write_bytecode = True

import os

from fast_runner.runs import _scan_runs, find_sim_folder
from fast_runner.settings import RELEASE_LINE_INDEX
from fast_runner.transfer import _round_winding
from fast_runner.ui import checkbox_menu

CLOSENESS_THRESHOLD = 0.3
SANE_MIN = -0.5
SANE_MAX = 1.5

C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RESET = "\033[0m"


def extract_windings_at_release(circ_path, release_line=RELEASE_LINE_INDEX):
    """Return (top_winding, bottom_winding) at the release line, or (None, None)."""
    try:
        with open(circ_path, "r") as fh:
            for idx, line in enumerate(fh, start=1):
                if idx == release_line:
                    parts = line.split()
                    if len(parts) < 3:
                        return None, None
                    try:
                        return float(parts[1]), float(parts[2])
                    except ValueError:
                        return None, None
        return None, None
    except OSError:
        return None, None


def classify_windings(top_wn, bot_wn):
    """Return (is_anomalous, list_of_reason_strings)."""
    reasons = []
    top_r = _round_winding(top_wn)
    bot_r = _round_winding(bot_wn)

    for label, wn in (("top", top_wn), ("bot", bot_wn)):
        if wn < SANE_MIN or wn > SANE_MAX:
            reasons.append(f"{label}={wn:.4f} outside [{SANE_MIN},{SANE_MAX}]")

    for label, wn, rounded in (("top", top_wn, top_r), ("bot", bot_wn, bot_r)):
        dist = abs(wn - rounded)
        if dist > CLOSENESS_THRESHOLD:
            reasons.append(f"{label}={wn:.4f} far from {rounded:.0f} (d={dist:.3f})")

    if top_r == bot_r:
        reasons.append(f"both round to {top_r:.0f}")

    return bool(reasons), reasons


def collect_results():
    """Scan every run directory, read windings at release, classify each."""
    results = []
    for run in _scan_runs():
        real_folder = find_sim_folder(run["path"], run["dir_name"], "real")
        if real_folder is None:
            continue

        circ_path = os.path.join(real_folder, "circulation.dat")
        if not os.path.isfile(circ_path):
            continue

        top_wn, bot_wn = extract_windings_at_release(circ_path)
        if top_wn is None or bot_wn is None:
            results.append({
                "run": run, "circ_path": circ_path,
                "top": None, "bot": None,
                "bad": True, "why": ["unreadable at release line"],
            })
            continue

        bad, why = classify_windings(top_wn, bot_wn)
        results.append({
            "run": run, "circ_path": circ_path,
            "top": top_wn, "bot": bot_wn,
            "bad": bad, "why": why,
        })

    results.sort(key=lambda r: r["run"]["dir_name"])
    return results


def print_table(results, only_bad=False):
    filtered = [r for r in results if r["bad"]] if only_bad else results
    if not filtered:
        print("\n  Nothing to show.")
        return

    hdr = f"{'Status':<10} {'Run':<52} {'Top':>10} {'Bot':>10}  Detail"
    print(f"\n  {hdr}")
    print(f"  {'─' * len(hdr)}")

    for r in filtered:
        tag = "ANOMALY" if r["bad"] else "OK"
        name = r["run"]["dir_name"]
        if len(name) > 50:
            name = name[:47] + "..."

        if r["top"] is not None:
            t_s, b_s = f"{r['top']:10.4f}", f"{r['bot']:10.4f}"
        else:
            t_s = b_s = f"{'N/A':>10}"

        if r["why"]:
            detail = "; ".join(r["why"])
        else:
            detail = (
                f"top~{_round_winding(r['top']):.0f}, "
                f"bot~{_round_winding(r['bot']):.0f}"
            )

        color = C_RED if r["bad"] else C_GREEN
        print(f"  {color}{tag:<10}{C_RESET} {name:<52} {t_s} {b_s}  {detail}")


def browse_circulation_files(results, only_bad=False):
    """Checkbox menu to pick circulation.dat files and display excerpts."""
    filtered = [r for r in results if r["bad"]] if only_bad else results
    if not filtered:
        print("\n  Nothing to browse.")
        return

    labels = []
    for r in filtered:
        tag = "ANOMALY" if r["bad"] else "OK"
        name = r["run"]["dir_name"]
        if r["top"] is not None:
            labels.append(
                f"[{tag}] {name}  (top={r['top']:.4f}, bot={r['bot']:.4f})"
            )
        else:
            labels.append(f"[{tag}] {name}  (unreadable)")

    print("\nSelect circulation.dat files to inspect:")
    print("(Toggle number, 'a'=all, 'n'=none, 'd'=done, '0'=cancel)")
    chosen = checkbox_menu(labels, "\nToggle/command: ")
    if not chosen:
        return

    for i in chosen:
        entry = filtered[i]
        path = entry["circ_path"]
        print(f"\n{'=' * 72}")
        print(f"  {entry['run']['dir_name']}")
        print(f"  {path}")
        if entry["why"]:
            print(f"  {C_YELLOW}Flags: {'; '.join(entry['why'])}{C_RESET}")
        print(f"{'=' * 72}")

        try:
            with open(path, "r") as fh:
                lines = fh.readlines()
        except OSError as exc:
            print(f"  Error: {exc}")
            continue

        total = len(lines)
        rel_idx = RELEASE_LINE_INDEX - 1

        print(f"\n  Total lines: {total},  Release line: {RELEASE_LINE_INDEX}")

        print(f"\n  --- First 3 lines ---")
        for k in range(min(3, total)):
            print(f"  {k + 1:>6}:  {lines[k].rstrip()}")

        window = 5
        lo = max(0, rel_idx - window)
        hi = min(total, rel_idx + window + 1)
        print(f"\n  --- Around release line {RELEASE_LINE_INDEX} ---")
        for k in range(lo, hi):
            arrow = " >>>" if k == rel_idx else "    "
            print(f"  {k + 1:>6}{arrow}:  {lines[k].rstrip()}")

        print(f"\n  --- Last 3 lines ---")
        for k in range(max(0, total - 3), total):
            print(f"  {k + 1:>6}:  {lines[k].rstrip()}")

        print()


def main():
    print("=" * 60)
    print("  ANOMALY DETECTOR — Winding Number Sanity Check")
    print("=" * 60)
    print(f"  Release line: {RELEASE_LINE_INDEX}")
    print(f"  Closeness threshold: ±{CLOSENESS_THRESHOLD}")
    print(f"  Sane value range: [{SANE_MIN}, {SANE_MAX}]")
    print(f"  Rule: top and bottom must round to different values")
    print()
    print("  Scanning runs...", flush=True)

    results = collect_results()

    n_total = len(results)
    n_bad = sum(1 for r in results if r["bad"])
    n_ok = n_total - n_bad

    print(f"\n  Scanned {n_total} runs  —  {C_GREEN}{n_ok} OK{C_RESET}, "
          f"{C_RED}{n_bad} anomalous{C_RESET}")

    if n_bad:
        print_table(results, only_bad=True)

    while True:
        print(f"\n{'─' * 40}")
        print("  1. Show all results")
        print("  2. Show anomalous only")
        print("  3. Browse circulation.dat (all runs)")
        print("  4. Browse circulation.dat (anomalous only)")
        print("  0. Exit")

        try:
            choice = int(input("\n  Select: ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            continue

        if choice == 0:
            break
        elif choice == 1:
            print_table(results)
        elif choice == 2:
            print_table(results, only_bad=True)
        elif choice == 3:
            browse_circulation_files(results)
        elif choice == 4:
            browse_circulation_files(results, only_bad=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
