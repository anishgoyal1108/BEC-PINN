import os
import subprocess

from .runs import find_existing_runs, find_sim_folder
from .settings import get_circulation_png_path
from .ui import (
    build_group_options,
    build_secondary_options,
    checkbox_menu,
    select_from_menu,
)
from .viewer import open_files_in_viewer


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


def _gnuplot_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _detect_circulation_pair_count(circ_file: str) -> int:
    max_cols = 0
    with open(circ_file, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            max_cols = max(max_cols, len(line.split()))
    if max_cols < 3:
        return 0
    return (max_cols - 1) // 2


def _build_circulation_script(
    run_dir_name: str,
    png_path: str,
    pair_count: int,
) -> str:
    if pair_count <= 1:
        return (
            "set term pngcairo size 1000,700\n"
            f"set output {_gnuplot_quote(png_path)}\n"
            "set xlabel 'time'\n"
            "set ylabel 'winding number'\n"
            f"set title {_gnuplot_quote(f'circulation: {run_dir_name}')}\n"
            "set yrange [-3:3]\n"
            "set grid\n"
            "plot 'circulation.dat' u 1:2 w d title 'top ring', \\\n"
            "     'circulation.dat' u 1:3 w d title 'bottom ring'\n"
            "set output\n"
        )

    height = max(700, 240 * pair_count)
    lines = [
        f"set term pngcairo size 1200,{height}",
        f"set output {_gnuplot_quote(png_path)}",
        "set grid",
        "set key outside right top",
        "set yrange [-3:3]",
        f"set multiplot layout {pair_count},1 rowsfirst downwards "
        "margins 0.08,0.86,0.07,0.95 spacing 0.00,0.04",
    ]

    DISPLAY_ORDER = [
        (2, "TL"),
        (3, "TR"),
        (0, "BL"),
        (1, "BR"),
    ]

    for display_idx, (fortran_pair_idx, cell_label) in enumerate(DISPLAY_ORDER):
        if fortran_pair_idx >= pair_count:
            continue
        col_a = 2 + (2 * fortran_pair_idx)
        col_b = col_a + 1
        pair_label = cell_label
        lines.append(
            f"set title {_gnuplot_quote(f'circulation: {run_dir_name} | {pair_label}')}"
        )
        lines.append(f"set ylabel {_gnuplot_quote(pair_label)}")
        if display_idx < pair_count - 1:
            lines.append("unset xlabel")
            lines.append("set format x ''")
        else:
            lines.append("set xlabel 'time'")
            lines.append("set format x '%g'")
        lines.append(
            "plot 'circulation.dat' u 1:"
            f"{col_a} w d lw 1.6 title 'ring 1 (col {col_a})', "
            "'' u 1:"
            f"{col_b} w d lw 1.6 title 'ring 2 (col {col_b})'"
        )
    lines.extend(["unset multiplot", "set output"])
    return "\n".join(lines) + "\n"


def _run_gnuplot_script(folder: str, script_text: str) -> subprocess.CompletedProcess:
    script_path = os.path.join(folder, "_temp_circulation_plot.gnu")
    try:
        with open(script_path, "w") as f:
            f.write(script_text)
        return subprocess.run(
            ["gnuplot", script_path],
            cwd=folder,
            capture_output=True,
        )
    finally:
        if os.path.isfile(script_path):
            os.remove(script_path)


def run_circulation_plotter():
    print("=" * 60)
    print("CIRCULATION PLOT - Select simulation runs")
    print("=" * 60)

    runs_grouped = find_existing_runs()

    if not runs_grouped:
        print("\nNo existing simulation runs found.")
        return

    selected_runs = _select_multiple_runs(runs_grouped)
    if not selected_runs:
        print("No runs selected.")
        return

    print(f"\nSelected {len(selected_runs)} run(s). Generating plots...")

    plots_created = []
    for run in selected_runs:
        run_dir = run["path"]
        run_dir_name = run["dir_name"]
        real_folder = find_sim_folder(run_dir, run_dir_name, "real")

        if real_folder is None:
            print(f"  No real folder for {run_dir_name}")
            continue

        circ_file = os.path.join(real_folder, "circulation.dat")
        if not os.path.isfile(circ_file):
            print(f"  No circulation.dat in {os.path.basename(real_folder)}")
            continue

        pair_count = _detect_circulation_pair_count(circ_file)
        if pair_count == 0:
            print(
                f"  Invalid circulation.dat format in {os.path.basename(real_folder)}"
            )
            continue

        print(f"  Plotting {run_dir_name}...")
        png_path = get_circulation_png_path(run_dir_name)
        circulation_script = _build_circulation_script(
            run_dir_name, png_path, pair_count
        )
        result = _run_gnuplot_script(real_folder, circulation_script)
        if result.returncode == 0:
            if os.path.isfile(png_path):
                plots_created.append(png_path)
        else:
            print(
                f"  Failed to plot {run_dir_name} (gnuplot exit code {result.returncode})"
            )

    if plots_created:
        viewer, opened = open_files_in_viewer(plots_created)
        print(f"\n  Created {len(plots_created)} plot(s). Opening with {viewer}...")
        if opened < len(plots_created):
            print(f"  Warning: opened {opened}/{len(plots_created)} file(s).")
    else:
        print("\n  No circulation.dat files found to plot.")
