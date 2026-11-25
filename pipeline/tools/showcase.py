"""Write a small static page for the film (upload outputs/final as a Hugging Face static Space)."""

from __future__ import annotations

import html

from ..core.context import Context
from ..core.log import log
from ..core.storyboard import Storyboard

STYLE = (
    "body{background:#14100d;color:#eee2cd;font:18px/1.6 'Noto Sans','Noto Sans Ethiopic',sans-serif;max-width:60rem;"
    "margin:auto;padding:2rem 1rem}video{width:100%;max-height:80vh}li{margin:.6rem 0}a{color:#e9b872}"
)


def page(sb: Storyboard) -> str:
    esc = html.escape
    shots = "".join(
        f"<li lang='{sb['language']['code']}'>{esc(s['narration']['text'])}<br>"
        f"<small lang='en'>{esc(s['narration']['subtitle_en'])}</small></li>"
        for s in sb["shots"]
        if s["narration"]["text"].strip()
    )
    notes = "".join(f"<p>{esc(line)}</p>" for line in sb["end_card"]["lines"])
    return (
        f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        f"<title>{esc(sb['title']['en'])}</title><style>{STYLE}</style>"
        f"<h1>{esc(sb['title']['native'])}</h1><p>{esc(sb['logline'])}</p>"
        f"<video controls src='film.horizontal.mp4'></video>"
        f"<p><a href='film.vertical.mp4'>Vertical version</a></p><ol>{shots}</ol>{notes}</html>"
    )


def run(ctx: Context, sb: Storyboard) -> None:
    target = ctx.paths.final / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page(sb))
    log.info("wrote %s", target)
