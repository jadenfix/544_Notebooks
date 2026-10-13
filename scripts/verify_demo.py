#!/usr/bin/env python3
"""Verify source provenance, calculations, and complete media decoding."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from econ544.ads_did import analyze_paid_search, load_paid_search


DEMO_DIR = ROOT / "docs" / "demo"


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    receipt = json.loads((DEMO_DIR / "receipt.json").read_text(encoding="utf-8"))
    manifest = json.loads((DEMO_DIR / "source-manifest.json").read_text(encoding="utf-8"))
    source = manifest["captured_source_commit"]
    if source != receipt["captured_source_commit"]:
        raise SystemExit("receipt and manifest source commits differ")
    if run("git", "rev-parse", f"{source}^{{tree}}") != manifest["captured_source_tree"]:
        raise SystemExit("captured source tree does not match commit")
    subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=ROOT, check=True)
    for relative, expected_blob in manifest["inputs"].items():
        actual_blob = run("git", "hash-object", relative)
        if actual_blob != expected_blob:
            raise SystemExit(f"captured input drift: {relative}")

    result, _ = analyze_paid_search(load_paid_search()[0])
    if result.as_dict() != receipt["result"]:
        raise SystemExit("analysis result differs from the recorded receipt")
    dataset = ROOT / "08_Returns_to_ads" / "PaidSearch.csv"
    if digest(dataset) != receipt["dataset_sha256"]:
        raise SystemExit("dataset digest mismatch")

    gif = DEMO_DIR / "ads-did-demo.gif"
    mp4 = DEMO_DIR / "ads-did-demo.mp4"
    poster = DEMO_DIR / "ads-did-poster.png"
    for media in (gif, mp4, poster):
        record = receipt["media"][media.name]
        if media.stat().st_size != record["bytes"] or digest(media) != record["sha256"]:
            raise SystemExit(f"media digest mismatch: {media.name}")

    with Image.open(gif) as image:
        gif_frames = image.n_frames
        image.seek(gif_frames - 1)
        image.load()
        if image.size != (960, 540) or gif_frames != 130:
            raise SystemExit(f"unexpected GIF geometry/frame count: {image.size}, {gif_frames}")
    with Image.open(poster) as image:
        image.verify()
        if image.size != (1280, 720):
            raise SystemExit(f"unexpected poster geometry: {image.size}")

    probe = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                           "-show_entries", "stream=codec_name,width,height,nb_read_frames", "-of", "json", str(mp4)))
    stream = probe["streams"][0]
    if stream != {"codec_name": "h264", "width": 1280, "height": 720, "nb_read_frames": "130"}:
        raise SystemExit(f"unexpected MP4 stream: {stream}")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "null", "-"], check=True)
    print(f"verified source {source}, 6 tests, GIF {gif_frames} frames, MP4 {stream['nb_read_frames']} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
