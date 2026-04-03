import os
import sys
import subprocess

sys.dont_write_bytecode = True

from .settings import RELEASE_LINE_INDEX
from .transfer import _round_winding

from anomaly_detector import (
    collect_results,
    extract_windings_at_release,
    classify_windings,
)


def _classify_category(top: float, bot: float, why: list[str]) -> str:
    """Coarse anomaly category label."""
    top_r = _round_winding(top)
    bot_r = _round_winding(bot)
    out = any("outside [" in w for w in why)
    if not why:
        return "ok"
    if top_r == 0.0 and bot_r == 0.0 and not out:
        return "both0"
    if top_r == 1.0 and bot_r == 1.0 and not out:
        return "both1"
    if out:
        return "out_range"
    return "other"


def select_representative_cases() -> list[dict]:
    """Pick a small, representative set of runs across anomaly types.

    Returns a list of result dicts from anomaly_detector.collect_results().
    """
    results = collect_results()
    buckets: dict[str, list[dict]] = {
        "both0": [],
        "both1": [],
        "out_range": [],
        "ok": [],
        "other": [],
    }
    for r in results:
        if not r["bad"]:
            buckets["ok"].append(r)
            continue
        top, bot = r["top"], r["bot"]
        if top is None or bot is None:
            buckets["other"].append(r)
            continue
        cat = _classify_category(top, bot, r["why"])
        buckets[cat].append(r)

    selection: list[dict] = []

    def take(cat: str, n: int) -> None:
        for r in buckets.get(cat, [])[:n]:
            selection.append(r)

    take("both0", 2)
    take("both1", 3)
    take("out_range", 3)
    take("ok", 2)
    return selection


def mirror_cases_to_bec_pinn(bec_root: str, selection: list[dict]) -> None:
    """Mirror dtap/general inputs for selected runs into BEC-PINN/cases/*.

    This does not try to be smart; it just copies the standard small inputs.
    """
    cases_root = os.path.join(bec_root, "cases")
    os.makedirs(cases_root, exist_ok=True)

    print(f"\nMirroring {len(selection)} cases into {cases_root} ...")
    for r in selection:
        run = r["run"]
        name = run["dir_name"]
        src_real = os.path.join(run["path"], f"{name}_real")
        case_dir = os.path.join(cases_root, name)
        os.makedirs(case_dir, exist_ok=True)
        print(f"  CASE {name} -> {case_dir}")
        for fname in (
            "dtap_inputs.dat",
            "rfgpe_2d_solver_general_inputs.dat",
            "initial_wf.dat",
            "initial_pot.dat",
        ):
            src = os.path.join(src_real, fname)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(case_dir, fname)
            try:
                with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
                    fdst.write(fsrc.read())
            except OSError as exc:
                print(f"    COPY_ERROR {fname}: {exc}")


def _make_solver_preexec():
    """Return a preexec_fn that mimics `ulimit -s unlimited` for the child.

    This is what `run_rfgpe_2d_solver.sh` does before launching the Fortran
    binary. On Linux this prevents stack overflows that otherwise show up
    exactly as exit code -11.
    """
    try:
        import resource  # type: ignore
    except Exception:
        return None

    def _preexec() -> None:  # pragma: no cover - platform specific
        try:
            resource.setrlimit(
                resource.RLIMIT_STACK,
                (resource.RLIM_INFINITY, resource.RLIM_INFINITY),
            )
        except Exception:
            # If this fails we still try to run with default limits.
            pass

    return _preexec


def run_bec_pinn_for_cases(bec_root: str, selection: list[dict]) -> None:
    """Run the modified BEC-PINN solver once for each mirrored case.

    This follows the same pattern fast_runner uses: Python orchestrates,
    the heavy lifting is in the external Fortran executable.
    """
    exe = os.path.join(bec_root, "template", "rfgpe_2d_solver")
    if not os.path.isfile(exe):
        print(f"ERROR: solver not found at {exe} (did you run 'make' in template?)")
        return

    preexec_fn = _make_solver_preexec()
    base_env = os.environ.copy()
    base_env.setdefault("OMP_STACKSIZE", "512M")
    if "OMP_NUM_THREADS" not in base_env:
        base_env["OMP_NUM_THREADS"] = str(os.cpu_count() or 1)

    cases_root = os.path.join(bec_root, "cases")
    print("\nRunning BEC-PINN solver for each case...")
    for r in selection:
        name = r["run"]["dir_name"]
        case_dir = os.path.join(cases_root, name)
        if not os.path.isdir(case_dir):
            print(f"  SKIP {name}: case directory missing ({case_dir})")
            continue
        print(f"  CASE {name} ...", end="", flush=True)
        try:
            result = subprocess.run(
                [exe],
                cwd=case_dir,
                env=base_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=preexec_fn,
            )
        except OSError as exc:
            print(f" ERROR ({exc})")
            continue
        if result.returncode != 0:
            print(f" ERROR (exit={result.returncode})")
        else:
            print(" OK")


def compare_original_vs_bec_pinn(bec_root: str, selection: list[dict]) -> None:
    """Compare winding numbers at release for original vs BEC-PINN runs."""
    print(
        "\nComparing original DTAP runs vs BEC-PINN cases at release line "
        f"{RELEASE_LINE_INDEX} ..."
    )
    for r in selection:
        run = r["run"]
        name = run["dir_name"]
        src_real = os.path.join(run["path"], f"{name}_real")
        orig_circ = os.path.join(src_real, "circulation.dat")

        base_case_dir = os.path.join(bec_root, "cases", name)
        case_circ = os.path.join(base_case_dir, "circulation.dat")
        if not os.path.isfile(case_circ):
            alt_circ = os.path.join(base_case_dir, "sim_folder", "circulation.dat")
            if os.path.isfile(alt_circ):
                case_circ = alt_circ

        orig_top, orig_bot = extract_windings_at_release(orig_circ)
        if orig_top is None or orig_bot is None:
            print(f"  {name}: original circulation.dat unreadable")
            continue

        if not os.path.isfile(case_circ):
            print(f"  {name}: BEC-PINN circulation.dat missing")
            continue

        new_top, new_bot = extract_windings_at_release(case_circ)
        if new_top is None or new_bot is None:
            print(f"  {name}: BEC-PINN circulation.dat unreadable")
            continue

        _, orig_why = classify_windings(orig_top, orig_bot)
        _, new_why = classify_windings(new_top, new_bot)

        print(f"  {name}:")
        print(
            f"    original:  top={orig_top:.4f}  bot={orig_bot:.4f}  "
            f"flags={'; '.join(orig_why) if orig_why else 'OK'}"
        )
        print(
            f"    BEC-PINN:  top={new_top:.4f}  bot={new_bot:.4f}  "
            f"flags={'; '.join(new_why) if new_why else 'OK'}"
        )


def main() -> None:
    """End-to-end helper for the winding-number fix experiment.

    - Selects representative runs via anomaly_detector / fast_runner.
    - Mirrors their inputs into BEC-PINN/cases under the current workspace.
    - Prints shell commands to actually run the modified BEC-PINN solver.
    - Provides a comparison helper (once runs are complete).
    """
    workspace_root = os.getcwd()
    bec_root = os.path.join(workspace_root, "BEC-PINN")
    if not os.path.isdir(bec_root):
        print(f"ERROR: BEC-PINN directory not found at {bec_root}")
        return

    selection = select_representative_cases()
    print(f"Selected {len(selection)} representative runs:")
    for r in selection:
        top, bot = r["top"], r["bot"]
        print(f"  {r['run']['dir_name']}: " f"top={top!r} bot={bot!r} -> {r['why']}")

    mirror_cases_to_bec_pinn(bec_root, selection)
    run_bec_pinn_for_cases(bec_root, selection)
    compare_original_vs_bec_pinn(bec_root, selection)


if __name__ == "__main__":
    main()
