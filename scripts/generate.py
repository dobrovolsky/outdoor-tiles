import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import yaml

from common import TILES_DIR, require, run

SCRIPTS_DIR = TILES_DIR / "scripts"
SOURCES_DIR = TILES_DIR / "sources"
OUTPUT_DIR = TILES_DIR / "output"
TMP_DIR = TILES_DIR / "tmp"
BASEMAP_PROFILE_JAR = TILES_DIR / "planetiler-openmaptiles.jar"
BASEMAP_PROFILE_VERSION = TILES_DIR / ".planetiler-openmaptiles.version"
PLANETILER_JAR = TILES_DIR / "planetiler.jar"
PLANETILER_VERSION = TILES_DIR / ".planetiler.version"
ROUTES_PROFILE_JAR = TILES_DIR / "routes-profile.jar"
BASEMAP_PROFILE_PATCH = TILES_DIR / "planetiler-openmaptiles.patch"
BASEMAP_PROFILE_BUILDER = SCRIPTS_DIR / "build_profile.py"
ROUTES_PROFILE_BUILDER = SCRIPTS_DIR / "build_routes.py"
ROUTES_PROFILE_SOURCE_DIR = TILES_DIR / "profiles" / "routes"
SHIELD_SPRITE_GENERATOR = TILES_DIR / "tools" / "waymarked-sprite" / "generate.py"
SHIELDS_PATH = TMP_DIR / "shields.txt"
ROUTES_SPRITE_PATH = OUTPUT_DIR / "routes-sprite"
TARGETS = ("basemap", "poi", "routes")


@dataclass(frozen=True)
class Options:
    scope: str
    countries: tuple[str, ...]
    openmaptiles_repository: str
    openmaptiles_commit: str
    replace: bool


def newer(source: Path, destination: Path) -> bool:
    return source.stat().st_mtime > destination.stat().st_mtime


def prepare_output(output: Path, replace: bool) -> None:
    if output.exists() and not replace:
        raise SystemExit(f"Output exists: {output}\nRe-run with --replace to replace it.")


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

    def run_basemap(self, *args: str) -> None:
        self.java(
            "-jar",
            self.path(BASEMAP_PROFILE_JAR),
            *args,
        )

    def run_routes(self, *args: str) -> None:
        main_class = "studio.gpx.tiles.routes.RoutesProfile"
        self.java(
            "-cp",
            os.pathsep.join(map(self.path, (ROUTES_PROFILE_JAR, PLANETILER_JAR))),
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
        and PLANETILER_VERSION.is_file()
        and PLANETILER_VERSION.read_text().strip() == version
    ):
        return
    temporary = PLANETILER_JAR.with_suffix(".tmp.jar")
    bundled_jar = os.environ.get("BUNDLED_PLANETILER_JAR")
    bundled_version = os.environ.get("BUNDLED_PLANETILER_VERSION")
    if bundled_jar and bundled_version == version:
        print(f"Using bundled Planetiler {version}...")
        shutil.copy2(bundled_jar, temporary)
    else:
        require("curl")
        print(f"Downloading Planetiler {version}...")
        run(
            "curl",
            "--fail",
            "--location",
            "--output",
            str(temporary),
            f"https://github.com/onthegomap/planetiler/releases/download/v{version}/planetiler.jar",
        )
    temporary.replace(PLANETILER_JAR)
    PLANETILER_VERSION.write_text(f"{version}\n")


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
            print(f"Downloading {country}...")
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
            print(f"Reusing {pbf}")
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
        print(f"Merging {len(sources)} {label} extracts...")
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
        print(f"Reusing {planet}")
        return planet

    require("curl")
    SOURCES_DIR.mkdir(exist_ok=True)
    partial = planet.with_suffix(planet.suffix + ".part")
    print("Downloading Planet PBF (resume supported)...")
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


@contextmanager
def source(options: Options, runner: ToolRunner) -> Iterator[Path]:
    if options.scope == "country":
        with merged_sources(ensure_country_sources(options), "countries", runner) as path:
            yield path
    else:
        yield ensure_world_source(options)


def generate_osmium_filters(schema_path: Path) -> str:
    schema = yaml.safe_load(schema_path.read_text())
    filters = defaultdict(set)
    presence_filters = set()

    def collect(condition: dict) -> None:
        for key, value in condition.items():
            if key.startswith("__"):
                for nested_condition in value:
                    collect(nested_condition)
            elif value == "__any__":
                if key != "name":
                    presence_filters.add(key)
            else:
                filters[key].update(value if isinstance(value, list) else [value])

    for layer in schema["layers"]:
        for feature in layer.get("features", []):
            if condition := feature.get("include_when"):
                collect(condition)

    expressions = []
    for key in sorted(filters.keys() | presence_filters):
        if key in presence_filters:
            expressions.append(f"nwr/{key}")
        else:
            values = ",".join(sorted(map(str, filters[key])))
            expressions.append(f"nwr/{key}={values}")
    return "\n".join(expressions) + "\n"


def filter_source(kind: str, raw: Path, filtered: Path, runner: ToolRunner) -> Path:
    if filtered.is_file():
        print(f"Reusing {filtered}")
        return filtered

    temporary = filtered.with_suffix(filtered.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    print(f"Filtering {kind} data from {raw}...")

    if kind == "routes":
        expression_options = []
        inline_expressions = ["r/route=hiking,foot,bicycle"]
        remove_tags = []
    elif kind == "poi":
        expressions = TMP_DIR / "poi-filters.txt"
        expressions.write_text(
            generate_osmium_filters(TILES_DIR / "schemas" / "poi.yml")
        )
        expression_options = [f"--expressions={runner.path(expressions)}"]
        inline_expressions = []
        remove_tags = ["--remove-tags"]
    else:
        raise SystemExit(f"Unknown filtered source: {kind}")

    runner.run_osmium(
        "tags-filter",
        "--progress",
        *remove_tags,
        *expression_options,
        f"--output={runner.path(temporary)}",
        "--output-format=pbf",
        runner.path(raw),
        *inline_expressions,
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

    filtered = SOURCES_DIR / f"{kind}-world.osm.pbf"
    if filtered.is_file():
        print(f"Reusing {filtered} (raw Planet PBF is not needed)")
        yield filtered
        return

    yield filter_source(kind, ensure_world_source(options), filtered, runner)


def ensure_basemap_profile(repository: str, commit: str) -> None:
    expected_version = f"{repository}@{commit}"
    correct_version = (
        BASEMAP_PROFILE_VERSION.is_file()
        and BASEMAP_PROFILE_VERSION.read_text().strip() == expected_version
    )
    inputs = (BASEMAP_PROFILE_PATCH, BASEMAP_PROFILE_BUILDER)
    if (
        not BASEMAP_PROFILE_JAR.is_file()
        or any(newer(path, BASEMAP_PROFILE_JAR) for path in inputs)
        or not correct_version
    ):
        run(
            sys.executable,
            str(BASEMAP_PROFILE_BUILDER),
            "--repository",
            repository,
            "--commit",
            commit,
        )


def ensure_routes_profile(planetiler_version: str) -> None:
    ensure_planetiler_jar(planetiler_version)
    inputs = (
        ROUTES_PROFILE_BUILDER,
        PLANETILER_JAR,
        *ROUTES_PROFILE_SOURCE_DIR.rglob("*.java"),
    )
    if not ROUTES_PROFILE_JAR.is_file() or any(newer(path, ROUTES_PROFILE_JAR) for path in inputs):
        run(sys.executable, str(ROUTES_PROFILE_BUILDER))


def generate_basemap(options: Options, runner: ToolRunner) -> None:
    output = OUTPUT_DIR / "openmaptiles.mbtiles"
    temporary = OUTPUT_DIR / "openmaptiles.tmp.mbtiles"
    prepare_output(output, options.replace)
    ensure_basemap_profile(
        options.openmaptiles_repository,
        options.openmaptiles_commit,
    )
    temporary.unlink(missing_ok=True)

    print(f"Generating basemap ({options.scope})...")
    with source(options, runner) as osm_pbf:
        runner.run_basemap(
            f"--osm-path={runner.path(osm_pbf)}",
            "--download",
            "--download-threads=10",
            "--download-chunk-size-mb=1000",
            "--fetch-wikidata",
            f"--output={runner.path(temporary)}",
            "--nodemap-type=sortedtable",
            "--storage=mmap",
            "--force",
        )
    temporary.replace(output)
    print(f"Done: {output}")


def generate_poi(options: Options, runner: ToolRunner) -> None:
    output = OUTPUT_DIR / "poi.mbtiles"
    temporary = OUTPUT_DIR / "poi.tmp.mbtiles"
    prepare_output(output, options.replace)
    ensure_planetiler_jar(runner.version)
    temporary.unlink(missing_ok=True)

    print(f"Generating POI tiles ({options.scope})...")
    with filtered_source("poi", options, runner) as poi_pbf:
        runner.run_custom(
            f"--schema={runner.path(TILES_DIR / 'schemas' / 'poi.yml')}",
            f"--osm-path={runner.path(poi_pbf)}",
            f"--output={runner.path(temporary)}",
            "--force",
        )
    temporary.replace(output)
    print(f"Done: {output}")


def generate_routes(options: Options, runner: ToolRunner) -> None:
    output = OUTPUT_DIR / "routes.mbtiles"
    temporary = OUTPUT_DIR / "routes.tmp.mbtiles"
    prepare_output(output, options.replace)
    ensure_routes_profile(runner.version)
    temporary.unlink(missing_ok=True)

    print(f"Generating hiking, foot and bicycle routes ({options.scope})...")
    with filtered_source("routes", options, runner) as routes_pbf:
        runner.run_routes(
            f"--osm-path={runner.path(routes_pbf)}",
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
        str(ROUTES_SPRITE_PATH),
    )
    temporary.replace(output)
    print(f"Done: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate vector tile targets")
    parser.add_argument("targets", nargs="*", choices=TARGETS)
    parser.add_argument(
        "--scope",
        choices=("country", "world"),
        help="override target-specific scopes",
    )
    for target in TARGETS:
        parser.add_argument(
            f"--{target}-scope",
            choices=("country", "world"),
            required=True,
        )
    parser.add_argument("--java-memory", required=True)
    parser.add_argument("--planetiler-version", required=True)
    parser.add_argument("--openmaptiles-repository", required=True)
    parser.add_argument("--openmaptiles-commit", required=True)
    parser.add_argument(
        "--country",
        action="append",
        default=[],
        metavar="GEOFABRIK_PATH",
        help="Geofabrik path; repeat for multiple countries (example: europe/monaco)",
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    targets = args.targets or TARGETS
    scopes = {
        target: args.scope or getattr(args, f"{target}_scope")
        for target in targets
    }
    if "country" in scopes.values() and not args.country:
        parser.error(
            "--country is required for country scope "
            "(example: --country europe/monaco)"
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    SOURCES_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)
    runner = ToolRunner(args.java_memory, args.planetiler_version)

    generators = {
        "basemap": generate_basemap,
        "poi": generate_poi,
        "routes": generate_routes,
    }
    for target in targets:
        options = Options(
            scope=scopes[target],
            countries=tuple(args.country),
            openmaptiles_repository=args.openmaptiles_repository,
            openmaptiles_commit=args.openmaptiles_commit,
            replace=args.replace,
        )
        generators[target](options, runner)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
