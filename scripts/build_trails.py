import shutil
import subprocess
import sys
from pathlib import Path

from common import TILES_DIR, require, run

SOURCE_DIR = TILES_DIR / "profiles" / "trails"
BUILD_DIR = TILES_DIR / "tmp" / "trails-classes"
PLANETILER_JAR = TILES_DIR / "planetiler.jar"
OUTPUT_JAR = TILES_DIR / "trails-profile.jar"


def java_sources() -> list[Path]:
    sources = sorted(SOURCE_DIR.rglob("*.java"))
    if not sources:
        raise SystemExit(f"No Java sources found in {SOURCE_DIR}")
    return sources


def build_trails(sources: list[Path], temporary: Path) -> None:
    require("javac")
    require("jar")
    run(
        "javac",
        "--release",
        "21",
        "-proc:none",
        "-implicit:none",
        "-sourcepath",
        str(BUILD_DIR),
        "-cp",
        str(PLANETILER_JAR),
        "-d",
        str(BUILD_DIR),
        *map(str, sources),
    )
    run(
        "jar",
        "--create",
        "--file",
        str(temporary),
        "-C",
        str(BUILD_DIR),
        ".",
    )


def main() -> None:
    sources = java_sources()
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    BUILD_DIR.mkdir(parents=True)
    temporary = OUTPUT_JAR.with_suffix(".tmp.jar")
    temporary.unlink(missing_ok=True)

    build_trails(sources, temporary)

    temporary.replace(OUTPUT_JAR)
    print(f"Built {OUTPUT_JAR}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
