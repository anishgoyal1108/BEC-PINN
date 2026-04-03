from .settings import get_sweep_mode


def select_from_menu(options: list, prompt: str) -> int:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  0. Cancel")

    while True:
        try:
            choice = int(input(prompt))
            if 0 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        print("Invalid selection, try again.")


def checkbox_menu(options: list, prompt: str) -> list[int]:
    selected: set[int] = set()

    while True:
        print()
        for i, opt in enumerate(options, 1):
            marker = "[x]" if (i - 1) in selected else "[ ]"
            print(f"  {i}. {marker} {opt}")
        print("  a. Select all")
        print("  n. Select none")
        print("  d. Done (proceed)")
        print("  0. Cancel")

        choice = input(prompt).strip().lower()

        if choice == "0":
            return []
        if choice == "d":
            return sorted(selected)
        if choice == "a":
            selected = set(range(len(options)))
            continue
        if choice == "n":
            selected = set()
            continue

        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                if (idx - 1) in selected:
                    selected.remove(idx - 1)
                else:
                    selected.add(idx - 1)
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input. Enter a number, 'a', 'n', 'd', or '0'.")


def mode_labels() -> tuple[str, str]:
    if get_sweep_mode() == "ubmax":
        return "Omega", "Ubmax"
    return "Ubmax", "Omega"


def format_secondary_option(run: dict) -> str:
    if get_sweep_mode() == "ubmax":
        label = f"Ubmax = {run['ub']}"
    else:
        label = f"omega = {run['omega']:.4f}"

    geometry = run.get("geometry")
    if geometry:
        label += f" ({geometry})"

    if run.get("experiment_k") is not None:
        label += f" (2x2 k={run['experiment_k']})"
    return label


def build_group_options(runs_grouped: dict) -> tuple[list[str], str, str, list[str]]:
    group_list = sorted(runs_grouped.keys(), key=lambda x: float(x))
    group_label, secondary_label = mode_labels()

    if get_sweep_mode() == "ubmax":
        group_options = [
            f"Omega = {g} ({len(runs_grouped[g])} Ubmax values)" for g in group_list
        ]
    else:
        group_options = [
            f"Ubmax = {g} ({len(runs_grouped[g])} omega values)" for g in group_list
        ]

    return group_list, group_label, secondary_label, group_options


def build_secondary_options(selected_group: str, runs: list[dict]) -> list[str]:
    if get_sweep_mode() == "ubmax":
        print(f"\nUbmax values for Omega = {selected_group}:\n")
        return [format_secondary_option(r) for r in runs]

    print(f"\nOmega values for Ubmax = {selected_group}:\n")
    return [format_secondary_option(r) for r in runs]
