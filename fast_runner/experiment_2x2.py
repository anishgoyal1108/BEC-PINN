import os
import shutil
import time
from typing import NamedTuple

from .execution_log import (
    build_execution_log_path,
    print_simulation_debug,
    write_execution_log_header,
    write_execution_log_result,
    write_execution_log_total_runtime,
)
from .mode_utils import cleanup_real_time_artifacts, is_imag_only_mode
from .movies import _get_frame_range, _run_gnuplot_frame, parse_frame_range
from .physics import ubmax_scaled_from_T_nK
from .settings import (
    OUTPUT_PNG_DIR,
    get_geometry_mode,
    get_mode_cache_dir,
    get_omega_cache_dir,
)
from .solver import run_solver_script
from .templates import cleanup_run_directory, prepare_directory_2x2, validate_template_dir

EXPERIMENT_LABELS = {
    0: "0 transfers (all no-transfer)",
    1: "1 transfer (TL only)",
    2: "2 transfers (TL, TR)",
    3: "3 transfers (TL, TR, BL)",
    4: "4 transfers (all transfer)",
}
TARGET_ORDER = ["TL", "TR", "BL", "BR"]


class CriticalRow(NamedTuple):
    ub_nk: float
    ub_seu: float
    critical_omega: float


class ExperimentSelection(NamedTuple):
    ub_nk_by_target: dict[str, float]
    ub_seu_by_target: dict[str, float]
    transfer_bin_nk: list[float]
    no_transfer_nk: float


def _critical_omega_dat_path() -> str | None:
    mode_path = os.path.join(get_mode_cache_dir(), "critical_omega_vs_ubmax.dat")
    if os.path.isfile(mode_path):
        return mode_path
    return None


def parse_critical_omega_data() -> list[CriticalRow]:
    rows: list[CriticalRow] = []
    dat_path = _critical_omega_dat_path()
    if dat_path is None:
        return rows

    with open(dat_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            rows.append(
                CriticalRow(
                    ub_nk=float(parts[0]),
                    ub_seu=float(parts[1]),
                    critical_omega=float(parts[2]),
                )
            )
    return rows


def _pick_nearest_unique(rows: list[CriticalRow], center_nk: float, used: set[float]) -> float:
    ordered = sorted(rows, key=lambda r: abs(r.ub_nk - center_nk))
    for row in ordered:
        if row.ub_nk not in used:
            used.add(row.ub_nk)
            return row.ub_nk
    return ordered[0].ub_nk


def classify_and_select_ubmax_values(omega_r: float, experiment_k: int) -> ExperimentSelection:
    all_rows = parse_critical_omega_data()
    if not all_rows:
        raise ValueError("No rows found in critical_omega_vs_ubmax data file.")

    transfer_capable = [r for r in all_rows if r.critical_omega <= omega_r]
    no_transfer = [r for r in all_rows if r.critical_omega > omega_r]

    if not transfer_capable:
        raise ValueError(
            f"OmegaR={omega_r:.4f} is below all critical values; no transfer-capable Ub found."
        )
    if not no_transfer:
        raise ValueError(
            f"OmegaR={omega_r:.4f} is above all critical values; no no-transfer Ub found."
        )

    transfer_margin = 0.03
    no_transfer_margin = 0.03
    strong_transfer = [r for r in transfer_capable if r.critical_omega <= omega_r - transfer_margin]
    strong_no_transfer = [r for r in no_transfer if r.critical_omega >= omega_r + no_transfer_margin]

    tc_sorted = sorted(strong_transfer or transfer_capable, key=lambda r: r.ub_nk)
    tc_min = tc_sorted[0].ub_nk
    tc_max = tc_sorted[-1].ub_nk
    interval = (tc_max - tc_min) / 4.0

    transfer_bin_nk: list[float] = []
    used_nk: set[float] = set()
    for i in range(4):
        center = tc_min + (i + 0.5) * interval
        transfer_bin_nk.append(_pick_nearest_unique(tc_sorted, center, used_nk))
    transfer_bin_nk = sorted(
        transfer_bin_nk,
        key=lambda ub: min(all_rows, key=lambda r: abs(r.ub_nk - ub)).critical_omega,
    )

    no_transfer_row = min(strong_no_transfer or no_transfer, key=lambda r: abs(r.critical_omega - (omega_r + 1)))
    no_transfer_nk = no_transfer_row.ub_nk

    ub_nk_by_target: dict[str, float] = {}
    for idx, target in enumerate(TARGET_ORDER):
        ub_nk_by_target[target] = transfer_bin_nk[idx] if idx < experiment_k else no_transfer_nk

    ub_seu_by_target = {
        target: ubmax_scaled_from_T_nK(ub_nk_by_target[target]) for target in TARGET_ORDER
    }
    return ExperimentSelection(
        ub_nk_by_target=ub_nk_by_target,
        ub_seu_by_target=ub_seu_by_target,
        transfer_bin_nk=transfer_bin_nk,
        no_transfer_nk=no_transfer_nk,
    )


def parse_experiment_selection(selection_text: str) -> list[int]:
    return parse_frame_range(selection_text, (0, 4))


def _cache_num(value: float) -> str:
    return f"{value:.1f}".replace(".", "p")


def get_omega_cache_path_2x2(
    omega: float,
    geometry_mode: str | None = None,
) -> str:
    mode = (geometry_mode or get_geometry_mode()).lower()
    return os.path.join(
        get_omega_cache_dir("2x2", mode),
        f"ground_state_geom_{mode}_omega_{omega:.4f}.dat",
    )


def _run_phase_with_inputs(
    run_dir: str,
    run_dir_name: str,
    gi_source_name: str,
    out_suffix: str,
) -> int:
    shutil.copy2(os.path.join(run_dir, "di_modified.dat"), os.path.join(run_dir, "dtap_inputs.dat"))
    shutil.copy2(
        os.path.join(run_dir, gi_source_name),
        os.path.join(run_dir, "rfgpe_2d_solver_general_inputs.dat"),
    )

    exit_code = run_solver_script(run_dir, "run_rfgpe_2d_solver.sh")
    if exit_code != 0:
        return exit_code

    exit_code = run_solver_script(run_dir, "save_sim.sh")
    if exit_code != 0:
        return exit_code

    sim_folder = os.path.join(run_dir, "sim_folder")
    target_folder = os.path.join(run_dir, f"{run_dir_name}_{out_suffix}")
    if os.path.exists(sim_folder):
        if os.path.isdir(target_folder):
            shutil.rmtree(target_folder)
        shutil.move(sim_folder, target_folder)

    return 0


def find_or_create_ground_state_2x2(
    omega: float,
    run_dir: str,
    run_dir_name: str,
    geometry_mode: str,
) -> str | None:
    cache_path = get_omega_cache_path_2x2(omega, geometry_mode)
    if os.path.isfile(cache_path):
        print(f"  Found cached 2x2 ground state for omega={omega:.4f}: {cache_path}")
        return cache_path

    imag_folder = os.path.join(run_dir, f"{run_dir_name}_imag")
    final_wf_imag = os.path.join(imag_folder, "final_wf.dat")
    if os.path.isfile(final_wf_imag):
        os.makedirs(get_omega_cache_dir("2x2", geometry_mode), exist_ok=True)
        shutil.copy2(final_wf_imag, cache_path)
        print(f"  cached existing 2x2 ground state to: {cache_path}")
        return cache_path

    print(
        "  No cached 2x2 ground state for "
        f"omega={omega:.4f} and current Ub matrix; running imag time..."
    )
    exit_code = _run_phase_with_inputs(run_dir, run_dir_name, "gi_imag_modified.dat", "imag")
    if exit_code != 0:
        print(f"  Error running 2x2 imag phase: exit_code={exit_code}")
        return None

    final_wf_root = os.path.join(run_dir, "final_wf.dat")
    final_wf = final_wf_root if os.path.isfile(final_wf_root) else final_wf_imag
    if not os.path.isfile(final_wf):
        print("  ERROR: Could not find final_wf.dat after imag phase")
        return None

    shutil.copy2(final_wf, os.path.join(run_dir, "initial_wf.dat"))
    os.makedirs(get_omega_cache_dir("2x2", geometry_mode), exist_ok=True)
    shutil.copy2(final_wf, cache_path)
    print(f"  2x2 ground state cached to: {cache_path}")
    return cache_path


def run_real_time_2x2(run_dir: str, run_dir_name: str) -> int:
    if not os.path.isfile(os.path.join(run_dir, "initial_wf.dat")):
        print("  ERROR: initial_wf.dat is missing before real-time phase")
        return 1
    return _run_phase_with_inputs(run_dir, run_dir_name, "gi_real_modified.dat", "real")


def _render_density_preview_2x2(run_dir_name: str, real_folder: str) -> str | None:
    os.makedirs(OUTPUT_PNG_DIR, exist_ok=True)

    frame_range = _get_frame_range(real_folder)
    if frame_range is None:
        print("  WARNING: no wf_ascii_*.dat files found; skipping density preview frame")
        return None

    min_frame, max_frame = frame_range
    frame_num = 285 if min_frame <= 285 <= max_frame else max_frame
    if frame_num != 285:
        print(
            f"  Frame 285 not available for {run_dir_name}; using frame {frame_num} "
            f"(available range: {min_frame}-{max_frame})"
        )

    output_name = f"{run_dir_name}_density_frame_{frame_num:03d}.png"
    png_path = os.path.join(OUTPUT_PNG_DIR, output_name)
    success = _run_gnuplot_frame(
        folder=real_folder,
        script_name="density_distribution_movie.gnu",
        frame_num=frame_num,
        output_dir=OUTPUT_PNG_DIR,
        output_name=output_name,
        bare_plot=False,
    )

    if success and os.path.isfile(png_path):
        return png_path
    return None


def _run_single_experiment(
    omega: float,
    experiment_k: int,
    diag_stride: int,
    selection: ExperimentSelection,
    geometry_mode: str,
) -> tuple[str, float, int]:
    start = time.time()
    imag_only_mode = is_imag_only_mode()

    ub_ref_seu = sum(selection.ub_seu_by_target.values()) / len(TARGET_ORDER)
    run_dir_name, run_dir = prepare_directory_2x2(
        omega=omega,
        experiment_k=experiment_k,
        ub_ref_seu=ub_ref_seu,
        ubmax_assignment_seu=selection.ub_seu_by_target,
        diag_stride=diag_stride,
        geometry_mode=geometry_mode,
    )

    cached_gs = find_or_create_ground_state_2x2(
        omega,
        run_dir,
        run_dir_name,
        geometry_mode,
    )
    if cached_gs is None:
        return run_dir_name, time.time() - start, 1

    initial_wf_path = os.path.join(run_dir, "initial_wf.dat")
    if not os.path.isfile(initial_wf_path):
        shutil.copy2(cached_gs, initial_wf_path)

    print_simulation_debug(run_dir_name, imag_only=imag_only_mode, global_imag_only=is_imag_only_mode())
    if imag_only_mode:
        print(f"  [k={experiment_k}] Skipping real-time evolution (IMAG_ONLY mode)")
        cleanup_real_time_artifacts(run_dir, run_dir_name)
    else:
        exit_code = run_real_time_2x2(run_dir, run_dir_name)
        if exit_code != 0:
            return run_dir_name, time.time() - start, exit_code

        real_folder = os.path.join(run_dir, f"{run_dir_name}_real")
        png_path = _render_density_preview_2x2(run_dir_name, real_folder)
        if png_path is not None:
            print(f"  [k={experiment_k}] Density frame saved to: {png_path}")
        else:
            print(
                f"  [k={experiment_k}] WARNING: failed to render density preview frame "
                f"(expected under {OUTPUT_PNG_DIR})"
            )

    cleanup_run_directory(run_dir)
    elapsed = time.time() - start
    return run_dir_name, elapsed, 0


def run_2x2_threshold_experiment() -> None:
    print("=" * 60)
    print("2x2 THRESHOLD EXPERIMENT")
    print("=" * 60)

    try:
        validate_template_dir()
    except FileNotFoundError as exc:
        print(f"\n  ERROR: {exc}")
        return

    critical_path = _critical_omega_dat_path()
    if critical_path is None:
        print(f"\n  ERROR: Critical omega data file not found: {os.path.join(get_mode_cache_dir(), 'critical_omega_vs_ubmax.dat')}")
        return

    geometry_mode = get_geometry_mode().lower()
    imag_only_mode = is_imag_only_mode()
    print(f"  Geometry mode: {geometry_mode.upper()}")
    print(f"  Imag mode: {'IMAG_ONLY' if imag_only_mode else 'FULL'}")
    print(f"  Critical data: {critical_path}")

    print("\n  Experiment patterns:")
    print("    0 = no transfers")
    print("    1 = TL transfer")
    print("    2 = TL, TR transfer")
    print("    3 = TL, TR, BL transfer")
    print("    4 = all transfer")

    selection_text = input(
        "\n  Select experiment type(s) (0-4, ranges/commas allowed, e.g. 0-2,4): "
    ).strip()
    selected_experiments = parse_experiment_selection(selection_text)
    if not selected_experiments:
        print("  Invalid selection. Please choose values in [0, 4].")
        return

    omega_str = input("  Enter OmegaR (e.g., 0.2300): ").strip()
    try:
        omega = float(omega_str)
    except ValueError:
        print("  Invalid OmegaR value.")
        return

    ds_str = input("  Enter diag_stride (default=15): ").strip()
    try:
        diag_stride = int(ds_str) if ds_str else 15
    except ValueError:
        print("  Invalid diag_stride value.")
        return

    selections_by_k: dict[int, ExperimentSelection] = {}
    try:
        for experiment_k in selected_experiments:
            selections_by_k[experiment_k] = classify_and_select_ubmax_values(omega, experiment_k)
    except ValueError as e:
        print(f"\n  ERROR: {e}")
        return

    print(f"\n  OmegaR = {omega:.4f}")
    print(f"  diag_stride = {diag_stride}")
    print(f"  geometry = {geometry_mode}")
    print(f"  Experiments to run: {selected_experiments}")

    for experiment_k in selected_experiments:
        selection = selections_by_k[experiment_k]
        print(f"\n  k={experiment_k}: {EXPERIMENT_LABELS[experiment_k]}")
        for idx, target in enumerate(TARGET_ORDER):
            ub_seu = selection.ub_seu_by_target[target]
            ub_nk = selection.ub_nk_by_target[target]
            expected = "TRANSFER" if idx < experiment_k else "NO TRANSFER"
            print(f"    {target}: {ub_seu:.4f} SEU ({ub_nk:.4f} nK) [{expected}]")

    confirm = input("\n  Proceed with these experiments? (y/n): ").strip().lower()
    if confirm != "y":
        print("  Aborted.")
        return

    session_start = time.time()
    log_header = (
        f"(omega={omega:.4f}, experiments={selected_experiments}, "
        f"diag_stride={diag_stride}, geometry={geometry_mode}, imag_only={imag_only_mode})\n"
    )
    log_path = build_execution_log_path(session_start)

    success_count = 0
    with open(log_path, "w") as log:
        write_execution_log_header(
            log=log,
            script_start=session_start,
            log_header=log_header,
            template_name="template/",
            cached_ground_state=False,
            imag_only=imag_only_mode,
        )

        for experiment_k in selected_experiments:
            print(f"\n  Running experiment k={experiment_k}...")
            run_dir_name, elapsed, exit_code = _run_single_experiment(
                omega=omega,
                experiment_k=experiment_k,
                diag_stride=diag_stride,
                selection=selections_by_k[experiment_k],
                geometry_mode=geometry_mode,
            )
            write_execution_log_result(log, run_dir_name, elapsed, exit_code)
            print(f"  Completed: {run_dir_name} ({elapsed:.2f}s, exit_code={exit_code})")
            if exit_code == 0:
                success_count += 1

        total_elapsed = write_execution_log_total_runtime(log, session_start)

    print(f"\n  2x2 experiment session complete: {success_count}/{len(selected_experiments)} succeeded")
    print(f"  Total runtime: {total_elapsed:.2f}s")
    print(f"  Log file: {log_path}")
    print(f"  PNG output directory: {OUTPUT_PNG_DIR}")
    print("=" * 60)
