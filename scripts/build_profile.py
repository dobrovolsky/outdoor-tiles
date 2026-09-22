import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import TILES_DIR, require, run

PROFILE_SOURCE = TILES_DIR / "profiles" / "openmaptiles" / "Transportation.java"
OUTPUT_JAR = TILES_DIR / "planetiler-openmaptiles.jar"
VERSION_FILE = TILES_DIR / ".planetiler-openmaptiles.version"
MAVEN_CACHE = TILES_DIR / ".m2"


def build_profile(source_dir: Path) -> None:
    require("mvn")
    MAVEN_CACHE.mkdir(exist_ok=True)
    run(
        "mvn",
        f"-Dmaven.repo.local={MAVEN_CACHE}",
        "-DskipTests",
        "package",
        cwd=source_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the custom OpenMapTiles basemap profile")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    require("git")
    with tempfile.TemporaryDirectory(prefix="planetiler-openmaptiles.") as directory:
        source_dir = Path(directory) / "source"
        run("git", "clone", "--quiet", args.repository, str(source_dir))
        run(
            "git",
            "checkout",
            "--quiet",
            "--detach",
            args.commit,
            cwd=source_dir,
        )
        shutil.copy2(
            PROFILE_SOURCE,
            source_dir / "src/main/java/org/openmaptiles/layers/Transportation.java",
        )

        build_profile(source_dir)

        jars = list((source_dir / "target").glob("*-with-deps.jar"))
        if len(jars) != 1:
            raise SystemExit(f"Expected one profile JAR, found {len(jars)}")
        shutil.copy2(jars[0], OUTPUT_JAR)

    digest = hashlib.sha256(OUTPUT_JAR.read_bytes()).hexdigest()
    VERSION_FILE.write_text(f"{args.repository}@{args.commit}\n")
    print(f"{digest}  {OUTPUT_JAR}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
