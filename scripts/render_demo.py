#!/usr/bin/env python3
"""Render a truthful video receipt from the bundled paid-search workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from econ544.ads_did import analyze_paid_search, load_paid_search


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "docs" / "demo"
WIDTH, HEIGHT = 1280, 720
FPS = 10
SOURCE_PATHS = [
    ".github/workflows/reproducible-demo.yml",
    "08_Returns_to_ads/PaidSearch.csv",
    "08_Returns_to_ads/ebay_did.ipynb",
    "econ544/__init__.py",
    "econ544/ads_did.py",
    "requirements-demo.txt",
    "scripts/render_demo.py",
    "scripts/run_ads_did.py",
    "scripts/verify_demo.py",
    "tests/test_ads_did.py",
]


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int, color: str, bold: bool = False) -> None:
    draw.text(xy, value, font=font(size, bold), fill=color)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#07111f")
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        blend = y / HEIGHT
        draw.line((0, y, WIDTH, y), fill=(7 + int(10 * blend), 17 + int(15 * blend), 31 + int(22 * blend)))
    draw.ellipse((880, -260, 1420, 280), fill="#102c42")
    draw.ellipse((-220, 500, 300, 1020), fill="#101e38")
    return image, draw


def header(draw: ImageDraw.ImageDraw, source_short: str) -> None:
    rounded(draw, (48, 34, 228, 76), "#15344b", 18)
    text(draw, (66, 45), "ECON 544", 19, "#80e7ce", True)
    text(draw, (955, 46), f"SOURCE {source_short}", 16, "#91a7bd", True)


def intro(progress: float, source_short: str) -> Image.Image:
    image, draw = canvas()
    header(draw, source_short)
    alpha = ease(progress)
    y = int(200 + (1 - alpha) * 24)
    text(draw, (75, y), "Paid-search experiment", 54, "#f5f8fb", True)
    text(draw, (76, y + 75), "A reproducible difference-in-differences walkthrough", 26, "#b8c9d9")
    rounded(draw, (76, y + 145, 610, y + 201), "#173b39", 18)
    text(draw, (99, y + 160), "HISTORICAL CLASSROOM DATA • PROVIDER-FREE", 18, "#7ce7c8", True)
    text(draw, (76, 602), "Actual checked-in data and executable analysis", 18, "#91a7bd")
    return image


def validation(progress: float, result: dict, source_short: str) -> Image.Image:
    image, draw = canvas()
    header(draw, source_short)
    text(draw, (70, 118), "1  Validate the panel", 39, "#f5f8fb", True)
    text(draw, (72, 170), "Fail closed before taking logs or comparing groups", 22, "#a8bed1")
    cards = [
        ("23,730", "daily observations"),
        ("210", "DMA markets"),
        ("2", "complete periods"),
    ]
    shown = max(1, math.ceil(progress * len(cards)))
    for index, (value, label) in enumerate(cards):
        x = 72 + index * 385
        fill = "#11283a" if index < shown else "#0d1d2b"
        rounded(draw, (x, 240, x + 340, 420), fill, 24)
        text(draw, (x + 28, 277), value, 45, "#73e1c3" if index < shown else "#415769", True)
        text(draw, (x + 28, 343), label, 20, "#c2d0dc" if index < shown else "#415769")
    checks = "✓ positive revenue   ✓ stable assignment   ✓ complete pre/post pairs"
    rounded(draw, (72, 485, 1200, 552), "#112f2d", 20)
    text(draw, (100, 506), checks, 22, "#87e4cc", True)
    text(draw, (72, 608), "Input: 08_Returns_to_ads/PaidSearch.csv", 18, "#91a7bd")
    return image


def comparison(progress: float, result: dict, source_short: str) -> Image.Image:
    image, draw = canvas()
    header(draw, source_short)
    text(draw, (70, 112), "2  Compare pre/post log revenue", 38, "#f5f8fb", True)
    text(draw, (72, 162), "Average daily log change within each DMA", 22, "#a8bed1")
    center = 640
    scale = 5600
    draw.line((center, 247, center, 535), fill="#567087", width=2)
    draw.line((170, 535, 1110, 535), fill="#355066", width=2)
    values = [
        ("Paid search off", result["treated_log_change"], "68 treated DMAs", "#ffb66e"),
        ("Paid search on", result["control_log_change"], "142 control DMAs", "#6fd9c2"),
    ]
    for index, (label, value, count, color) in enumerate(values):
        y = 298 + index * 145
        animated = value * ease(progress)
        endpoint = center + int(animated * scale)
        draw.line((center, y, endpoint, y), fill=color, width=34)
        draw.ellipse((endpoint - 13, y - 13, endpoint + 13, y + 13), fill="#f5f8fb")
        text(draw, (72, y - 18), label, 22, "#e8eef4", True)
        text(draw, (910, y - 24), f"{animated:+.4f}", 31, color, True)
        text(draw, (910, y + 17), count, 16, "#91a7bd")
    text(draw, (585, 565), "0.000", 16, "#8299ad")
    return image


def result_frame(progress: float, result: dict, source_short: str) -> Image.Image:
    image, draw = canvas()
    header(draw, source_short)
    text(draw, (70, 106), "3  Reconcile the estimate", 38, "#f5f8fb", True)
    effect = result["log_effect"] * ease(progress)
    lower, upper = result["ci_lower"], result["ci_upper"]
    rounded(draw, (72, 186, 574, 512), "#11283a", 28)
    text(draw, (104, 222), "Difference-in-differences", 20, "#a8bed1", True)
    text(draw, (104, 276), f"{effect:+.4f}", 72, "#ffbd79", True)
    text(draw, (106, 372), "95% interval", 18, "#91a7bd")
    text(draw, (106, 405), f"[{lower:+.4f}, {upper:+.4f}]", 29, "#e8eef4", True)
    rounded(draw, (618, 186, 1200, 512), "#112f2d", 28)
    text(draw, (650, 222), "Exponentiated revenue ratio", 20, "#9bdcca", True)
    text(draw, (650, 276), f"{result['revenue_ratio']:.4f}", 72, "#7ce7c8", True)
    text(draw, (652, 372), "95% interval", 18, "#91a7bd")
    text(draw, (652, 405), f"[{result['revenue_ratio_ci_lower']:.4f}, {result['revenue_ratio_ci_upper']:.4f}]", 29, "#e8eef4", True)
    text(draw, (72, 570), "The interval includes no change; this demo does not claim a business effect.", 22, "#d8c39e", True)
    return image


def receipt_frame(progress: float, source_short: str) -> Image.Image:
    image, draw = canvas()
    header(draw, source_short)
    text(draw, (70, 106), "Reproducible receipt", 43, "#f5f8fb", True)
    rows = [
        ("DATA", "SHA-256 pinned checked-in CSV"),
        ("TESTS", "validation, portability, and input preservation"),
        ("MEDIA", "GIF + MP4 decoded and source-verified"),
        ("SCOPE", "historical classroom workflow; no live provider"),
    ]
    for index, (label, value) in enumerate(rows):
        y = 195 + index * 91
        rounded(draw, (72, y, 1200, y + 67), "#102638", 18)
        text(draw, (98, y + 20), label, 18, "#74dec3", True)
        text(draw, (235, y + 17), value, 23, "#dbe6ee")
        if progress > index / len(rows):
            text(draw, (1139, y + 16), "✓", 28, "#7ce7c8", True)
    text(draw, (72, 612), "python scripts/run_ads_did.py", 19, "#91a7bd")
    return image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captured-source", help="source commit to pin (default: HEAD)")
    args = parser.parse_args()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required")

    source = args.captured_source or run("git", "rev-parse", "HEAD")
    source_tree = run("git", "rev-parse", f"{source}^{{tree}}")
    if run("git", "status", "--short"):
        raise SystemExit("rendering requires a clean source checkout")
    result, _ = analyze_paid_search(load_paid_search()[0])
    values = result.as_dict()

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="econ544-demo-") as directory:
        frame_dir = Path(directory)
        frame_index = 0
        scenes = [intro, validation, comparison, result_frame, receipt_frame]
        durations = [20, 26, 30, 28, 26]
        for scene, duration in zip(scenes, durations):
            for offset in range(duration):
                progress = offset / max(duration - 1, 1)
                if scene in (intro, receipt_frame):
                    image = scene(progress, source[:8])
                else:
                    image = scene(progress, values, source[:8])
                image.save(frame_dir / f"frame-{frame_index:04d}.png", optimize=True)
                frame_index += 1

        poster = DEMO_DIR / "ads-did-poster.png"
        result_frame(1.0, values, source[:8]).save(poster, optimize=True)
        mp4 = DEMO_DIR / "ads-did-demo.mp4"
        gif = DEMO_DIR / "ads-did-demo.gif"
        pattern = str(frame_dir / "frame-%04d.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", pattern,
             "-vf", "scale=1280:720:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-crf", "20",
             "-movflags", "+faststart", str(mp4)], check=True
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", pattern,
             "-filter_complex", "[0:v]fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
             str(gif)], check=True
        )

    manifest = {
        "captured_source_commit": source,
        "captured_source_tree": source_tree,
        "inputs": {path: run("git", "rev-parse", f"{source}:{path}") for path in SOURCE_PATHS},
    }
    (DEMO_DIR / "source-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    receipt = {
        "workflow": "paid-search difference-in-differences",
        "scope": "bundled historical classroom dataset; no live advertising platform or business-effect claim",
        "captured_source_commit": source,
        "captured_source_tree": source_tree,
        "dataset_sha256": sha256(ROOT / "08_Returns_to_ads" / "PaidSearch.csv"),
        "result": values,
        "media": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in (gif, mp4, poster)
        },
    }
    (DEMO_DIR / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
