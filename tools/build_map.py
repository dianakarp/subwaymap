#!/usr/bin/env python3
"""Keep the subway map current with the MTA's official diagrams.

Downloads the MTA's weekday and late-night subway diagrams (PDFs). If either
one changed, it re-renders the overview images and map tiles the site uses
and stamps the new map version into sw.js, index.html and README.md, so
installed copies of the app download the new map the next time they're online.

    pip install -r tools/requirements.txt
    python tools/build_map.py                # download; rebuild only if the MTA map changed
    python tools/build_map.py --force        # download and rebuild no matter what
    python tools/build_map.py --no-download  # rebuild from the PDFs already in the repo

The "Update subway map" GitHub Action runs this every week.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import imagequant
import pypdfium2 as pdfium
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# name, MTA download URL, PDF in this repo, overview image, tile folder
MAPS = [
    ("day", "https://www.mta.info/map/5256", "mta-subway-map.pdf", "base.png", "tiles"),
    ("night", "https://www.mta.info/map/5336", "mta-subway-map-night.pdf", "base-night.png", "tiles-night"),
]
BASE_WIDTH = 2000                 # overview image, always loaded
LEVELS = [(1, 4000), (2, 8000)]   # (zoom level, width in pixels), cut into tiles
TILE = 1024
RENDER_REVISION = 1               # bump after changing how images are made, so phones re-download them
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0 Safari/537.36 subwaymap-updater (+https://github.com/dianakarp/subwaymap)")


def download(url):
    error = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if not data.startswith(b"%PDF-"):
                raise ValueError("the response isn't a PDF (starts with %r)" % data[:40])
            if len(data) < 50_000:
                raise ValueError("the PDF is suspiciously small (%d bytes)" % len(data))
            return data
        except Exception as err:  # network errors, HTTP errors, bad content
            error = err
            print("  attempt %d failed: %s" % (attempt, err))
            if attempt < 3:
                time.sleep(10 * attempt)
    sys.exit("Could not download %s: %s" % (url, error))


def forced_from_actions():
    """True when the workflow was started by hand with "force" ticked."""
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        return False
    try:
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
            inputs = json.load(f).get("inputs") or {}
    except (KeyError, OSError, ValueError):
        return False
    return str(inputs.get("force", "")).lower() == "true"


def edition_date(pdf):
    """The date the MTA made the PDF, e.g. "2026-11-19"."""
    metadata = pdf.get_metadata_dict()
    for key in ("CreationDate", "ModDate"):
        found = re.match(r"D:(\d{4})(\d{2})(\d{2})", metadata.get(key) or "")
        if found:
            return "-".join(found.groups())
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def render(page, width):
    page_w, page_h = page.get_size()
    height = round(width * page_h / page_w)
    image = page.render(scale=width / page_w, fill_color=(255, 255, 255, 255)).to_pil().convert("RGB")
    if image.size != (width, height):
        # PDFium rounds the bitmap size up, so this usually trims a sliver of margin.
        if image.width >= width and image.height >= height:
            image = image.crop((0, 0, width, height))
        else:
            image = image.resize((width, height), Image.LANCZOS)
    return image


def save_png(image, path):
    """256-colour PNG: looks the same as full colour on this map, about half the size."""
    small = imagequant.quantize_pil_image(image, dithering_level=0.5, max_colors=256)
    small.putpalette(small.getpalette("RGB"), "RGB")  # the map is opaque: no alpha channel
    small.save(path, optimize=True)


def write_tiles(image, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    cols = -(-image.width // TILE)
    rows = -(-image.height // TILE)
    for x in range(cols):
        for y in range(rows):
            box = (x * TILE, y * TILE, min(image.width, (x + 1) * TILE), min(image.height, (y + 1) * TILE))
            save_png(image.crop(box), folder / ("%d_%d.png" % (x, y)))
    return cols * rows


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def replace_marked_line(path, marker, new_line):
    """Swap the one line containing the marker for new_line, keeping its indent."""
    lines = path.read_text(encoding="utf-8").split("\n")
    hits = [i for i, line in enumerate(lines) if marker in line]
    if len(hits) != 1:
        sys.exit("%s: expected one line containing %r, found %d" % (path.name, marker, len(hits)))
    i = hits[0]
    lines[i] = re.match(r"\s*", lines[i]).group(0) + new_line
    write_text(path, "\n".join(lines))


def replace_between(path, start, end, new_text):
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(start) + ".*?" + re.escape(end), re.S)
    if len(pattern.findall(text)) != 1:
        sys.exit("%s: expected one %s ... %s block" % (path.name, start, end))
    write_text(path, pattern.sub(lambda m: start + new_text + end, text))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="rebuild even if the MTA maps haven't changed")
    parser.add_argument("--no-download", action="store_true", help="use the PDFs already in the repo")
    args = parser.parse_args()
    force = args.force or args.no_download or forced_from_actions()

    pdf_bytes = {}
    changed = []
    for name, url, pdf_file, _, _ in MAPS:
        path = ROOT / pdf_file
        if args.no_download:
            data = path.read_bytes()
        else:
            print("Downloading the %s map: %s" % (name, url))
            data = download(url)
            if not path.exists() or path.read_bytes() != data:
                changed.append(name)
        pdf_bytes[name] = data

    if not changed and not force:
        print("The MTA maps haven't changed since the last update. Nothing to do.")
        return
    print("Changed: %s" % (", ".join(changed) or "nothing (rebuilding anyway)"))

    docs = {}
    for name in pdf_bytes:
        docs[name] = pdfium.PdfDocument(pdf_bytes[name])
        if len(docs[name]) != 1:
            sys.exit("The %s map has %d pages; expected 1." % (name, len(docs[name])))
    sizes = {name: tuple(round(v, 1) for v in docs[name][0].get_size()) for name in docs}
    if len(set(sizes.values())) != 1:
        sys.exit("The day and night maps have different page sizes %s; the site needs them to match." % sizes)

    for name, _, pdf_file, base_file, tile_dir in MAPS:
        page = docs[name][0]
        print("Rendering the %s map" % name)
        save_png(render(page, BASE_WIDTH), ROOT / base_file)
        for z, width in LEVELS:
            image = render(page, width)
            count = write_tiles(image, ROOT / tile_dir / str(z))
            print("  level %d: %d x %d px, %d tiles" % (z, image.width, image.height, count))
            del image
        (ROOT / pdf_file).write_bytes(pdf_bytes[name])

    page_w, page_h = docs["day"][0].get_size()
    levels = [{"z": z, "w": w, "h": round(w * page_h / page_w)} for z, w in LEVELS]
    size = {"w": levels[-1]["w"], "h": levels[-1]["h"], "levels": levels}
    edition = edition_date(docs["day"])
    settings = json.dumps([size, BASE_WIDTH, TILE, RENDER_REVISION]).encode()
    digest = hashlib.sha256(pdf_bytes["day"] + pdf_bytes["night"] + settings).hexdigest()[:8]
    version = "%s-%s" % (edition, digest)
    d = date.fromisoformat(edition)
    pretty = "%s %d, %d" % (d.strftime("%B"), d.day, d.year)

    size_line = "const MAP_SIZE = %s; // @map-size: written by tools/build_map.py" % json.dumps(size)
    replace_marked_line(ROOT / "sw.js", "@map-version", "const MAP_VERSION = '%s'; // @map-version: written by tools/build_map.py" % version)
    replace_marked_line(ROOT / "sw.js", "@map-size", size_line)
    replace_marked_line(ROOT / "index.html", "@map-size", size_line)
    replace_between(ROOT / "README.md", "<!-- map-version -->", "<!-- /map-version -->",
                    "Current map: the MTA's subway diagram dated **%s**." % pretty)

    message = "Update subway map to the MTA edition of %s" % pretty
    print("Map version %s. %s" % (version, message))
    if os.environ.get("RUNNER_TEMP"):
        write_text(Path(os.environ["RUNNER_TEMP"]) / "map-commit-message.txt", message + "\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("Rebuilt the map from the MTA edition of %s (changed: %s).\n" % (pretty, ", ".join(changed) or "none, forced"))


if __name__ == "__main__":
    main()
