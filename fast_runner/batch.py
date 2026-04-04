import os
import shutil
import time

import numpy as np  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]

from .execution_log import (
    build_execution_log_path,
    print_simulation_debug,
    write_execution_log_header,
    write_execution_log_result,
    write_execution_log_total_runtime,
)
from .mode_utils import cleanup_real_time_artifacts, is_imag_only_mode
from .physics import ubmax_scaled_from_T_nK as ubmax_scaled_from_T_nK
from .settings import (
    SCRIPT_DIR,
    TEMPLATE_DIR,
    get_geometry_mode,
    get_sweep_mode,
)
from .solver import run_solver_script
from .templates import (
    cleanup_run_directory,
    find_template_files,
    prepare_directory,
    validate_template_dir,
)


def _print_template_status() -> None:
    print(f"\nLooking for template files in: {TEMPLATE_DIR}")
    validate_template_dir(TEMPLATE_DIR)
    di_template, gi_template, _ = find_template_files(TEMPLATE_DIR)
    print(f"  Found DI template: {os.path.basename(di_template)}")
    print(f"  Found GI template: {os.path.basename(gi_template)}")


def _prepare_single_1x1_run(
    omega: float,
    ubmax_seu: float,
    diag_stride: int,
    geometry_mode: str | None = None,
) -> str:
    run_dir_name, _run_dir = prepare_directory(
        omega=omega,
        diag_stride=diag_stride,
        geometry_mode=geometry_mode,
        ubmax_seu=ubmax_seu,
    )
    return run_dir_name


def run_simulation(
    run_dir_name: str,
    imag_only: bool | None = None,
) -> tuple[str, float, int]:
    if imag_only is None:
        imag_only = is_imag_only_mode()

    print_simulation_debug(run_dir_name, imag_only, is_imag_only_mode())

    start = time.time()
    run_dir = os.path.join(SCRIPT_DIR, run_dir_name)

    try:
        # Always run imaginary time to obtain ground state
        print(f"  {run_dir_name}: [IMAG] Starting imaginary-time evolution...")
        shutil.copy2(
            os.path.join(run_dir, "di_modified.dat"),
            os.path.join(run_dir, "dtap_inputs.dat"),
        )
        shutil.copy2(
            os.path.join(run_dir, "gi_imag_modified.dat"),
            os.path.join(run_dir, "rfgpe_2d_solver_general_inputs.dat"),
        )

        exit_code = run_solver_script(
            run_dir,
            "run_rfgpe_2d_solver.sh",
            capture_output_on_failure=True,
        )
        if exit_code != 0:
            return run_dir_name, time.time() - start, exit_code

        exit_code = run_solver_script(run_dir, "save_sim.sh")
        if exit_code != 0:
            return run_dir_name, time.time() - start, exit_code

        print(f"  {run_dir_name}: [IMAG] Imaginary-time evolution complete.")
        imag_folder = os.path.join(run_dir, f"{run_dir_name}_imag")
        if os.path.exists(os.path.join(run_dir, "sim_folder")):
            shutil.move(os.path.join(run_dir, "sim_folder"), imag_folder)

        final_wf_imag = os.path.join(imag_folder, "final_wf.dat")
        final_wf_parent = os.path.join(run_dir, "final_wf.dat")
        final_wf_src = (
            final_wf_imag if os.path.isfile(final_wf_imag) else final_wf_parent
        )
        if os.path.isfile(final_wf_src):
            shutil.copy2(final_wf_src, os.path.join(run_dir, "initial_wf.dat"))

        if imag_only:
            print(f"  {run_dir_name}: Skipping real-time evolution (IMAG_ONLY mode)")
            cleanup_real_time_artifacts(run_dir, run_dir_name)
        else:
            # Discard imag folder — only initial_wf.dat is needed for real time
            if os.path.exists(imag_folder):
                shutil.rmtree(imag_folder)

            shutil.copy2(
                os.path.join(run_dir, "di_modified.dat"),
                os.path.join(run_dir, "dtap_inputs.dat"),
            )
            shutil.copy2(
                os.path.join(run_dir, "gi_real_modified.dat"),
                os.path.join(run_dir, "rfgpe_2d_solver_general_inputs.dat"),
            )

            exit_code = run_solver_script(run_dir, "run_rfgpe_2d_solver.sh")
            if exit_code != 0:
                return run_dir_name, time.time() - start, exit_code

            exit_code = run_solver_script(run_dir, "save_sim.sh")
            if exit_code != 0:
                return run_dir_name, time.time() - start, exit_code

            real_folder = os.path.join(run_dir, f"{run_dir_name}_real")
            if os.path.exists(os.path.join(run_dir, "sim_folder")):
                shutil.move(os.path.join(run_dir, "sim_folder"), real_folder)

        for tmp_file in [
            "di_modified.dat",
            "gi_imag_modified.dat",
            "gi_real_modified.dat",
        ]:
            tmp_path = os.path.join(run_dir, tmp_file)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        cleanup_run_directory(run_dir)

        elapsed = time.time() - start
        return run_dir_name, elapsed, 0

    except Exception as e:
        elapsed = time.time() - start
        print(f"Error in {run_dir_name}: {e}")
        return run_dir_name, elapsed, -1


def prompt_batch_inputs_ubmax_sweep():
    print("=" * 60)
    print("BATCH RUN - Ubmax Sweep (fixed omega)")
    print("=" * 60)

    omega = float(input("Enter omega_rf value (e.g., 0.23): "))
    t_start = float(input("Enter temperature T start value (in nK, e.g., 40.0): "))
    t_end = float(
        input("Enter temperature T end value (inclusive, in nK, e.g., 50.0): ")
    )
    num_runs = int(input("Enter number of temperature values (e.g., 6): "))
    diag_stride = int(
        input("Enter diag_stride (diagnostics every N steps, 0=skip, e.g., 10): ")
    )

    _print_template_status()

    t_values = np.round(np.linspace(t_start, t_end, num=num_runs), 4)
    ubmax_values = [ubmax_scaled_from_T_nK(t) for t in t_values]

    print("\n--- Configuration Summary ---")
    print(f"  Sweep mode: Ubmax (fixed omega={omega})")
    print(f"  Temperature range: {t_start} to {t_end} nK ({num_runs} values)")
    print(f"  Ubmax (SEU) range: {ubmax_values[0]:.2f} to {ubmax_values[-1]:.2f}")
    print(f"  diag_stride: {diag_stride}")

    confirm = input("\nProceed with these settings? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted by user.")
        return None

    return {
        "mode": "ubmax",
        "omega": omega,
        "t_start": t_start,
        "t_end": t_end,
        "num_runs": num_runs,
        "diag_stride": diag_stride,
    }


def prompt_batch_inputs_omega_sweep():
    print("=" * 60)
    print("BATCH RUN - Omega Sweep (fixed Ubmax)")
    print("=" * 60)

    t_nk = float(input("Enter temperature T (in nK, e.g., 85.0): "))
    omega_start = float(input("Enter omega_rf start value (e.g., 0.0): "))
    omega_end = float(input("Enter omega_rf end value (e.g., 0.5): "))
    num_runs = int(input("Enter number of omega values (e.g., 11): "))
    diag_stride = int(
        input("Enter diag_stride (diagnostics every N steps, 0=skip, e.g., 10): ")
    )

    _print_template_status()

    ubmax_seu = ubmax_scaled_from_T_nK(t_nk)
    omega_values = np.round(np.linspace(omega_start, omega_end, num=num_runs), 4)

    print("\n--- Configuration Summary ---")
    print(f"  Sweep mode: Omega (fixed T={t_nk} nK, Ubmax={ubmax_seu:.2f} SEU)")
    print(f"  Omega range: {omega_start} to {omega_end} ({num_runs} values)")
    print(f"  Omega values: {list(omega_values)}")
    print(f"  diag_stride: {diag_stride}")

    confirm = input("\nProceed with these settings? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted by user.")
        return None

    return {
        "mode": "omega",
        "t_nk": t_nk,
        "omega_start": omega_start,
        "omega_end": omega_end,
        "num_runs": num_runs,
        "diag_stride": diag_stride,
    }


def prompt_batch_inputs():
    if get_sweep_mode() == "omega":
        return prompt_batch_inputs_omega_sweep()
    return prompt_batch_inputs_ubmax_sweep()


def run_batch():
    params = prompt_batch_inputs()
    if params is None:
        return

    imag_only_mode = is_imag_only_mode()
    if imag_only_mode:
        print("\n" + "=" * 60)
        print("IMAGINARY TIME ONLY MODE ENABLED")
        print("Real-time simulations will be SKIPPED")
        print("=" * 60 + "\n")

    num_runs = params["num_runs"]
    diag_stride = params["diag_stride"]
    script_start = time.time()
    geometry_mode = get_geometry_mode()

    if params["mode"] == "omega":
        t_nk = params["t_nk"]
        omega_start = params["omega_start"]
        omega_end = params["omega_end"]

        ubmax_seu = ubmax_scaled_from_T_nK(t_nk)
        omega_values = np.round(np.linspace(omega_start, omega_end, num=num_runs), 4)

        print(f"\nOmega values: {list(omega_values)}")
        print(f"Fixed Ubmax (SEU): {ubmax_seu:.4f}")

        run_dirs = [
            _prepare_single_1x1_run(omega, ubmax_seu, diag_stride, geometry_mode)
            for omega in omega_values
        ]
        log_header = (
            f"(T={t_nk}nK, Ubmax={ubmax_seu:.4f}, omega in [{omega_start},{omega_end}], "
            f"n={num_runs}, diag_stride={diag_stride}, geometry={geometry_mode})\n"
        )
    else:
        omega = params["omega"]
        t_start = params["t_start"]
        t_end = params["t_end"]

        t_values = np.round(np.linspace(t_start, t_end, num=num_runs), 4)
        print(f"\nTemperature values (nK): {t_values}")

        ubmax_values = [ubmax_scaled_from_T_nK(t) for t in t_values]
        print(f"Ubmax (SEU) values: {[f'{ub:.4f}' for ub in ubmax_values]}")

        run_dirs = [
            _prepare_single_1x1_run(omega, ubmax_seu, diag_stride, geometry_mode)
            for ubmax_seu in ubmax_values
        ]
        log_header = (
            f"(omega={omega}, T in [{t_start},{t_end}]nK, "
            f"n={num_runs}, diag_stride={diag_stride}, geometry={geometry_mode})\n"
        )

    print(f"\nCreated {len(run_dirs)} run directories. Starting simulations...\n")

    log_path = build_execution_log_path(script_start)
    with open(log_path, "w") as log:
        write_execution_log_header(
            log=log,
            script_start=script_start,
            log_header=log_header,
            template_name="template/",
            imag_only=imag_only_mode,
        )

        for run_dir_name in run_dirs:
            run_dir_name_result, elapsed, exit_code = run_simulation(
                run_dir_name,
                imag_only_mode,
            )
            write_execution_log_result(log, run_dir_name_result, elapsed, exit_code)
            print(
                f"  Completed: {run_dir_name_result} ({elapsed:.2f}s, exit_code={exit_code})"
            )

        script_elapsed = write_execution_log_total_runtime(log, script_start)
        print(f"\nTotal runtime: {script_elapsed:.2f}s")


def run_single_1x1(
    omega: float,
    ubmax_seu: float,
    diag_stride: int,
    geometry_mode: str | None = None,
) -> tuple[str, float, int]:
    validate_template_dir(TEMPLATE_DIR)
    mode = geometry_mode or get_geometry_mode()
    run_dir_name = _prepare_single_1x1_run(omega, ubmax_seu, diag_stride, mode)
    return run_simulation(run_dir_name, is_imag_only_mode())


def run_single_ubmax(
    omega: float,
    ubmax_nK: float,
    diag_stride: int,
) -> tuple[str, float, int]:
    ubmax_seu = ubmax_scaled_from_T_nK(ubmax_nK)
    return run_single_1x1(omega, ubmax_seu, diag_stride, get_geometry_mode())
