import os
import re

from .settings import SCRIPT_DIR, get_sweep_mode

# New-style run directories (current layout), e.g.:
#   om_0.2300_ub_0396.0_geom_ring
RUN_DIR_PATTERN = re.compile(
    r"^om_([\d.]+)_ub_([\d.]+)(?:_2x2_k(\d+))?_geom_(ring|target)(?:_r(\d+))?$"
)

# Backwards-compatible legacy runs:
#   - Older directories may not include the geometry suffix but DO include omega and Ubmax,
#     with subdirectories containing '_imag' and '_real'.
#   - Example: om_0.2300_ub_0396.0_wp_1.1250
LEGACY_RUN_DIR_PATTERN = re.compile(
    r"^om_([\d.]+)_ub_([\d.]+)_wp_([\d.]+)$"
)


def _scan_runs() -> list[dict]:
    run_infos: list[dict] = []
    for name in os.listdir(SCRIPT_DIR):
        path = os.path.join(SCRIPT_DIR, name)
        if not os.path.isdir(path):
            continue

        match = RUN_DIR_PATTERN.match(name)
        legacy_match = None

        if match:
            omega, ub, experiment_k, geom, _suffix = match.groups()
            run_infos.append(
                {
                    "dir_name": name,
                    "omega": float(omega),
                    "ub": ub,
                    "ub_float": float(ub),
                    "geometry": geom,
                    "path": path,
                    "run_kind": "2x2" if experiment_k is not None else "1x1",
                    "experiment_k": int(experiment_k) if experiment_k is not None else None,
                }
            )
            continue

        # Try legacy naming pattern (no explicit geometry suffix, but includes omega and Ubmax)
        legacy_match = LEGACY_RUN_DIR_PATTERN.match(name)
        if legacy_match:
            omega, ub, _wp = legacy_match.groups()
            run_infos.append(
                {
                    "dir_name": name,
                    "omega": float(omega),
                    "ub": ub,
                    "ub_float": float(ub),
                    # Assume 1x1 ring geometry for legacy runs unless encoded elsewhere
                    "geometry": "ring",
                    "path": path,
                    "run_kind": "1x1",
                    "experiment_k": None,
                }
            )
    return run_infos


def find_existing_runs() -> dict:
    mode = get_sweep_mode()
    runs_grouped = {}
    for run_info in _scan_runs():
        key = run_info["ub"] if mode == "omega" else f"{run_info['omega']:.4f}"
        runs_grouped.setdefault(key, []).append(run_info)

    for key in runs_grouped:
        if mode == "omega":
            runs_grouped[key].sort(key=lambda x: x["omega"])
        else:
            runs_grouped[key].sort(key=lambda x: x["ub_float"])
    return runs_grouped


def find_runs_grouped_by_omega() -> dict[str, list[dict]]:
    runs_grouped: dict[str, list[dict]] = {}
    for run_info in _scan_runs():
        key = f"{run_info['omega']:.4f}"
        runs_grouped.setdefault(key, []).append(run_info)

    for key in runs_grouped:
        runs_grouped[key].sort(key=lambda x: x["ub_float"])
    return runs_grouped


def find_sim_folder(run_dir: str, run_dir_name: str, phase: str):
    folder_name = f"{run_dir_name}_{phase}"
    folder = os.path.join(run_dir, folder_name)
    if os.path.isdir(folder):
        return folder
    return None
