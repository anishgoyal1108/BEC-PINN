import time
from typing import TextIO

from .settings import get_execution_log_path


def print_simulation_debug(
    run_dir_name: str, imag_only: bool, global_imag_only: bool
) -> None:
    if imag_only:
        print(
            f"  [DEBUG] {run_dir_name}: imag_only={imag_only}, IMAG_ONLY={global_imag_only}, will SKIP real-time"
        )
    else:
        print(
            f"  [DEBUG] {run_dir_name}: imag_only={imag_only}, IMAG_ONLY={global_imag_only}, will RUN real-time"
        )


def build_execution_log_path(script_start: float) -> str:
    """Path for run execution log: output/log/run_log_fast_{timestamp}.txt"""
    return get_execution_log_path(script_start)


def write_execution_log_header(
    log: TextIO,
    script_start: float,
    log_header: str,
    template_name: str,
    cached_ground_state: bool = False,
    imag_only: bool = False,
) -> None:
    log.write(
        f"Run started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(script_start))} "
        + log_header
        + f"Using {template_name} (with transfer physics and OpenMP)\n"
    )
    if cached_ground_state:
        log.write(
            "Using cached ground state for omega_r (imag time skipped for repeated Ubmax values)\n"
        )
    if imag_only:
        log.write("IMAGINARY TIME ONLY MODE: Real-time simulations will be skipped\n")
    log.flush()


def write_execution_log_result(
    log: TextIO,
    run_dir_name: str,
    elapsed: float,
    exit_code: int,
) -> None:
    omega_str = run_dir_name.split("_")[1] if "_" in run_dir_name else "unknown"
    log.write(
        f"  {run_dir_name} (OmegaR={omega_str}): {elapsed:.2f}s, exit_code={exit_code}\n"
    )
    log.flush()


def write_execution_log_total_runtime(log: TextIO, script_start: float) -> float:
    script_elapsed = time.time() - script_start
    log.write(f"Total script runtime: {script_elapsed:.2f}s\n\n")
    log.flush()
    return script_elapsed
