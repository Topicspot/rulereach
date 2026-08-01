"""Render a terminal session GIF from real command output.

Commands are executed inside a pty, so the captured text is exactly what a user sees,
colours included. Nothing is retyped by hand: if the tool output changes, rerun the
script and the GIF changes with it.

Regenerate the README demo after changing the terminal output:

    uv sync --extra dev
    uv run python scripts/demo_gif.py
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# DejaVu first on purpose: some Debian FiraCode builds draw "@" as a wrong glyph, and
# the diff scene of the demo contains a hunk header ("@@ -2,7 +2,7 @@").
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FALLBACK_REGULAR = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
FALLBACK_BOLD = "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"

BG = (13, 17, 23)
FG = (201, 209, 217)
PROMPT = (126, 231, 135)
COLORS = {
    30: (72, 79, 88),
    31: (255, 123, 114),
    32: (126, 231, 135),
    33: (231, 196, 118),
    34: (121, 192, 255),
    35: (210, 168, 255),
    36: (118, 211, 222),
    37: FG,
    90: (110, 118, 129),
}
ANSI = re.compile(r"\x1b\[([0-9;]*)m")


@dataclass(frozen=True)
class Cell:
    char: str
    color: tuple[int, int, int] = FG
    bold: bool = False


Line = list[Cell]


def run_in_pty(command: str, cwd: Path, columns: int) -> str:
    """Run a command through `script` so the tool believes it talks to a terminal."""
    result = subprocess.run(
        ["script", "-qec", command, "/dev/null"],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "PATH": f"{cwd}/.venv/bin:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "TERM": "xterm-256color",
            "COLUMNS": str(columns),
        },
        check=False,
    )
    return result.stdout


def parse_ansi(text: str) -> list[Line]:
    lines: list[Line] = []
    style = Cell(" ")
    for raw in text.replace("\r\n", "\n").replace("\r", "").split("\n"):
        line: Line = []
        pos = 0
        for match in ANSI.finditer(raw):
            for char in raw[pos : match.start()]:
                line.append(replace(style, char=char))
            for code in (match.group(1) or "0").split(";"):
                number = int(code or 0)
                if number == 0:
                    style = Cell(" ")
                elif number == 1:
                    style = replace(style, bold=True)
                elif number in COLORS:
                    style = replace(style, color=COLORS[number])
            pos = match.end()
        for char in raw[pos:]:
            line.append(replace(style, char=char))
        lines.append(line)
    while lines and not "".join(cell.char for cell in lines[-1]).strip():
        lines.pop()
    return lines


def as_line(text: str, color: tuple[int, int, int] = FG, bold: bool = False) -> Line:
    return [Cell(char, color, bold) for char in text]


def build_frames(commands: list[str], cwd: Path, columns: int) -> list[tuple[list[Line], int]]:
    """Return (screen, duration_ms) pairs: typing, then output appearing line by line."""
    frames: list[tuple[list[Line], int]] = []
    screen: list[Line] = []
    for index, command in enumerate(commands):
        output = parse_ansi(run_in_pty(command, cwd, columns))
        prefix = as_line("$ ", PROMPT)
        if index:
            screen = [*screen, []]
        for typed in range(2, len(command) + 2, 2):
            frames.append(([*screen, prefix + as_line(command[:typed])], 70))
        screen = [*screen, prefix + as_line(command)]
        frames.append((list(screen), 550))
        for line in output:
            screen = [*screen, line]
            frames.append((list(screen), 90))
        frames.append((list(screen), 1400 if index < len(commands) - 1 else 2600))
    return frames


def fixed_palette() -> Image.Image:
    """One palette for the whole animation, so colours never shift between frames."""
    colors = {BG, FG, PROMPT, *COLORS.values(), (255, 95, 86), (255, 189, 46), (39, 201, 63)}
    palette = Image.new("P", (1, 1))
    flat = [channel for color in sorted(colors) for channel in color]
    palette.putpalette(flat + [0] * (768 - len(flat)))
    return palette


def render(frames: list[tuple[list[Line], int]], out: Path, columns: int, font_size: int) -> None:
    try:
        regular = ImageFont.truetype(FONT_REGULAR, font_size)
        bold = ImageFont.truetype(FONT_BOLD, font_size)
    except OSError:
        regular = ImageFont.truetype(FALLBACK_REGULAR, font_size)
        bold = ImageFont.truetype(FALLBACK_BOLD, font_size)
    char_w = regular.getlength("M")
    line_h = font_size + 6
    pad = 18
    rows = max(len(screen) for screen, _ in frames)
    width = int(char_w * columns) + pad * 2
    height = line_h * rows + pad * 2 + 26

    images = []
    base = None
    for screen, _ in frames:
        image = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(image)
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            draw.ellipse((pad + i * 20, 12, pad + i * 20 + 11, 23), fill=color)
        for row, line in enumerate(screen):
            y = pad + 26 + row * line_h
            for column, cell in enumerate(line):
                if cell.char == " ":
                    continue
                draw.text(
                    (pad + column * char_w, y),
                    cell.char,
                    font=bold if cell.bold else regular,
                    fill=cell.color,
                )
        if base is None:
            base = fixed_palette()
        images.append(image.quantize(palette=base, dither=Image.Dither.NONE))

    images[0].save(
        out,
        save_all=True,
        append_images=images[1:],
        duration=[duration for _, duration in frames],
        loop=0,
        optimize=True,
        disposal=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, default=Path("assets/demo.gif"))
    parser.add_argument(
        "--cmd",
        action="append",
        default=None,
        help="Defaults to the report and --fix scenes shown in the README.",
    )
    parser.add_argument("--columns", type=int, default=104)
    parser.add_argument("--font-size", type=int, default=15)
    args = parser.parse_args()

    commands = args.cmd or [
        "rulereach check tests/fixtures/broken --tool cursor --tool claude",
        "rulereach explain packages/web/index.ts --path tests/fixtures/broken",
        "rulereach list tests/fixtures/clean",
    ]
    frames = build_frames(commands, args.cwd.resolve(), args.columns)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(frames, args.out, args.columns, args.font_size)
    print(f"{args.out}: {len(frames)} frames, {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
