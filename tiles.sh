#!/bin/sh

set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$root"

java_memory=16g
planetiler_version=0.10.2
tiles_image="gpx-studio-tiles:$planetiler_version"
demo_image=ghcr.io/astral-sh/uv:0.12.17-python3.14-trixie-slim
usage() {
    cat <<'EOF'
Usage:
  ./tiles.sh generate [low-zoom-outdoor|poi|trails ...] (--country PATH ... | --world) [options]
  ./tiles.sh generate-local [low-zoom-outdoor|poi|trails ...] (--country PATH ... | --world) [options]
  ./tiles.sh generate-world-low-zoom-outdoor
  ./tiles.sh generate-world-poi
  ./tiles.sh generate-world-trails
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
        "$@"
}

generate_local() {
    PLANETILER_VERSION="$planetiler_version" uv run python ./scripts/generate.py \
        "--java-memory=$java_memory" \
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
    generate-world-low-zoom-outdoor) generate low-zoom-outdoor --world "$@" ;;
    generate-world-poi) generate poi --world "$@" ;;
    generate-world-trails) generate trails --world "$@" ;;
    demo) demo "$@" ;;
    deploy)
        mkdir -p "$HOME/media/tiles"
        cp output/*.mbtiles "$HOME/media/tiles/"
        if [ -f output/trails-sprite.json ]; then
            cp output/trails-sprite.json output/trails-sprite.png \
                output/trails-sprite@2x.json output/trails-sprite@2x.png \
                "$HOME/media/tiles/"
        fi
        ;;
    help|-h|--help) usage ;;
    *)
        usage >&2
        exit 2
        ;;
esac
