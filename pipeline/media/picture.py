"""Per-shot video segments (Ken Burns or generated clip) and the end card. Cached like everything else."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..core import cache
from ..core.config import ASPECTS, FONTS, FPS
from ..core.context import Context
from ..core.log import log
from ..core.storyboard import Shot, Storyboard
from . import ffmpeg

ZOOM, CLIP_PUSH, MAX_SLOWDOWN, EDGE_TRIM_S = 0.10, 0.03, 1.45, 0.17
INK, PAPER = (238, 226, 205), (20, 16, 13)


def encoder(crf: int) -> list[str]:
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS)]


SEGMENT = [*encoder(17), "-g", str(FPS * 2)]


def is_ethiopic(text: str) -> bool:
    return any(0x1200 <= ord(char) <= 0x139F for char in text)


def kenburns(kind: str, frames: int) -> tuple[str, str, str]:
    """zoompan expressions (zoom, x, y) with an ease-in, ease-out curve."""
    ease = f"(0.5-0.5*cos(PI*on/{max(1, frames - 1)}))"
    centre_x, centre_y, full = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)", f"{1 + ZOOM}"
    moves = {
        "push_in": (f"1+{ZOOM}*{ease}", centre_x, centre_y),
        "pull_out": (f"{full}-{ZOOM}*{ease}", centre_x, centre_y),
        "pan_left": (full, f"(iw-iw/zoom)*(1-{ease})", centre_y),
        "pan_right": (full, f"(iw-iw/zoom)*{ease}", centre_y),
        "tilt_up": (full, centre_x, f"(ih-ih/zoom)*(1-{ease})"),
        "tilt_down": (full, centre_x, f"(ih-ih/zoom)*{ease}"),
    }
    return moves[kind]


def cover(width: int, height: int) -> str:
    return f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height},setsar=1"


def still_filter(kind: str, frames: int, width: int, height: int) -> str:
    zoom, x, y = kenburns(kind, frames)
    # work at 2x so zoompan's whole-pixel steps stay invisible
    return f"{cover(2 * width, 2 * height)},zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={FPS}"


def clip_filter(raw_s: float, frames: int, width: int, height: int) -> str:
    """Trim weak edges, slow gently to fill the shot, hold the end; a slight push hides the hold."""
    wanted = frames / FPS
    edge = min(EDGE_TRIM_S, raw_s * 0.04)
    slow = min(MAX_SLOWDOWN, max(1.0, wanted / (raw_s - 2 * edge)))
    push = f"zoompan=z='1+{CLIP_PUSH}*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    return (
        f"trim=start={edge}:end={raw_s - edge},setpts=(PTS-STARTPTS)*{slow:.5f},"
        f"minterpolate=fps={FPS}:mi_mode=blend,{cover(width, height)},"
        f"tpad=stop_mode=clone:stop_duration={wanted},{push}:d=1:s={width}x{height}:fps={FPS}"
    )


def segment(ctx: Context, shot: Shot, aspect: str, clip: Path | None, seconds: float) -> Path:
    width, height = ASPECTS[aspect]
    frames = round(seconds * FPS)
    source = clip or ctx.paths.keyframe(shot["id"], aspect)
    target = ctx.paths.segment(shot["id"], aspect)
    move = shot["motion"]["kenburns"]
    if clip:
        video_filter = clip_filter(ffmpeg.duration(clip), frames, width, height)
    else:
        video_filter = still_filter(move, frames, width, height)
    wanted = {"source": cache.file_digest(source), "filter": video_filter, "frames": frames}
    if not cache.is_fresh(target, wanted):
        log.info("segment %s.%s: %s, %.2fs", shot["id"], aspect, "clip" if clip else move, seconds)
        with cache.atomic(target) as temp:
            ffmpeg.run("-i", source, "-vf", video_filter, "-frames:v", frames, "-an", *SEGMENT, temp)
        cache.record(target, wanted)
    return target


def _font(text: str, size: int) -> ImageFont.FreeTypeFont:
    name = "NotoSansEthiopic-Regular.ttf" if is_ethiopic(text) else "NotoSans-Regular.ttf"
    return ImageFont.truetype(str(FONTS / name), size)


def _rows(draw: ImageDraw.ImageDraw, lines: list[str], width: int, tall: bool) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        scale = (0.06 if tall else 0.034) if index == 0 else (0.034 if tall else 0.02)
        size, current = int(width * scale), ""
        for word in line.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, _font(candidate, size)) > width * 0.82:
                rows.append((current, size))
                current = word
            else:
                current = candidate
        rows += [(current, size), ("", size // 2)]
    return rows


def draw_end_card(lines: list[str], aspect: str) -> Image.Image:
    width, height = ASPECTS[aspect]
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    rows = _rows(draw, lines, width, aspect == "vertical")
    y = (height - sum(int(size * 1.5) for _, size in rows)) / 2
    for text, size in rows:
        if text:
            font = _font(text, size)
            draw.text(((width - draw.textlength(text, font)) / 2, y), text, font=font, fill=INK)
        y += int(size * 1.5)
    return image


def end_card(ctx: Context, sb: Storyboard, aspect: str) -> Path:
    card, target = sb["end_card"], ctx.paths.segment("end_card", aspect)
    wanted = {"lines": card["lines"], "seconds": card["duration_s"], "aspect": aspect}
    if not cache.is_fresh(target, wanted):
        target.parent.mkdir(parents=True, exist_ok=True)
        still = target.with_suffix(".png")
        draw_end_card(card["lines"], aspect).save(still)
        frames = round(card["duration_s"] * FPS)
        fade = f"fade=in:0:{FPS // 3},fps={FPS}"
        with cache.atomic(target) as temp:
            ffmpeg.run("-loop", 1, "-i", still, "-frames:v", frames, "-vf", fade, "-an", *SEGMENT, temp)
        cache.record(target, wanted)
    return target
