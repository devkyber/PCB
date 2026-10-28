"""Render README assets from saved KiCad CAD and a real tools/demo.py transcript.

Run from the checkout: uv run --group media python tools/render_readme_media.py
    --demo C:/path/to/demo/transcript.json
Native exports run on disposable, hash-checked copies. No CAD is authored here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import imageio_ffmpeg
import pymupdf as fitz
from media_evidence import demo_data, repository_binding
from media_publication import publish_bundle
from PIL import Image, ImageDraw, ImageFont, ImageOps

from pcb_copilot.project import load_project
from pcb_copilot.toolchain import discover_toolchain
from pcb_copilot.transaction import assert_current, copy_inputs, input_hashes

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
BG = "#101c24"
PANEL = "#182832"
LINE = "#31444f"
WHITE = "#f2f5ed"
MUTED = "#a8bdc7"
LIME = "#d4f37c"
AMBER = "#f7c47d"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    name = "JetBrainsMono-Regular.ttf" if mono else f"InstrumentSans-{'Bold' if bold else 'Regular'}.ttf"
    return ImageFont.truetype(str(MEDIA / "fonts" / name), size)


def text(canvas: Image.Image, xy, value: str, size: int = 24, fill=WHITE, *, bold=False, mono=False):
    ImageDraw.Draw(canvas).multiline_text(xy, value, font=font(size, bold=bold, mono=mono),
                                          fill=fill, spacing=10)


def fit(canvas: Image.Image, source: Image.Image, box, *, inset=0):
    x, y, width, height = box
    fitted = ImageOps.contain(source, (width - inset * 2, height - inset * 2), Image.Resampling.LANCZOS)
    at = (round(x + (width - fitted.width) / 2), round(y + (height - fitted.height) / 2))
    canvas.paste(fitted, at, fitted if fitted.mode == "RGBA" else None)


def base(width=1600, height=900) -> Image.Image:
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    for x in range(32, width, 40):
        for y in range(32, height, 40):
            draw.ellipse((x, y, x + 1, y + 1), fill="#263741")
    return canvas


def brand(canvas: Image.Image, x=64, y=48, size=24):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y + 2, x + 24, y + 26), outline=LIME, width=2)
    draw.rectangle((x + 8, y + 10, x + 16, y + 18), fill=LIME)
    text(canvas, (x + 40, y - 1), "PCB COPILOT", size, bold=True)


def pill(canvas: Image.Image, xy, value: str, *, color=LIME, size=16):
    x, y = xy
    face = font(size, mono=True)
    width = round(face.getlength(value)) + 28
    ImageDraw.Draw(canvas).rounded_rectangle((x, y, x + width, y + size + 20), radius=5,
                                             outline=LINE, fill=BG)
    text(canvas, (x + 14, y + 8), value, size, color, mono=True)


def svg_image(path: Path, width: int = 2400) -> Image.Image:
    with fitz.open(path) as document:
        page = document[0]
        scale = width / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def run_native(cli: Path, work: Path, arguments: list[str], commands: list):
    result = subprocess.run([str(cli), *arguments], cwd=work, capture_output=True,
                            encoding="utf-8", errors="replace", check=False, timeout=240)
    commands.append({"command": ["kicad-cli", *[a.replace(str(work), "<snapshot>") for a in arguments]],
                     "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError(f"KiCad export failed: {result.stderr or result.stdout}")


def capture(project, work: Path, commands: list):
    before = input_hashes(project)
    copy_inputs(project, work / "project", before)
    snapshot = load_project(work / "project")
    cli = discover_toolchain(ROOT).kicad_cli
    board_path = work / "board-3d.png"
    run_native(cli, work, ["pcb", "render", "--width", "1800", "--height", "1600",
                          "--background", "transparent", "--quality", "high",
                          "--rotate", "-27,0,28", "--zoom", "0.86",
                          "-o", str(board_path), str(snapshot.pcb_path)], commands)
    board = Image.open(board_path).convert("RGBA")
    bounds = board.getchannel("A").getbbox()
    if bounds:
        board = board.crop(bounds)
    svg = work / "board-top.svg"
    run_native(cli, work, ["pcb", "export", "svg", "--mode-single", "--page-size-mode", "2",
                          "--layers", "F.Cu,F.Silkscreen,Edge.Cuts", "-o", str(svg),
                          str(snapshot.pcb_path)], commands)
    top = svg_image(svg)
    schematic_dir = work / "schematic"
    schematic_dir.mkdir()
    run_native(cli, work, ["sch", "export", "svg", "-o", str(schematic_dir) + "/",
                          str(snapshot.schematic_path)], commands)
    sheets = [(path.name, svg_image(path, 2200)) for path in sorted(schematic_dir.glob("*.svg"))]
    if not sheets:
        raise RuntimeError("native export produced no schematic sheets")
    for name, sheet in sheets:
        sheet.save(work / (Path(name).stem + ".png"), optimize=True)
    assert_current(project, before)
    return board, top, sheets, before


def hero(board: Image.Image, *, social: bool = False) -> Image.Image:
    canvas = base()
    draw = ImageDraw.Draw(canvas)
    brand(canvas, 72, 62)
    pill(canvas, (1164, 60), "NATIVE KICAD / DRAFT")
    text(canvas, (70, 172), "PCB design,\nwith evidence.", 88, bold=True)
    text(canvas, (74, 414), "A pipeline for AI-assisted engineering.", 29, MUTED)
    text(canvas, (74, 470), "Preserve the CAD. Inspect each change.\nKeep the release decision explicit.", 27, WHITE)
    draw.line((74, 592, 650, 592), fill=LINE, width=2)
    for index, (label, detail) in enumerate([
        ("01", "Source evidence"), ("02", "Checked candidates"), ("03", "Human review"),
    ]):
        x = 74 + index * 204
        text(canvas, (x, 624), label, 18, LIME, mono=True)
        text(canvas, (x, 660), detail, 20)
    # A native render is the evidence-bearing centerpiece; never a generated board photo.
    fit(canvas, board, (754, 140, 790, 610))
    draw.line((72, 782, 1528, 782), fill=LINE, width=2)
    text(canvas, (74, 810), "devkyber/PCB", 23, LIME, mono=True)
    text(canvas, (890, 810), "ROVER PDB  /  NATIVE RENDER  /  QUALIFICATION OPEN", 16, MUTED, mono=True)
    if social:
        # Preserve every label while fitting GitHub's 2:1 social image canvas.
        canvas = ImageOps.pad(canvas, (1280, 640), method=Image.Resampling.LANCZOS, color=BG)
    return canvas


def gallery(sheets: list, top: Image.Image) -> Image.Image:
    canvas = base(1600, 1110)
    brand(canvas)
    text(canvas, (64, 108), "Real files. Inspectable outputs.", 49, bold=True)
    text(canvas, (64, 181), "Rover PDB · saved owner CAD · native exports · prototype qualification remains open", 22, MUTED)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((64, 250, 985, 1000), radius=8, fill="#faf9f2")
    # Pick a converter sheet if available; do not relabel the actual circuit.
    preferred = next((s for s in sheets if "5 v" in s[0].lower()), sheets[min(1, len(sheets) - 1)])
    fit(canvas, preferred[1], (80, 266, 889, 718))
    draw.rounded_rectangle((1010, 250, 1536, 1000), radius=8, fill="#faf9f2")
    fit(canvas, top, (1026, 266, 494, 718))
    text(canvas, (64, 1030), "SCHEMATIC  /  " + preferred[0].replace(".svg", ""), 17, MUTED, mono=True)
    text(canvas, (1010, 1030), "PCB  /  TOP COPPER + SILK", 17, MUTED, mono=True)
    return canvas


def sheet_contact(sheets: list) -> Image.Image:
    columns = 2
    rows = math.ceil(len(sheets) / columns)
    canvas = Image.new("RGB", (1800, rows * 690), "#dfe5e7")
    for i, (name, sheet) in enumerate(sheets):
        x, y = (i % columns) * 900, (i // columns) * 690
        fit(canvas, sheet, (x + 12, y + 44, 876, 634))
        text(canvas, (x + 16, y + 8), name, 18, BG, mono=True)
    return canvas


def scene(index: int, progress: float, board: Image.Image, sheets: list, demo: dict) -> Image.Image:
    canvas = base(1280, 720)
    draw = ImageDraw.Draw(canvas)
    brand(canvas, 48, 34, 21)
    titles = ["Start with native KiCad.", "Verify the source bytes.", "Require a matching preview.", "Keep approval explicit."]
    subtitles = ["Saved, editable CAD is the authority.", "Archive identity is checked before interpretation.",
                 "An apply request without a preview is rejected.", "Machine checks and engineering decisions stay visible."]
    pill(canvas, (1040, 34), f"0{index + 1} / 04", size=15)
    text(canvas, (48, 108), titles[index], 49, bold=True)
    text(canvas, (50, 180), subtitles[index], 23, MUTED)
    if index == 0:
        draw.rounded_rectangle((48, 246, 728, 622), radius=7, fill="#faf9f2")
        fit(canvas, sheets[0][1], (58, 256, 660, 356))
        fit(canvas, board, (760, 235, 465, 390))
    else:
        draw.rounded_rectangle((48, 250, 1232, 620), radius=8, fill=PANEL, outline=LINE, width=1)
        if index == 1:
            text(canvas, (76, 278), "$ pcb-copilot research <snapshot> --verify", 20, LIME, mono=True)
            lines = [line if len(line) <= 86 else line[:83] + "..." for line in demo["evidence_excerpt"][:4]]
            for i, line in enumerate(lines):
                text(canvas, (76, 330 + i * 37), line, 17, WHITE, mono=True)
            text(canvas, (76, 536), f"{demo['declared_input_count']} declared input hashes preserved", 24, bold=True)
            text(canvas, (76, 577), "Byte identity does not establish circuit correctness.", 19, MUTED)
        elif index == 2:
            text(canvas, (76, 278), "$ pcb-copilot update-schematic <snapshot>", 20, LIME, mono=True)
            text(canvas, (76, 316), "    --candidate <saved-sheet> --apply", 20, LIME, mono=True)
            text(canvas, (76, 392), "No successful matching unconsumed preview", 26, AMBER, mono=True)
            text(canvas, (76, 439), "Run preview again against saved current CAD", 24, AMBER, mono=True)
            text(canvas, (76, 530), "OBSERVED EXIT CODE  2", 18, WHITE, mono=True)
            text(canvas, (76, 574), "Real rejection in a disposable copy. Owner CAD unchanged.", 20, MUTED)
        else:
            review = demo["review"]
            if review is None:
                raise ValueError("the final media scene requires a real --full review transcript")
            results = review["results"]
            passed = sum(result["passed"] for result in results)
            text(canvas, (76, 278), "$ pcb-copilot review <snapshot> --format json", 20, LIME, mono=True)
            text(canvas, (76, 346), f"{passed}/{len(results)} checks passed", 48, WHITE, bold=True)
            pill(canvas, (750, 350), "BLOCKED" if review["blocking"] else "NO REGISTERED BLOCKER", color=AMBER)
            failed = [result["check_id"] for result in results if not result["passed"]]
            text(canvas, (76, 430), "Reported blockers: " + ", ".join(failed), 23, AMBER)
            text(canvas, (76, 485), "Release waits for current engineering decisions.", 23, WHITE)
            text(canvas, (76, 561), "Exact results and hashes: docs/media/demo-results.json", 18, MUTED, mono=True)
    draw.line((48, 661, 1232, 661), fill=LINE, width=3)
    draw.line((48, 661, 48 + round(1184 * (index + progress) / 4), 661), fill=LIME, width=3)
    text(canvas, (48, 678), "RECORDED CLI RESULTS  /  NATIVE CAD RENDERS", 14, MUTED, mono=True)
    text(canvas, (963, 678), "devkyber/PCB", 16, LIME, mono=True)
    return canvas


def animations(board, sheets, demo, output: Path):
    # Low frame rate keeps the in-README GIF light; the MP4 is the same evidence at 24 fps.
    fps, seconds = 4, 4
    frames = [scene(index, frame / (fps * seconds - 1), board, sheets, demo)
              for index in range(4) for frame in range(fps * seconds)]
    palette = frames[0].resize((960, 540), Image.Resampling.LANCZOS).quantize(colors=128)
    gif_frames = [frame.resize((960, 540), Image.Resampling.LANCZOS).quantize(palette=palette,
                  dither=Image.Dither.NONE) for frame in frames]
    gif_frames[0].save(output / "workflow.gif", save_all=True, append_images=gif_frames[1:],
                       duration=250, loop=0, optimize=True, disposal=1)
    video = imageio_ffmpeg.write_frames(str(output / "workflow.mp4"), (1280, 720), fps=24,
                                       codec="libx264", quality=8, macro_block_size=16,
                                       ffmpeg_log_level="error", output_params=["-movflags", "+faststart"])
    video.send(None)
    try:
        for frame in frames:
            for _ in range(6):
                video.send(frame.tobytes())
    finally:
        video.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, required=True, help="real --full demo transcript.json")
    parser.add_argument("--work-dir", type=Path, help="new external directory to retain native exports for visual review")
    args = parser.parse_args()
    MEDIA.mkdir(parents=True, exist_ok=True)
    demo = demo_data(args.demo)
    project = load_project(ROOT / "projects" / "rover-pdb")
    if demo["source_input_hashes"] != input_hashes(project):
        raise ValueError("demo transcript is stale for the current saved Rover inputs")
    commands = []

    def render(work):
        output = work / "assets"
        output.mkdir()
        board, top, sheets, inputs = capture(project, work, commands)
        if inputs != demo["source_input_hashes"]:
            raise RuntimeError("project changed after the transcript was validated")
        hero(board).save(output / "hero.png", optimize=True)
        hero(board, social=True).save(output / "social-preview.png", optimize=True)
        gallery(sheets, top).save(output / "native-cad.png", optimize=True)
        sheet_contact(sheets).save(work / "all-sheets.png", optimize=True)
        board.save(output / "rover-3d.png", optimize=True)
        animations(board, sheets, demo, output)
        (output / "demo-results.json").write_text(json.dumps(demo, indent=2) + "\n", encoding="utf-8")
        outputs = ["hero.png", "social-preview.png", "native-cad.png", "rover-3d.png",
                   "workflow.gif", "workflow.mp4", "demo-results.json"]
        manifest = {
            "schema_version": 1, "generated_utc": datetime.now(UTC).isoformat(),
            "source_project": "projects/rover-pdb", "source_inputs": inputs,
            **repository_binding(ROOT, project.root, inputs),
            "source_cad_unchanged": True,
            "kicad_version": subprocess.check_output([str(discover_toolchain(ROOT).kicad_cli), "version"],
                                                       encoding="utf-8").strip(),
            "schematic_sheets": [name for name, _ in sheets], "native_commands": commands,
            "generator_sha256": digest(Path(__file__)),
            "font_hashes": {path.name: digest(path) for path in sorted((MEDIA / "fonts").glob("*.ttf"))},
            "outputs": {name: {"sha256": digest(output / name), "bytes": (output / name).stat().st_size}
                        for name in outputs},
            "scope": "Native 3D renders and animated recorded CLI results. Not manufactured-board photos, "
                     "a screen recording, a successful edit, or fabrication approval.",
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        publish_bundle(output, MEDIA, "manifest.json", source_check=lambda: assert_current(project, inputs))
        print(json.dumps({"outputs": manifest["outputs"], "review_sheet_contact": str(work / "all-sheets.png")}, indent=2))

    if args.work_dir:
        work = args.work_dir.resolve()
        if work == ROOT or work.is_relative_to(ROOT):
            parser.error("--work-dir must be a new directory outside the checkout")
        work.mkdir(parents=True, exist_ok=False)
        render(work)
    else:
        with tempfile.TemporaryDirectory(prefix="pcb-readme-media-") as directory:
            render(Path(directory))


if __name__ == "__main__":
    main()
