"""Regenerate assets/downloads-chart.svg from pypistats.org data.

Fetches daily download counts for pbi-cli-tool (mirrors excluded), merges them
into assets/downloads-history.csv, computes a cumulative series, and writes a
dark-theme SVG line chart that matches the visual style of the other assets in
this repo.

pypistats only keeps roughly the last 180 days, so the CSV is the source of
truth for older days. Without it the cumulative total shrinks as early days
age out of the API window. Values returned by the API override stored values
for the same date, so late corrections and backfilled days are picked up.

Runs with stdlib only so it works in CI without extra dependencies.

Usage:
    python scripts/generate_downloads_chart.py
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

PACKAGE = "pbi-cli-tool"
API_URL = f"https://pypistats.org/api/packages/{PACKAGE}/overall?mirrors=false"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
OUTPUT_PATH = ASSETS_DIR / "downloads-chart.svg"
HISTORY_PATH = ASSETS_DIR / "downloads-history.csv"

# Chart geometry
WIDTH = 850
HEIGHT = 340
PLOT_LEFT = 70
PLOT_RIGHT = 810
PLOT_TOP = 78
PLOT_BOTTOM = 280

# Colors (match stats.svg / banner.svg palette)
BG = "#0d1117"
ACCENT_YELLOW = "#F2C811"
LINE_BLUE = "#58a6ff"
GRID = "#21262d"
TEXT_PRIMARY = "#c9d1d9"
TEXT_SECONDARY = "#8b949e"
CARD_BG = "#0d1a2a"


def fetch_downloads() -> list[tuple[date, int]]:
    """Return sorted list of (date, daily_downloads) from pypistats."""
    with urllib.request.urlopen(API_URL, timeout=30) as resp:
        payload = json.loads(resp.read())

    rows = [
        (datetime.strptime(r["date"], "%Y-%m-%d").date(), int(r["downloads"]))
        for r in payload["data"]
        if r["category"] == "without_mirrors"
    ]
    rows.sort(key=lambda item: item[0])
    return rows


def load_history(path: Path = HISTORY_PATH) -> dict[date, int]:
    """Return stored daily downloads keyed by date (empty if no file yet)."""
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {
            datetime.strptime(row["date"], "%Y-%m-%d").date(): int(row["downloads"])
            for row in csv.DictReader(fh)
        }


def save_history(history: dict[date, int], path: Path = HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["date", "downloads"])
        for d in sorted(history):
            writer.writerow([d.isoformat(), history[d]])


def merge_history(
    history: dict[date, int], fetched: list[tuple[date, int]]
) -> dict[date, int]:
    """Union of stored and fetched days; fetched values win on overlap."""
    merged = dict(history)
    merged.update(fetched)
    return merged


def to_cumulative(daily: dict[date, int]) -> list[tuple[date, int]]:
    """Cumulative series with one point per calendar day.

    Days missing from the data carry the previous total forward, so a gap in
    pypistats shows as a flat segment instead of compressing the x-axis.
    """
    if not daily:
        return []
    first, last = min(daily), max(daily)
    total = 0
    out: list[tuple[date, int]] = []
    d = first
    while d <= last:
        total += daily.get(d, 0)
        out.append((d, total))
        d += timedelta(days=1)
    return out


def nice_ceiling(value: int) -> int:
    """Round up to a nice axis maximum (1-2-5 * 10^n)."""
    if value <= 0:
        return 10
    import math

    exp = math.floor(math.log10(value))
    base = 10**exp
    for step in (1, 2, 2.5, 5, 10):
        candidate = int(step * base)
        if candidate >= value:
            return candidate
    return int(10 * base)


def build_svg(series: list[tuple[date, int]]) -> str:
    if not series:
        raise RuntimeError("No download data returned from pypistats")

    n = len(series)
    max_val = series[-1][1]
    y_max = nice_ceiling(int(max_val * 1.15))

    plot_width = PLOT_RIGHT - PLOT_LEFT
    plot_height = PLOT_BOTTOM - PLOT_TOP

    def x_at(i: int) -> float:
        if n == 1:
            return PLOT_LEFT + plot_width / 2
        return PLOT_LEFT + (i / (n - 1)) * plot_width

    def y_at(v: int) -> float:
        return PLOT_BOTTOM - (v / y_max) * plot_height

    points = [(x_at(i), y_at(v)) for i, (_, v) in enumerate(series)]

    line_path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area_path = (
        f"M {points[0][0]:.2f},{PLOT_BOTTOM} "
        + "L "
        + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        + f" L {points[-1][0]:.2f},{PLOT_BOTTOM} Z"
    )

    # Y-axis gridlines (5 steps)
    gridlines = []
    y_labels = []
    for step in range(6):
        v = y_max * step / 5
        y = PLOT_BOTTOM - (v / y_max) * plot_height
        gridlines.append(
            f'<line x1="{PLOT_LEFT}" y1="{y:.1f}" x2="{PLOT_RIGHT}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="2,3"/>'
        )
        label = f"{int(v):,}"
        y_labels.append(
            f'<text x="{PLOT_LEFT - 8}" y="{y + 4:.1f}" font-family="\'Segoe UI\', Arial, sans-serif" '
            f'font-size="10" fill="{TEXT_SECONDARY}" text-anchor="end">{label}</text>'
        )

    # X-axis labels: first, last, and ~3 intermediate
    label_indices = sorted({0, n - 1, n // 4, n // 2, (3 * n) // 4})
    x_labels = []
    for i in label_indices:
        d, _ = series[i]
        x = x_at(i)
        x_labels.append(
            f'<text x="{x:.1f}" y="{PLOT_BOTTOM + 18}" font-family="\'Segoe UI\', Arial, sans-serif" '
            f'font-size="10" fill="{TEXT_SECONDARY}" text-anchor="middle">{d.strftime("%b %d")}</text>'
        )

    # Data point dots + highlight on last
    dots = []
    for i, (x, y) in enumerate(points):
        is_last = i == n - 1
        r = 4 if is_last else 2.5
        fill = ACCENT_YELLOW if is_last else LINE_BLUE
        dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{fill}"/>')

    # Last-value callout
    last_x, last_y = points[-1]
    last_val = series[-1][1]
    callout_x = min(last_x + 10, PLOT_RIGHT - 90)
    callout_y = max(last_y - 28, PLOT_TOP + 14)

    # Summary stats
    first_date = series[0][0].strftime("%b %d, %Y")
    last_date = series[-1][0].strftime("%b %d, %Y")
    total_str = f"{max_val:,}"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{LINE_BLUE}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{LINE_BLUE}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="100%" height="100%" fill="{BG}" rx="8"/>

  <!-- Title -->
  <text x="{WIDTH // 2}" y="33" font-family="'Segoe UI', Arial, sans-serif" font-size="17" fill="{ACCENT_YELLOW}" text-anchor="middle" font-weight="bold">pbi-cli Downloads Over Time</text>
  <text x="{WIDTH // 2}" y="52" font-family="'Segoe UI', Arial, sans-serif" font-size="11" fill="{TEXT_SECONDARY}" text-anchor="middle">Cumulative installs from PyPI \u2022 mirrors excluded \u2022 source: pypistats.org</text>

  <!-- Gridlines & y-labels -->
  {"".join(gridlines)}
  {"".join(y_labels)}

  <!-- Area fill -->
  <path d="{area_path}" fill="url(#areaFill)"/>

  <!-- Line -->
  <path d="{line_path}" fill="none" stroke="{LINE_BLUE}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>

  <!-- Data points -->
  {"".join(dots)}

  <!-- Last-value callout -->
  <rect x="{callout_x:.1f}" y="{callout_y:.1f}" width="82" height="24" rx="4" fill="{CARD_BG}" stroke="{ACCENT_YELLOW}" stroke-width="1"/>
  <text x="{callout_x + 41:.1f}" y="{callout_y + 16:.1f}" font-family="'Segoe UI', Arial, sans-serif" font-size="12" fill="{ACCENT_YELLOW}" text-anchor="middle" font-weight="bold">{total_str} total</text>

  <!-- X-axis labels -->
  {"".join(x_labels)}

  <!-- Footer: date range -->
  <text x="{PLOT_LEFT}" y="{HEIGHT - 12}" font-family="'Segoe UI', Arial, sans-serif" font-size="10" fill="{TEXT_SECONDARY}">{first_date} \u2192 {last_date}</text>
  <text x="{PLOT_RIGHT}" y="{HEIGHT - 12}" font-family="'Segoe UI', Arial, sans-serif" font-size="10" fill="{TEXT_SECONDARY}" text-anchor="end">{n} days of data</text>
</svg>
"""
    return svg


def main() -> int:
    try:
        daily = fetch_downloads()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch pypistats data: {exc}", file=sys.stderr)
        return 1

    if not daily:
        print("pypistats returned no rows", file=sys.stderr)
        return 1

    history = merge_history(load_history(), daily)
    cumulative = to_cumulative(history)
    svg = build_svg(cumulative)

    save_history(history)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(cumulative)} days, {cumulative[-1][1]:,} total downloads)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
