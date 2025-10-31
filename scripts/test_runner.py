"""Lightweight test executor.

Runs pytest locally inside the current environment with a timeout. This is a
non-containerized fallback suitable for pilot usage. For full isolation, a
Docker-based executor can be added later.
"""

from typing import Dict, List
from pathlib import Path
import subprocess
import shutil


def run_pytest(repo_path: str, timeout: int = 600, extra_args: List[str] | None = None) -> Dict:
    repo = Path(repo_path)
    if not repo.exists():
        return {"status": "error", "error": f"repo_path not found: {repo}"}
    pytest_bin = shutil.which("pytest")
    if not pytest_bin:
        return {"status": "skipped", "reason": "pytest_not_installed"}
    cmd = [pytest_bin, "-q"]
    if extra_args:
        cmd += list(extra_args)
    try:
        cp = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok" if cp.returncode == 0 else "fail",
            "returncode": cp.returncode,
            "stdout": cp.stdout[-20000:],
            "stderr": cp.stderr[-20000:],
        }
    except subprocess.TimeoutExpired as e:
        return {"status": "timeout", "stdout": (e.stdout or "")[-20000:], "stderr": (e.stderr or "")[-20000:]}


def run_tests_in_docker(repo_path: str, timeout: int = 600) -> Dict:
    """Compatibility shim to existing API; currently calls local pytest fallback."""
    return run_pytest(repo_path, timeout)
