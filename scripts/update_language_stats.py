#!/usr/bin/env python3
"""Update profile README language totals and render an animated GIF.

Only public, non-archived software repositories are considered. Known privacy
policy/website repositories and documentation-only repositories are excluded.
If GitHub API collection fails or is incomplete, this script exits before
changing tracked outputs, preserving the last successful version.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OWNER = os.environ.get("GITHUB_OWNER", "jorgeezequiel")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GIF = ROOT / "assets" / "language-stats.gif"
START = "<!-- PROFILE-STATS:START -->"
END = "<!-- PROFILE-STATS:END -->"
EXCLUDED_REPOS = {
    "jorgeezequiel.github.io",
    "pazcall-privacidade",
    "questlog-privacy",
}
EXCLUDED_NAME_WORDS = ("privacy", "privacidade", "policy", "política", "legal")
EXCLUDED_TOPICS = {"privacy-policy", "privacy", "documentation-only"}


def request_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-language-stats/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP status {response.status} for {url}")
        return json.load(response)


def eligible_repositories():
    repos = []
    for page in range(1, 11):
        url = (
            f"https://api.github.com/users/{urllib.parse.quote(OWNER)}/repos"
            f"?type=public&per_page=100&page={page}&sort=updated"
        )
        batch = request_json(url)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub returned an unexpected repository list.")
        repos.extend(batch)
        if len(batch) < 100:
            return [
                repo for repo in repos
                if repo.get("owner", {}).get("login", "").lower() == OWNER.lower()
                and not repo.get("private", True)
                and not repo.get("archived", False)
                and repo.get("name", "").lower() not in EXCLUDED_REPOS
                and not any(word in repo.get("name", "").lower() for word in EXCLUDED_NAME_WORDS)
                and not EXCLUDED_TOPICS.intersection(repo.get("topics") or [])
                and not repo.get("fork", False)
            ]
    raise RuntimeError("Repository listing exceeded 1,000 entries; refusing partial totals.")


def language_totals(repos):
    totals = Counter()
    # Fail closed: any API error prevents publication of partial totals.
    for repo in repos:
        full_name = repo.get("full_name")
        if not full_name:
            raise RuntimeError("Repository record missing full_name.")
        encoded = urllib.parse.quote(full_name, safe="/")
        data = request_json(f"https://api.github.com/repos/{encoded}/languages")
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected languages response for {full_name}.")
        totals.update({k: v for k, v in data.items() if isinstance(v, int) and v > 0})
    return totals


def font(size, bold=False):
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def render_gif(totals):
    GIF.parent.mkdir(parents=True, exist_ok=True)
    colors = [
        (92, 124, 250), (56, 178, 172), (246, 173, 85),
        (237, 100, 166), (129, 140, 248), (104, 211, 145),
        (246, 113, 113), (160, 174, 192)
    ]
    ranked = totals.most_common(8)
    if not ranked:
        ranked = [("No language data yet", 1)]
    total_bytes = sum(value for _, value in ranked) or 1
    frames = []
    width, height = 960, 420
    title_font, body_font, small_font = font(28, True), font(18), font(14)
    for offset in range(12):
        image = Image.new("RGB", (width, height), (17, 24, 39))
        draw = ImageDraw.Draw(image)
        draw.text((38, 28), "Programming Languages", font=title_font, fill=(243, 244, 246))
        draw.text((40, 70), f"Public software repositories · frame {offset + 1}/12",
                  font=small_font, fill=(156, 163, 175))
        x, y, bar_width, bar_height = 40, 130, 880, 30
        draw.rounded_rectangle((x, y, x + bar_width, y + bar_height), radius=12,
                               fill=(55, 65, 81))
        running_x = x
        for index, (name, value) in enumerate(ranked):
            segment = round(bar_width * value / total_bytes)
            if index == len(ranked) - 1:
                segment = x + bar_width - running_x
            if segment > 0:
                draw.rectangle((running_x, y, running_x + segment, y + bar_height),
                               fill=colors[index % len(colors)])
                running_x += segment
        for index, (name, value) in enumerate(ranked):
            row_y = 190 + index * 26
            color = colors[index % len(colors)]
            draw.ellipse((42, row_y + 4, 56, row_y + 18), fill=color)
            pct = value / sum(totals.values()) * 100 if totals else 0
            draw.text((68, row_y), name, font=body_font, fill=(229, 231, 235))
            draw.text((880, row_y), f"{pct:.1f}%", font=body_font, fill=(229, 231, 235), anchor="ra")
        draw.text((40, 390), "Updated automatically · excludes archived and privacy-policy repositories",
                  font=small_font, fill=(156, 163, 175))
        frames.append(image)
    frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=500,
                   loop=0, optimize=True, disposal=2)


def update_readme(totals, repo_count):
    current = README.read_text(encoding="utf-8")
    if START not in current or END not in current:
        raise RuntimeError("README stats markers are missing; refusing to overwrite content.")
    start = current.index(START) + len(START)
    end = current.index(END)
    if end < start:
        raise RuntimeError("README stats markers are out of order.")
    total_bytes = sum(totals.values())
    lines = [
        "",
        f"**Eligible public software repositories:** {repo_count}",
        "",
        "| Language | Share |",
        "|---|---:|",
    ]
    if totals:
        for name, value in totals.most_common(10):
            share = (value / total_bytes * 100) if total_bytes else 0
            lines.append(f"| {name} | {share:.1f}% |")
    else:
        lines.append("| No language data available | — |")
    replacement = "\n" + "\n".join(lines) + "\n"
    README.write_text(current[:start] + replacement + current[end:], encoding="utf-8")


def main():
    try:
        repos = eligible_repositories()
        totals = language_totals(repos)
        # Do not publish misleading zero/empty totals if collection unexpectedly
        # returns no eligible repositories; preserve the last valid artifacts.
        if not repos or not totals:
            raise RuntimeError("No eligible repositories or no language data; preserving previous outputs.")
        update_readme(totals, len(repos))
        render_gif(totals)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
