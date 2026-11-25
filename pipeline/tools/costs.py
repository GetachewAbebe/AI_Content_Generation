"""Summarise runs.jsonl into the generated block of COSTS.md."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from ..core.config import ROOT
from ..core.context import Context
from ..core.log import log

START, END = "<!-- generated:start -->", "<!-- generated:end -->"


def table(lines: list[dict[str, Any]]) -> str:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in lines:
        groups[(line["stage"], line["model"])].append(line)
    rows = [
        "| Stage | Model | Attempts | OK | Retried | Failed | Median latency (s) | GPU min | List price (USD) | Paid (USD) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for (stage, model), items in sorted(groups.items()):
        count = {s: sum(i["status"] == s for i in items) for s in ("ok", "retry", "error")}
        times = [i["latency_s"] for i in items if i["status"] == "ok"]
        median = f"{statistics.median(times):.1f}" if times else "-"
        gpu = sum(i["gpu_minutes"] or 0 for i in items)
        priced = [i["list_price_usd"] for i in items if i["list_price_usd"] is not None]
        price = f"{sum(priced):.4f}" if priced else "-"
        paid = sum(i["cost_usd"] for i in items)
        rows.append(
            f"| {stage} | {model} | {len(items)} | {count['ok']} | {count['retry']} | {count['error']} "
            f"| {median} | {gpu:.1f} | {price} | {paid:.2f} |"
        )
    return "\n".join(rows)


def run(ctx: Context) -> None:
    lines = ctx.runlog.read()
    if not lines:
        log.info("no runs logged yet")
        return
    target = ROOT / "COSTS.md" if ctx.paths.base == ROOT else ctx.paths.base / "COSTS.md"
    text = target.read_text() if target.exists() else f"# Costs\n\n{START}\n{END}\n"
    head, rest = text.split(START, 1)
    tail = rest.split(END, 1)[1]
    target.write_text(f"{head}{START}\n{table(lines)}\n{END}{tail}")
    log.info("updated %s from %d log lines", target, len(lines))
