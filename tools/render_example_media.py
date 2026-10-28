"""Make a native-CAD example showcase and turntable; never synthesize board geometry.

uv run --group media python tools/render_example_media.py --work-dir NEW_EXTERNAL_DIR
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import imageio_ffmpeg
from media_evidence import repository_binding
from media_publication import publish_bundle
from PIL import Image, ImageDraw
from render_readme_media import (
    BG,
    LINE,
    MEDIA,
    MUTED,
    ROOT,
    WHITE,
    base,
    brand,
    capture,
    digest,
    fit,
    pill,
    run_native,
    text,
)

from pcb_copilot.project import load_project
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import assert_current


def showcase(board: Image.Image, sheets: list) -> Image.Image:
    canvas = base(1600, 1000)
    draw = ImageDraw.Draw(canvas)
    brand(canvas)
    pill(canvas, (1270, 48), "EXAMPLE / DRAFT")
    text(canvas, (64, 118), "A small board. The whole workflow.", 58, bold=True)
    text(canvas, (66, 202), "Four independent 3.3 V GPIO indicators · editable native KiCad · unbuilt prototype", 25, MUTED)
    draw.rounded_rectangle((64, 282, 1020, 855), radius=7, fill="#faf9f2")
    fit(canvas, sheets[0][1], (76, 294, 932, 549))
    fit(canvas, board, (1048, 280, 488, 565))
    draw.line((64, 899, 1536, 899), fill=LINE, width=2)
    text(canvas, (66, 925), "ONE SHEET  /  45 x 35 mm  /  TWO LAYERS", 19, WHITE, mono=True)
    text(canvas, (1005, 925), "NATIVE 3D RENDER / UNBUILT", 18, MUTED, mono=True)
    return canvas


def turntable_frame(board: Image.Image, index: int, frames: int) -> Image.Image:
    canvas = base(960, 720)
    brand(canvas, 44, 32, 20)
    pill(canvas, (710, 30), "UNBUILT / DRAFT", size=14)
    text(canvas, (43, 89), "GPIO indicator", 43, bold=True)
    fit(canvas, board, (100, 160, 760, 470))
    draw = ImageDraw.Draw(canvas)
    draw.line((44, 646, 916, 646), fill=LINE, width=2)
    text(canvas, (44, 665), "45 x 35 mm / 4 channels / native KiCad render", 16, MUTED, mono=True)
    text(canvas, (808, 665), f"{index + 1:02}/{frames:02}", 16, WHITE, mono=True)
    return canvas


def render(work: Path, frames: int):
    output = work / "assets"
    output.mkdir()
    project = load_project(ROOT / "examples" / "gpio-indicator")
    commands = []
    board, _, sheets, before = capture(project, work, commands)
    showcase(board, sheets).save(output / "gpio-demo.png", optimize=True)
    board.save(output / "gpio-3d.png", optimize=True)
    snapshot = load_project(work / "project")
    cli = discover_toolchain(ROOT).kicad_cli
    orbit = work / "orbit"
    orbit.mkdir()

    def native_frame(index):
        path = orbit / f"{index:03}.png"
        angle = index * 360 / frames
        run_native(cli, work, ["pcb", "render", "--width", "1056", "--height", "880",
                              "--quality", "basic", "--background", "transparent",
                              "--rotate", f"-30,0,{angle:.4f}", "--zoom", "0.82",
                              "-o", str(path), str(snapshot.pcb_path)], commands)
        return index, path

    rendered = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(native_frame, index) for index in range(frames)]
        for future in as_completed(futures):
            index, path = future.result()
            rendered[index] = path
            if len(rendered) % 8 == 0 or len(rendered) == frames:
                print(f"Native turntable renders: {len(rendered)}/{frames}", flush=True)
    assert_current(project, before)
    native_images = [Image.open(rendered[index]).convert("RGBA") for index in range(frames)]
    bounds = [image.getchannel("A").getbbox() for image in native_images]
    if any(bound is None for bound in bounds):
        raise RuntimeError("a native turntable frame contains no board")
    # Crop one shared transparent margin so the real board fills the frame
    # without changing scale or center as it rotates.
    crop = (max(0, min(b[0] for b in bounds) - 16), max(0, min(b[1] for b in bounds) - 16),
            min(native_images[0].width, max(b[2] for b in bounds) + 16),
            min(native_images[0].height, max(b[3] for b in bounds) + 16))
    images = [turntable_frame(image.crop(crop), index, frames)
              for index, image in enumerate(native_images)]
    # One palette shared by all views prevents palette flashes in GitHub's GIF.
    palette_sample = Image.new("RGB", (960 * 4, 720), BG)
    for column, index in enumerate([0, frames // 4, frames // 2, frames * 3 // 4]):
        palette_sample.paste(images[index], (column * 960, 0))
    palette = palette_sample.quantize(colors=192)
    gifs = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    gifs[0].save(output / "gpio-turntable.gif", save_all=True, append_images=gifs[1:],
                 duration=round(4000 / frames), loop=0, optimize=True, disposal=1)
    writer = imageio_ffmpeg.write_frames(str(output / "gpio-turntable.mp4"), (960, 720), fps=24,
                                        codec="libx264", quality=8, ffmpeg_log_level="error",
                                        output_params=["-movflags", "+faststart"])
    writer.send(None)
    try:
        # 48 native views at 12 fps: repeat each once for a 24 fps encoded file.
        for frame_number in range(96):
            writer.send(images[min(frames - 1, frame_number * frames // 96)].tobytes())
    finally:
        writer.close()
    contact = Image.new("RGB", (1920, 1440), BG)
    for n, index in enumerate([0, frames // 4, frames // 2, frames * 3 // 4]):
        contact.paste(images[index], ((n % 2) * 960, (n // 2) * 720))
    contact.save(work / "turntable-contact.png", optimize=True)
    outputs = ["gpio-demo.png", "gpio-3d.png", "gpio-turntable.gif", "gpio-turntable.mp4"]
    manifest = {
        "schema_version": 1, "generated_utc": datetime.now(UTC).isoformat(),
        "source_project": "examples/gpio-indicator", "source_inputs": before,
        **repository_binding(ROOT, project.root, before),
        "source_cad_unchanged": True,
        "kicad_version": subprocess.check_output([str(cli), "version"], encoding="utf-8").strip(),
        "generator_sha256": digest(Path(__file__)),
        "shared_renderer_sha256": digest(ROOT / "tools" / "render_readme_media.py"),
        "native_commands": sorted(commands, key=lambda item: str(item["command"])),
        "outputs": {name: {"sha256": digest(output / name), "bytes": (output / name).stat().st_size}
                    for name in outputs},
        "scope": "Actual native 3D views of an unbuilt educational PCB. No physical or fabrication approval.",
    }
    (output / "example-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    publish_bundle(output, MEDIA, "example-manifest.json", source_check=lambda: assert_current(project, before))
    print(json.dumps({"outputs": manifest["outputs"], "visual_review": str(work / "turntable-contact.png")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, help="new directory outside checkout retaining exports for inspection")
    parser.add_argument("--frames", type=int, default=48, choices=range(12, 73), metavar="12..72")
    args = parser.parse_args()
    if args.work_dir:
        work = args.work_dir.resolve()
        if work == ROOT or work.is_relative_to(ROOT):
            parser.error("--work-dir must be outside the checkout")
        work.mkdir(parents=True, exist_ok=False)
        render(work, args.frames)
    else:
        with tempfile.TemporaryDirectory(prefix="pcb-example-media-") as directory:
            render(Path(directory), args.frames)


if __name__ == "__main__":
    main()
