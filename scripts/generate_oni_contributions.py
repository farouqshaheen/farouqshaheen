#!/usr/bin/env python3
"""Render a self-contained ONI contribution animation from GitHub's contribution calendar.

Run in GitHub Actions with GITHUB_TOKEN. Demo mode uses clearly-labelled synthetic data
and is intended exclusively for the optional local preview, not for the profile image.
Python 3.10+, standard library only. Never exposes a token or fetches private repo contents.
"""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
USER = os.environ.get("GITHUB_LOGIN", "farouqshaheen")
GRAPHQL = "https://api.github.com/graphql"
QUERY = '''query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}'''


def _utc_iso(day: date) -> str:
    return f"{day.isoformat()}T00:00:00Z"


def graphql_calendar(token: str, login: str, start: date, end: date) -> dict[str, int]:
    body = json.dumps({"query": QUERY, "variables": {"login": login, "from": _utc_iso(start), "to": _utc_iso(end)}}).encode()
    req = urllib.request.Request(
        GRAPHQL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/vnd.github+json", "User-Agent": "oni-contribution-trail/2.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            data = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RuntimeError(f"GitHub contribution query failed: {exc}") from exc
    errors = data.get("errors")
    if errors:
        raise RuntimeError("GitHub GraphQL: " + "; ".join(str(e.get("message", e)) for e in errors))
    user = (data.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub account not found: {login}")
    days: dict[str, int] = {}
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for d in week["contributionDays"]:
            days[d["date"]] = int(d["contributionCount"])
    return days


def real_contributions(token: str, login: str, today: date) -> dict[str, int]:
    # Keep 52 weeks + current week; the one-year range is fetched in a single request
    # if possible. Some GraphQL servers apply resource limits to wide calendars,
    # so split into 65-day windows as a fallback.
    start = today - timedelta(days=364)
    end = today + timedelta(days=1)
    try:
        data = graphql_calendar(token, login, start, end)
    except RuntimeError as exc:
        print(f"Full-year query failed, retrying smaller date ranges: {exc}", file=sys.stderr)
        data = {}
        current = start
        while current < end:
            next_end = min(current + timedelta(days=60), end)
            data.update(graphql_calendar(token, login, current, next_end))
            current = next_end
    # Only show the intended 365-day period (GraphQL weeks may contain padding days).
    return { (start + timedelta(days=i)).isoformat(): data.get((start + timedelta(days=i)).isoformat(), 0) for i in range(365) }


def color(level: int) -> str:
    if level == 0: return "#171e29"
    if level == 1: return "#512036"
    if level == 2: return "#8f2546"
    if level == 3: return "#c72c54"
    return "#ff587e"


def generate(days: dict[str, int] | None, avatar: Path, date_label: str, login: str, demo=False) -> str:
    W, H = 1180, 362
    start = date.fromisoformat(date_label) - timedelta(days=364)
    # Align to Sunday for a standard contribution calendar of 53/54 columns.
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    end = date.fromisoformat(date_label)
    ncols = ((end - first_sunday).days // 7) + 1
    gap = 16.2 if ncols <= 54 else 15.6
    tile = 12.2
    gx, gy = 45.0, 150.0

    all_days = []
    for i in range(365):
        d = start + timedelta(days=i)
        count = days.get(d.isoformat(),0) if days else 0
        col = (d - first_sunday).days // 7
        row = (d.weekday()+1)%7
        all_days.append((d,count,col,row))
    counts = [int(x[1]) for x in all_days]
    nonzero = [x for x in all_days if x[1] > 0]
    total = sum(counts)
    max_count = max(counts or [0])
    def level(n):
        if n <= 0: return 0
        if max_count < 3: return min(n, 2)
        ratio = n/max_count
        return 1 if ratio < 0.20 else 2 if ratio < 0.45 else 3 if ratio < 0.75 else 4

    main_tiles=[]
    for d,count,col,row in all_days:
        x,y = gx+col*gap,gy+row*gap
        fill = color(level(count))
        main_tiles.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{tile:.1f}" height="{tile:.1f}" rx="2.4" fill="{fill}" stroke="#384051" stroke-opacity=".3" stroke-width=".5"><title>{d.isoformat()}: {count} contributions</title></rect>')

    # Follow 6 to 11 actual active days distributed across the year, where possible.
    anchors=nonzero
    if len(anchors)>11:
        anchors=[anchors[round(i*(len(anchors)-1)/10)] for i in range(11)]
    if not anchors:
        # Placeholder only. Label prominently; never invent contribution activity.
        anchors=[all_days[i] for i in range(14,len(all_days),52)]
        anchors=anchors[:7]
    coords=[]
    for _,_,col,row in anchors:
        coords.append((gx+col*gap+tile/2, gy+row*gap+tile/2))
    if len(coords)==1:
        coords.append((coords[0][0]+45,coords[0][1]))
    # A single real sweep left to right over selected activity squares.
    route="M "+" L ".join(f"{x:.1f} {y:.1f}" for x,y in coords)
    motion_points = coords + [coords[0]]
    motion_values = ";".join(f"{x:.1f} {y:.1f}" for x,y in motion_points)
    motion_times = ";".join(f"{i/(len(motion_points)-1):.5f}" for i in range(len(motion_points)))
    path_overlay=f'<path d="{route}" fill="none" stroke="#fb7185" stroke-width="1.4" stroke-opacity=".30" stroke-dasharray="3 8" />'
    glows=''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.4" fill="none" stroke="#f43f5e" stroke-width="1.5" opacity=".45"/>' for x,y in coords)
    avatar_b64=base64.b64encode(avatar.read_bytes()).decode('ascii')
    badge = 'SAMPLE DATA / PREVIEW ONLY' if demo else 'AWAITING FIRST GITHUB ACTION SYNC' if days is None else 'LIVE GITHUB CONTRIBUTIONS'
    total_txt = '—' if days is None else str(total)
    active_txt = '—' if days is None else str(len(nonzero))
    corner = 'EXAMPLE' if demo else 'PENDING' if days is None else 'SYNCED'
    start_x, start_y = coords[0]
    date_short=escape(date_label)
    # Embedded avatar makes the SVG self-contained for GitHub README's image proxy.
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="ONI mascot moving through a GitHub contribution graph for {escape(login)}">
<defs>
  <linearGradient id="bg" x2="1" y2="1"><stop stop-color="#0b1018"/><stop offset=".55" stop-color="#14101b"/><stop offset="1" stop-color="#0b1018"/></linearGradient>
  <radialGradient id="redLight"><stop stop-color="#c82e53" stop-opacity=".20"/><stop offset="1" stop-color="#c82e53" stop-opacity="0"/></radialGradient>
  <filter id="glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="3" /></filter>
  <pattern id="scanlines" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 5h6" stroke="#bd2451" stroke-width=".6" stroke-opacity=".06"/></pattern>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
    @media (prefers-reduced-motion: reduce) {{ animate, animateMotion, animateTransform {{ display: none; }} }}
  </style>
</defs>
<rect x="1" y="1" width="1178" height="360" rx="15" fill="url(#bg)" stroke="#713048" stroke-width="2"/>
<rect x="2" y="2" width="1176" height="358" rx="14" fill="url(#scanlines)"/>
<path d="M25 78h1130" stroke="#58233b"/><path d="M26 26h18M26 26v16" stroke="#ef4269" stroke-width="2"/>
<text x="43" y="43" fill="#f2f4f8" font-weight="700" font-size="23" letter-spacing="1.1">ONI // CONTRIBUTION TRAIL</text>
<text x="44" y="67" fill="#c192a6" font-size="12">THE OPERATOR FOLLOWS REAL GITHUB ACTIVITY NODES</text>
<circle cx="1125" cy="39" r="5" fill="#fb7185"><animate attributeName="opacity" values=".45;1;.45" dur="2s" repeatCount="indefinite"/></circle>
<text x="1109" y="44" text-anchor="end" fill="#fda4af" font-size="12">{corner}</text>
<text x="45" y="105" fill="#eb819f" font-size="12">GITHUB / {escape(login.upper())}</text>
<text x="45" y="126" fill="#939cac" font-size="11">{badge}</text>
<g> {''.join(main_tiles)} </g>
{path_overlay}
{glows}
<!-- ONI moves along the actual detected activity points when the Action populates this SVG. -->
<g id="oni-avatar" transform="translate({start_x:.1f} {start_y:.1f})">
  <animateTransform attributeName="transform" type="translate" values="{motion_values}" keyTimes="{motion_times}" dur="24s" repeatCount="indefinite" calcMode="linear" />
  <ellipse cx="0" cy="0" rx="44" ry="20" fill="url(#redLight)"/>
  <g><animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="1.3s" repeatCount="indefinite" />
   <image href="data:image/png;base64,{avatar_b64}" x="-23" y="-90" width="46" height="99" preserveAspectRatio="xMidYMid meet" />
  </g>
  <circle cx="0" cy="0" r="10" fill="none" stroke="#fb7185" opacity=".8"><animate attributeName="r" values="3;23;3" dur="1.7s" repeatCount="indefinite"/><animate attributeName="opacity" values=".85;0;0" dur="1.7s" repeatCount="indefinite" /></circle>
  <path d="M6 -8h38" stroke="#fb7185" stroke-width="1.7" stroke-dasharray="4 5"><animate attributeName="stroke-dashoffset" values="0;-28" dur="1.2s" repeatCount="indefinite"/></path>
</g>
<rect x="950" y="148" width="197" height="115" rx="9" fill="#0c1119" stroke="#76354a"/>
<text x="965" y="170" fill="#fb7185" font-size="11" letter-spacing="1">ACTIVITY TELEMETRY</text>
<text x="966" y="207" fill="#f9fafb" font-size="26" font-weight="700">{total_txt}</text>
<text x="966" y="226" fill="#8793a5" font-size="11">TOTAL CONTRIBUTIONS</text>
<text x="966" y="249" fill="#fda4af" font-size="12">{active_txt} ACTIVE DAYS</text>
<path d="M43 294h1091" stroke="#482438" stroke-width="1"/>
<text x="43" y="316" fill="#a5a9b9" font-size="11">YEARLY CONTRIBUTION GRID · UPDATED {date_short} UTC</text>
<g transform="translate(850 304)"><text x="-8" y="12" text-anchor="end" fill="#8c97a8" font-size="11">LESS</text>
 <rect x="0" y="1" width="11" height="11" rx="2" fill="#171e29"/><rect x="16" y="1" width="11" height="11" rx="2" fill="#512036"/><rect x="32" y="1" width="11" height="11" rx="2" fill="#8f2546"/><rect x="48" y="1" width="11" height="11" rx="2" fill="#c72c54"/><rect x="64" y="1" width="11" height="11" rx="2" fill="#ff587e"/>
 <text x="85" y="12" fill="#8c97a8" font-size="11">MORE</text></g>
<text x="43" y="340" fill="#6f7787" font-size="10">DATA SOURCE: GITHUB GRAPHQL / CONTRIBUTION CALENDAR · NO SCRIPTS IN SVG</text>
</svg>'''
    return svg


def main():
    parser=argparse.ArgumentParser(description="Generate an animated ONI contribution graph")
    parser.add_argument("--output", default=str(ROOT / "assets" / "oni-contributions.svg"))
    parser.add_argument("--fixture", type=Path, help="JSON fixture of date:count values for offline tests; not used in GitHub Actions")
    parser.add_argument("--demo", action="store_true", help="Label preview as sample data")
    parser.add_argument("--placeholder", action="store_true", help="Generate a no-data initial file (no pretend activity counts)")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    args=parser.parse_args()
    today=date.fromisoformat(args.date)
    avatar=ROOT/'assets'/'oni-avatar.png'
    if not avatar.exists(): raise SystemExit("Missing avatar: assets/oni-avatar.png")
    if args.placeholder:
        counts=None
    elif args.fixture:
        if not args.demo: raise SystemExit("Fixture runs require --demo, to avoid presenting sample activity as real")
        counts=json.loads(args.fixture.read_text())
    else:
        token=os.environ.get("GITHUB_TOKEN", "")
        if not token: raise SystemExit("Set GITHUB_TOKEN in GitHub Actions to get real contributions")
        counts=real_contributions(token,USER,today)
        if not counts: raise SystemExit("GitHub returned no calendar days; refusing to generate empty activity")
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    svg=generate(counts,avatar,args.date,USER,args.demo)
    out.write_text(svg,encoding="utf-8")
    print(f"Wrote {out} ({len(svg)} bytes); mode={'demo' if args.demo else 'placeholder' if counts is None else 'live'}")

if __name__ == '__main__': main()
