"""Bounded, resumable reference capture for the Terra Incognita linked tour.

Run with: uv tool run --from streetview-dl python tools/capture-reference-tour.py
Defaults to metadata discovery. --download fetches the accepted linked views.
Credentials are read locally and never included in logs or the manifest.
"""
import argparse
from collections import deque
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw
from streetview_dl.core import StreetViewDownloader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "source/captures/panoramas"
SEED_FILE = OUT / "terra-incognita-tearoom-2017-11.json"


def read_key():
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip().removeprefix("export ") == "GOOGLE_MAPS_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("No local API key configured")
    return key


class CheckedDownloader(StreetViewDownloader):
    def fetch_tile(self, *args, **kwargs):
        try:
            return super().fetch_tile(*args, **kwargs)
        except Exception:
            # Upstream silently replaces failed tiles with black pixels.
            # Raise a different exception so an incomplete image is not saved.
            raise RuntimeError("Tile request failed; credentials withheld") from None


def distance(a, b):
    if b.lat is None or b.lng is None:
        return float("inf")
    dy = math.radians(b.lat - a["lat"])
    dx = math.radians(b.lng - a["lng"]) * math.cos(math.radians(a["lat"]))
    return 6371000 * math.hypot(dx, dy)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.limit <= 40:
        parser.error("limit must be between 1 and 40")
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    manifest_path = OUT / "tour-manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    previous_by_id = {r["pano_id"]: r for r in previous.get("views", [])}
    allocated_ids = {r["view_id"] for r in previous.get("views", []) if "view_id" in r}
    client = CheckedDownloader(api_key=read_key(), timeout=20, retries=1)
    queue = deque([seed["pano_id"]])
    visited = set()
    rows = []
    while queue and len(visited) < args.limit:
        pano_id = queue.popleft()
        if pano_id in visited:
            continue
        visited.add(pano_id)
        try:
            metadata = client.get_metadata(pano_id=pano_id)
        except Exception:
            rows.append({"pano_id": pano_id, "status": "metadata_failed"})
            print("Metadata request failed; credentials withheld", flush=True)
            continue
        accepted = (metadata.date == seed["date"]
                    and metadata.copyright_info == seed["copyright_info"]
                    and distance(seed, metadata) <= 65)
        row = metadata.to_dict()
        row["distance_from_seed_m"] = round(distance(seed, metadata), 2)
        row["status"] = "accepted" if accepted else "outside_capture_bounds"
        if accepted:
            old = previous_by_id.get(pano_id, {})
            view_id = old.get("view_id")
            if not view_id:
                number = 1
                while "view-%02d" % number in allocated_ids:
                    number += 1
                view_id = "view-%02d" % number
                allocated_ids.add(view_id)
            row["view_id"] = view_id
            row["file"] = ("terra-incognita-tearoom-2017-11.jpg" if pano_id == seed["pano_id"]
                           else row["view_id"] + ".jpg")
            for link in metadata.links or []:
                if link["panoId"] not in visited:
                    queue.append(link["panoId"])
            print(row["view_id"] + ": " + str(metadata.date) + ", links=" + str(len(metadata.links or [])), flush=True)
        rows.append(row)
    manifest = {"seed": seed["pano_id"], "scope": "same date and attribution, within 65 m; maximum metadata requests " + str(args.limit),
                "queue_remaining": sorted(set(queue) - visited), "views": rows}
    write_json(OUT / "tour-manifest.json", manifest)
    accepted_rows = [r for r in rows if r["status"] == "accepted"]
    if args.download:
        for row in accepted_rows:
            target = OUT / row["file"]
            if target.exists():
                with Image.open(target) as im:
                    if im.size != (row["image_width"], row["image_height"]):
                        raise RuntimeError("Existing image dimensions do not match metadata")
                    im.verify()
                row["download_status"] = "verified_existing"
                print(row["view_id"] + ": existing image verified", flush=True)
                continue
            try:
                from streetview_dl.metadata import StreetViewMetadata
                metadata = StreetViewMetadata(**row)
                im = client.download_panorama(metadata, quality="high", concurrency=6)
                im.save(target, quality=92)
                im.close()
                row["download_status"] = "complete"
                print(row["view_id"] + ": downloaded", flush=True)
            except Exception:
                row["download_status"] = "failed"
                print(row["view_id"] + ": download failed; credentials withheld", flush=True)
            write_json(OUT / "tour-manifest.json", manifest)
    # Small visual index for inspection, retaining full panoramas separately.
    available = [r for r in accepted_rows if (OUT / r["file"]).exists()]
    for start in range(0, len(available), 6):
        group = available[start:start + 6]
        sheet = Image.new("RGB", (1400, math.ceil(len(group) / 2) * 390), "#202020")
        draw = ImageDraw.Draw(sheet)
        for i, row in enumerate(group):
            x, y = (i % 2) * 700, (i // 2) * 390
            with Image.open(OUT / row["file"]) as im:
                im.thumbnail((690, 345))
                sheet.paste(im, (x, y + 22))
            draw.text((x + 5, y + 3), row["view_id"] + " | " + row["date"], fill="white")
        sheet.save(OUT / ("contact-sheet-%02d.jpg" % (start // 6 + 1)), quality=90)
    print("Accepted views: " + str(len(accepted_rows)) + "; unexplored IDs: " + str(len(manifest["queue_remaining"])), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ": capture stopped; exception details withheld to protect credentials", flush=True)
        raise SystemExit(1)
