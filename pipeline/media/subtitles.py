"""SRT sidecars (English and the narration language) and the styled ASS that is burned in."""

from __future__ import annotations

from pathlib import Path

from ..core.config import ASPECTS
from ..core.context import Context
from ..core.storyboard import Storyboard
from ..timeline import Timeline
from .picture import is_ethiopic

# font size, bottom margin as a share of height (vertical clears the app's buttons), title size
LAYOUT = {"vertical": (56, 0.20, 96), "horizontal": (54, 0.07, 100)}
TITLE_START_S, TITLE_END_S = 0.5, 3.6


def srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02}:{ms // 60_000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    return f"{cs // 360_000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def srt(events: list[tuple[float, float, str]]) -> str:
    return "\n".join(
        f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n" for n, (a, b, text) in enumerate(events, 1)
    )


def ass(sb: Storyboard, timeline: Timeline, aspect: str) -> str:
    width, height = ASPECTS[aspect]
    size, margin, title_size = LAYOUT[aspect]
    native = sb["title"]["native"]
    title_font = "Noto Sans Ethiopic" if is_ethiopic(native) else "Noto Sans"
    title_end = min(TITLE_END_S, timeline.shots[0].end)
    title = f"{{\\fad(500,500)}}{native}\\N{{\\fnNoto Sans\\fs{title_size // 2}}}{sb['title']['en']}"
    rows = [
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\n\n[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV",
        f"Style: Sub,Noto Sans,{size},&H00FFFFFF,&H00101010,&H80000000,0,1,3,1,2,40,40,{int(height * margin)}",
        f"Style: Title,{title_font},{title_size},&H00E8F2FA,&H00101010,&H80000000,-1,1,3,1,8,60,60,{int(height * 0.16)}",
        "\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        f"Dialogue: 0,{ass_time(TITLE_START_S)},{ass_time(title_end)},Title,,0,0,0,,{title}",
    ]
    for event in timeline.subtitles:
        text = "\\N".join(event.lines).replace("{", "(").replace("}", ")")
        rows.append(f"Dialogue: 0,{ass_time(event.start)},{ass_time(event.end)},Sub,,0,0,0,,{text}")
    return "\n".join(rows) + "\n"


def write(ctx: Context, sb: Storyboard, timeline: Timeline) -> dict[str, Path]:
    folder = ctx.paths.final
    folder.mkdir(parents=True, exist_ok=True)
    english = [(e.start, e.end, "\n".join(e.lines)) for e in timeline.subtitles]
    native = [
        (timed.speech_start, timed.speech_start + timed.speech_s, shot["narration"]["text"])
        for timed, shot in zip(timeline.shots, sb["shots"], strict=True)
        if timed.speech_start is not None
    ]
    (folder / "film.en.srt").write_text(srt(english))
    if sb["language"]["code"] != "en":
        (folder / f"film.{sb['language']['code']}.srt").write_text(srt(native))
    paths = {aspect: folder / f"subs.{aspect}.ass" for aspect in ASPECTS}
    for aspect, path in paths.items():
        path.write_text(ass(sb, timeline, aspect))
    return paths
