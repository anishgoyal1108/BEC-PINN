"""Custom experiment UI: guided (omega, T, dt + auto time params) and expert (full editor)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .batch import run_simulation
from .mode_utils import is_imag_only_mode
from .physics import ubmax_scaled_from_T_nK
from .settings import get_geometry_mode
from .templates import (
    DI_PARAMS,
    GI_IMAG_PARAMS,
    GI_REAL_PARAMS,
    GI_SHARED_PARAMS,
    ParamDef,
    format_param_for_line,
    prepare_custom_directory,
)


@dataclass
class CustomExperimentSpec:
    mode: str
    geometry_mode: str
    nrows: int
    ncols: int
    omega_rf: float
    ubmax_seu: float
    temperature_nk: float | None
    diag_stride: int
    natoms_total: float
    di_values: dict[str, float | int | str]
    gi_shared_values: dict[str, float | int | str]
    gi_imag_values: dict[str, float | int | str]
    gi_real_values: dict[str, float | int | str]
    derived_values: dict[str, float | int | str] = field(default_factory=dict)


def _compute_time_params(
    dt_new: float,
    dt_old: float,
    tff_imag_old: float,
    tff_real_old: float,
    nt_imag_old: int,
    nt_real_old: int,
    nframes_imag_old: int,
    nframes_real_old: int,
) -> dict[str, float | int]:
    ratio = dt_old / dt_new
    nt_imag = int(round(tff_imag_old / dt_new))
    nt_real = int(round(tff_real_old / dt_new))
    tff_imag = dt_new * nt_imag
    tff_real = dt_new * nt_real
    nframes_imag = int(round(nframes_imag_old * ratio))
    nframes_real = int(round(nframes_real_old * ratio))
    return {
        "Nt_imag": nt_imag,
        "Nt_real": nt_real,
        "Nframes_imag": nframes_imag,
        "Nframes_real": nframes_real,
        "tff_imag": tff_imag,
        "tff_real": tff_real,
    }


def _guided_default_dicts() -> tuple[
    dict[str, float | int | str],
    dict[str, float | int | str],
    dict[str, float | int | str],
    dict[str, float | int | str],
]:
    di = {p.key: p.default for p in DI_PARAMS}
    di["nrows"] = 1
    di["ncols"] = 1
    gis = {p.key: p.default for p in GI_SHARED_PARAMS}
    gii = {p.key: p.default for p in GI_IMAG_PARAMS}
    gir = {p.key: p.default for p in GI_REAL_PARAMS}
    return di, gis, gii, gir


def _expert_default_dicts() -> tuple[
    dict[str, float | int | str],
    dict[str, float | int | str],
    dict[str, float | int | str],
    dict[str, float | int | str],
]:
    return _guided_default_dicts()


def compile_spec_to_overrides(
    spec: CustomExperimentSpec,
) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, str]]:
    di_overrides: dict[int, str] = {}
    for p in DI_PARAMS:
        if p.key in ("wd", "nrows", "ncols"):
            continue
        if p.key not in spec.di_values:
            continue
        v = spec.di_values[p.key]
        di_overrides[p.line_idx] = format_param_for_line(p, v)

    gi_shared_overrides: dict[int, str] = {}
    skip_shared = {"omega_rf", "diag_stride", "Natoms"}
    for p in GI_SHARED_PARAMS:
        if p.key in skip_shared:
            continue
        if p.key not in spec.gi_shared_values:
            continue
        v = spec.gi_shared_values[p.key]
        gi_shared_overrides[p.line_idx] = format_param_for_line(p, v)

    gi_imag_overrides: dict[int, str] = {}
    for p in GI_IMAG_PARAMS:
        if p.key not in spec.gi_imag_values:
            continue
        v = spec.gi_imag_values[p.key]
        gi_imag_overrides[p.line_idx] = format_param_for_line(p, v)

    gi_real_overrides: dict[int, str] = {}
    for p in GI_REAL_PARAMS:
        if p.key not in spec.gi_real_values:
            continue
        v = spec.gi_real_values[p.key]
        gi_real_overrides[p.line_idx] = format_param_for_line(p, v)

    return di_overrides, gi_shared_overrides, gi_imag_overrides, gi_real_overrides


def _choose_custom_mode() -> str | None:
    print("\nChoose mode:")
    print("  1. Guided Mode (recommended)")
    print("  2. Expert Mode (full parameter editor)")
    print("  0. Cancel")
    c = input("\nSelect: ").strip()
    if c == "1":
        return "guided"
    if c == "2":
        return "expert"
    return None


def _parse_value(p: ParamDef, text: str) -> float | int | str:
    t = text.strip()
    if p.fmt == "integer":
        return int(t)
    if p.fmt == "raw":
        return t
    return float(t)


def _display_params(
    di: dict[str, float | int | str],
    gis: dict[str, float | int | str],
    gii: dict[str, float | int | str],
    gir: dict[str, float | int | str],
    modified: set[str],
) -> None:
    n = 1
    print("\n=== DI Parameters (dtap_inputs.dat) ===")
    for p in DI_PARAMS:
        mark = " [*]" if p.key in modified else ""
        print(f"  {n}. {p.label}: {di.get(p.key, p.default)}{mark}")
        n += 1
    print("\n=== GI Shared Parameters ===")
    for p in GI_SHARED_PARAMS:
        if p.auto_set:
            continue
        mark = " [*]" if p.key in modified else ""
        print(f"  {n}. {p.label}: {gis.get(p.key, p.default)}{mark}")
        n += 1
    print("\n=== GI Imaginary Time ===")
    for p in GI_IMAG_PARAMS:
        mark = " [*]" if p.key in modified else ""
        print(f"  {n}. {p.label}: {gii.get(p.key, p.default)}{mark}")
        n += 1
    print("\n=== GI Real Time ===")
    for p in GI_REAL_PARAMS:
        mark = " [*]" if p.key in modified else ""
        print(f"  {n}. {p.label}: {gir.get(p.key, p.default)}{mark}")
        n += 1


def _flat_param_list() -> list[tuple[int, ParamDef, str]]:
    """(display_index_base_1, param, group) for expert editor."""
    items: list[tuple[int, ParamDef, str]] = []
    n = 1
    for p in DI_PARAMS:
        if p.expert_visible:
            items.append((n, p, "di"))
            n += 1
    for p in GI_SHARED_PARAMS:
        if p.expert_visible and not p.auto_set:
            items.append((n, p, "gis"))
            n += 1
    for p in GI_IMAG_PARAMS:
        if p.expert_visible:
            items.append((n, p, "gii"))
            n += 1
    for p in GI_REAL_PARAMS:
        if p.expert_visible:
            items.append((n, p, "gir"))
            n += 1
    return items


def _edit_param_loop(
    di: dict[str, float | int | str],
    gis: dict[str, float | int | str],
    gii: dict[str, float | int | str],
    gir: dict[str, float | int | str],
) -> bool:
    flat = _flat_param_list()
    modified: set[str] = set()
    dt_key = "dt"
    snapshot_dt = float(gis[dt_key])
    time_keys_imag = {"Nt_imag", "Nframes_imag", "tff_imag"}
    time_keys_real = {"Nt_real", "Nframes_real", "tff_real"}

    while True:
        _display_params(di, gis, gii, gir, modified)
        print("\nEnter parameter number to edit, 'd' when done, '0' to cancel.")
        choice = input("> ").strip().lower()
        if choice == "0":
            return False
        if choice == "d":
            cur_dt = float(gis[dt_key])
            if cur_dt != snapshot_dt:
                imag_touched = any(k in modified for k in time_keys_imag)
                real_touched = any(k in modified for k in time_keys_real)
                if not imag_touched or not real_touched:
                    print(
                        "\n  dt changed but imaginary/real time parameters may be inconsistent."
                    )
                    print("  1. Keep current Nt / Nframes / tff as shown")
                    print(
                        "  2. Auto-recompute time parameters from dt (like Guided mode)"
                    )
                    print("  3. Continue editing")
                    sub = input("Choose (1/2/3): ").strip()
                    if sub == "2":
                        t = _compute_time_params(
                            cur_dt,
                            snapshot_dt,
                            float(gii["tff_imag"]),
                            float(gir["tff_real"]),
                            int(gii["Nt_imag"]),
                            int(gir["Nt_real"]),
                            int(gii["Nframes_imag"]),
                            int(gir["Nframes_real"]),
                        )
                        gii["Nt_imag"] = t["Nt_imag"]
                        gii["Nframes_imag"] = t["Nframes_imag"]
                        gii["tff_imag"] = t["tff_imag"]
                        gir["Nt_real"] = t["Nt_real"]
                        gir["Nframes_real"] = t["Nframes_real"]
                        gir["tff_real"] = t["tff_real"]
                        modified.update(time_keys_imag | time_keys_real)
                    elif sub == "3":
                        continue
                    # sub == "1" or empty: keep current values
            return True
        try:
            idx = int(choice)
        except ValueError:
            print("Invalid input.")
            continue
        row = next((x for x in flat if x[0] == idx), None)
        if row is None:
            print("Invalid number.")
            continue
        _n, p, grp = row
        cur = (
            di if grp == "di" else gis if grp == "gis" else gii if grp == "gii" else gir
        )
        raw = input(f"New value for {p.label} [{cur[p.key]}]: ").strip()
        if not raw:
            continue
        try:
            cur[p.key] = _parse_value(p, raw)
            modified.add(p.key)
        except ValueError as e:
            print(f"  Invalid value: {e}")


def _advanced_param_menu(
    di: dict[str, float | int | str],
    gis: dict[str, float | int | str],
) -> bool:
    params: list[ParamDef] = []
    for p in DI_PARAMS:
        if p.guided_visible and p.key not in ("nrows", "ncols"):
            params.append(p)
    for p in GI_SHARED_PARAMS:
        if p.guided_visible and not p.auto_computed and p.key not in ("dt", "omega_rf"):
            params.append(p)

    modified: set[str] = set()
    while True:
        print("\n--- Advanced parameters ---")
        for i, p in enumerate(params, 1):
            d = di if p.file_group == "di" else gis
            mark = " [*]" if p.key in modified else ""
            print(f"  {i}. {p.label}: {d[p.key]}{mark}")
        print("  d. Done")
        print("  0. Cancel")
        choice = input("\nSelect: ").strip().lower()
        if choice == "0":
            return False
        if choice == "d":
            return True
        try:
            k = int(choice)
        except ValueError:
            print("Invalid.")
            continue
        if not 1 <= k <= len(params):
            print("Invalid.")
            continue
        p = params[k - 1]
        d = di if p.file_group == "di" else gis
        raw = input(f"New value for {p.label} [{d[p.key]}]: ").strip()
        if not raw:
            continue
        try:
            d[p.key] = _parse_value(p, raw)
            modified.add(p.key)
        except ValueError as e:
            print(f"  Invalid: {e}")


def _run_guided_custom_experiment() -> None:
    geom = get_geometry_mode().lower()
    print(f"\nCurrent geometry mode: {geom.upper()}")

    omega = float(input("omega_rf (rad/s): ").strip())
    t_nk = float(input("Temperature T (nK): ").strip())
    ubmax = ubmax_scaled_from_T_nK(t_nk)

    di, gis, gii, gir = _guided_default_dicts()
    dt_old = float(gis["dt"])
    dt_in = input(f"Enter new dt (STU), or Enter to keep [{dt_old}]: ").strip()
    dt_new = float(dt_in) if dt_in else dt_old
    if dt_new <= 0:
        print("dt must be positive.")
        return

    gis["dt"] = dt_new
    gis["omega_rf"] = omega
    derived = _compute_time_params(
        dt_new,
        dt_old,
        float(gii["tff_imag"]),
        float(gir["tff_real"]),
        int(gii["Nt_imag"]),
        int(gir["Nt_real"]),
        int(gii["Nframes_imag"]),
        int(gir["Nframes_real"]),
    )
    gii["Nt_imag"] = derived["Nt_imag"]
    gii["Nframes_imag"] = derived["Nframes_imag"]
    gii["tff_imag"] = derived["tff_imag"]
    gir["Nt_real"] = derived["Nt_real"]
    gir["Nframes_real"] = derived["Nframes_real"]
    gir["tff_real"] = derived["tff_real"]

    print("\n  Auto-computed time parameters:")
    print(f"    Nt imag / real: {derived['Nt_imag']} / {derived['Nt_real']}")
    print(
        f"    Nframes imag / real: {derived['Nframes_imag']} / {derived['Nframes_real']}"
    )
    print(f"    tff imag / real: {derived['tff_imag']:.6g} / {derived['tff_real']:.6g}")

    diag_stride = int(
        input(
            "\nEnter diag_stride (diagnostics every N steps, 0=skip, default 15): "
        ).strip()
        or "15"
    )

    adv = input("\nEdit advanced parameters? (y/n): ").strip().lower()
    if adv == "y":
        if not _advanced_param_menu(di, gis):
            print("Cancelled.")
            return

    natoms_total = float(gis["Natoms"])

    spec = CustomExperimentSpec(
        mode="guided",
        geometry_mode=geom,
        nrows=int(di["nrows"]),
        ncols=int(di["ncols"]),
        omega_rf=omega,
        ubmax_seu=ubmax,
        temperature_nk=t_nk,
        diag_stride=diag_stride,
        natoms_total=natoms_total,
        di_values=dict(di),
        gi_shared_values=dict(gis),
        gi_imag_values=dict(gii),
        gi_real_values=dict(gir),
        derived_values=dict(derived),
    )

    print("\n--- Configuration Summary ---")
    print(f"  omega_rf: {omega}")
    print(f"  T: {t_nk} nK  ->  Ubmax: {ubmax:.4f} SEU")
    print(f"  Geometry: {geom}  ({spec.nrows}x{spec.ncols})")
    print(f"  dt: {gis['dt']}")
    print(f"  diag_stride: {diag_stride}")
    print(f"  Natoms (effective): {natoms_total}")
    if input("\nProceed? (y/n): ").strip().lower() != "y":
        print("Aborted.")
        return

    _execute_custom_spec(spec)


def _run_expert_custom_experiment() -> None:
    geom = get_geometry_mode().lower()
    di, gis, gii, gir = _expert_default_dicts()
    if not _edit_param_loop(di, gis, gii, gir):
        print("Cancelled.")
        return

    omega = float(gis["omega_rf"])
    print("\nUbmax (SEU) sets the Gaussian barrier height in dtap_inputs (1x1).")
    ubmax = float(input("Ubmax (SEU): ").strip())

    diag_stride = int(gis["diag_stride"])
    ds_in = input(f"diag_stride [{diag_stride}]: ").strip()
    if ds_in:
        diag_stride = int(ds_in)
        gis["diag_stride"] = diag_stride

    natoms_total = float(gis["Natoms"])

    spec = CustomExperimentSpec(
        mode="expert",
        geometry_mode=geom,
        nrows=int(di["nrows"]),
        ncols=int(di["ncols"]),
        omega_rf=omega,
        ubmax_seu=ubmax,
        temperature_nk=None,
        diag_stride=diag_stride,
        natoms_total=natoms_total,
        di_values=dict(di),
        gi_shared_values=dict(gis),
        gi_imag_values=dict(gii),
        gi_real_values=dict(gir),
        derived_values={},
    )

    print("\n--- Expert Configuration Summary ---")
    print(f"  omega_rf: {omega}  Ubmax: {ubmax} SEU")
    print(f"  Geometry: {geom}  ({spec.nrows}x{spec.ncols})")
    print(f"  diag_stride: {diag_stride}")
    if input("\nProceed? (y/n): ").strip().lower() != "y":
        print("Aborted.")
        return

    _execute_custom_spec(spec)


def _execute_custom_spec(spec: CustomExperimentSpec) -> None:
    if is_imag_only_mode():
        print("\n" + "=" * 60)
        print("IMAGINARY TIME ONLY: real-time phase will be skipped.")
        print("=" * 60)

    di_o, gis_o, gii_o, gir_o = compile_spec_to_overrides(spec)
    run_dir_name, _run_dir = prepare_custom_directory(
        omega=spec.omega_rf,
        ubmax_seu=spec.ubmax_seu,
        diag_stride=spec.diag_stride,
        di_overrides=di_o,
        gi_shared_overrides=gis_o,
        gi_imag_overrides=gii_o,
        gi_real_overrides=gir_o,
        geometry_mode=spec.geometry_mode,
        nrows=spec.nrows,
        ncols=spec.ncols,
        natoms_total=spec.natoms_total,
    )
    print(f"\nCreated run directory: {run_dir_name}")
    run_simulation(run_dir_name, is_imag_only_mode())


def run_custom_experiment() -> None:
    print("\n" + "=" * 60)
    print("CUSTOM EXPERIMENT")
    print("=" * 60)
    mode = _choose_custom_mode()
    if mode is None:
        print("Cancelled.")
        return
    if mode == "guided":
        _run_guided_custom_experiment()
    else:
        _run_expert_custom_experiment()
