import argparse
import json
import math
from pathlib import Path

import cairo
import gi

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg
from wmt_shields import ShieldFactory
from wmt_shields.wmt_config import WmtConfig


class SpriteConfig(WmtConfig):
    image_border_width = 1.0


SPRITE_GUTTER = 2


def load_symbols(path: Path) -> list[str]:
    return sorted({symbol.strip() for symbol in path.read_text().splitlines() if symbol.strip()})


def render_shields(symbols: list[str]) -> list[tuple[str, bytes, int, int]]:
    factory = ShieldFactory((".osmc_symbol",), SpriteConfig())
    rendered = []

    for symbol in symbols:
        shield = factory.create(
            {"osmc:symbol": symbol},
            "",
            border_color=(0.33, 0.33, 0.33),
        )
        if shield is None:
            print(f"Skipping unsupported OSMC symbol: {symbol}")
            continue
        width, height = shield.dimensions()
        rendered.append((symbol, shield.create_image("svg"), math.ceil(width), math.ceil(height)))

    return rendered


def write_scale(
    shields: list[tuple[str, bytes, int, int]],
    output: Path,
    scale: int,
) -> None:
    cell_width = max((shield[2] for shield in shields), default=16)
    cell_height = max((shield[3] for shield in shields), default=16)
    columns = max(1, math.ceil(math.sqrt(len(shields) * cell_height / cell_width)))
    rows = max(1, math.ceil(len(shields) / columns))
    stride_width = cell_width + 2 * SPRITE_GUTTER
    stride_height = cell_height + 2 * SPRITE_GUTTER
    surface = cairo.ImageSurface(
        cairo.FORMAT_ARGB32,
        columns * stride_width * scale,
        rows * stride_height * scale,
    )
    context = cairo.Context(surface)
    index = {}

    for position, (symbol, svg, width, height) in enumerate(shields):
        x = position % columns * stride_width + SPRITE_GUTTER
        y = position // columns * stride_height + SPRITE_GUTTER
        viewport = Rsvg.Rectangle()
        viewport.x = (x + (cell_width - width) / 2) * scale
        viewport.y = (y + (cell_height - height) / 2) * scale
        viewport.width = width * scale
        viewport.height = height * scale
        Rsvg.Handle.new_from_data(svg).render_document(context, viewport)
        index[symbol] = {
            "width": cell_width * scale,
            "height": cell_height * scale,
            "x": x * scale,
            "y": y * scale,
            "pixelRatio": scale,
        }

    suffix = "" if scale == 1 else "@2x"
    surface.write_to_png(str(output) + suffix + ".png")
    Path(str(output) + suffix + ".json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MapLibre sprites from OSMC symbols")
    parser.add_argument("symbols", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shields = render_shields(load_symbols(args.symbols))
    write_scale(shields, args.output, 1)
    write_scale(shields, args.output, 2)


if __name__ == "__main__":
    main()
