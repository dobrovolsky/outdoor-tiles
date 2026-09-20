import argparse
import json
import re
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


DEMO_DIR = Path(__file__).resolve().parent
TILES_DIR = DEMO_DIR / "static" / "tiles"
TILESET_NAME = re.compile(r"[a-zA-Z0-9_-]+")


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def do_GET(self):
        parts = urlparse(self.path).path.strip("/").split("/")

        if len(parts) == 2 and parts[0] == "tiles":
            self.serve_tilejson(parts[1])
            return

        if len(parts) == 5 and parts[0] == "tiles":
            self.serve_tile(parts[1], parts[2], parts[3], parts[4])
            return

        super().do_GET()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def serve_tilejson(self, name: str):
        path = mbtiles_path(name)
        if path is None:
            self.send_error(404, "Tileset not found")
            return

        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as database:
            metadata = dict(database.execute("SELECT name, value FROM metadata"))

        embedded = json.loads(metadata.get("json", "{}"))
        payload = {
            "tilejson": "3.0.0",
            "name": metadata.get("name", name),
            "scheme": "xyz",
            "tiles": [
                f"http://{self.headers['Host']}/tiles/{name}/{{z}}/{{x}}/{{y}}.pbf"
            ],
            "minzoom": int(metadata.get("minzoom", 0)),
            "maxzoom": int(metadata.get("maxzoom", 14)),
            "bounds": numbers(metadata.get("bounds")),
            "center": numbers(metadata.get("center")),
            "vector_layers": embedded.get("vector_layers", []),
        }
        if attribution := metadata.get("attribution"):
            payload["attribution"] = attribution

        self.send_json(payload)

    def serve_tile(self, name: str, zoom: str, column: str, row: str):
        path = mbtiles_path(name)
        if path is None or not row.endswith(".pbf"):
            self.send_error(404, "Tile not found")
            return

        try:
            z = int(zoom)
            x = int(column)
            y = int(row.removesuffix(".pbf"))
        except ValueError:
            self.send_error(404, "Tile not found")
            return

        tms_y = (1 << z) - 1 - y
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as database:
            result = database.execute(
                """
                SELECT tile_data
                FROM tiles
                WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
                """,
                (z, x, tms_y),
            ).fetchone()

        if result is None:
            self.send_response(204)
            self.end_headers()
            return

        data = result[0]
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.mapbox-vector-tile")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, value: object):
        data = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def mbtiles_path(name: str) -> Path | None:
    if not TILESET_NAME.fullmatch(name):
        return None

    path = TILES_DIR / f"{name}.mbtiles"
    return path if path.is_file() else None


def numbers(value: str | None) -> list[float]:
    return [float(number) for number in value.split(",")] if value else []


def main():
    parser = argparse.ArgumentParser(description="Preview generated MBTiles")
    parser.add_argument("--port", type=int, default=8080)
    options = parser.parse_args()

    server = ThreadingHTTPServer(("", options.port), DemoHandler)
    print(f"Demo: http://localhost:{options.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
