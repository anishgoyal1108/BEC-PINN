import os
import shutil

from .settings import SCRIPT_DIR, TEMPLATE_DIR, TEMPLATE_REQUIRED_FILES, get_geometry_mode

_DI_WD_LINE_INDEX = 25
_DI_NROWS_LINE_INDEX = 53
_DI_NCOLS_LINE_INDEX = 60
_DI_UB_ROW0_LINE_INDEX = 95
_DI_UB_ROW1_LINE_INDEX = 96


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


_GI_NT_LINE_INDEX = 54
_GI_NFRAMES_LINE_INDEX = 68
_GI_TFF_LINE_INDEX = 82

_REAL_NT = 117268
_REAL_NFRAMES = 290
_REAL_TFF = 4.69072


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
) -> str:
    phase_lower = phase.lower()
    is_real = phase_lower == "real"

    content = replace_real_or_imag_in_gi(template_content, 1 if is_real else 0)
    content = replace_read_initial_wf_in_gi(content, 1 if is_real else 0)
    content = replace_phase_imprint_in_gi(content, 1 if is_real else 0)
    content = replace_omega_in_gi(content, omega)
    content = replace_diag_stride_in_gi(content, diag_stride)
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


def _copy_template_support_files(run_dir: str, template_dir: str = TEMPLATE_DIR) -> None:
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
    with open(os.path.join(template_dir, "rfgpe_2d_solver_general_inputs.dat"), "r") as f:
        gi_template = f.read()
    return di_template, gi_template


def _prepare_directory_shared(
    omega: float,
    ub_str: str,
    diag_stride: int,
    build_di_content_fn,
    geometry_mode: str | None = None,
    experiment_k: int | None = None,
    template_dir: str = TEMPLATE_DIR,
) -> tuple[str, str]:
    mode = (geometry_mode or get_geometry_mode()).lower()
    run_dir_base = _build_run_dir_name(omega, ub_str, mode, experiment_k)
    run_dir_name = _unique_run_dir_name(run_dir_base)
    run_dir = os.path.join(SCRIPT_DIR, run_dir_name)
    os.makedirs(run_dir, exist_ok=True)

    _copy_template_support_files(run_dir, template_dir)
    di_template_content, gi_template_content = _load_template_inputs(template_dir)

    di_content = build_di_content_fn(di_template_content, mode)
    gi_imag = build_gi_phase_content(gi_template_content, omega, diag_stride, "imag")
    gi_real = build_gi_phase_content(gi_template_content, omega, diag_stride, "real")

    with open(os.path.join(run_dir, "di_modified.dat"), "w") as f:
        f.write(di_content)
    with open(os.path.join(run_dir, "gi_imag_modified.dat"), "w") as f:
        f.write(gi_imag)
    with open(os.path.join(run_dir, "gi_real_modified.dat"), "w") as f:
        f.write(gi_real)

    return run_dir_name, run_dir


def prepare_directory(
    omega: float,
    ubmax_seu: float,
    ub_str: str,
    diag_stride: int,
    geometry_mode: str | None = None,
) -> str:
    run_dir_name, _run_dir = _prepare_directory_shared(
        omega=omega,
        ub_str=ub_str,
        diag_stride=diag_stride,
        build_di_content_fn=lambda di_template, mode: build_di_content_1x1(
            di_template,
            ubmax_seu=ubmax_seu,
            geometry_mode=mode,
        ),
        geometry_mode=geometry_mode,
    )
    return run_dir_name


def prepare_directory_2x2(
    omega: float,
    experiment_k: int,
    ub_ref_seu: float,
    ubmax_assignment_seu: dict[str, float],
    diag_stride: int,
    geometry_mode: str | None = None,
) -> tuple[str, str]:
    ub_str = ub_str_for_dir(ub_ref_seu)
    return _prepare_directory_shared(
        omega=omega,
        ub_str=ub_str,
        diag_stride=diag_stride,
        build_di_content_fn=lambda di_template, mode: build_di_content_2x2(
            di_template,
            ubmax_assignment_seu=ubmax_assignment_seu,
            geometry_mode=mode,
        ),
        geometry_mode=geometry_mode,
        experiment_k=experiment_k,
    )
