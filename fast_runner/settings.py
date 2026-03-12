import glob
import os
import time

RELEASE_LINE_INDEX = 7450

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "template")
TEMPLATE_REQUIRED_FILES = (
    "dtap_inputs.dat",
    "rfgpe_2d_solver_general_inputs.dat",
    "rfgpe_2d_solver.f",
    "Makefile",
    "run_rfgpe_2d_solver.sh",
    "save_sim.sh",
)

OUTPUT_LOG_DIR = os.path.join(SCRIPT_DIR, "output", "log")
OUTPUT_DAT_DIR = os.path.join(SCRIPT_DIR, "output", "dat")
OUTPUT_PNG_DIR = os.path.join(SCRIPT_DIR, "output", "png")


def ensure_output_dirs() -> None:
    """Create output/log, output/dat, output/png if they do not exist."""
    os.makedirs(OUTPUT_LOG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DAT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_PNG_DIR, exist_ok=True)


def get_execution_log_path(script_start: float) -> str:
    """Path for batch/run execution log: output/log/run_log_fast_{timestamp}.txt"""
    ensure_output_dirs()
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(script_start))
    return os.path.join(OUTPUT_LOG_DIR, f"run_log_fast_{timestamp}.txt")


def _output_geom_suffix(geometry_mode: str | None = None) -> str:
    """Lowercase geometry for output file names: target or ring."""
    return (geometry_mode or get_geometry_mode()).lower()


def get_transfer_log_path_omega(
    omega_key: str, geometry_mode: str | None = None
) -> str:
    """Path for omega-sweep transfer search log: output/log/om_{key}_geom_{mode}.txt"""
    ensure_output_dirs()
    mode = _output_geom_suffix(geometry_mode)
    return os.path.join(OUTPUT_LOG_DIR, f"om_{omega_key}_geom_{mode}.txt")


def get_transfer_log_path_ubmax(
    ubmax_nk: float, geometry_mode: str | None = None
) -> str:
    """Path for ubmax-sweep transfer search log: output/log/ub_{ubmax_nk}_geom_{mode}.txt"""
    ensure_output_dirs()
    mode = _output_geom_suffix(geometry_mode)
    return os.path.join(OUTPUT_LOG_DIR, f"ub_{ubmax_nk:.4f}_geom_{mode}.txt")


def get_circulation_png_path(run_dir_name: str) -> str:
    """Path for circulation plot: output/png/{run_dir_name}_circulation.png"""
    ensure_output_dirs()
    return os.path.join(OUTPUT_PNG_DIR, f"{run_dir_name}_circulation.png")


def get_density_frames_dir() -> str:
    """Directory for density frames: output/png/density"""
    ensure_output_dirs()
    path = os.path.join(OUTPUT_PNG_DIR, "density")
    os.makedirs(path, exist_ok=True)
    return path


def get_phase_frames_dir() -> str:
    """Directory for phase frames: output/png/phase"""
    ensure_output_dirs()
    path = os.path.join(OUTPUT_PNG_DIR, "phase")
    os.makedirs(path, exist_ok=True)
    return path


def get_transfer_summary_png_path_ubmax(
    omega: float, geometry_mode: str | None = None
) -> str:
    """Path for transfer-vs-ubmax summary plot: output/png/transfer_vs_ubmax_omega_{omega}_geom_{mode}.png"""
    ensure_output_dirs()
    mode = _output_geom_suffix(geometry_mode)
    return os.path.join(
        OUTPUT_PNG_DIR,
        f"transfer_vs_ubmax_omega_{omega:.4f}_geom_{mode}.png",
    )


def get_transfer_summary_png_path_omega(
    ubmax_seu: float, geometry_mode: str | None = None
) -> str:
    """Path for transfer-vs-omega summary plot: output/png/transfer_vs_omega_ubmax_{ubmax_seu}_geom_{mode}.png"""
    ensure_output_dirs()
    mode = _output_geom_suffix(geometry_mode)
    return os.path.join(
        OUTPUT_PNG_DIR,
        f"transfer_vs_omega_ubmax_{ubmax_seu:.4f}_geom_{mode}.png",
    )


def get_critical_summary_png_path(geometry_mode: str | None = None) -> str:
    """Path for critical-omega-vs-ubmax summary plot: output/png/critical_omega_vs_ubmax_geom_{mode}.png"""
    ensure_output_dirs()
    mode = _output_geom_suffix(geometry_mode)
    return os.path.join(OUTPUT_PNG_DIR, f"critical_omega_vs_ubmax_geom_{mode}.png")


TOLERANCE_NK = 1.5
WINDOW_TARGET_NK = 0.1
FALLBACK_SCAN_STEP_NK = 0.05
BOOTSTRAP_LEFT_NK = 40.0
BOOTSTRAP_RIGHT_NK = 50.0
BOOTSTRAP_STEP_NK = 2.0
BOOTSTRAP_RIGHT_MAX_NK = 48.6
OMEGA_ZERO_FIRST_TRANSFER_NK = 48.5
BINARY_SEARCH_MAX_ITER = 500
UB_NK_MATCH_TOLERANCE = 0.025

NUM_FRAME_WORKERS = 8

CACHE_ROOT = os.path.join(SCRIPT_DIR, "cache")

_SWEEP_MODE = "ubmax"
_GEOMETRY_MODE = "ring"
_IMAG_ONLY_MODE = False


def get_sweep_mode() -> str:
    return _SWEEP_MODE


def toggle_sweep_mode() -> str:
    global _SWEEP_MODE
    _SWEEP_MODE = "omega" if _SWEEP_MODE == "ubmax" else "ubmax"
    return _SWEEP_MODE


def get_geometry_mode() -> str:
    return _GEOMETRY_MODE


def toggle_geometry_mode() -> str:
    global _GEOMETRY_MODE
    _GEOMETRY_MODE = "target" if _GEOMETRY_MODE == "ring" else "ring"
    return _GEOMETRY_MODE


def get_imag_only_mode() -> bool:
    return _IMAG_ONLY_MODE


def toggle_imag_only_mode() -> bool:
    global _IMAG_ONLY_MODE
    _IMAG_ONLY_MODE = not _IMAG_ONLY_MODE
    return _IMAG_ONLY_MODE


def _mode_token(mode: str | None = None) -> str:
    geometry_mode = (mode or get_geometry_mode()).lower()
    if geometry_mode == "target":
        return "TARGET"
    return "RING"


def get_mode_cache_dir(mode: str | None = None) -> str:
    cache_dir = os.path.join(CACHE_ROOT, _mode_token(mode))
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_omega_cache_dir(run_kind: str, mode: str | None = None) -> str:
    if run_kind not in ("1x1", "2x2"):
        raise ValueError(f"Invalid run_kind: {run_kind}")
    cache_dir = os.path.join(get_mode_cache_dir(mode), f"OmegaR_{run_kind}")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_critical_omega_cache_path(mode: str | None = None) -> str:
    """Path for critical-omega vs ubmax data: output/dat/critical_omega_vs_ubmax_geom_{mode}.dat"""
    ensure_output_dirs()
    return os.path.join(
        OUTPUT_DAT_DIR,
        f"critical_omega_vs_ubmax_geom_{_output_geom_suffix(mode)}.dat",
    )


def _initialize_cache_layout() -> None:
    for mode in ("ring", "target"):
        get_mode_cache_dir(mode)
        get_omega_cache_dir("1x1", mode)
        get_omega_cache_dir("2x2", mode)


_initialize_cache_layout()


def get_cache_status_summary() -> str:
    cache_dir = get_omega_cache_dir("1x1")
    if os.path.isdir(cache_dir):
        cache_files = glob.glob(os.path.join(cache_dir, "ground_state_*.dat"))
        if cache_files:
            return f"{len(cache_files)} omega value(s) cached"
    return "none"
