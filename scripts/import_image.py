"""Create a small, metadata-free blog image without changing the original."""
import argparse
from pathlib import Path

from PIL import Image, ImageOps


def import_image(source, destination, max_size=1600):
    source, destination = Path(source), Path(destination)
    if destination.suffix.lower() != ".webp" or max_size < 1:
        raise ValueError("Use a .webp destination and positive maximum size")
    with Image.open(source) as original:
        if getattr(original, "is_animated", False):
            raise ValueError("Animated images are not supported by this importer")
        oriented = ImageOps.exif_transpose(original)
        oriented.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        converted = oriented.convert("RGBA" if "A" in oriented.getbands() else "RGB")
        clean = Image.new(converted.mode, converted.size)
        clean.paste(converted)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            clean.save(output, format="WEBP", quality=82, method=6)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="New .webp file under static/assets/images/")
    args = parser.parse_args()
    result = import_image(args.source, args.destination)
    print(f"Created {result} ({result.stat().st_size:,} bytes); original preserved")
