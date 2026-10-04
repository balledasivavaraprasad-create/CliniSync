"""Re-extract every ambient still from the landing page's own ambient loops.

Plan §6.5(a): patient-card and thumbnail imagery must be "stills extracted from
lightNoWatermark ... tinted to the sage palette" — never a patient photograph
and never invented artwork. The repo ships the source loops at the root
(lightNoWatermark.mp4) and in assets/video/ (hero-*, ribbon-*), so every still
in assets/images/ambient-*.jpg is reproducible from them.

The loops are bright chrome renders on near-white, so they are pushed through a
**duotone ramp** instead of a saturation tweak: luminance is mapped from the
palette's deep sage (§7.1 `primaryDark`) to the canvas off-white
(§7.1 `bgCanvas`). That lands the artwork inside the palette by construction,
reproduces the reference's "pale and desaturated, fading into the background"
look (§6.1 el. 5), and keeps the white headline legible on top of it.

Usage:  .venv/bin/python tools/extract_ambient_stills.py
Needs:  ffmpeg + Pillow
"""
from __future__ import annotations

import pathlib
import subprocess
import tempfile

from PIL import Image, ImageFilter, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'assets/images'

# §7.1 palette — the two ends of the duotone ramp.
RAMP_DARK = (0x3F, 0x66, 0x46)   # primaryDark
RAMP_LIGHT = (0xF6, 0xF8, 0xF4)  # bgCanvas

# (source loop, frame index, output name, contrast, brightness, blur px)
JOBS = [
    # Hero poster: a frame of the hero ambient loop itself, so poster -> video
    # is invisible (AmbientLayer paints the poster under the video).
    ('assets/video/hero-light.mp4', 96, 'ambient-hero.jpg', 1.06, 0.02, 0.8),
    # Ribbon wash behind the Brief / Approval / Consultation headers.
    ('assets/video/ribbon-light.mp4', 132, 'ambient-ribbon.jpg', 1.02, 0.04, 0.6),
    # Three distinct moments of lightNoWatermark for the patient-card and record
    # carousels (Home, patient list, Records tab, Overview).
    ('lightNoWatermark.mp4', 48, 'ambient-mist.jpg', 1.10, -0.02, 0.4),
    ('lightNoWatermark.mp4', 216, 'ambient-mist-alt.jpg', 1.10, -0.02, 0.4),
    ('lightNoWatermark.mp4', 408, 'ambient-mist-third.jpg', 1.08, -0.01, 0.4),
]


def grab_frame(source: str, frame: int, dest: pathlib.Path) -> None:
    subprocess.run(
        [
            'ffmpeg', '-v', 'error', '-y',
            '-i', str(ROOT / source),
            '-vf', f"select='eq(n\\,{frame})'",
            '-vsync', '0', '-frames:v', '1',
            str(dest),
        ],
        check=True,
    )


def duotone(path: pathlib.Path, contrast: float, brightness: float,
            blur: float) -> Image.Image:
    grey = Image.open(path).convert('L')
    grey = ImageOps.autocontrast(grey, cutoff=1)
    grey = grey.point(
        lambda v: max(0, min(255, (v - 128) * contrast + 128 + 255 * brightness))
    )
    if blur:
        grey = grey.filter(ImageFilter.GaussianBlur(blur))
    return ImageOps.colorize(grey, black=RAMP_DARK, white=RAMP_LIGHT)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for source, frame, name, contrast, brightness, blur in JOBS:
            raw = pathlib.Path(tmp) / f'{name}.png'
            grab_frame(source, frame, raw)
            image = duotone(raw, contrast, brightness, blur)
            out = OUT_DIR / name
            image.save(out, 'JPEG', quality=82, optimize=True, progressive=True)
            print(f'{out.relative_to(ROOT)}  {image.width}x{image.height}'
                  f'  {out.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
