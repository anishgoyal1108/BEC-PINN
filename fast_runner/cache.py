import glob
import os
import shutil

from .settings import get_geometry_mode, get_omega_cache_dir, get_mode_cache_dir, SCRIPT_DIR
from .solver import run_solver_script


def get_omega_cache_path(
    omega: float,
    cache_dir: str | None = None,
    geometry_mode: str | None = None,
) -> str:
    mode = (geometry_mode or get_geometry_mode()).lower()
    target_dir = cache_dir or get_omega_cache_dir("1x1", mode)
    return os.path.join(target_dir, f"ground_state_geom_{mode}_omega_{omega:.4f}.dat")


def check_omega_cache_exists(
    omega: float,
    cache_dir: str | None = None,
    geometry_mode: str | None = None,
) -> bool:
    return os.path.isfile(get_omega_cache_path(omega, cache_dir, geometry_mode))


def find_or_create_ground_state_omega(
    omega: float,
    run_dirs: list,
    cache_dir: str | None = None,
    geometry_mode: str | None = None,
) -> str | None:
    mode = (geometry_mode or get_geometry_mode()).lower()
    target_dir = cache_dir or get_omega_cache_dir("1x1", mode)
    cache_path = get_omega_cache_path(omega, target_dir, mode)

    if os.path.isfile(cache_path):
        print(f"  Found cached ground state for omega={omega:.4f}: {cache_path}")
        return cache_path

    if not run_dirs:
        print(f"  No run directories provided for omega={omega:.4f}")
        return None

    for run_dir_name in run_dirs:
        run_dir = os.path.join(SCRIPT_DIR, run_dir_name)
        imag_folder = os.path.join(run_dir, f"{run_dir_name}_imag")
        final_wf = os.path.join(imag_folder, "final_wf.dat")
        if os.path.isfile(final_wf):
            print(f"  Found existing ground state in {run_dir_name}/_imag")
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(final_wf, cache_path)
            print(f"  cached to: {cache_path}")
            return cache_path

    for run_dir_name in run_dirs:
        run_dir = os.path.join(SCRIPT_DIR, run_dir_name)
        real_folder = os.path.join(run_dir, f"{run_dir_name}_real")
        if os.path.isdir(real_folder):
            continue

        final_wf = os.path.join(run_dir, "final_wf.dat")
        if os.path.isfile(final_wf):
            print(f"  Found ground state in {run_dir_name} (no real-time run yet)")
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(final_wf, cache_path)
            print(f"  cached to: {cache_path}")
            return cache_path

    print(f"  No cached ground state found for omega={omega:.4f}.")
    print("  Running imaginary time on first directory to create cache...")
    first_run = run_dirs[0]
    run_dir = os.path.join(SCRIPT_DIR, first_run)

    shutil.copy2(
        os.path.join(run_dir, "di_modified.dat"),
        os.path.join(run_dir, "dtap_inputs.dat"),
    )
    shutil.copy2(
        os.path.join(run_dir, "gi_imag_modified.dat"),
        os.path.join(run_dir, "rfgpe_2d_solver_general_inputs.dat"),
    )

    exit_code = run_solver_script(run_dir, "run_rfgpe_2d_solver.sh")
    if exit_code != 0:
        print(f"  Error running imaginary time: exit_code={exit_code}")
        return None

    exit_code = run_solver_script(run_dir, "save_sim.sh")
    if exit_code != 0:
        print(f"  Error saving simulation: exit_code={exit_code}")
        return None

    imag_folder = os.path.join(run_dir, f"{first_run}_imag")
    if os.path.exists(os.path.join(run_dir, "sim_folder")):
        shutil.move(os.path.join(run_dir, "sim_folder"), imag_folder)

    final_wf = os.path.join(run_dir, "final_wf.dat")
    if os.path.isfile(final_wf):
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(final_wf, cache_path)
        print(f"  Ground state cached to: {cache_path}")
        return cache_path

    return None


def manage_omega_cache():
    mode = get_geometry_mode().lower()
    cache_dir = get_omega_cache_dir("1x1", mode)
    mode_dir = get_mode_cache_dir(mode)
    print("=" * 60)
    print("OMEGA_R GROUND STATE CACHE")
    print("=" * 60)
    print("\n  THEORY: Ground state depends only on omega_r, not Ubmax.")
    print("  Caching allows skipping imaginary time for Ubmax sweeps.")
    print(f"\n  mode: {mode.upper()}")
    print(f"  cache directory: {cache_dir}")
    print(f"  mode cache root: {mode_dir}")

    if os.path.isdir(cache_dir):
        cache_files = glob.glob(os.path.join(cache_dir, "ground_state_*.dat"))
        if cache_files:
            print("\n  cached omega values:")
            total_size = 0
            for cf in sorted(cache_files):
                fname = os.path.basename(cf)
                omega_str = (
                    fname.replace("ground_state_geom_ring_omega_", "")
                    .replace("ground_state_geom_target_omega_", "")
                    .replace(".dat", "")
                )
                size = os.path.getsize(cf)
                total_size += size
                print(f"    omega = {omega_str} ({size / (1024*1024):.1f} MB)")
            print(f"\n  Total cache size: {total_size / (1024*1024):.1f} MB")
        else:
            print("\n  cache directory is empty.")
            print("  cache will be created automatically during Ubmax sweeps.")
            return
    else:
        print("\n  No cache found.")
        print("  cache will be created automatically during Ubmax sweeps.")
        return

    print("\n  Options:")
    print("    1. Delete all caches")
    print("    2. Delete specific omega cache")
    print("    0. Back to main menu")

    choice = input("\n  Select: ").strip()

    if choice == "1":
        confirm = input("  Delete ALL cached ground states? (y/n): ").strip().lower()
        if confirm == "y":
            shutil.rmtree(cache_dir)
            print("  All caches deleted.")
    elif choice == "2":
        cache_files = glob.glob(os.path.join(cache_dir, "ground_state_*.dat"))
        if cache_files:
            print("\n  Select omega to delete:")
            sorted_files = sorted(cache_files)
            for i, cf in enumerate(sorted_files, 1):
                fname = os.path.basename(cf)
                omega_str = (
                    fname.replace("ground_state_geom_ring_omega_", "")
                    .replace("ground_state_geom_target_omega_", "")
                    .replace(".dat", "")
                )
                print(f"    {i}. omega = {omega_str}")
            print("    0. Cancel")
            sel = input("  Select: ").strip()
            try:
                idx = int(sel)
                if 1 <= idx <= len(sorted_files):
                    os.remove(sorted_files[idx - 1])
                    print("  cache deleted.")
            except (ValueError, IndexError):
                pass
