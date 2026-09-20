import shutil
import subprocess
from pathlib import Path

TILES_DIR = Path(__file__).resolve().parent.parent


def require(command: str, hint: str = "") -> None:
    if shutil.which(command) is None:
        suffix = f" ({hint})" if hint else ""
        raise SystemExit(f"{command} is required{suffix}")


def run(
    *command: str,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
    )
