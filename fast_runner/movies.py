import glob
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor

from .runs import find_existing_runs, find_sim_folder
from .settings import (
    NUM_FRAME_WORKERS,
    OUTPUT_PNG_DIR,
    get_density_frames_dir,
    get_phase_frames_dir,
)
from .ui import (
    build_group_options,
    build_secondary_options,
    checkbox_menu,
    select_from_menu,
)
from .viewer import open_files_in_viewer


def parse_frame_range(frame_str: str, available_range: tuple[int, int]) -> list[int]:
    min_frame, max_frame = available_range
    frame_numbers = set()
    parts = [p.strip() for p in frame_str.split(",")]

    for part in parts:
        if not part:
            continue
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                start = int(start_str.strip())
                end = int(end_str.strip())
                if start > end:
                    print(f"  Warning: Invalid range {part} (start > end), skipping")
                    continue

                start = max(start, min_frame)
                end = min(end, max_frame)

                if start <= end:
                    frame_numbers.update(range(start, end + 1))
            except ValueError:
                print(f"  Warning: Invalid range format '{part}', skipping")
                continue
        else:
            try:
                frame_num = int(part.strip())
                if min_frame <= frame_num <= max_frame:
                    frame_numbers.add(frame_num)
                else:
                    print(
                        f"  Warning: Frame {frame_num} out of range [{min_frame}, {max_frame}], skipping"
                    )
            except ValueError:
                print(f"  Warning: Invalid frame number '{part}', skipping")
                continue

    return sorted(frame_numbers)


def _get_frame_range(folder: str) -> tuple[int, int] | None:
    pattern = re.compile(r"wf_ascii_(\d+)\.dat")
    indices = []
    for f in glob.glob(os.path.join(folder, "wf_ascii_*.dat")):
        m = pattern.search(os.path.basename(f))
        if m:
            indices.append(int(m.group(1)))
    if not indices:
        return None
    return min(indices), max(indices)


def _run_gnuplot_chunk(folder: str, script_name: str, start: int, end: int) -> bool:
    script_path = os.path.join(folder, script_name)
    if not os.path.isfile(script_path):
        return False
    with open(script_path) as f:
        content = f.read()

    content = re.sub(r"do for \[i=\d+:\d+\]", f"do for [i={start}:{end}]", content)
    temp_script = os.path.join(folder, f"_temp_{script_name}.{start}_{end}")
    try:
        with open(temp_script, "w") as f:
            f.write(content)
        result = subprocess.run(
            ["gnuplot", temp_script],
            cwd=folder,
            capture_output=True,
        )
        return result.returncode == 0
    finally:
        if os.path.isfile(temp_script):
            os.remove(temp_script)


def _run_gnuplot_frame(
    folder: str,
    script_name: str,
    frame_num: int,
    output_dir: str,
    output_name: str,
    bare_plot: bool = False,
) -> bool:
    if os.path.isabs(script_name):
        script_path = script_name
    else:
        script_path = os.path.join(folder, script_name)
    if not os.path.isfile(script_path):
        return False

    with open(script_path) as f:
        content = f.read()

    os.makedirs(output_dir, exist_ok=True)
    output_path_abs = os.path.abspath(os.path.join(output_dir, output_name))

    content = re.sub(
        r"do for \[i=\d+:\d+\]", f"do for [i={frame_num}:{frame_num}]", content
    )

    content = re.sub(r"set term\s+gif", "set term png", content, flags=re.IGNORECASE)
    content = re.sub(
        r"set terminal\s+gif", "set terminal png", content, flags=re.IGNORECASE
    )

    content = re.sub(
        r'set output\s+"[^"]*"\.i\.[^"]*"', f'set output "{output_path_abs}"', content
    )
    content = re.sub(
        r"set output\s+'[^']*'\.i\.[^']*'", f'set output "{output_path_abs}"', content
    )
    content = re.sub(
        r'set output\s+sprintf\("[^"]*",\s*i\)',
        f'set output "{output_path_abs}"',
        content,
    )
    content = re.sub(
        r"set output\s+sprintf\('[^']*',\s*i\)",
        f'set output "{output_path_abs}"',
        content,
    )
    content = re.sub(
        r'set output\s+"[^"]*"\.sprintf\("[^"]*",\s*i\)\.[^"]*"',
        f'set output "{output_path_abs}"',
        content,
    )
    content = re.sub(
        r"set output\s+'[^']*'\.sprintf\('[^']*',\s*i\)\.[^']*'",
        f'set output "{output_path_abs}"',
        content,
    )

    if "set term" not in content.lower() and "set terminal" not in content.lower():
        content = re.sub(r"(set output)", r"set term png\n\1", content, count=1)

    if bare_plot:
        content = re.sub(
            r"^\s*set\s+xlabel\s+[^\n]*\n",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        content = re.sub(
            r"^\s*set\s+ylabel\s+[^\n]*\n",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        content = re.sub(
            r"^\s*set\s+xtics\s+[^\n]*\n",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        content = re.sub(
            r"^\s*set\s+ytics\s+[^\n]*\n",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        content = re.sub(
            r"^\s*set\s+title\s+[^\n]*\n",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        content = re.sub(
            r"^\s*set\s+border\s+[^\n]*\n",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        content = re.sub(
            r"set term\s+png\b[^ \n]*",
            'set term png size 600,600 background rgb "#000080"',
            content,
            flags=re.IGNORECASE,
        )
        bare_commands = (
            "unset border\n"
            "unset key\n"
            "unset colorbox\n"
            "unset xtics\n"
            "unset ytics\n"
            "unset xlabel\n"
            "unset ylabel\n"
            "unset title\n"
            "set lmargin at screen 0\n"
            "set rmargin at screen 1\n"
            "set tmargin at screen 1\n"
            "set bmargin at screen 0\n"
        )
        content = bare_commands + content

    script_basename = os.path.basename(script_path)
    temp_script = os.path.join(folder, f"_temp_{script_basename}.{frame_num}")
    try:
        with open(temp_script, "w") as f:
            f.write(content)
        result = subprocess.run(
            ["gnuplot", temp_script],
            cwd=folder,
            capture_output=True,
        )
        success = result.returncode == 0 and os.path.isfile(output_path_abs)
        return success
    finally:
        if os.path.isfile(temp_script):
            os.remove(temp_script)


def _combine_frames_to_movie(folder: str, frame_pattern: str, output_name: str) -> bool:
    frames = sorted(glob.glob(os.path.join(folder, frame_pattern)))
    if not frames:
        return False
    subprocess.run(
        ["magick", "-delay", "10", "-loop", "0"] + frames + [output_name],
        cwd=folder,
    )
    return os.path.isfile(output_name)


def _chunk_range(lo: int, hi: int, n: int) -> list[tuple[int, int]]:
    if n <= 1:
        return [(lo, hi)]
    total = hi - lo + 1
    base, extra = divmod(total, n)
    chunks = []
    pos = lo
    for i in range(n):
        size = base + (1 if i < extra else 0)
        if size > 0:
            chunks.append((pos, pos + size - 1))
            pos += size
    return chunks


def create_movies(folder: str, phase: str):
    density_gnu = os.path.join(folder, "density_distribution_movie.gnu")
    phase_gnu = os.path.join(folder, "phase_distribution_movie.gnu")

    if not os.path.isfile(density_gnu):
        print("  Warning: density_distribution_movie.gnu not found")
    if not os.path.isfile(phase_gnu):
        print("  Warning: phase_distribution_movie.gnu not found")

    frame_range = _get_frame_range(folder)
    if frame_range is None:
        print("  No wf_ascii_*.dat files found, skipping frame generation")
        return False

    lo, hi = frame_range
    num_frames = hi - lo + 1
    n_workers = min(NUM_FRAME_WORKERS, num_frames)
    chunks = _chunk_range(lo, hi, n_workers)

    print(f"  Creating density and phase frames ({len(chunks)} workers each, {lo}-{hi})...")
    tasks = []
    for start, end in chunks:
        tasks.append(("density_distribution_movie.gnu", start, end))
        tasks.append(("phase_distribution_movie.gnu", start, end))

    with ProcessPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [
            executor.submit(_run_gnuplot_chunk, folder, script, start, end)
            for script, start, end in tasks
        ]
        for f in futures:
            f.result()

    density_movie = os.path.join(folder, f"{phase}_density_movie.gif")
    phase_movie = os.path.join(folder, f"{phase}_phase_movie.gif")

    print("  Combining frames into movies (parallel)...")
    with ProcessPoolExecutor(max_workers=2) as executor:
        density_combine = executor.submit(
            _combine_frames_to_movie,
            folder,
            "density_distribution_*.gif",
            density_movie,
        )
        phase_combine = executor.submit(
            _combine_frames_to_movie,
            folder,
            "phase_distribution_*.gif",
            phase_movie,
        )
        if density_combine.result():
            size_mb = os.path.getsize(density_movie) / (1024 * 1024)
            print(f"  Created: {phase}_density_movie.gif ({size_mb:.1f} MB)")
        if phase_combine.result():
            size_mb = os.path.getsize(phase_movie) / (1024 * 1024)
            print(f"  Created: {phase}_phase_movie.gif ({size_mb:.1f} MB)")

    return True


def create_density_phase_frames(
    folder: str, run_dir_name: str, frame_numbers: list[int], combine_gif: bool
) -> dict:
    density_gnu = os.path.join(folder, "density_distribution_movie.gnu")
    phase_gnu = os.path.join(folder, "phase_distribution_movie.gnu")

    if not os.path.isfile(density_gnu):
        print("  Warning: density_distribution_movie.gnu not found")
        return {
            "density_count": 0,
            "phase_count": 0,
            "density_paths": [],
            "phase_paths": [],
        }
    if not os.path.isfile(phase_gnu):
        print("  Warning: phase_distribution_movie.gnu not found")
        return {
            "density_count": 0,
            "phase_count": 0,
            "density_paths": [],
            "phase_paths": [],
        }

    density_output_dir = get_density_frames_dir()
    phase_output_dir = get_phase_frames_dir()

    tasks = []
    for frame_num in frame_numbers:
        density_output_name = f"{run_dir_name}_real_{frame_num:03d}.png"
        tasks.append(("density", density_gnu, frame_num, density_output_dir, density_output_name))

        phase_output_name = f"{run_dir_name}_real_{frame_num:03d}.png"
        tasks.append(("phase", phase_gnu, frame_num, phase_output_dir, phase_output_name))

    density_paths = []
    phase_paths = []
    density_count = 0
    phase_count = 0

    print(f"  Processing {len(frame_numbers)} frame(s) for density and phase...")

    with ProcessPoolExecutor(max_workers=NUM_FRAME_WORKERS) as executor:
        futures = [
            executor.submit(
                _run_gnuplot_frame,
                folder,
                script_name,
                frame_num,
                output_dir,
                output_name,
                True,
            )
            for frame_type, script_name, frame_num, output_dir, output_name in tasks
        ]

        for i, future in enumerate(futures):
            frame_type, _, _, output_dir, output_name = tasks[i]
            success = future.result()
            output_path = os.path.join(output_dir, output_name)

            if success and os.path.isfile(output_path):
                if frame_type == "density":
                    density_paths.append(output_path)
                    density_count += 1
                else:
                    phase_paths.append(output_path)
                    phase_count += 1

    print(f"  Created {density_count} density frame(s) and {phase_count} phase frame(s)")

    if combine_gif and density_paths and phase_paths:
        print("  Combining frames into GIFs...")
        density_paths_sorted = sorted(density_paths)
        phase_paths_sorted = sorted(phase_paths)

        density_gif = os.path.join(density_output_dir, f"{run_dir_name}_real_density.gif")
        phase_gif = os.path.join(phase_output_dir, f"{run_dir_name}_real_phase.gif")

        if density_paths_sorted:
            result = subprocess.run(
                ["magick", "-delay", "10", "-loop", "0"] + density_paths_sorted + [density_gif],
                cwd=density_output_dir,
                capture_output=True,
            )
            if result.returncode == 0 and os.path.isfile(density_gif):
                size_mb = os.path.getsize(density_gif) / (1024 * 1024)
                print(f"  Created: {os.path.basename(density_gif)} ({size_mb:.1f} MB)")

        if phase_paths_sorted:
            result = subprocess.run(
                ["magick", "-delay", "10", "-loop", "0"] + phase_paths_sorted + [phase_gif],
                cwd=phase_output_dir,
                capture_output=True,
            )
            if result.returncode == 0 and os.path.isfile(phase_gif):
                size_mb = os.path.getsize(phase_gif) / (1024 * 1024)
                print(f"  Created: {os.path.basename(phase_gif)} ({size_mb:.1f} MB)")

    return {
        "density_count": density_count,
        "phase_count": phase_count,
        "density_paths": density_paths,
        "phase_paths": phase_paths,
    }


def create_density_phase_frames_batch(
    runs_data: list[tuple[str, str, list[int]]],
    combine_gif: bool,
    image_type: str = "both",
) -> dict:
    density_output_dir = get_density_frames_dir()
    phase_output_dir = get_phase_frames_dir()

    do_density = image_type in ("density", "both")
    do_phase = image_type in ("phase", "both")

    tasks = []
    for folder, run_dir_name, frame_numbers in runs_data:
        density_gnu = os.path.join(folder, "density_distribution_movie.gnu")
        phase_gnu = os.path.join(folder, "phase_distribution_movie.gnu")
        if do_density and not os.path.isfile(density_gnu):
            continue
        if do_phase and not os.path.isfile(phase_gnu):
            continue
        if not do_density and not do_phase:
            continue
        for frame_num in frame_numbers:
            if do_density:
                density_output_name = f"{run_dir_name}_real_{frame_num:03d}.png"
                tasks.append(
                    (
                        "density",
                        run_dir_name,
                        folder,
                        density_gnu,
                        frame_num,
                        density_output_dir,
                        density_output_name,
                    )
                )
            if do_phase:
                phase_output_name = f"{run_dir_name}_real_{frame_num:03d}.png"
                tasks.append(
                    (
                        "phase",
                        run_dir_name,
                        folder,
                        phase_gnu,
                        frame_num,
                        phase_output_dir,
                        phase_output_name,
                    )
                )

    if not tasks:
        return {"density_count": 0, "phase_count": 0}

    total_density = 0
    total_phase = 0
    run_density_paths = {}
    run_phase_paths = {}

    print(f"  Processing {len(tasks)} frame(s) in parallel ({NUM_FRAME_WORKERS} workers)...")

    with ProcessPoolExecutor(max_workers=NUM_FRAME_WORKERS) as executor:
        futures = [
            executor.submit(
                _run_gnuplot_frame,
                folder,
                script_path,
                frame_num,
                output_dir,
                output_name,
                True,
            )
            for (
                _ft,
                _rn,
                folder,
                script_path,
                frame_num,
                output_dir,
                output_name,
            ) in tasks
        ]

        for i, future in enumerate(futures):
            (
                frame_type,
                run_dir_name,
                _folder,
                _script_path,
                frame_num,
                output_dir,
                output_name,
            ) = tasks[i]
            success = future.result()
            output_path = os.path.join(output_dir, output_name)

            if success and os.path.isfile(output_path):
                if frame_type == "density":
                    total_density += 1
                    run_density_paths.setdefault(run_dir_name, []).append((output_path, frame_num))
                else:
                    total_phase += 1
                    run_phase_paths.setdefault(run_dir_name, []).append((output_path, frame_num))

    print(f"  Created {total_density} density frame(s) and {total_phase} phase frame(s)")

    if combine_gif:
        for run_dir_name in set(run_density_paths) | set(run_phase_paths):
            density_list = run_density_paths.get(run_dir_name, [])
            phase_list = run_phase_paths.get(run_dir_name, [])
            density_list.sort(key=lambda x: x[1])
            phase_list.sort(key=lambda x: x[1])
            density_paths_sorted = [p for p, _ in density_list]
            phase_paths_sorted = [p for p, _ in phase_list]
            if density_paths_sorted:
                density_gif = os.path.join(density_output_dir, f"{run_dir_name}_real_density.gif")
                subprocess.run(
                    ["magick", "-delay", "10", "-loop", "0"] + density_paths_sorted + [density_gif],
                    cwd=density_output_dir,
                    capture_output=True,
                )
            if phase_paths_sorted:
                phase_gif = os.path.join(phase_output_dir, f"{run_dir_name}_real_phase.gif")
                subprocess.run(
                    ["magick", "-delay", "10", "-loop", "0"] + phase_paths_sorted + [phase_gif],
                    cwd=phase_output_dir,
                    capture_output=True,
                )

    return {"density_count": total_density, "phase_count": total_phase}


def _select_single_run(runs_grouped: dict) -> dict | None:
    group_list, group_label, secondary_label, group_options = build_group_options(runs_grouped)
    print(f"\nFound {len(group_list)} {group_label} values (fixed parameter):\n")
    group_choice = select_from_menu(group_options, f"\nSelect {group_label}: ")
    if group_choice == 0:
        return None

    selected_group = group_list[group_choice - 1]
    runs = runs_grouped[selected_group]

    secondary_options = build_secondary_options(selected_group, runs)
    secondary_choice = select_from_menu(secondary_options, f"\nSelect {secondary_label}: ")
    if secondary_choice == 0:
        return None

    return runs[secondary_choice - 1]


def _select_multiple_runs(runs_grouped: dict) -> list[dict]:
    group_list, group_label, _, group_options = build_group_options(runs_grouped)
    print(f"\nFound {len(group_list)} {group_label} values (fixed parameter):\n")
    group_choice = select_from_menu(group_options, f"\nSelect {group_label}: ")
    if group_choice == 0:
        return []

    selected_group = group_list[group_choice - 1]
    runs = runs_grouped[selected_group]

    secondary_options = build_secondary_options(selected_group, runs)

    print("(Toggle with number, 'a'=all, 'n'=none, 'd'=done, '0'=cancel)")
    selected_indices = checkbox_menu(secondary_options, "\nToggle/command: ")
    if not selected_indices:
        return []
    return [runs[i] for i in selected_indices]


def run_movie_creator():
    print("=" * 60)
    print("MOVIE CREATOR - Select simulation run")
    print("=" * 60)

    runs_grouped = find_existing_runs()

    if not runs_grouped:
        print("\nNo existing simulation runs found.")
        print("Run a batch first to create simulation data.")
        return

    selected_run = _select_single_run(runs_grouped)
    if selected_run is None:
        return

    run_dir = selected_run["path"]
    run_dir_name = selected_run["dir_name"]

    print(f"\nSelected: {run_dir_name}")

    imag_folder = find_sim_folder(run_dir, run_dir_name, "imag")
    real_folder = find_sim_folder(run_dir, run_dir_name, "real")

    print("\nAvailable simulation phases:")
    print(f"  [{'✓' if imag_folder else '✗'}] Imaginary time folder {'found' if imag_folder else 'NOT found'}")
    print(f"  [{'✓' if real_folder else '✗'}] Real time folder {'found' if real_folder else 'NOT found'}")

    if not imag_folder and not real_folder:
        print("\nNo simulation folders found!")
        return

    options = []
    if imag_folder:
        options.append(("imag", "Imaginary time only"))
    if real_folder:
        options.append(("real", "Real time only"))
    if imag_folder and real_folder:
        options.append(("both", "Both imaginary and real time"))

    print("\nCreate movies for:\n")
    choice = select_from_menu([o[1] for o in options], "\nSelect: ")
    if choice == 0:
        return

    selected = options[choice - 1][0]

    folders_to_process = []
    if selected in ("imag", "both"):
        folders_to_process.append(("imag", imag_folder))
    if selected in ("real", "both"):
        folders_to_process.append(("real", real_folder))

    for phase, folder in folders_to_process:
        print(f"\n{'='*40}")
        print(f"Processing {phase.upper()} time folder...")
        print(f"{'='*40}")
        create_movies(folder, phase)

    print(f"\n{'='*60}")
    print("Movie creation complete!")
    print(f"{'='*60}")


def movies_exist(folder, phase: str):
    if folder is None:
        return {"density": False, "phase": False}
    density = os.path.isfile(os.path.join(folder, f"{phase}_density_movie.gif"))
    phase_exists = os.path.isfile(os.path.join(folder, f"{phase}_phase_movie.gif"))
    return {"density": density, "phase": phase_exists}


def run_movie_viewer():
    print("=" * 60)
    print("MOVIE VIEWER - Select simulation run")
    print("=" * 60)

    runs_grouped = find_existing_runs()

    if not runs_grouped:
        print("\nNo existing simulation runs found.")
        return

    selected_run = _select_single_run(runs_grouped)
    if selected_run is None:
        return

    run_dir = selected_run["path"]
    run_dir_name = selected_run["dir_name"]

    print(f"\nSelected: {run_dir_name}")

    imag_folder = find_sim_folder(run_dir, run_dir_name, "imag")
    real_folder = find_sim_folder(run_dir, run_dir_name, "real")

    imag_movies = movies_exist(imag_folder, "imag")
    real_movies = movies_exist(real_folder, "real")

    print("\nMovie availability:")
    print(
        f"  Imaginary: density={'✓' if imag_movies['density'] else '✗'}, phase={'✓' if imag_movies['phase'] else '✗'}"
    )
    print(
        f"  Real:      density={'✓' if real_movies['density'] else '✗'}, phase={'✓' if real_movies['phase'] else '✗'}"
    )

    view_options = []
    if imag_folder:
        view_options.append(("imag_both", "Imaginary: density + phase"))
        view_options.append(("imag_density", "Imaginary: density only"))
        view_options.append(("imag_phase", "Imaginary: phase only"))
    if real_folder:
        view_options.append(("real_both", "Real: density + phase"))
        view_options.append(("real_density", "Real: density only"))
        view_options.append(("real_phase", "Real: phase only"))
    if imag_folder and real_folder:
        view_options.append(("density_compare", "Density: imag + real side-by-side"))
        view_options.append(("phase_compare", "Phase: imag + real side-by-side"))
        view_options.append(("all", "All four movies"))

    if not view_options:
        print("\nNo folders available to view.")
        return

    print("\nView options:\n")
    choice = select_from_menu([o[1] for o in view_options], "\nSelect: ")
    if choice == 0:
        return

    selected = view_options[choice - 1][0]
    movies_to_open = []

    def add_movie(folder, phase: str, movie_type: str, movies_status):
        if folder is None:
            return
        movie_path = os.path.join(folder, f"{phase}_{movie_type}_movie.gif")
        if movies_status[movie_type]:
            movies_to_open.append(movie_path)
        else:
            print(f"\n  {phase.upper()} {movie_type} movie doesn't exist in {os.path.basename(folder)}")
            create = input("  Create it now? (y/n): ").strip().lower()
            if create == "y":
                create_movies(folder, phase)
                if os.path.isfile(movie_path):
                    movies_to_open.append(movie_path)

    if selected == "imag_both":
        add_movie(imag_folder, "imag", "density", imag_movies)
        add_movie(imag_folder, "imag", "phase", imag_movies)
    elif selected == "imag_density":
        add_movie(imag_folder, "imag", "density", imag_movies)
    elif selected == "imag_phase":
        add_movie(imag_folder, "imag", "phase", imag_movies)
    elif selected == "real_both":
        add_movie(real_folder, "real", "density", real_movies)
        add_movie(real_folder, "real", "phase", real_movies)
    elif selected == "real_density":
        add_movie(real_folder, "real", "density", real_movies)
    elif selected == "real_phase":
        add_movie(real_folder, "real", "phase", real_movies)
    elif selected == "density_compare":
        add_movie(imag_folder, "imag", "density", imag_movies)
        add_movie(real_folder, "real", "density", real_movies)
    elif selected == "phase_compare":
        add_movie(imag_folder, "imag", "phase", imag_movies)
        add_movie(real_folder, "real", "phase", real_movies)
    elif selected == "all":
        add_movie(imag_folder, "imag", "density", imag_movies)
        add_movie(imag_folder, "imag", "phase", imag_movies)
        add_movie(real_folder, "real", "density", real_movies)
        add_movie(real_folder, "real", "phase", real_movies)

    if movies_to_open:
        viewer, opened = open_files_in_viewer(movies_to_open)
        print(f"\n  Opening {len(movies_to_open)} movie(s) with {viewer} (separate windows)...")
        if opened < len(movies_to_open):
            print(f"  Warning: opened {opened}/{len(movies_to_open)} file(s).")
    else:
        print("\n  No movies to open.")


def run_mass_density_phase_creator():
    print("=" * 60)
    print("MASS DENSITY/PHASE IMAGE CREATOR - Select simulation runs")
    print("=" * 60)

    runs_grouped = find_existing_runs()

    if not runs_grouped:
        print("\nNo existing simulation runs found.")
        return

    selected_runs = _select_multiple_runs(runs_grouped)
    if not selected_runs:
        print("No runs selected.")
        return

    print(f"\nSelected {len(selected_runs)} run(s).")

    first_run = selected_runs[0]
    first_run_dir = first_run["path"]
    first_run_dir_name = first_run["dir_name"]
    first_real_folder = find_sim_folder(first_run_dir, first_run_dir_name, "real")

    if first_real_folder is None:
        print(f"\nNo real folder found for {first_run_dir_name}. Cannot determine frame range.")
        return

    available_range = _get_frame_range(first_real_folder)
    if available_range is None:
        print(f"\nNo wf_ascii_*.dat files found in {os.path.basename(first_real_folder)}.")
        return

    min_frame, max_frame = available_range
    print(f"\nAvailable frame range: {min_frame} to {max_frame}")

    print("\nEnter frame range (e.g., '1-10', '1,2,3', '1-5,10,20-25'):")
    print("(Leave empty to process all frames)")
    frame_range_input = input("Frame range: ").strip()

    if not frame_range_input:
        frame_numbers = list(range(min_frame, max_frame + 1))
    else:
        frame_numbers = parse_frame_range(frame_range_input, available_range)
        if not frame_numbers:
            print("No valid frames specified.")
            return

    print(f"\nWill process {len(frame_numbers)} frame(s): {frame_numbers[:10]}{'...' if len(frame_numbers) > 10 else ''}")

    print("\nGenerate images:")
    print("  1. Density only")
    print("  2. Phase only")
    print("  3. Both density and phase (default)")
    image_type_input = input("Choice (1/2/3, default=3): ").strip() or "3"
    if image_type_input == "1":
        image_type = "density"
    elif image_type_input == "2":
        image_type = "phase"
    else:
        image_type = "both"

    combine_gif_input = input("\nCombine frames into GIFs? (y/n, default=n): ").strip().lower()
    combine_gif = combine_gif_input == "y"

    runs_data = []
    for run in selected_runs:
        run_dir = run["path"]
        run_dir_name = run["dir_name"]
        real_folder = find_sim_folder(run_dir, run_dir_name, "real")

        if real_folder is None:
            print(f"  Skipping {run_dir_name}: No real folder found")
            continue

        run_range = _get_frame_range(real_folder)
        if run_range is None:
            print(f"  Skipping {run_dir_name}: No wf_ascii_*.dat files found")
            continue

        run_min, run_max = run_range
        valid_frames = [f for f in frame_numbers if run_min <= f <= run_max]

        if not valid_frames:
            print(f"  Skipping {run_dir_name}: No valid frames in range")
            continue

        runs_data.append((real_folder, run_dir_name, valid_frames))

    if not runs_data:
        print("\nNo runs to process.")
        return

    print(f"\nGenerating images for {len(runs_data)} run(s) in one parallel batch...")

    result = create_density_phase_frames_batch(runs_data, combine_gif, image_type)
    total_density = result["density_count"]
    total_phase = result["phase_count"]

    print(f"\n{'='*60}")
    print(f"Complete! Created {total_density} density frame(s) and {total_phase} phase frame(s)")
    print(f"Output directory: {OUTPUT_PNG_DIR}")
    print(f"  Density frames: {get_density_frames_dir()}")
    print(f"  Phase frames:   {get_phase_frames_dir()}")
    print(f"{'='*60}")
