import os
import shutil

from .settings import get_imag_only_mode


def is_imag_only_mode() -> bool:
    return get_imag_only_mode()


def cleanup_real_time_artifacts(run_dir: str, run_dir_name: str) -> None:
    real_folder = os.path.join(run_dir, f"{run_dir_name}_real")
    if os.path.exists(real_folder):
        print(
            f"  {run_dir_name}: WARNING - Found existing _real folder, removing it (imag-only mode)"
        )
        shutil.rmtree(real_folder)

    sim_folder = os.path.join(run_dir, "sim_folder")
    if os.path.exists(sim_folder):
        print(
            f"  {run_dir_name}: WARNING - Found sim_folder, removing it (imag-only mode)"
        )
        shutil.rmtree(sim_folder)
