import os
import shutil
from dataclasses import dataclass

from .settings import (
    SCRIPT_DIR,
    TEMPLATE_DIR,
    TEMPLATE_REQUIRED_FILES,
    get_geometry_mode,
)

_DI_WD_LINE_INDEX = 25
_DI_NROWS_LINE_INDEX = 53
_DI_NCOLS_LINE_INDEX = 60
_DI_UB_ROW0_LINE_INDEX = 95
_DI_UB_ROW1_LINE_INDEX = 96

_DI_V0_LINE_INDEX = 11
_DI_A_LINE_INDEX = 18
_DI_WR_LINE_INDEX = 32
_DI_R_LINE_INDEX = 39
_DI_N_LINE_INDEX = 46
_DI_XC_LINE_INDEX = 67
_DI_YC_LINE_INDEX = 74
_DI_WPERP_LINE_INDEX = 81
_DI_WPARA_LINE_INDEX = 88
_DI_TRAMP_LINE_INDEX = 103
_DI_TON_LINE_INDEX = 110
_DI_TPI_LINE_INDEX = 117
_DI_TREL_LINE_INDEX = 124

_GI_NX_LINE_INDEX = 19
_GI_NY_LINE_INDEX = 26
_GI_DX_LINE_INDEX = 33
_GI_DY_LINE_INDEX = 40
_GI_GBAR_LINE_INDEX = 47
_GI_DT_LINE_INDEX = 61
_GI_TFI_LINE_INDEX = 75
_GI_L0_LINE_INDEX = 89
_GI_REAL_OR_IMAG_LINE_INDEX = 96
_GI_READ_INITIAL_WF_LINE_INDEX = 103
_GI_OUTPUT_FRAMES_LINE_INDEX = 110
_GI_PHASE_IMPRINT_LINE_INDEX = 117
_GI_WITH_DISS_LINE_INDEX = 124
_GI_GAMMA_DISS_LINE_INDEX = 131
_GI_OMEGA_LINE_INDEX = 138
_GI_DIAG_STRIDE_LINE_INDEX = 145

_IMAG_NT = 133443
_IMAG_NFRAMES = 330
_IMAG_TFF = 5.33772

_GI_NT_LINE_INDEX = 54
_GI_NFRAMES_LINE_INDEX = 68
_GI_TFF_LINE_INDEX = 82
_GI_NATOMS_LINE_INDEX = 12

_REAL_NT = 117268
_REAL_NFRAMES = 290
_REAL_TFF = 4.69072
_BASE_NATOMS = 166667.0


@dataclass(frozen=True)
class ParamDef:
    key: str
    label: str
    line_idx: int
    default: float | int | str
    fmt: str
    file_group: str
    guided_visible: bool
    expert_visible: bool
    auto_computed: bool
    auto_set: bool


def apply_line_overrides(content: str, overrides: dict[int, str]) -> str:
    """Replace lines at 0-based indices. Values must not include trailing newline."""
    if not overrides:
        return content
    lines = content.splitlines(keepends=True)
    for idx, new_text in sorted(overrides.items()):
        if idx < len(lines):
            lines[idx] = new_text + "\n"
    return "".join(lines)


def format_fortran_float(value: float) -> str:
    return f"{value}d0"


def format_fortran_sci(value: float) -> str:
    return f" {value:.4f}D+00"


def format_ubmax_line(value: float) -> str:
    return f" {value:.4E}".replace("E", "D")


def format_integer(value: int) -> str:
    return str(int(value))


def format_raw(value: float | int | str) -> str:
    return str(value)


def format_natoms_line(value: float) -> str:
    return f"{value:.1f}d0"


def format_wd_line(value: float) -> str:
    return f"{value:.1f}d0"


def format_param_for_line(p: ParamDef, value: float | int | str) -> str:
    f = p.fmt
    if f == "fortran_float":
        return format_fortran_float(float(value))
    if f == "fortran_sci":
        return format_fortran_sci(float(value))
    if f == "integer":
        return format_integer(int(value))
    if f == "raw":
        return format_raw(value)
    if f == "natoms":
        return format_natoms_line(float(value))
    if f == "wd":
        return format_wd_line(float(value))
    if f == "ubmax_line":
        return format_ubmax_line(float(value))
    raise ValueError(f"Unknown format {f!r} for param {p.key}")


DI_PARAMS: tuple[ParamDef, ...] = (
    ParamDef("V0", "V0 (potential height, SEU)", _DI_V0_LINE_INDEX, 2000.0, "fortran_float", "di", True, True, False, False),
    ParamDef("a", "a (relative depth)", _DI_A_LINE_INDEX, 1.0, "fortran_float", "di", True, True, False, False),
    ParamDef("wd", "wd (disk width, SLU)", _DI_WD_LINE_INDEX, 1.0, "wd", "di", False, True, False, False),
    ParamDef("wr", "wr (ring width, SLU)", _DI_WR_LINE_INDEX, 0.5, "fortran_float", "di", True, True, False, False),
    ParamDef("R", "R (midtrack radius, SLU)", _DI_R_LINE_INDEX, 2.25, "fortran_float", "di", True, True, False, False),
    ParamDef("n", "n (exponent)", _DI_N_LINE_INDEX, 1.0, "fortran_float", "di", True, True, False, False),
    ParamDef("nrows", "nrows (array rows)", _DI_NROWS_LINE_INDEX, 2, "integer", "di", True, True, False, False),
    ParamDef("ncols", "ncols (array columns)", _DI_NCOLS_LINE_INDEX, 2, "integer", "di", True, True, False, False),
    ParamDef("xc_array", "xc_array (center X, SLU)", _DI_XC_LINE_INDEX, 100.0, "fortran_float", "di", True, True, False, False),
    ParamDef("yc_array", "yc_array (center Y, SLU)", _DI_YC_LINE_INDEX, 100.0, "fortran_float", "di", True, True, False, False),
    ParamDef("wperp", "wperp (perp barrier width, SLU)", _DI_WPERP_LINE_INDEX, 1.125, "fortran_sci", "di", True, True, False, False),
    ParamDef("wpara", "wpara (para barrier width, SLU)", _DI_WPARA_LINE_INDEX, 1.125, "fortran_float", "di", True, True, False, False),
    ParamDef("tramp_si", "tramp_si (ramp time, s)", _DI_TRAMP_LINE_INDEX, 0.1, "fortran_float", "di", True, True, False, False),
    ParamDef("ton_si", "ton_si (hold time, s)", _DI_TON_LINE_INDEX, 0.1, "fortran_float", "di", True, True, False, False),
    ParamDef("tpi_si", "tpi_si (phase imprint time, s)", _DI_TPI_LINE_INDEX, 0.025, "fortran_float", "di", True, True, False, False),
    ParamDef("trel_si", "trel_si (release time, s)", _DI_TREL_LINE_INDEX, 0.005, "fortran_float", "di", True, True, False, False),
)

GI_SHARED_PARAMS: tuple[ParamDef, ...] = (
    ParamDef("Natoms", "Natoms (atom count)", _GI_NATOMS_LINE_INDEX, _BASE_NATOMS, "natoms", "gi_shared", True, True, False, False),
    ParamDef("Nx", "Nx (x grid points)", _GI_NX_LINE_INDEX, 400, "integer", "gi_shared", True, True, False, False),
    ParamDef("Ny", "Ny (y grid points)", _GI_NY_LINE_INDEX, 400, "integer", "gi_shared", True, True, False, False),
    ParamDef("dx", "dx (x grid step, SLU)", _GI_DX_LINE_INDEX, 0.061875, "fortran_float", "gi_shared", True, True, False, False),
    ParamDef("dy", "dy (y grid step, SLU)", _GI_DY_LINE_INDEX, 0.061875, "fortran_float", "gi_shared", True, True, False, False),
    ParamDef("g_bar", "g_bar (nonlinear coeff)", _GI_GBAR_LINE_INDEX, 0.0316, "fortran_float", "gi_shared", True, True, False, False),
    ParamDef("dt", "dt (time step, STU)", _GI_DT_LINE_INDEX, 0.00004, "raw", "gi_shared", False, True, False, False),
    ParamDef("tfi", "tfi (initial time, STU)", _GI_TFI_LINE_INDEX, 0.0, "fortran_float", "gi_shared", True, True, False, False),
    ParamDef("L0", "L0 (length unit, m)", _GI_L0_LINE_INDEX, "10.0d-6", "raw", "gi_shared", True, True, False, False),
    ParamDef("output_frames", "output_frames (0=no, 1=yes)", _GI_OUTPUT_FRAMES_LINE_INDEX, 1, "integer", "gi_shared", True, True, False, False),
    ParamDef("with_diss", "with_diss (0=no, 1=yes)", _GI_WITH_DISS_LINE_INDEX, 0, "integer", "gi_shared", True, True, False, False),
    ParamDef("gamma_diss", "gamma_diss (dissipation)", _GI_GAMMA_DISS_LINE_INDEX, 0.0, "fortran_float", "gi_shared", True, True, False, False),
    ParamDef("omega_rf", "omega_rf (rotation, rad/s)", _GI_OMEGA_LINE_INDEX, 0.1, "fortran_float", "gi_shared", False, True, False, False),
    ParamDef("diag_stride", "diag_stride (diagnostic stride)", _GI_DIAG_STRIDE_LINE_INDEX, 15, "integer", "gi_shared", True, True, False, False),
)

GI_IMAG_PARAMS: tuple[ParamDef, ...] = (
    ParamDef("Nt_imag", "Nt - imag (timesteps)", _GI_NT_LINE_INDEX, _IMAG_NT, "integer", "gi_imag", False, True, True, False),
    ParamDef("Nframes_imag", "Nframes - imag (output frames)", _GI_NFRAMES_LINE_INDEX, _IMAG_NFRAMES, "integer", "gi_imag", False, True, True, False),
    ParamDef("tff_imag", "tff - imag (final time, STU)", _GI_TFF_LINE_INDEX, _IMAG_TFF, "fortran_float", "gi_imag", False, True, True, False),
)

GI_REAL_PARAMS: tuple[ParamDef, ...] = (
    ParamDef("Nt_real", "Nt - real (timesteps)", _GI_NT_LINE_INDEX, _REAL_NT, "integer", "gi_real", False, True, True, False),
    ParamDef("Nframes_real", "Nframes - real (output frames)", _GI_NFRAMES_LINE_INDEX, _REAL_NFRAMES, "integer", "gi_real", False, True, True, False),
    ParamDef("tff_real", "tff - real (final time, STU)", _GI_TFF_LINE_INDEX, _REAL_TFF, "fortran_float", "gi_real", False, True, True, False),
)

AUTO_GI_FLAG_PARAMS: tuple[ParamDef, ...] = (
    ParamDef("real_or_imag", "real_or_imag (internal)", _GI_REAL_OR_IMAG_LINE_INDEX, 0, "integer", "gi_shared", False, False, False, True),
    ParamDef("read_initial_wf", "read_initial_wf (internal)", _GI_READ_INITIAL_WF_LINE_INDEX, 0, "integer", "gi_shared", False, False, False, True),
    ParamDef("phase_imprint", "phase_imprint (internal)", _GI_PHASE_IMPRINT_LINE_INDEX, 0, "integer", "gi_shared", False, False, False, True),
)

ALL_CUSTOM_PARAMS: tuple[ParamDef, ...] = (
    DI_PARAMS + GI_SHARED_PARAMS + GI_IMAG_PARAMS + GI_REAL_PARAMS + AUTO_GI_FLAG_PARAMS
)

PARAM_BY_KEY: dict[str, ParamDef] = {p.key: p for p in ALL_CUSTOM_PARAMS}


def prepare_custom_directory(
    omega: float,
    ubmax_seu: float,
    diag_stride: int,
    di_overrides: dict[int, str],
    gi_shared_overrides: dict[int, str],
    gi_imag_overrides: dict[int, str],
    gi_real_overrides: dict[int, str],
    geometry_mode: str = "ring",
    nrows: int = 1,
    ncols: int = 1,
    natoms_total: float | None = None,
    template_dir: str = TEMPLATE_DIR,
) -> tuple[str, str]:
    """Build a 1x1 run directory from templates with explicit line overrides.

    Line overrides use template 0-based indices. Geometry (wd, topology, Ubmax)
    and GI flags, omega, diag_stride, and Natoms are applied after overrides.
    """
    mode = geometry_mode.lower()
    ub_str = ub_str_for_dir(ubmax_seu)
    run_dir_base = _build_run_dir_name(omega, ub_str, mode, None)
    run_dir_name = _unique_run_dir_name(run_dir_base)
    run_dir = os.path.join(SCRIPT_DIR, run_dir_name)
    os.makedirs(run_dir, exist_ok=True)

    _copy_template_support_files(run_dir, template_dir)
    di_template, gi_template = _load_template_inputs(template_dir)

    di = apply_line_overrides(di_template, di_overrides)
    wd_value = 0.0 if mode == "ring" else 1.0
    di = replace_wd_in_di(di, wd_value)
    di = replace_topology_in_di(di, nrows, ncols)
    if nrows == 1 and ncols == 1:
        di = replace_ubmax_in_di(di, ubmax_seu)
        lines = di.splitlines(keepends=True)
        if len(lines) > _DI_UB_ROW1_LINE_INDEX:
            lines.pop(_DI_UB_ROW1_LINE_INDEX)
        di = "".join(lines)
    else:
        di = replace_ubmax_matrix_in_di(
            di, ubmax_seu, ubmax_seu, ubmax_seu, ubmax_seu
        )

    gi_imag = apply_line_overrides(gi_template, gi_shared_overrides)
    gi_imag = apply_line_overrides(gi_imag, gi_imag_overrides)
    gi_imag = replace_real_or_imag_in_gi(gi_imag, 0)
    gi_imag = replace_read_initial_wf_in_gi(gi_imag, 0)
    gi_imag = replace_phase_imprint_in_gi(gi_imag, 0)
    gi_imag = replace_omega_in_gi(gi_imag, omega)
    gi_imag = replace_diag_stride_in_gi(gi_imag, diag_stride)
    natoms = (
        natoms_total
        if natoms_total is not None
        else _BASE_NATOMS * nrows * ncols
    )
    gi_imag = replace_natoms_in_gi(gi_imag, natoms)

    gi_real = apply_line_overrides(gi_template, gi_shared_overrides)
    gi_real = apply_line_overrides(gi_real, gi_real_overrides)
    gi_real = replace_real_or_imag_in_gi(gi_real, 1)
    gi_real = replace_read_initial_wf_in_gi(gi_real, 1)
    gi_real = replace_phase_imprint_in_gi(gi_real, 1)
    gi_real = replace_omega_in_gi(gi_real, omega)
    gi_real = replace_diag_stride_in_gi(gi_real, diag_stride)
    gi_real = replace_natoms_in_gi(gi_real, natoms)

    with open(os.path.join(run_dir, "di_modified.dat"), "w") as f:
        f.write(di)
    with open(os.path.join(run_dir, "gi_imag_modified.dat"), "w") as f:
        f.write(gi_imag)
    with open(os.path.join(run_dir, "gi_real_modified.dat"), "w") as f:
        f.write(gi_real)

    return run_dir_name, run_dir



def validate_template_dir(template_dir: str = TEMPLATE_DIR) -> None:
    missing = [
        name
        for name in TEMPLATE_REQUIRED_FILES
        if not os.path.exists(os.path.join(template_dir, name))
    ]
    if missing:
        raise FileNotFoundError(
            f"Invalid template directory: {template_dir}. Missing: {', '.join(missing)}"
        )


def find_template_files(template_dir: str = TEMPLATE_DIR) -> tuple[str, str, str]:
    validate_template_dir(template_dir)
    di = os.path.join(template_dir, "dtap_inputs.dat")
    gi = os.path.join(template_dir, "rfgpe_2d_solver_general_inputs.dat")
    return di, gi, gi


def fortran_float_str(value: float) -> str:
    return f"{value:.6f}d0"


def replace_ubmax_in_di(content: str, ubmax_seu: float) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _DI_UB_ROW0_LINE_INDEX:
        lines[_DI_UB_ROW0_LINE_INDEX] = f" {ubmax_seu:.4E}\n".replace("E", "D")
    return "".join(lines)


def replace_wd_in_di(content: str, wd_value: float) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _DI_WD_LINE_INDEX:
        lines[_DI_WD_LINE_INDEX] = f"{wd_value:.1f}d0\n"
    return "".join(lines)


def replace_topology_in_di(content: str, nrows: int, ncols: int) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _DI_NROWS_LINE_INDEX:
        lines[_DI_NROWS_LINE_INDEX] = f"{nrows}\n"
    if len(lines) > _DI_NCOLS_LINE_INDEX:
        lines[_DI_NCOLS_LINE_INDEX] = f"{ncols}\n"
    return "".join(lines)


def replace_ubmax_matrix_in_di(
    content: str,
    bl_seu: float,
    br_seu: float,
    tl_seu: float,
    tr_seu: float,
) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _DI_UB_ROW1_LINE_INDEX:
        lines[_DI_UB_ROW0_LINE_INDEX] = f"{bl_seu:.4f}d0 {br_seu:.4f}d0\n"
        lines[_DI_UB_ROW1_LINE_INDEX] = f"{tl_seu:.4f}d0 {tr_seu:.4f}d0\n"
    return "".join(lines)


def build_di_content_1x1(
    template_content: str,
    ubmax_seu: float,
    geometry_mode: str | None = None,
) -> str:
    mode = (geometry_mode or get_geometry_mode()).lower()
    wd_value = 0.0 if mode == "ring" else 1.0

    content = replace_wd_in_di(template_content, wd_value)
    content = replace_topology_in_di(content, nrows=1, ncols=1)
    content = replace_ubmax_in_di(content, ubmax_seu)

    # For 1x1 we have one Ubmax line; remove the second row so the next 6 comment
    # lines and tramp_si stay aligned (Fortran reads 1 line then 6 comments then tramp_si).
    lines = content.splitlines(keepends=True)
    if len(lines) > _DI_UB_ROW1_LINE_INDEX:
        lines.pop(_DI_UB_ROW1_LINE_INDEX)
    return "".join(lines)


def build_di_content_2x2(
    template_content: str,
    ubmax_assignment_seu: dict[str, float],
    geometry_mode: str | None = None,
) -> str:
    mode = (geometry_mode or get_geometry_mode()).lower()
    wd_value = 0.0 if mode == "ring" else 1.0

    content = replace_wd_in_di(template_content, wd_value)
    content = replace_topology_in_di(content, nrows=2, ncols=2)
    return replace_ubmax_matrix_in_di(
        content,
        bl_seu=ubmax_assignment_seu["BL"],
        br_seu=ubmax_assignment_seu["BR"],
        tl_seu=ubmax_assignment_seu["TL"],
        tr_seu=ubmax_assignment_seu["TR"],
    )


def replace_omega_in_gi(content: str, omega: float) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) >= 140:
        lines[138] = f" {omega:.4f}D+00\n"
    return "".join(lines)


def replace_diag_stride_in_gi(content: str, diag_stride: int) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) >= 146:
        lines[145] = f"{diag_stride}\n"
    return "".join(lines)


def replace_nt_in_gi(content: str, nt: int) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _GI_NT_LINE_INDEX:
        lines[_GI_NT_LINE_INDEX] = f"{nt}\n"
    return "".join(lines)


def replace_nframes_in_gi(content: str, nframes: int) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _GI_NFRAMES_LINE_INDEX:
        lines[_GI_NFRAMES_LINE_INDEX] = f"{nframes}\n"
    return "".join(lines)


def replace_tff_in_gi(content: str, tff: float) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _GI_TFF_LINE_INDEX:
        lines[_GI_TFF_LINE_INDEX] = f"{tff}d0\n"
    return "".join(lines)


def replace_natoms_in_gi(content: str, natoms: float) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) > _GI_NATOMS_LINE_INDEX:
        lines[_GI_NATOMS_LINE_INDEX] = f"{natoms:.1f}d0\n"
    return "".join(lines)


def replace_real_or_imag_in_gi(content: str, value: int) -> str:
    """Set real_or_imag: 0 = imaginary time, 1 = real time (per solver general_inputs)."""
    lines = content.splitlines(keepends=True)
    if len(lines) >= 97:
        lines[96] = f"{value}\n"
    return "".join(lines)


def replace_read_initial_wf_in_gi(content: str, value: int) -> str:
    """Set read_initial_wf: 0 = use Gaussian initial state (no initial_wf.dat), 1 = read initial_wf.dat."""
    lines = content.splitlines(keepends=True)
    if len(lines) >= 104:
        lines[103] = f"{value}\n"
    return "".join(lines)


def replace_phase_imprint_in_gi(content: str, value: int) -> str:
    lines = content.splitlines(keepends=True)
    if len(lines) >= 118:
        lines[117] = f"{value}\n"
    return "".join(lines)


def build_gi_phase_content(
    template_content: str,
    omega: float,
    diag_stride: int,
    phase: str,
    nrows: int = 1,
    ncols: int = 1,
) -> str:
    phase_lower = phase.lower()
    is_real = phase_lower == "real"

    content = replace_real_or_imag_in_gi(template_content, 1 if is_real else 0)
    content = replace_read_initial_wf_in_gi(content, 1 if is_real else 0)
    content = replace_phase_imprint_in_gi(content, 1 if is_real else 0)
    content = replace_omega_in_gi(content, omega)
    content = replace_diag_stride_in_gi(content, diag_stride)
    content = replace_natoms_in_gi(content, _BASE_NATOMS * nrows * ncols)
    if is_real:
        content = replace_nt_in_gi(content, _REAL_NT)
        content = replace_nframes_in_gi(content, _REAL_NFRAMES)
        content = replace_tff_in_gi(content, _REAL_TFF)
    return content


def ub_str_for_dir(ubmax_seu: float) -> str:
    return f"{ubmax_seu:09.4f}".replace(" ", "0")


def cleanup_run_directory(run_dir: str) -> None:
    for name in os.listdir(run_dir):
        path = os.path.join(run_dir, name)
        if os.path.isfile(path):
            os.remove(path)


def _copy_template_support_files(
    run_dir: str, template_dir: str = TEMPLATE_DIR
) -> None:
    skip_names = {"dtap_inputs.dat", "rfgpe_2d_solver_general_inputs.dat"}
    for name in os.listdir(template_dir):
        if name in skip_names:
            continue
        src = os.path.join(template_dir, name)
        dst = os.path.join(run_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)


def _unique_run_dir_name(base_run_dir_name: str) -> str:
    run_dir_name = base_run_dir_name
    suffix = 2
    while os.path.exists(os.path.join(SCRIPT_DIR, run_dir_name)):
        run_dir_name = f"{base_run_dir_name}_r{suffix}"
        suffix += 1
    return run_dir_name


def _build_run_dir_name(
    omega: float,
    ub_str: str,
    geometry_mode: str,
    experiment_k: int | None,
) -> str:
    if experiment_k is None:
        return f"om_{omega:.4f}_ub_{ub_str}_geom_{geometry_mode}"
    return f"om_{omega:.4f}_ub_{ub_str}_2x2_k{experiment_k}_geom_{geometry_mode}"


def _load_template_inputs(template_dir: str = TEMPLATE_DIR) -> tuple[str, str]:
    validate_template_dir(template_dir)
    with open(os.path.join(template_dir, "dtap_inputs.dat"), "r") as f:
        di_template = f.read()
    with open(
        os.path.join(template_dir, "rfgpe_2d_solver_general_inputs.dat"), "r"
    ) as f:
        gi_template = f.read()
    return di_template, gi_template


def prepare_directory(
    omega: float,
    diag_stride: int,
    geometry_mode: str | None = None,
    ubmax_seu: float | None = None,
    ubmax_assignment_seu: dict[str, float] | None = None,
    experiment_k: int | None = None,
    template_dir: str = TEMPLATE_DIR,
) -> tuple[str, str]:
    """Unified directory preparation for both 1x1 and 2x2 runs.

    For 1x1: pass ubmax_seu.
    For 2x2: pass ubmax_assignment_seu (and optionally experiment_k).
    """
    mode = (geometry_mode or get_geometry_mode()).lower()

    if ubmax_assignment_seu is not None:
        nrows, ncols = 2, 2
        ub_ref_seu = sum(ubmax_assignment_seu.values()) / len(ubmax_assignment_seu)
        ub_str = ub_str_for_dir(ub_ref_seu)
        build_di = lambda content, m: build_di_content_2x2(
            content, ubmax_assignment_seu, m
        )
    else:
        if ubmax_seu is None:
            raise ValueError(
                "Either ubmax_seu or ubmax_assignment_seu must be provided."
            )
        nrows, ncols = 1, 1
        ub_str = ub_str_for_dir(ubmax_seu)
        build_di = lambda content, m: build_di_content_1x1(content, ubmax_seu, m)

    run_dir_base = _build_run_dir_name(omega, ub_str, mode, experiment_k)
    run_dir_name = _unique_run_dir_name(run_dir_base)
    run_dir = os.path.join(SCRIPT_DIR, run_dir_name)
    os.makedirs(run_dir, exist_ok=True)

    _copy_template_support_files(run_dir, template_dir)
    di_template, gi_template = _load_template_inputs(template_dir)

    di_content = build_di(di_template, mode)
    gi_imag = build_gi_phase_content(
        gi_template, omega, diag_stride, "imag", nrows, ncols
    )
    gi_real = build_gi_phase_content(
        gi_template, omega, diag_stride, "real", nrows, ncols
    )

    with open(os.path.join(run_dir, "di_modified.dat"), "w") as f:
        f.write(di_content)
    with open(os.path.join(run_dir, "gi_imag_modified.dat"), "w") as f:
        f.write(gi_imag)
    with open(os.path.join(run_dir, "gi_real_modified.dat"), "w") as f:
        f.write(gi_real)

    return run_dir_name, run_dir
