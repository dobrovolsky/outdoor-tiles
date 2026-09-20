#!/bin/sh

set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$root"

java_memory=16g
planetiler_version=0.10.2
tiles_image="gpx-studio-tiles:$planetiler_version"
demo_image=ghcr.io/astral-sh/uv:0.12.17-python3.14-trixie-slim
openmaptiles_repository=https://github.com/openmaptiles/planetiler-openmaptiles.git
openmaptiles_commit=7adf3bbc34576a3c7e70e069670f404152d88f9e

usage() {
    cat <<'EOF'
Usage:
  ./tiles.sh generate [basemap|poi|routes ...] [options]
  ./tiles.sh generate-local [basemap|poi|routes ...] [options]
  ./tiles.sh generate-world-poi
  ./tiles.sh generate-world-routes
  ./tiles.sh demo
  ./tiles.sh deploy

Example:
  ./tiles.sh generate --country europe/monaco
EOF
}

build_image() {
    docker build \
        --build-arg "PLANETILER_VERSION=$planetiler_version" \
        --tag "$tiles_image" \
        .
}

generate() {
    build_image
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        --env HOME=/tmp \
        --volume "$root:/data" \
        --workdir /data \
        "$tiles_image" \
        "--java-memory=$java_memory" \
        --basemap-scope=country \
        --poi-scope=country \
        --routes-scope=country \
        "--planetiler-version=$planetiler_version" \
        "--openmaptiles-repository=$openmaptiles_repository" \
        "--openmaptiles-commit=$openmaptiles_commit" \
        --replace \
        "$@"
}

generate_local() {
    uv run python ./scripts/generate.py \
        "--java-memory=$java_memory" \
        --basemap-scope=country \
        --poi-scope=country \
        --routes-scope=country \
        "--planetiler-version=$planetiler_version" \
        "--openmaptiles-repository=$openmaptiles_repository" \
        "--openmaptiles-commit=$openmaptiles_commit" \
        --replace \
        "$@"
}

demo() {
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        --env HOME=/tmp \
        --publish 8080:8080 \
        --volume "$root:/data" \
        --workdir /data \
        --entrypoint python \
        "$demo_image" \
        demo/server.py
}

command=${1:-help}
if [ "$#" -gt 0 ]; then
    shift
fi

case "$command" in
    generate) generate "$@" ;;
    generate-local) generate_local "$@" ;;
    generate-world-poi) generate poi --scope world "$@" ;;
    generate-world-routes) generate routes --scope world "$@" ;;
    demo) demo "$@" ;;
    deploy)
        mkdir -p "$HOME/media/tiles"
        cp output/*.mbtiles "$HOME/media/tiles/"
        ;;
    help|-h|--help) usage ;;
    *)
        usage >&2
        exit 2
        ;;
esac
