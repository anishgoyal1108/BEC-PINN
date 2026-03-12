import os
import re
import subprocess
import time

from .batch import run_single_1x1, run_single_ubmax
from .physics import T_nK_from_ubmax_seu, ubmax_scaled_from_T_nK
from .runs import find_existing_runs, find_runs_grouped_by_omega, find_sim_folder
from .settings import (
    BINARY_SEARCH_MAX_ITER,
    BOOTSTRAP_LEFT_NK,
    BOOTSTRAP_RIGHT_MAX_NK,
    BOOTSTRAP_RIGHT_NK,
    BOOTSTRAP_STEP_NK,
    FALLBACK_SCAN_STEP_NK,
    OMEGA_LARGE_JUMP_THRESHOLD,
    OMEGA_REFINE_TOLERANCE,
    OMEGA_VERIFY_COUNT,
    OMEGA_ZERO_FIRST_TRANSFER_NK,
    OUTPUT_DAT_DIR,
    OUTPUT_LOG_DIR,
    OUTPUT_PNG_DIR,
    RELEASE_LINE_INDEX,
    SCRIPT_DIR,
    TOLERANCE_NK,
    UB_NK_MATCH_TOLERANCE,
    WINDOW_TARGET_NK,
    get_critical_omega_cache_path,
    get_critical_summary_png_path,
    get_geometry_mode,
    get_imag_only_mode,
    get_sweep_mode,
    get_transfer_log_path_omega,
    get_transfer_log_path_ubmax,
    get_transfer_summary_png_path_omega,
    get_transfer_summary_png_path_ubmax,
)
from .templates import ub_str_for_dir, validate_template_dir
from .ui import build_group_options, select_from_menu


def _geom_mode(mode: str | None = None) -> str:
    return (mode or get_geometry_mode()).lower()


def _require_real_time_mode(feature_name: str) -> bool:
    if get_imag_only_mode():
        print(
            f"\n{feature_name} requires FULL execution mode (real-time enabled). "
            "Toggle execution mode in the main menu and retry."
        )
        return False
    return True


def _transfer_vs_ubmax_dat_path(
    dat_dir: str, omega: float, mode: str | None = None
) -> str:
    geometry_mode = _geom_mode(mode)
    return os.path.join(
        dat_dir, f"transfer_vs_ubmax_omega_{omega:.4f}_geom_{geometry_mode}.dat"
    )


def _transfer_vs_omega_dat_path(
    dat_dir: str, ubmax_seu: float, mode: str | None = None
) -> str:
    geometry_mode = _geom_mode(mode)
    return os.path.join(
        dat_dir,
        f"transfer_vs_omega_ubmax_{ubmax_seu:.4f}_geom_{geometry_mode}.dat",
    )


def _critical_omega_cache_path(mode: str | None = None) -> str:
    return get_critical_omega_cache_path(mode)


def _read_critical_omega_cache(dat_path: str) -> list[tuple[float, float, float]]:
    rows: list[tuple[float, float, float]] = []
    if not os.path.isfile(dat_path):
        return rows
    with open(dat_path, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                ub_nk = float(parts[0])
                ub_seu = float(parts[1])
                crit_omega = float(parts[2])
            except ValueError:
                continue
            rows.append((ub_nk, ub_seu, crit_omega))
    return rows


def _write_critical_omega_cache(
    dat_path: str, rows: list[tuple[float, float, float]]
) -> None:
    os.makedirs(os.path.dirname(dat_path), exist_ok=True)
    rows_sorted = sorted(rows, key=lambda r: r[0])
    deduped: list[tuple[float, float, float]] = []
    seen: set[float] = set()
    for ub_nk, ub_seu, crit_omega in rows_sorted:
        key = round(ub_nk, 4)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((ub_nk, ub_seu, crit_omega))
    with open(dat_path, "w") as f:
        f.write("# Ubmax_nK Ubmax_SEU Critical_Omega_R\n")
        for ub_nk, ub_seu, crit_omega in deduped:
            f.write(f"{ub_nk:.4f} {ub_seu:.4f} {crit_omega:.4f}\n")


def _ensure_critical_omega_cached(
    dat_path: str, ub_nk: float, ub_seu: float, crit_omega: float
) -> None:
    rows = _read_critical_omega_cache(dat_path)
    ub_key = round(ub_nk, 4)
    existing = {round(r[0], 4) for r in rows}
    if ub_key in existing:
        _write_critical_omega_cache(dat_path, rows)
        return
    rows.append((ub_nk, ub_seu, crit_omega))
    _write_critical_omega_cache(dat_path, rows)


def extract_bottom_winding_at_release(
    circ_path: str, release_line: int = RELEASE_LINE_INDEX
) -> float | None:
    try:
        with open(circ_path, "r") as f:
            for idx, line in enumerate(f, start=1):
                if idx == release_line:
                    parts = line.split()
                    if len(parts) < 3:
                        return None
                    try:
                        return float(parts[2])
                    except ValueError:
                        return None
            return None
    except OSError:
        return None


def _round_winding(winding: float) -> float:
    if abs(winding - 1.0) <= abs(winding):
        return 1.0
    return 0.0


def _is_transfer(wn: float) -> bool:
    return round(wn) == 1


def _collect_release_winding_rows(
    runs: list[dict], x_from_run
) -> list[tuple[float, float]]:
    data_rows: list[tuple[float, float]] = []
    for run in runs:
        run_dir = run["path"]
        run_dir_name = run["dir_name"]
        real_folder = find_sim_folder(run_dir, run_dir_name, "real")
        if real_folder is None:
            continue

        circ_file = os.path.join(real_folder, "circulation.dat")
        if not os.path.isfile(circ_file):
            continue

        bottom_winding = extract_bottom_winding_at_release(circ_file)
        if bottom_winding is None:
            continue

        rounded_winding = _round_winding(bottom_winding)
        x_val = x_from_run(run)
        data_rows.append((x_val, rounded_winding))

    data_rows.sort(key=lambda row: row[0])
    return data_rows


def build_transfer_dat_for_omega(omega: float, dat_dir: str) -> bool:
    runs_grouped = find_runs_grouped_by_omega()
    omega_key = f"{omega:.4f}"
    if omega_key not in runs_grouped:
        return False

    geometry_mode = _geom_mode()
    runs = [
        run
        for run in runs_grouped[omega_key]
        if run.get("geometry", "ring") == geometry_mode
    ]
    if not runs:
        return False
    data_rows = _collect_release_winding_rows(
        runs,
        lambda run: T_nK_from_ubmax_seu(run["ub_float"]),
    )
    if not data_rows:
        return False

    os.makedirs(dat_dir, exist_ok=True)
    data_filename = _transfer_vs_ubmax_dat_path(dat_dir, omega, geometry_mode)
    with open(data_filename, "w") as f:
        f.write(
            "# Ubmax (nK) vs bottom-ring winding number at release time\n"
            f"# Omega = {omega:.4f}, release line = {RELEASE_LINE_INDEX}, geometry = {geometry_mode}\n"
            "# Columns: Ubmax_nK  bottom_ring_winding_rounded\n"
        )
        for ub, wn in data_rows:
            f.write(f"{ub:.6f} {wn:.6f}\n")
    return True


def build_transfer_dat_for_ubmax(ub_key: str, dat_dir: str) -> bool:
    runs_grouped = find_existing_runs()
    if ub_key not in runs_grouped:
        return False

    geometry_mode = _geom_mode()
    runs = [
        run
        for run in runs_grouped[ub_key]
        if run.get("geometry", "ring") == geometry_mode
    ]
    if not runs:
        return False
    data_rows = _collect_release_winding_rows(runs, lambda run: run["omega"])
    if not data_rows:
        return False

    os.makedirs(dat_dir, exist_ok=True)
    ub_float = runs[0]["ub_float"]
    ub_nk = T_nK_from_ubmax_seu(ub_float)
    data_filename = _transfer_vs_omega_dat_path(dat_dir, ub_float, geometry_mode)
    with open(data_filename, "w") as f:
        f.write(
            "# Omega_R vs bottom-ring winding number at release time\n"
            f"# Ubmax = {ub_nk:.3f} nK (fixed), release line = {RELEASE_LINE_INDEX}, geometry = {geometry_mode}\n"
            "# Columns: Omega_R  bottom_ring_winding_rounded\n"
        )
        for om, wn in data_rows:
            f.write(f"{om:.6f} {wn:.6f}\n")
    return True


def read_transfer_dat(omega: float, dat_dir: str) -> list[tuple[float, float]]:
    path = _transfer_vs_ubmax_dat_path(dat_dir, omega)
    if not os.path.isfile(path):
        return []

    rows: list[tuple[float, float]] = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    ub_nk = float(parts[0])
                    wn = float(parts[1])
                    rows.append((ub_nk, wn))
                except ValueError:
                    pass
    return rows


def _first_transition_bracket(
    no_transfer: list[float], transfer: list[float]
) -> tuple[float, float] | None:
    if not no_transfer or not transfer:
        return None
    right_first = min(transfer)
    below = [ub for ub in no_transfer if ub < right_first]
    if not below:
        return None
    left_first = max(below)
    return (left_first, right_first)


def extract_critical_ubmax_nK(omega: float, dat_dir: str) -> float | None:
    rows = read_transfer_dat(omega, dat_dir)
    if not rows:
        return None
    no_transfer = [ub for ub, wn in rows if not _is_transfer(wn)]
    transfer = [ub for ub, wn in rows if _is_transfer(wn)]
    bracket = _first_transition_bracket(no_transfer, transfer)
    if bracket is None:
        return None
    _, right = bracket
    return right


def is_omega_complete(omega: float, dat_dir: str) -> bool:
    rows = read_transfer_dat(omega, dat_dir)
    no_transfer = [ub for ub, wn in rows if not _is_transfer(wn)]
    transfer = [ub for ub, wn in rows if _is_transfer(wn)]
    bracket = _first_transition_bracket(no_transfer, transfer)
    if bracket is None:
        return False
    left, right = bracket
    return right - left <= WINDOW_TARGET_NK


def closest_ub_nk_to_target(
    rows: list[tuple[float, float]], target_nK: float
) -> float | None:
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r[0] - target_nK))[0]


def get_existing_result_at(
    rows: list[tuple[float, float]],
    ub_nk: float,
    tolerance: float = UB_NK_MATCH_TOLERANCE,
) -> bool | None:
    for u, wn in rows:
        if abs(u - ub_nk) <= tolerance:
            return _is_transfer(wn)
    return None


def _compute_bracket_from_existing(
    rows: list[tuple[float, float]], prev_critical_nK: float | None
) -> tuple[float, float] | None:
    no_transfer = [ub for ub, wn in rows if not _is_transfer(wn)]
    transfer = [ub for ub, wn in rows if _is_transfer(wn)]
    bracket = _first_transition_bracket(no_transfer, transfer)
    if bracket is not None:
        return bracket
    if no_transfer and prev_critical_nK is not None:
        left = max(no_transfer)
        right = prev_critical_nK + TOLERANCE_NK
        if left < right:
            return (left, right)
    if transfer and prev_critical_nK is not None:
        right = min(transfer)
        left = prev_critical_nK - TOLERANCE_NK
        if left < right:
            return (left, right)
    return None


def check_transfer_for_run(run_dir_path: str, run_dir_name: str) -> bool:
    real_folder = find_sim_folder(run_dir_path, run_dir_name, "real")
    if real_folder is None:
        return False
    circ_file = os.path.join(real_folder, "circulation.dat")
    if not os.path.isfile(circ_file):
        return False
    bottom_winding = extract_bottom_winding_at_release(circ_file)
    if bottom_winding is None:
        return False
    return _round_winding(bottom_winding) == 1.0


def _generate_transfer_png(
    omega: float, dat_dir: str, png_dir: str | None = None
) -> bool:
    geometry_mode = _geom_mode()
    dat_filename = _transfer_vs_ubmax_dat_path(dat_dir, omega, geometry_mode)
    if not os.path.isfile(dat_filename):
        return False

    png_path = get_transfer_summary_png_path_ubmax(omega, geometry_mode)

    first_transfer_nK = None
    with open(dat_filename, "r") as f:
        for line in f:
            if line.strip().startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                val_nk = float(parts[0])
                wn = float(parts[1])
                if _is_transfer(wn):
                    first_transfer_nK = val_nk
                    break

    extra_label = ""
    if first_transfer_nK is not None:
        extra_label = (
            f"set label 'Ub_c = {first_transfer_nK:.2f} nK' at {first_transfer_nK}, "
            "0.5 center offset 0,1.2 boxed;"
        )

    gnu_script = (
        "set term pngcairo size 800,600;"
        f"set output '{png_path}';"
        "set xlabel 'Umax (nK)';"
        "set ylabel 'bottom-ring winding number (wn)';"
        f"set title 'transfer for Omega_R={omega:.4f} ({geometry_mode}) (wn = 0 = no; wn = 1 = yes)';"
        "set grid;"
        "set yrange [-0.2:1.2];"
        f"{extra_label}"
        f"plot '{dat_filename}' using 1:2 with lp lc rgb 'red' pt 7 ps 1.0 notitle;"
        "set output;"
    )
    result = subprocess.run(["gnuplot", "-e", gnu_script], capture_output=True)
    return result.returncode == 0


def _generate_transfer_png_omega_sweep(
    ub_key: str, ub_nk: float, dat_dir: str, png_dir: str | None = None
) -> bool:
    runs_grouped = find_existing_runs()
    if ub_key in runs_grouped:
        ub_float = runs_grouped[ub_key][0]["ub_float"]
    else:
        ub_float = float(ub_key)

    geometry_mode = _geom_mode()
    dat_filename = _transfer_vs_omega_dat_path(dat_dir, ub_float, geometry_mode)
    if not os.path.isfile(dat_filename):
        return False

    png_path = get_transfer_summary_png_path_omega(ub_float, geometry_mode)

    gnu_script = (
        "set term pngcairo size 800,600;"
        f"set output '{png_path}';"
        "set xlabel 'Omega_R (rad/s)';"
        "set ylabel 'bottom-ring winding number (wn)';"
        f"set title 'transfer for Ubmax={ub_nk:.2f} nK ({geometry_mode}) (wn = 0 = no; wn = 1 = yes)';"
        "set grid;"
        "set yrange [-0.2:1.2];"
        f"plot '{dat_filename}' using 1:2 with lp lc rgb 'red' pt 7 ps 1.0 notitle;"
        "set output;"
    )
    result = subprocess.run(["gnuplot", "-e", gnu_script], capture_output=True)
    return result.returncode == 0


def binary_search_one_omega(
    omega: float,
    prev_critical_nK: float | None,
    diag_stride: int,
    log_path: str,
    dat_dir: str,
) -> float:
    geometry_mode = _geom_mode()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    runs_grouped = find_runs_grouped_by_omega()
    omega_key = f"{omega:.4f}"
    has_runs = omega_key in runs_grouped

    dat_path = _transfer_vs_ubmax_dat_path(dat_dir, omega)
    if not os.path.isfile(dat_path) and has_runs:
        build_transfer_dat_for_omega(omega, dat_dir)

    rows = read_transfer_dat(omega, dat_dir)
    bracket = _compute_bracket_from_existing(rows, prev_critical_nK)

    effective_right_max = min(
        BOOTSTRAP_RIGHT_MAX_NK,
        OMEGA_ZERO_FIRST_TRANSFER_NK,
        (
            prev_critical_nK
            if prev_critical_nK is not None
            else OMEGA_ZERO_FIRST_TRANSFER_NK
        ),
    )

    if bracket is not None:
        left, right = bracket
        right = min(right, effective_right_max)
    else:
        if prev_critical_nK is None:
            left = BOOTSTRAP_LEFT_NK
            right = min(BOOTSTRAP_RIGHT_NK, effective_right_max)
        else:
            right = min(prev_critical_nK, effective_right_max)
            closest = closest_ub_nk_to_target(rows, prev_critical_nK)
            if closest is not None and closest < right:
                left = closest
            else:
                left = max(BOOTSTRAP_LEFT_NK, right - TOLERANCE_NK)

    with open(log_path, "a") as log:
        log.write(
            f"Run started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} "
            f"(AUTO binary search, omega={omega:.4f}, geometry={geometry_mode}, "
            f"bracket=[{left:.3f},{right:.3f}] nK)\n"
        )
        log.flush()

    def run_probe(ub_nk: float) -> tuple[bool, str, float, int]:
        rows_local = read_transfer_dat(omega, dat_dir)
        existing = get_existing_result_at(rows_local, ub_nk)
        if existing is not None:
            return (existing, "", 0.0, 0)

        run_dir_name, elapsed, exit_code = run_single_ubmax(omega, ub_nk, diag_stride)
        if exit_code != 0:
            mid_alt = ub_nk + 0.05
            existing_alt = get_existing_result_at(
                read_transfer_dat(omega, dat_dir), mid_alt
            )
            if existing_alt is not None:
                return (existing_alt, "", 0.0, 0)
            run_dir_name_alt, elapsed_alt, exit_code_alt = run_single_ubmax(
                omega, mid_alt, diag_stride
            )
            if exit_code_alt != 0:
                return (False, run_dir_name, elapsed, exit_code)
            run_dir_name, elapsed, exit_code = (
                run_dir_name_alt,
                elapsed_alt,
                exit_code_alt,
            )

        has_transfer = check_transfer_for_run(
            os.path.join(SCRIPT_DIR, run_dir_name), run_dir_name
        )
        build_transfer_dat_for_omega(omega, dat_dir)
        return (has_transfer, run_dir_name, elapsed, exit_code)

    iteration = 0
    while True:
        iteration += 1
        if iteration > BINARY_SEARCH_MAX_ITER:
            print(
                f"  Warning: Omega_R={omega:.4f} - max iterations ({BINARY_SEARCH_MAX_ITER}) reached"
            )
            with open(log_path, "a") as log:
                log.write("  [bootstrap] max iterations reached, breaking\n")
                log.flush()
            break

        rows = read_transfer_dat(omega, dat_dir)
        no_transfer_list = [ub for ub, wn in rows if not _is_transfer(wn)]
        transfer_list = [ub for ub, wn in rows if _is_transfer(wn)]
        has_both = bool(no_transfer_list and transfer_list)
        has_any = bool(no_transfer_list or transfer_list)
        bracket_rejected_above_cap = False

        if has_both:
            bracket_first = _first_transition_bracket(no_transfer_list, transfer_list)
            if bracket_first is not None:
                left_data, right_data = bracket_first
                right_data = min(right_data, effective_right_max)
                if left_data >= right_data:
                    bracket_rejected_above_cap = True
                    has_both = False
                elif right_data - left_data <= WINDOW_TARGET_NK:
                    left, right = left_data, right_data
                    break
                if right_data - left_data > BOOTSTRAP_STEP_NK:
                    probe_check = right_data - BOOTSTRAP_STEP_NK
                    if (
                        probe_check > left_data
                        and get_existing_result_at(rows, probe_check) is None
                    ):
                        with open(log_path, "a") as log:
                            log.write(
                                f"  [sanity] wide bracket [{left_data:.2f},{right_data:.2f}], "
                                f"probing left at {probe_check:.2f} nK to avoid missing first transition\n"
                            )
                            log.flush()
                        _ = run_probe(probe_check)
                        continue
                left, right = left_data, right_data
            else:
                has_both = False

        if not has_any:
            mid = (left + right) / 2.0
            with open(log_path, "a") as log:
                log.write(
                    f"  [bootstrap] no data yet, probing middle: ub_nk={mid:.3f}\n"
                )
                log.flush()
            existing = get_existing_result_at(rows, mid)
            if existing is not None:
                has_transfer = existing
                with open(log_path, "a") as log:
                    log.write(
                        f"  [reused] ub_nk={mid:.3f} from existing dat -> "
                        f"{'TRANSFER' if has_transfer else 'NO TRANSFER'}\n"
                    )
                    log.flush()
            else:
                has_transfer, run_dir_name, elapsed, exit_code = run_probe(mid)
                with open(log_path, "a") as log:
                    log.write(
                        f"  {run_dir_name} (OmegaR={omega:.4f}): {elapsed:.2f}s, exit_code={exit_code}\n"
                    )
                    log.flush()
            if has_transfer:
                right = mid
            else:
                left = mid
        elif has_both:
            bracket_first = _first_transition_bracket(no_transfer_list, transfer_list)
            if bracket_first is None:
                left = BOOTSTRAP_LEFT_NK
                right = BOOTSTRAP_RIGHT_NK
            else:
                left, right = bracket_first
                right = min(right, effective_right_max)
            if right - left <= WINDOW_TARGET_NK:
                break

            mid = (left + right) / 2.0
            existing = get_existing_result_at(rows, mid)
            if existing is not None:
                has_transfer = existing
                with open(log_path, "a") as log:
                    log.write(
                        f"  [reused] ub_nk={mid:.3f} from existing dat -> "
                        f"{'TRANSFER' if has_transfer else 'NO TRANSFER'}\n"
                    )
                    log.flush()
            else:
                has_transfer, run_dir_name, elapsed, exit_code = run_probe(mid)
                with open(log_path, "a") as log:
                    log.write(
                        f"  {run_dir_name} (OmegaR={omega:.4f}): {elapsed:.2f}s, exit_code={exit_code}\n"
                    )
                    log.flush()

            if has_transfer:
                right = mid
            else:
                left = mid
        else:
            if transfer_list and not no_transfer_list:
                right_candidate = min(transfer_list)
                new_left = max(BOOTSTRAP_LEFT_NK, right_candidate - BOOTSTRAP_STEP_NK)
                existing_left = get_existing_result_at(rows, new_left)
                if existing_left is None:
                    has_transfer, run_dir_name, elapsed, exit_code = run_probe(new_left)
                    with open(log_path, "a") as log:
                        log.write(
                            f"  {run_dir_name} (OmegaR={omega:.4f}): {elapsed:.2f}s, exit_code={exit_code}\n"
                        )
                        log.flush()
                else:
                    has_transfer = existing_left
                if has_transfer:
                    right = new_left
                else:
                    left = new_left
            else:
                left_candidate = max(no_transfer_list)
                probe = min(effective_right_max, left_candidate + BOOTSTRAP_STEP_NK)
                if probe <= left_candidate:
                    probe = min(
                        effective_right_max, left_candidate + FALLBACK_SCAN_STEP_NK
                    )
                existing_probe = get_existing_result_at(rows, probe)
                if existing_probe is None:
                    has_transfer, run_dir_name, elapsed, exit_code = run_probe(probe)
                    with open(log_path, "a") as log:
                        log.write(
                            f"  {run_dir_name} (OmegaR={omega:.4f}): {elapsed:.2f}s, exit_code={exit_code}\n"
                        )
                        log.flush()
                else:
                    has_transfer = existing_probe
                if has_transfer:
                    right = probe
                else:
                    left = probe

        if right - left <= WINDOW_TARGET_NK:
            break

        if bracket_rejected_above_cap:
            break

    critical = right
    with open(log_path, "a") as log:
        log.write(
            f"  Final bracket: [{left:.4f}, {right:.4f}] -> critical={critical:.4f} nK\n"
        )
        log.flush()
    return critical


def get_critical_omega_from_ubmax_log(log_dir: str, ubmax_nk: float) -> float | None:
    mode = _geom_mode()
    log_path = os.path.join(log_dir, f"ub_{ubmax_nk:.4f}_geom_{mode}.txt")
    if not os.path.isfile(log_path):
        return None

    last_crit = None
    with open(log_path, "r") as f:
        for line in f:
            if "Critical Omega=" in line:
                idx = line.find("Critical Omega=")
                if idx >= 0:
                    rest = line[idx + len("Critical Omega=") :].strip()
                    end = rest.find(",")
                    if end >= 0:
                        rest = rest[:end]
                    try:
                        last_crit = float(rest.strip())
                    except ValueError:
                        pass
    return last_crit


def get_prev_critical_omega_from_logs(
    log_dir: str, below_ubmax_nk: float
) -> float | None:
    if not os.path.isdir(log_dir):
        return None

    mode = _geom_mode()
    pattern = re.compile(rf"ub_([\d.]+)_geom_{mode}\.txt")
    candidates = []
    for name in os.listdir(log_dir):
        m = pattern.match(name)
        if not m:
            continue
        try:
            u_nk = float(m.group(1))
        except ValueError:
            continue
        if u_nk <= below_ubmax_nk:
            continue
        crit = get_critical_omega_from_ubmax_log(log_dir, u_nk)
        if crit is not None:
            candidates.append((u_nk, crit))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def prompt_and_run_auto_transfer_search() -> None:
    if not _require_real_time_mode("AUTO TRANSFER SEARCH"):
        return
    print("=" * 60)
    print("AUTO TRANSFER SEARCH - Binary search for critical ubmax per Omega_R")
    print("=" * 60)
    omega_start = float(input("Enter omega_R start (e.g., 0.04): ").strip() or "0.04")
    omega_end = float(input("Enter omega_R end (e.g., 3.0): ").strip() or "3.0")
    omega_step = float(input("Enter omega_R step (e.g., 0.01): ").strip() or "0.01")
    diag_stride_str = input("Enter diag_stride [15]: ").strip()
    diag_stride = int(diag_stride_str) if diag_stride_str else 15

    print("\n--- Configuration ---")
    print(f"  Omega_R: {omega_start} to {omega_end}, step {omega_step}")
    print(f"  diag_stride: {diag_stride}")
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return
    run_auto_transfer_search(omega_start, omega_end, omega_step, diag_stride)


def run_auto_transfer_search(
    omega_start: float,
    omega_end: float,
    omega_step: float,
    diag_stride: int,
) -> None:
    if not _require_real_time_mode("AUTO TRANSFER SEARCH"):
        return
    try:
        validate_template_dir()
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}")
        return

    omegas = []
    o = omega_start
    while o <= omega_end + 1e-9:
        omegas.append(round(o, 4))
        o += omega_step

    print(f"\nAUTO mode: Omega_R range [{omega_start}, {omega_end}], step {omega_step}")
    print(
        f"  Omegas: {omegas[:10]}{'...' if len(omegas) > 10 else ''} ({len(omegas)} total)"
    )
    print(f"  diag_stride={diag_stride}")

    os.makedirs(OUTPUT_LOG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DAT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_PNG_DIR, exist_ok=True)

    for omega in omegas:
        omega_key = f"{omega:.4f}"
        log_path = get_transfer_log_path_omega(omega_key, get_geometry_mode())

        runs_grouped = find_runs_grouped_by_omega()
        has_runs = omega_key in runs_grouped

        if has_runs:
            build_transfer_dat_for_omega(omega, OUTPUT_DAT_DIR)

        if is_omega_complete(omega, OUTPUT_DAT_DIR):
            print(
                f"  [SKIP] Omega_R={omega:.4f} already complete (transfer + window <= 0.1 nK)"
            )
            continue

        prev_omega = omega - omega_step
        prev_critical = None
        if prev_omega >= 0:
            prev_critical = extract_critical_ubmax_nK(prev_omega, OUTPUT_DAT_DIR)

        print(
            f"\n  Binary search for Omega_R={omega:.4f} (prev_critical={prev_critical})"
        )
        critical = binary_search_one_omega(
            omega, prev_critical, diag_stride, log_path, OUTPUT_DAT_DIR
        )
        print(f"  Critical ubmax for Omega_R={omega:.4f}: {critical:.3f} nK")

        if _generate_transfer_png(omega, OUTPUT_DAT_DIR, OUTPUT_PNG_DIR):
            print(
                "  PNG created: "
                + get_transfer_summary_png_path_ubmax(omega, get_geometry_mode())
            )


def _probe_omega(
    omega_val: float,
    ubmax_seu: float,
    diag_stride: int,
    geometry_mode: str,
    dat_vs_omega_path: str,
    log_path: str,
) -> tuple[bool, str, float, int]:
    """Run (or reuse) a single simulation at *omega_val* for fixed ubmax_seu.

    Returns (has_transfer, run_dir_name, elapsed_seconds, exit_code).
    Results are appended to *dat_vs_omega_path* if not already present.
    """
    rows = _read_omega_transfer_dat(dat_vs_omega_path)
    for om, wn in rows:
        if abs(om - omega_val) < 1e-5:
            reused = _is_transfer(wn)
            with open(log_path, "a") as log:
                log.write(
                    f"  [reused] OmegaR={omega_val:.4f} -> "
                    f"{'TRANSFER' if reused else 'NO TRANSFER'}\n"
                )
                log.flush()
            return (reused, "", 0.0, 0)

    run_dir_name, elapsed, exit_code = run_single_1x1(
        omega=omega_val,
        ubmax_seu=ubmax_seu,
        diag_stride=diag_stride,
        geometry_mode=geometry_mode,
    )
    run_dir = os.path.join(SCRIPT_DIR, run_dir_name)

    has_transfer = False
    if exit_code == 0:
        has_transfer = check_transfer_for_run(run_dir, run_dir_name)

    already_logged = False
    if os.path.isfile(dat_vs_omega_path):
        with open(dat_vs_omega_path, "r") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and abs(float(parts[0]) - omega_val) < 1e-5:
                    already_logged = True
                    break

    if not already_logged:
        with open(dat_vs_omega_path, "a") as f:
            f.write(f"{omega_val:.4f} {1 if has_transfer else 0}\n")

    with open(log_path, "a") as log:
        log.write(
            f"  {run_dir_name} (OmegaR={omega_val:.4f}): {elapsed:.2f}s, "
            f"exit={exit_code}, transfer={'YES' if has_transfer else 'NO'}\n"
        )
        log.flush()

    return (has_transfer, run_dir_name, elapsed, exit_code)


def verified_search_one_ubmax(
    ubmax_seu: float,
    prev_critical_omega: float | None,
    omega_max: float,
    omega_step: float,
    verify_count: int,
    diag_stride: int,
    log_path: str,
    output_dat_dir: str,
) -> float:
    """Find the first omega where transfer occurs and *stays* (consecutive verification).

    Forward-scans from prev_critical_omega in *omega_step* increments.  When a
    transfer is found at a candidate omega, it must be followed by
    (verify_count - 1) additional consecutive transfers (same spacing) to be
    accepted.  Any gap resets the counter, rejecting isolated
    dynamical-resonance spikes.

    Optimization A: if the candidate omega is >= prev_critical_omega +
    OMEGA_LARGE_JUMP_THRESHOLD, skip verification (large jumps are extremely
    unlikely to be spikes).

    The *omega_step* parameter is the user-configured probe spacing (e.g. 0.01),
    passed from the main menu; this is separate from the Ubmax step used in the
    sweep.
    """
    if prev_critical_omega is not None and prev_critical_omega > 0:
        start_omega = prev_critical_omega + omega_step
    elif prev_critical_omega is not None:
        start_omega = prev_critical_omega
    else:
        start_omega = 0.0
    start_omega = round(round(start_omega / omega_step) * omega_step, 4)

    geometry_mode = _geom_mode()

    with open(log_path, "a") as log:
        log.write(
            f"Run started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} "
            f"(VERIFIED OMEGA search, Ubmax={ubmax_seu:.4f}, "
            f"scan_from={start_omega:.4f} (prev_crit={prev_critical_omega}), "
            f"verify_count={verify_count})\n"
        )
        log.flush()

    build_transfer_dat_for_ubmax(f"{ubmax_seu:.4f}", output_dat_dir)

    dat_vs_omega_path = _transfer_vs_omega_dat_path(
        output_dat_dir, ubmax_seu, geometry_mode
    )
    if not os.path.isfile(dat_vs_omega_path):
        with open(dat_vs_omega_path, "w") as f:
            f.write("# Omega Transfer(0/1)\n")

    candidate: float | None = None
    consecutive = 0
    omega = start_omega
    iteration = 0

    while omega <= omega_max + 1e-9:
        iteration += 1
        if iteration > BINARY_SEARCH_MAX_ITER:
            with open(log_path, "a") as log:
                log.write(
                    f"  [verified] max iterations ({BINARY_SEARCH_MAX_ITER}) reached at omega={omega:.4f}\n"
                )
                log.flush()
            break

        omega_rounded = round(omega, 4)

        has_transfer, run_dir_name, elapsed, exit_code = _probe_omega(
            omega_rounded, ubmax_seu, diag_stride, geometry_mode,
            dat_vs_omega_path, log_path,
        )

        if exit_code != 0 and run_dir_name:
            with open(log_path, "a") as log:
                log.write(
                    f"  [verified] simulation failed at omega={omega_rounded:.4f}, "
                    f"exit={exit_code}, skipping\n"
                )
                log.flush()
            omega += OMEGA_STEP
            continue

        if has_transfer:
            if candidate is None:
                candidate = omega_rounded
                consecutive = 1
            else:
                consecutive += 1

            large_jump = (
                prev_critical_omega is not None
                and candidate >= prev_critical_omega + OMEGA_LARGE_JUMP_THRESHOLD
            )
            if large_jump:
                with open(log_path, "a") as log:
                    log.write(
                        f"  [verified] large jump: candidate={candidate:.4f} >= "
                        f"prev_crit+{OMEGA_LARGE_JUMP_THRESHOLD} "
                        f"({prev_critical_omega:.4f}+{OMEGA_LARGE_JUMP_THRESHOLD}), "
                        f"accepting without full verification\n"
                    )
                    log.flush()
                break

            if consecutive >= verify_count:
                with open(log_path, "a") as log:
                    log.write(
                        f"  [verified] {consecutive} consecutive transfers from "
                        f"omega={candidate:.4f}, VERIFIED\n"
                    )
                    log.flush()
                break
        else:
            if candidate is not None:
                with open(log_path, "a") as log:
                    log.write(
                        f"  [verified] spike rejected: candidate={candidate:.4f} "
                        f"lost transfer at omega={omega_rounded:.4f} "
                        f"(had {consecutive} consecutive)\n"
                    )
                    log.flush()
                print(
                    f"  No transfer at Omega_R={omega_rounded:.4f} "
                    f"(rejecting spike at {candidate:.4f}, increasing omega)..."
                )
            candidate = None
            consecutive = 0

            if prev_critical_omega is None or omega_rounded > prev_critical_omega:
                with open(log_path, "a") as log:
                    log.write(
                        f"  [verified] no transfer at omega={omega_rounded:.4f}, "
                        f"increasing omega\n"
                    )
                    log.flush()
                if candidate is None:
                    print(
                        f"  No transfer at Omega_R={omega_rounded:.4f}, "
                        "increasing omega..."
                    )

        omega += omega_step

    if candidate is not None:
        critical = candidate
    else:
        critical = omega_max

    with open(log_path, "a") as log:
        log.write(
            f"  Verified critical omega: {critical:.4f} "
            f"(consecutive={consecutive})\n"
        )
        log.flush()

    return critical


def _binary_refine_omega(
    ubmax_seu: float,
    omega_low: float,
    omega_high: float,
    diag_stride: int,
    log_path: str,
    output_dat_dir: str,
) -> float:
    """Binary search within [omega_low, omega_high] for the exact transition.

    Used by the injectivity guard when the coarse 0.01-step search returns the
    same critical omega as the previous Ubmax.  Refines to
    OMEGA_REFINE_TOLERANCE resolution.
    """
    geometry_mode = _geom_mode()
    dat_vs_omega_path = _transfer_vs_omega_dat_path(
        output_dat_dir, ubmax_seu, geometry_mode
    )

    with open(log_path, "a") as log:
        log.write(
            f"  [refine] binary refinement in [{omega_low:.4f}, {omega_high:.4f}]\n"
        )
        log.flush()

    lo = omega_low
    hi = omega_high
    iteration = 0

    while hi - lo > OMEGA_REFINE_TOLERANCE:
        iteration += 1
        if iteration > 20:
            break

        mid = round((lo + hi) / 2.0, 4)
        has_transfer, _, _, exit_code = _probe_omega(
            mid, ubmax_seu, diag_stride, geometry_mode,
            dat_vs_omega_path, log_path,
        )

        if exit_code != 0:
            with open(log_path, "a") as log:
                log.write(
                    f"  [refine] sim failed at {mid:.4f}, nudging up\n"
                )
                log.flush()
            lo = mid
            continue

        if has_transfer:
            hi = mid
        else:
            lo = mid

    result = round(hi, 4)
    with open(log_path, "a") as log:
        log.write(
            f"  [refine] result={result:.4f} (bracket [{lo:.4f}, {hi:.4f}])\n"
        )
        log.flush()

    return result


def _load_existing_critical_results(dat_file_path: str) -> dict[float, float]:
    existing_results: dict[float, float] = {}
    if not os.path.isfile(dat_file_path):
        return existing_results

    for ub_nk, _ub_seu, crit_omega in _read_critical_omega_cache(dat_file_path):
        existing_results[round(ub_nk, 4)] = crit_omega
    return existing_results


def run_auto_omega_search(
    ub_start: float,
    ub_end: float,
    ub_step: float,
    omega_min: float,
    omega_max: float,
    omega_step: float,
    verify_count: int,
    diag_stride: int,
) -> None:
    """Sweep Ubmax from ub_start toward ub_end, finding the verified critical
    omega for each point.

    Enforces:
      - **Consecutive verification**: rejects isolated dynamical-resonance
        spikes by requiring *verify_count* consecutive transfer results.
      - **Monotonicity**: critical omega must be non-decreasing as Ubmax
        decreases (lower barrier -> higher rotation needed).  If a violation is
        detected the search restarts from prev_critical_omega.
      - **Injectivity**: each Ubmax must map to a unique critical omega.  When
        the coarse 0.01 step gives the same value as the previous Ubmax, a
        binary refinement within [prev_crit, prev_crit + 0.01] resolves a
        sub-step distinction.
    """
    if not _require_real_time_mode("AUTO OMEGA SEARCH"):
        return

    geometry_mode = _geom_mode()
    dat_file_path = _critical_omega_cache_path(geometry_mode)
    existing_results = _load_existing_critical_results(dat_file_path)

    step = -abs(ub_step) if ub_start > ub_end else abs(ub_step)
    ubmax_nk_list: list[float] = []
    current = ub_start
    while (step < 0 and current >= ub_end - 1e-9) or (
        step > 0 and current <= ub_end + 1e-9
    ):
        ubmax_nk_list.append(round(current, 4))
        current += step

    print(f"\nAUTO OMEGA mode (verified): Ubmax range [{ub_start}, {ub_end}], step {ub_step}")
    print(
        f"  Ubmax values: {ubmax_nk_list[:10]}{'...' if len(ubmax_nk_list) > 10 else ''} "
        f"({len(ubmax_nk_list)} total)"
    )
    print(f"  diag_stride={diag_stride}")
    print(f"  geometry={geometry_mode}")
    print(
        f"  verify_count={verify_count}, "
        f"refine_tol={OMEGA_REFINE_TOLERANCE}, probe_step={omega_step}"
    )

    os.makedirs(OUTPUT_LOG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DAT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_PNG_DIR, exist_ok=True)

    prev_critical_omega = get_critical_omega_from_ubmax_log(
        OUTPUT_LOG_DIR, ubmax_nk_list[0]
    )
    if prev_critical_omega is None:
        prev_critical_omega = 0.0

    for ubmax_nk in ubmax_nk_list:
        if ubmax_nk in existing_results:
            print(f"  [SKIP] Ubmax={ubmax_nk:.4f} nK already complete.")
            prev_critical_omega = get_critical_omega_from_ubmax_log(
                OUTPUT_LOG_DIR, ubmax_nk
            )
            if prev_critical_omega is None:
                prev_critical_omega = existing_results[ubmax_nk]
            continue

        ubmax_seu = ubmax_scaled_from_T_nK(ubmax_nk)
        log_path = get_transfer_log_path_ubmax(ubmax_nk, geometry_mode)

        with open(log_path, "a") as log:
            log.write(
                f"\nSearch for Ubmax={ubmax_nk:.4f} nK "
                f"(SEU={ubmax_seu:.2f}, geometry={geometry_mode})\n"
            )

        print(
            f"\n  Verified search for Ubmax={ubmax_nk:.4f} nK (SEU={ubmax_seu:.2f}) "
            f"[prev_crit_omega={prev_critical_omega:.4f}, geometry={geometry_mode}]"
        )

        search_start = time.time()
        crit_omega = verified_search_one_ubmax(
            ubmax_seu,
            prev_critical_omega,
            omega_max,
            omega_step,
            verify_count,
            diag_stride,
            log_path,
            OUTPUT_DAT_DIR,
        )
        elapsed = time.time() - search_start
        elapsed_min = elapsed / 60.0

        # --- Monotonicity guard ---
        if crit_omega < prev_critical_omega:
            with open(log_path, "a") as log:
                log.write(
                    f"  [monotonicity] violation: {crit_omega:.4f} < "
                    f"prev={prev_critical_omega:.4f}, re-searching from prev\n"
                )
                log.flush()
            print(
                f"  [monotonicity] {crit_omega:.4f} < prev {prev_critical_omega:.4f}, "
                f"re-searching from prev_critical_omega"
            )
            crit_omega = verified_search_one_ubmax(
                ubmax_seu,
                prev_critical_omega,
                omega_max,
                omega_step,
                verify_count,
                diag_stride,
                log_path,
                OUTPUT_DAT_DIR,
            )
            extra_elapsed = time.time() - search_start - elapsed
            elapsed = time.time() - search_start
            elapsed_min = elapsed / 60.0
            if crit_omega < prev_critical_omega:
                crit_omega = prev_critical_omega
                with open(log_path, "a") as log:
                    log.write(
                        f"  [monotonicity] still violated after retry, "
                        f"clamping to {prev_critical_omega:.4f}\n"
                    )
                    log.flush()

        # --- Injectivity guard ---
        if (
            abs(crit_omega - prev_critical_omega) < 1e-5
            and prev_critical_omega > 0
        ):
            with open(log_path, "a") as log:
                log.write(
                    f"  [injectivity] coarse crit_omega={crit_omega:.4f} == "
                    f"prev={prev_critical_omega:.4f}, refining\n"
                )
                log.flush()
            refined = _binary_refine_omega(
                ubmax_seu,
                prev_critical_omega,
                prev_critical_omega + omega_step,
                diag_stride,
                log_path,
                OUTPUT_DAT_DIR,
            )
            if refined > prev_critical_omega:
                crit_omega = refined
                with open(log_path, "a") as log:
                    log.write(
                        f"  [injectivity] refined to {crit_omega:.4f}\n"
                    )
                    log.flush()
            elapsed = time.time() - search_start
            elapsed_min = elapsed / 60.0

        _ensure_critical_omega_cached(dat_file_path, ubmax_nk, ubmax_seu, crit_omega)
        existing_results[round(ubmax_nk, 4)] = crit_omega

        ub_key = ub_str_for_dir(ubmax_seu)
        build_transfer_dat_for_ubmax(ub_key, OUTPUT_DAT_DIR)

        ub_nk_val = T_nK_from_ubmax_seu(ubmax_seu)
        _generate_transfer_png_omega_sweep(
            ub_key, ub_nk_val, OUTPUT_DAT_DIR, OUTPUT_PNG_DIR
        )

        _generate_critical_omega_summary_png(OUTPUT_DAT_DIR, OUTPUT_PNG_DIR)

        print(
            f"  Verified Critical Omega={crit_omega:.4f}  "
            f"({elapsed_min:.1f} min / {elapsed:.0f} s)"
        )

        with open(log_path, "a") as log:
            log.write(
                f"  Search complete: Critical Omega={crit_omega:.4f}, "
                f"elapsed={elapsed_min:.1f} min ({elapsed:.0f} s)\n"
            )

        prev_critical_omega = crit_omega

    _generate_critical_omega_summary_png(OUTPUT_DAT_DIR, OUTPUT_PNG_DIR)
    print(f"  Summary PNG created: {get_critical_summary_png_path(geometry_mode)}")


def _generate_transfer_vs_omega_png(
    ubmax_seu: float, dat_dir: str, png_dir: str
) -> bool:
    geometry_mode = _geom_mode()
    dat_filename = _transfer_vs_omega_dat_path(dat_dir, ubmax_seu, geometry_mode)
    if not os.path.isfile(dat_filename):
        return False

    ub_nk = T_nK_from_ubmax_seu(ubmax_seu)

    os.makedirs(png_dir, exist_ok=True)
    png_name = f"transfer_vs_omega_ubmax_{ubmax_seu:.4f}_geom_{geometry_mode}.png"
    png_path = os.path.join(png_dir, png_name)

    gnu_script = (
        "set term pngcairo size 800,600;"
        f"set output '{png_path}';"
        "set xlabel 'Omega_R';"
        "set ylabel 'Transfer (0=No, 1=Yes)';"
        f"set title 'Transfer for Ubmax={ubmax_seu:.4f} SEU ({ub_nk:.2f} nK, {geometry_mode})';"
        "set grid;"
        "set yrange [-0.2:1.2];"
        f"plot '{dat_filename}' using 1:2 with lp lc rgb 'blue' pt 7 ps 1.0 notitle;"
        "set output;"
    )
    subprocess.run(["gnuplot", "-e", gnu_script], capture_output=True)
    return os.path.isfile(png_path)


def _generate_critical_omega_summary_png(
    dat_dir: str, png_dir: str | None = None
) -> bool:
    geometry_mode = _geom_mode()
    dat_filename = _critical_omega_cache_path(geometry_mode)
    if not os.path.isfile(dat_filename):
        return False

    png_path = get_critical_summary_png_path(geometry_mode)

    gnu_script = (
        "set term pngcairo size 800,600;"
        f"set output '{png_path}';"
        "set xlabel 'Ubmax (nK)';"
        "set ylabel 'Critical Omega_R';"
        f"set title 'Critical Rotation vs Barrier Height ({geometry_mode})';"
        "set grid;"
        f"plot '{dat_filename}' using 1:3 with lp lc rgb 'red' pt 7 ps 1.0 title 'Critical Omega';"
        "set output;"
    )
    subprocess.run(["gnuplot", "-e", gnu_script], capture_output=True)
    return os.path.isfile(png_path)


def prompt_and_run_auto_omega_search() -> None:
    if not _require_real_time_mode("AUTO OMEGA SEARCH"):
        return
    print("=" * 60)
    print("AUTO OMEGA SEARCH - Verified search for critical Omega per Ubmax")
    print(
        f"  (default consecutive verification={OMEGA_VERIFY_COUNT}, "
        f"refine tolerance={OMEGA_REFINE_TOLERANCE})"
    )
    print("=" * 60)
    ub_start = float(
        input("Enter Ubmax start (high nK, e.g., 48.5): ").strip() or "48.5"
    )
    ub_end = float(input("Enter Ubmax end (low nK, e.g., 40.0): ").strip() or "40.0")
    ub_step = float(input("Enter Ubmax step size (nK, e.g., 0.5): ").strip() or "0.5")

    omega_step = float(
        input("Enter omega probe step (rad/s, e.g., 0.01): ").strip() or "0.01"
    )

    verify_str = input(
        "Enter total probe count per candidate (including the candidate itself) "
        f"[{OMEGA_VERIFY_COUNT}]: "
    ).strip() or str(OMEGA_VERIFY_COUNT)
    verify_count = int(verify_str)

    om_min = 0.0
    om_max = 7.0

    diag_stride_str = input("Enter diag_stride [15]: ").strip()
    diag_stride = int(diag_stride_str) if diag_stride_str else 15

    print("\n--- Configuration ---")
    print(f"  Ubmax: {ub_start} to {ub_end} nK, step {ub_step}")
    print(f"  Omega Search Window: [{om_min}, {om_max}] (Dynamic Lower Bound)")
    print(f"  Omega probe step: {omega_step}")
    print(f"  Total probes per candidate: {verify_count}")
    print(f"  diag_stride: {diag_stride}")

    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    run_auto_omega_search(
        ub_start,
        ub_end,
        ub_step,
        om_min,
        om_max,
        omega_step,
        verify_count,
        diag_stride,
    )


def _read_omega_transfer_dat(dat_path: str) -> list[tuple[float, float]]:
    data_rows_list: list[tuple[float, float]] = []
    with open(dat_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    data_rows_list.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
    return data_rows_list


def run_transfer_vs_ubmax_plotter():
    geometry_mode = _geom_mode()
    print("=" * 60)
    if get_sweep_mode() == "ubmax":
        print("TRANSFER SUMMARY - Ubmax vs bottom-ring winding (fixed Omega)")
    else:
        print("TRANSFER SUMMARY - Omega_R vs bottom-ring winding (fixed Ubmax)")
    print("=" * 60)

    runs_grouped = find_existing_runs()
    if not runs_grouped:
        print("\nNo existing simulation runs found.")
        return

    group_list, group_label, _, group_options = build_group_options(runs_grouped)
    dat_dir = OUTPUT_DAT_DIR
    png_dir = OUTPUT_PNG_DIR

    print(f"\nFound {len(group_list)} {group_label} values (fixed parameter):\n")
    group_choice = select_from_menu(group_options, f"\nSelect {group_label}: ")
    if group_choice == 0:
        return

    selected_group = group_list[group_choice - 1]

    if get_sweep_mode() == "ubmax":
        omega_value = float(selected_group)
        runs = [
            r
            for r in runs_grouped[selected_group]
            if r.get("geometry", "ring") == geometry_mode
        ]
        if not runs:
            print(f"\nNo runs found for geometry={geometry_mode} in selected group.")
            return
        print(
            f"\nProcessing {len(runs)} Ubmax value(s) for Omega = {omega_value:.4f} "
            f"(release line = {RELEASE_LINE_INDEX}, geometry={geometry_mode})"
        )
        if not build_transfer_dat_for_omega(omega_value, dat_dir):
            print(
                "\nNo valid circulation.dat data found at the release line for any run."
            )
            return

        data_rows = read_transfer_dat(omega_value, dat_dir)
        transfer_detected = any(_is_transfer(wn) for _, wn in data_rows)
        for ub_nk, wn in data_rows:
            ub_seu = ubmax_scaled_from_T_nK(ub_nk)
            status = "TRANSFER" if _is_transfer(wn) else "NO TRANSFER"
            print(
                f"  Ubmax (SEU) = {ub_seu:.4f}, Ubmax (nK) = {ub_nk:.3f}, "
                f"wn(rounded) = {wn:.0f} -> {status}"
            )

        if _generate_transfer_png(omega_value, dat_dir, png_dir):
            print(
                f"\nSummary plot created: {get_transfer_summary_png_path_ubmax(omega_value, geometry_mode)}"
            )
        else:
            print("\n  gnuplot reported an error while creating the summary plot.")
    else:
        runs = [
            r
            for r in runs_grouped[selected_group]
            if r.get("geometry", "ring") == geometry_mode
        ]
        if not runs:
            print(f"\nNo runs found for geometry={geometry_mode} in selected group.")
            return
        ub_nk = T_nK_from_ubmax_seu(runs[0]["ub_float"])
        print(
            f"\nProcessing {len(runs)} Omega value(s) for Ubmax = {ub_nk:.2f} nK "
            f"(release line = {RELEASE_LINE_INDEX}, geometry={geometry_mode})"
        )
        if not build_transfer_dat_for_ubmax(selected_group, dat_dir):
            print(
                "\nNo valid circulation.dat data found at the release line for any run."
            )
            return

        ub_float = runs[0]["ub_float"]
        dat_path = _transfer_vs_omega_dat_path(dat_dir, ub_float, geometry_mode)
        data_rows_list = _read_omega_transfer_dat(dat_path)
        transfer_detected = any(_is_transfer(wn) for _, wn in data_rows_list)

        for omega_val, wn in data_rows_list:
            status = "TRANSFER" if _is_transfer(wn) else "NO TRANSFER"
            print(f"  Omega_R = {omega_val:.4f}, wn(rounded) = {wn:.0f} -> {status}")

        if _generate_transfer_png_omega_sweep(selected_group, ub_nk, dat_dir, png_dir):
            print(
                f"\nSummary plot created: {get_transfer_summary_png_path_omega(ub_float, geometry_mode)}"
            )
        else:
            print("\n  gnuplot reported an error while creating the summary plot.")

    if transfer_detected:
        print(
            "\nTransfer detected in at least one real-time run "
            "(bottom-ring winding number at release is non-zero)."
        )
    else:
        print(
            "\nNo transfer detected in any processed real-time run "
            "(bottom-ring winding number at release is zero)."
        )
