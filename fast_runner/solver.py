import signal
import subprocess
import sys

_current_solver_process = None


def _sigint_handler(signum, frame):
    global _current_solver_process
    if _current_solver_process is not None:
        try:
            _current_solver_process.terminate()
            _current_solver_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                _current_solver_process.kill()
            except ProcessLookupError:
                pass
        _current_solver_process = None
    print("\n[Stopped by user (Ctrl+C)]")
    sys.exit(130)


def install_sigint_handler() -> None:
    signal.signal(signal.SIGINT, _sigint_handler)


def run_solver_script(
    cwd: str, script_name: str, capture_output_on_failure: bool = False
) -> int:
    """Run a script in cwd. If capture_output_on_failure is True and the script
    exits non-zero, stdout/stderr are printed so the user can see the error."""
    global _current_solver_process
    if capture_output_on_failure:
        proc = subprocess.Popen(
            ["./" + script_name],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    else:
        proc = subprocess.Popen(
            ["./" + script_name],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    _current_solver_process = proc
    try:
        if capture_output_on_failure:
            out, _ = proc.communicate()
            code = proc.returncode
            if code != 0 and out:
                print(f"  [solver output from {script_name}, exit {code}]:")
                for line in out.strip().splitlines()[-50:]:  # last 50 lines
                    print(f"    {line}")
            return code
        return proc.wait()
    finally:
        _current_solver_process = None
