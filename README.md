# Outdoor style

![Liberty Topo and OpenFreeMap comparison](demo/static/screenshot.png)

Builds three OpenStreetMap-based MBTiles:

- `output/openmaptiles.mbtiles` - OpenMapTiles basemap; paths, tracks, service, minor, and tertiary roads start at zoom 10
- `output/routes.mbtiles` - hiking, foot, and bicycle route relations, similar to [Waymarked Trails](https://waymarkedtrails.org/)
- `output/poi.mbtiles` - selected outdoor POIs

## Highlights

- Adds [maplibre-contour](https://github.com/onthegomap/maplibre-contour)
- Based on [gpxstudio's Liberty Topo](https://github.com/gpxstudio/styles/blob/main/liberty-topo.json)
- Custom colors for bicycle routes and restricted areas
- Removes basemap POIs and provides selected POIs as a separate overlay
- Shows hiking routes
- Shows paths from zoom 10

## Usage

Install [Docker](https://docs.docker.com/get-docker/), then run:

```sh
./tiles.sh generate --country europe/monaco
```

Country values are [Geofabrik](https://download.geofabrik.de/) extract paths.
Repeat `--country` to combine extracts. To generate one target:

```sh
./tiles.sh generate routes --country europe/monaco
```

Run `./tiles.sh` to list all commands.

## Demo

```sh
./tiles.sh demo
```

Open [http://localhost:8080](http://localhost:8080).
