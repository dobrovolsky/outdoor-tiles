import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from common import TILES_DIR, require, run
from filter_tags import FILTER_TAGS_BY_TARGET

SCRIPTS_DIR = TILES_DIR / "scripts"
SOURCES_DIR = TILES_DIR / "sources"
OUTPUT_DIR = TILES_DIR / "output"
TMP_DIR = TILES_DIR / "tmp"
PLANETILER_JAR = TILES_DIR / "planetiler.jar"
PLANETILER_VERSION_FILE = TILES_DIR / ".planetiler.version"
TRAILS_PROFILE_JAR = TILES_DIR / "trails-profile.jar"
TRAILS_PROFILE_BUILDER = SCRIPTS_DIR / "build_trails.py"
TRAILS_PROFILE_SOURCE_DIR = TILES_DIR / "profiles" / "trails"
LOW_ZOOM_OUTDOOR_SCHEMA = TILES_DIR / "schemas" / "low_zoom_outdoor.yml"
SHIELD_SPRITE_GENERATOR = TILES_DIR / "tools" / "waymarked-sprite" / "generate.py"
SHIELDS_PATH = TMP_DIR / "shields.txt"
TRAILS_SPRITE_PATH = OUTPUT_DIR / "trails-sprite"
TARGETS = ("low-zoom-outdoor", "poi", "trails")


def log(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True)
class Options:
    scope: str
    countries: tuple[str, ...]


def newer(source: Path, destination: Path) -> bool:
    return source.stat().st_mtime > destination.stat().st_mtime


class ToolRunner:
    def __init__(self, java_memory: str, version: str) -> None:
        self.java_memory = java_memory
        self.version = version
        require("java")
        require("osmium")

    def path(self, path: Path) -> str:
        return str(path.resolve())

    def java(self, *command: str) -> None:
        run(
            "java",
            f"-Xmx{self.java_memory}",
            "-XX:MaxHeapFreeRatio=40",
            *command,
        )

    def run_trails(self, *args: str) -> None:
        main_class = "tiles.trails.TrailsProfile"
        self.java(
            "-cp",
            os.pathsep.join(map(self.path, (TRAILS_PROFILE_JAR, PLANETILER_JAR))),
            main_class,
            *args,
        )

    def run_custom(self, *args: str) -> None:
        self.java(
            "-jar",
            self.path(PLANETILER_JAR),
            "generate-custom",
            *args,
        )

    def run_osmium(self, *args: str) -> None:
        run("osmium", *args)


def ensure_planetiler_jar(version: str) -> None:
    if (
        PLANETILER_JAR.is_file()
        and PLANETILER_VERSION_FILE.is_file()
        and PLANETILER_VERSION_FILE.read_text().strip() == version
    ):
        return
    temporary = PLANETILER_JAR.with_suffix(".tmp.jar")
    bundled_jar = os.environ.get("BUNDLED_PLANETILER_JAR")
    bundled_version = os.environ.get("BUNDLED_PLANETILER_VERSION")
    if bundled_jar and bundled_version == version:
        log(f"Using bundled Planetiler {version}...")
        shutil.copy2(bundled_jar, temporary)
    else:
        require("curl")
        log(f"Downloading Planetiler {version}...")
        run(
            "curl",
            "--fail",
            "--location",
            "--output",
            str(temporary),
            f"https://github.com/onthegomap/planetiler/releases/download/v{version}/planetiler.jar",
        )
    temporary.replace(PLANETILER_JAR)
    PLANETILER_VERSION_FILE.write_text(f"{version}\n")


def country_cache_path(country: str, stage: str) -> Path:
    slug = country.replace("/", "-")
    suffix = "latest" if stage == "source" else stage
    return SOURCES_DIR / f"{slug}-{suffix}.osm.pbf"


def ensure_country_sources(options: Options) -> tuple[Path, ...]:
    if not options.countries:
        raise SystemExit("No --country arguments provided")

    pbf_files: list[Path] = []
    SOURCES_DIR.mkdir(exist_ok=True)

    for country in options.countries:
        pbf = country_cache_path(country, "source")
        if not pbf.is_file():
            require("curl")
            temporary = pbf.with_suffix(pbf.suffix + ".tmp")
            temporary.unlink(missing_ok=True)
            log(f"Downloading {country}...")
            run(
                "curl",
                "--fail",
                "--location",
                "--output",
                str(temporary),
                f"https://download.geofabrik.de/{country}-latest.osm.pbf",
            )
            temporary.replace(pbf)
        else:
            log(f"Reusing {pbf}")
        pbf_files.append(pbf)

    return tuple(pbf_files)


@contextmanager
def merged_sources(
    sources: tuple[Path, ...], label: str, runner: ToolRunner
) -> Iterator[Path]:
    if len(sources) == 1:
        yield sources[0]
        return

    TMP_DIR.mkdir(exist_ok=True)
    descriptor, filename = tempfile.mkstemp(
        prefix=f"{label}-",
        suffix=".osm.pbf",
        dir=TMP_DIR,
    )
    os.close(descriptor)
    merged = Path(filename)
    merged.unlink()

    try:
        log(f"Merging {len(sources)} {label} extracts...")
        runner.run_osmium(
            "merge",
            "--overwrite",
            "--output-format=pbf",
            f"--output={runner.path(merged)}",
            *map(runner.path, sources),
        )
        yield merged
    finally:
        merged.unlink(missing_ok=True)


def ensure_world_source(options: Options) -> Path:
    planet = SOURCES_DIR / "planet-latest.osm.pbf"
    if planet.is_file():
        log(f"Reusing {planet}")
        return planet

    require("curl")
    SOURCES_DIR.mkdir(exist_ok=True)
    partial = planet.with_suffix(planet.suffix + ".part")
    log("Downloading Planet PBF (resume supported)...")
    run(
        "curl",
        "--fail",
        "--location",
        "--continue-at",
        "-",
        "--output",
        str(partial),
        "https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf",
    )
    partial.replace(planet)
    return planet


def filter_source(kind: str, raw: Path, filtered: Path, runner: ToolRunner) -> Path:
    if filtered.is_file():
        log(f"Reusing {filtered}")
        return filtered

    temporary = filtered.with_suffix(filtered.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    log(f"Filtering {kind} data from {raw}...")

    try:
        filter_tags = FILTER_TAGS_BY_TARGET[kind]
    except KeyError:
        raise SystemExit(f"Unknown filtered source: {kind}")

    runner.run_osmium(
        "tags-filter",
        "--progress",
        *(["--remove-tags"] if kind == "poi" else []),
        f"--output={runner.path(temporary)}",
        "--output-format=pbf",
        runner.path(raw),
        *filter_tags,
    )
    temporary.replace(filtered)
    return filtered


@contextmanager
def filtered_source(kind: str, options: Options, runner: ToolRunner) -> Iterator[Path]:
    if options.scope == "country":
        raw_sources = ensure_country_sources(options)
        filtered_sources = tuple(
            filter_source(kind, raw, country_cache_path(country, kind), runner)
            for country, raw in zip(options.countries, raw_sources, strict=True)
        )
        with merged_sources(filtered_sources, kind, runner) as path:
            yield path
        return

    filtered = SOURCES_DIR / f"planet-{kind}.osm.pbf"
    if filtered.is_file():
        log(f"Reusing {filtered} (raw Planet PBF is not needed)")
        yield filtered
        return

    yield filter_source(kind, ensure_world_source(options), filtered, runner)


def ensure_trails_profile(planetiler_version: str) -> None:
    ensure_planetiler_jar(planetiler_version)
    inputs = (
        TRAILS_PROFILE_BUILDER,
        PLANETILER_JAR,
        *TRAILS_PROFILE_SOURCE_DIR.rglob("*.java"),
    )
    if not TRAILS_PROFILE_JAR.is_file() or any(newer(path, TRAILS_PROFILE_JAR) for path in inputs):
        run(sys.executable, str(TRAILS_PROFILE_BUILDER))


def generate_poi(options: Options, runner: ToolRunner) -> None:
    output = OUTPUT_DIR / "poi.mbtiles"
    temporary = OUTPUT_DIR / "poi.tmp.mbtiles"
    ensure_planetiler_jar(runner.version)
    temporary.unlink(missing_ok=True)

    log(f"Generating POI tiles ({options.scope})...")
    with filtered_source("poi", options, runner) as poi_pbf:
        runner.run_custom(
            f"--schema={runner.path(TILES_DIR / 'schemas' / 'poi.yml')}",
            f"--osm-path={runner.path(poi_pbf)}",
            f"--output={runner.path(temporary)}",
            "--force",
        )
    temporary.replace(output)
    log(f"Done: {output}")


def generate_low_zoom_outdoor(options: Options, runner: ToolRunner) -> None:
    output = OUTPUT_DIR / "low-zoom-outdoor.mbtiles"
    temporary = OUTPUT_DIR / "low-zoom-outdoor.tmp.mbtiles"
    ensure_planetiler_jar(runner.version)
    temporary.unlink(missing_ok=True)

    log(f"Generating early outdoor roads ({options.scope})...")
    with filtered_source("low-zoom-outdoor", options, runner) as outdoor_pbf:
        runner.run_custom(
            f"--schema={runner.path(LOW_ZOOM_OUTDOOR_SCHEMA)}",
            f"--osm-path={runner.path(outdoor_pbf)}",
            f"--output={runner.path(temporary)}",
            "--force",
        )
    temporary.replace(output)
    log(f"Done: {output}")


def generate_trails(options: Options, runner: ToolRunner) -> None:
    output = OUTPUT_DIR / "trails.mbtiles"
    temporary = OUTPUT_DIR / "trails.tmp.mbtiles"
    ensure_trails_profile(runner.version)
    temporary.unlink(missing_ok=True)

    log(f"Generating hiking, foot and bicycle trails ({options.scope})...")
    with filtered_source("trails", options, runner) as trails_pbf:
        runner.run_trails(
            f"--osm-path={runner.path(trails_pbf)}",
            f"--output={runner.path(temporary)}",
            f"--shields-path={runner.path(SHIELDS_PATH)}",
            "--minzoom=6",
            "--nodemap-type=sortedtable",
            "--storage=mmap",
            "--force",
        )
    sprite_python = os.environ.get("WAYMARKED_SPRITE_PYTHON")
    if sprite_python:
        sprite_command = (sprite_python,)
    else:
        require("uv")
        sprite_command = (
            "uv",
            "run",
            "--project",
            str(SHIELD_SPRITE_GENERATOR.parent),
            "python",
        )
    run(
        *sprite_command,
        str(SHIELD_SPRITE_GENERATOR),
        str(SHIELDS_PATH),
        str(TRAILS_SPRITE_PATH),
    )
    temporary.replace(output)
    log(f"Done: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate vector tile targets")
    parser.add_argument("targets", nargs="*", choices=TARGETS)
    parser.add_argument("--java-memory", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--country",
        action="append",
        default=[],
        metavar="GEOFABRIK_PATH",
        help="Geofabrik path; repeat for multiple countries (example: europe/monaco)",
    )
    source.add_argument(
        "--world",
        action="store_true",
        help="use the full OpenStreetMap planet",
    )
    args = parser.parse_args()

    targets = args.targets or TARGETS
    scope = "world" if args.world else "country"
    planetiler_version = os.environ.get("BUNDLED_PLANETILER_VERSION") or os.environ.get(
        "PLANETILER_VERSION"
    )
    if not planetiler_version:
        parser.error("PLANETILER_VERSION is not set")

    OUTPUT_DIR.mkdir(exist_ok=True)
    SOURCES_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)
    runner = ToolRunner(args.java_memory, planetiler_version)

    generators = {
        "low-zoom-outdoor": generate_low_zoom_outdoor,
        "poi": generate_poi,
        "trails": generate_trails,
    }
    for target in targets:
        log(f"Starting target: {target} ({scope})")
        options = Options(
            scope=scope,
            countries=tuple(args.country),
        )
        generators[target](options, runner)
        log(f"Finished target: {target}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
