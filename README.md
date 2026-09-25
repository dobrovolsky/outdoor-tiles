# Outdoor style

![Liberty Topo and OpenFreeMap comparison](demo/static/screenshot.png)

Builds three small OpenStreetMap-based MBTiles by default:

- `output/low-zoom-outdoor.mbtiles` - paths, tracks, service, minor, and tertiary roads from 10 to 13, so it can
  be displayed earlier.
- `output/trails.mbtiles` - hiking, foot, and bicycle trails, similar to [Waymarked Trails](https://waymarkedtrails.org/)
- `output/poi.mbtiles` - selected outdoor POIs

Trail generation also creates sprite:

- `output/trails-sprite.png` and `output/trails-sprite.json`
- `output/trails-sprite@2x.png` and `output/trails-sprite@2x.json`

## Highlights

- Adds [maplibre-contour](https://github.com/onthegomap/maplibre-contour)
- Based on [gpxstudio's Liberty Topo](https://github.com/gpxstudio/styles/blob/main/liberty-topo.json)
- Custom colors for bicycle trails and restricted areas
- Provides low-zoom outdoor context and selected POIs as small overlays
- Shows hiking trails

## Usage

Install [Docker](https://docs.docker.com/get-docker/), then run:

```sh
./tiles.sh generate --country europe/monaco
```

Country values are [Geofabrik](https://download.geofabrik.de/) extract paths.
Repeat `--country` to combine extracts. To generate selected targets:

```sh
./tiles.sh generate low-zoom-outdoor trails --country europe/monaco
```

Use `--world` instead of `--country` to generate from the full OpenStreetMap planet:

```sh
./tiles.sh generate trails --world
```

## Licenses

The code is MIT-licensed.

`tools/waymarked-sprite` is GPL-3.0 and uses `waymarkedtrails-shields` under
the same license.

Run `./tiles.sh` to list all commands.

## Demo

```sh
./tiles.sh demo
```

Open [http://localhost:8080](http://localhost:8080).
