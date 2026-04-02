import os
import shutil
import subprocess


def _read_os_release() -> dict[str, str]:
    path = "/etc/os-release"
    values: dict[str, str] = {}
    if not os.path.isfile(path):
        return values

    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key] = val.strip().strip('"').strip("'")
    return values


def preferred_viewer_binary() -> str:
    info = _read_os_release()
    distro_id = info.get("ID", "").lower()
    distro_like = info.get("ID_LIKE", "").lower().split()

    if distro_id == "ubuntu" or "ubuntu" in distro_like:
        return "eog"
    if distro_id == "arch" or "arch" in distro_like:
        return "gwenview"
    return "gwenview"


def resolve_viewer_binary() -> str:
    preferred = preferred_viewer_binary()
    if shutil.which(preferred):
        return preferred

    for candidate in ("eog", "gwenview", "xdg-open"):
        if shutil.which(candidate):
            return candidate
    return preferred


def open_files_in_viewer(paths: list[str]) -> tuple[str, int]:
    viewer = resolve_viewer_binary()
    opened = 0
    for path in paths:
        try:
            subprocess.Popen(
                [viewer, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            opened += 1
        except OSError:
            continue
    return viewer, opened
