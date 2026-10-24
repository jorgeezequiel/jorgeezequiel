#!/usr/bin/env python3
"""Generate privacy-conscious, aggregate language stats for the profile README.

Eligible public repositories and explicitly authorized private repositories are
aggregated. No repository names, URLs, descriptions, or per-repository data are
published. Outputs are staged and validated before replacing the README and GIF.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OWNER = os.environ.get("GITHUB_OWNER", "jorgeezequiel")
PUBLIC_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PRIVATE_REPOS_TOKEN = os.environ.get("PRIVATE_REPOS_TOKEN", "")
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ASSETS = ROOT / "assets"
GIF = ASSETS / "language-stats.gif"
SVG = ASSETS / "language-stats.svg"
START = "<!-- PROFILE-STATS:START -->"
END = "<!-- PROFILE-STATS:END -->"
EXCLUDED_REPOS = {
    "jorgeezequiel.github.io",
    "pazcall-privacidade",
    "questlog-privacy",
}
EXCLUDED_NAME_WORDS = (
    "privacy", "privacidade", "policy", "política", "legal",
    "documentation", "docs-only", "docs_only", "wiki",
)
EXCLUDED_TOPICS = {
    "privacy-policy", "privacy", "documentation-only", "documentation", "docs", "docs-only",
}
PAGE_SIZE = 100
MAX_PAGES = 10


def request_json(url: str, token: str = ""):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-language-stats/2.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError("GitHub returned an unexpected HTTP status.")
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        # Do not print the URL or raw exception: private repository names can be
        # present in API URLs and must never appear in public Actions logs.
        raise RuntimeError(
            "GitHub API request failed; response details suppressed for privacy."
        ) from None


def is_eligible(repo: dict, allow_private: bool = False) -> bool:
    name = str(repo.get("name") or "").lower()
    name_parts = set(name.replace("_", "-").replace(".", "-").split("-"))
    owner = str((repo.get("owner") or {}).get("login") or "").lower()
    topics = {str(topic).lower() for topic in (repo.get("topics") or [])}
    description = str(repo.get("description") or "").lower()
    return (
        owner == OWNER.lower()
        and (
            repo.get("private") is False
            or (allow_private and repo.get("private") is True)
        )
        and not repo.get("archived", False)
        and not repo.get("fork", False)
        and name not in EXCLUDED_REPOS
        and not any(word in name for word in EXCLUDED_NAME_WORDS)
        and not name_parts.intersection({"docs", "documentation", "wiki"})
        and not topics.intersection(EXCLUDED_TOPICS)
        and "documentation-only" not in description
        and "documentation site" not in description
        and "documentation website" not in description
        and "privacy policy" not in description
        and "política de privacidade" not in description
    )


def collect_repository_pages(url_template: str, token: str):
    repositories = []
    for page in range(1, MAX_PAGES + 1):
        batch = request_json(url_template.format(page=page), token)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub returned an unexpected repository list.")
        repositories.extend(batch)
        if len(batch) < PAGE_SIZE:
            return repositories
    raise RuntimeError("Repository listing exceeded 1,000 entries; refusing partial totals.")


def eligible_repositories():
    if not PRIVATE_REPOS_TOKEN:
        raise RuntimeError(
            "PRIVATE_REPOS_TOKEN is not configured; preserving previous outputs."
        )

    public_url = (
        f"https://api.github.com/users/{urllib.parse.quote(OWNER)}"
        f"/repos?type=public&per_page={PAGE_SIZE}&page={{page}}&sort=updated"
    )
    private_url = (
        "https://api.github.com/user/repos?visibility=private&affiliation=owner"
        f"&per_page={PAGE_SIZE}&page={{page}}&sort=updated"
    )

    public_repositories = collect_repository_pages(public_url, PUBLIC_TOKEN)
    # A fine-grained token can see only the private repositories explicitly
    # selected by the owner. Never log or publish the returned repository list.
    private_repositories = collect_repository_pages(private_url, PRIVATE_REPOS_TOKEN)

    eligible_public = [
        repo for repo in public_repositories if is_eligible(repo)
    ]
    eligible_private = [
        repo for repo in private_repositories if is_eligible(repo, allow_private=True)
    ]
    return eligible_public + eligible_private


def language_totals(repositories):
    totals = Counter()
    for repo in repositories:
        full_name = repo.get("full_name")
        if not full_name:
            raise RuntimeError("Repository record missing full_name.")
        url = f"https://api.github.com/repos/{urllib.parse.quote(full_name, safe='/')}/languages"
        token = PRIVATE_REPOS_TOKEN if repo.get("private") is True else PUBLIC_TOKEN
        data = request_json(url, token)
        if not isinstance(data, dict):
            raise RuntimeError("GitHub returned an unexpected languages response.")
        totals.update({
            language: size for language, size in data.items()
            if isinstance(size, int) and not isinstance(size, bool) and size > 0
        })
    return totals


def load_font(size: int, bold: bool = False):
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


def render_gif(totals, output_path: Path):
    palette = [
        (99, 102, 241), (20, 184, 166), (245, 158, 11), (236, 72, 153),
        (139, 92, 246), (34, 197, 94), (239, 68, 68), (148, 163, 184),
    ]
    ranked = totals.most_common(7)
    remainder = sum(value for _, value in totals.most_common()[7:])
    if remainder:
        ranked.append(("Other", remainder))
    total_bytes = sum(totals.values())
    if not ranked or total_bytes <= 0:
        raise RuntimeError("Cannot render a chart without positive language totals.")

    frames = []
    width, height = 960, 420
    title_font = load_font(28, True)
    body_font = load_font(18)
    small_font = load_font(14)
    for frame in range(12):
        image = Image.new("RGB", (width, height), (15, 23, 42))
        draw = ImageDraw.Draw(image)
        draw.text((38, 28), "Programming Languages", font=title_font, fill=(248, 250, 252))
        draw.text((40, 70), "Aggregate · eligible public and authorized private repositories",
                  font=small_font, fill=(148, 163, 184))
        # A visible build-in animation fills the language bar over each loop.
        x, y, bar_width, bar_height = 40, 132, 880, 30
        progress = (frame + 1) / 12
        filled_width = max(1, round(bar_width * progress))
        draw.rounded_rectangle((x, y, x + bar_width, y + bar_height), radius=10,
                               fill=(51, 65, 85))
        cursor = x
        for index, (_, value) in enumerate(ranked):
            segment = round(filled_width * value / total_bytes)
            if index == len(ranked) - 1:
                segment = x + filled_width - cursor
            if segment > 0:
                draw.rectangle((cursor, y, cursor + segment, y + bar_height),
                               fill=palette[index % len(palette)])
                cursor += segment
        # A bright scanning marker makes the motion noticeable at profile size.
        marker_x = min(x + filled_width - 5, x + bar_width - 5)
        draw.rounded_rectangle((marker_x - 3, y - 5, marker_x + 3, y + bar_height + 5),
                               radius=3, fill=(94, 234, 212))
        for index, (name, value) in enumerate(ranked):
            row_y = 184 + index * 27
            color = palette[index % len(palette)]
            draw.ellipse((42, row_y + 4, 56, row_y + 18), fill=color)
            draw.text((68, row_y), name, font=body_font, fill=(226, 232, 240))
            draw.text((880, row_y), f"{value / total_bytes * 100:.1f}%",
                      font=body_font, fill=(226, 232, 240), anchor="ra")
        draw.text((40, 390), "Updated by GitHub Actions · repository identities are never published",
                  font=small_font, fill=(148, 163, 184))
        frames.append(image)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path, format="GIF", save_all=True, append_images=frames[1:],
        duration=140, loop=0, optimize=True, disposal=2,
    )
    with Image.open(output_path) as generated:
        if generated.format != "GIF" or getattr(generated, "n_frames", 1) < 2:
            raise RuntimeError("Generated chart is not a valid animated GIF.")


def updated_readme(current: str, totals, repo_count: int) -> str:
    if current.count(START) != 1 or current.count(END) != 1:
        raise RuntimeError("README must contain exactly one pair of stats markers.")
    start = current.index(START) + len(START)
    end = current.index(END)
    if end < start:
        raise RuntimeError("README stats markers are out of order.")

    totals = Counter(totals)
    total_bytes = sum(totals.values())
    rows = [
        "",
        f"**Eligible software repositories included:** {repo_count}",
        "",
        "| Language | Share |",
        "|---|---:|",
    ]
    for name, value in totals.most_common(10):
        rows.append(f"| {name} | {value / total_bytes * 100:.1f}% |")
    replacement = "\n" + "\n".join(rows) + "\n"
    result = current[:start] + replacement + current[end:]
    result = result.replace(
        "![Language statistics preview](assets/language-stats.svg)",
        "![Animated language statistics from eligible public repositories](assets/language-stats.gif)",
    )
    result = result.replace(
        "![Prévia das estatísticas de linguagens](assets/language-stats.svg)",
        "![Estatísticas animadas de linguagens dos repositórios públicos elegíveis](assets/language-stats.gif)",
    )
    return result


def write_temp(directory: Path, suffix: str, content: bytes) -> Path:
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".profile-stats-", suffix=suffix,
                                     delete=False) as temporary:
        temporary.write(content)
        return Path(temporary.name)


def publish_outputs(totals, repo_count: int):
    current_readme = README.read_bytes()
    new_readme = updated_readme(current_readme.decode("utf-8"), totals, repo_count).encode("utf-8")
    staged_gif = None
    staged_readme = None
    old_gif = GIF.read_bytes() if GIF.exists() else None
    try:
        staged_fd, staged_name = tempfile.mkstemp(dir=ASSETS, prefix=".language-stats-", suffix=".gif")
        os.close(staged_fd)
        staged_gif = Path(staged_name)
        render_gif(totals, staged_gif)
        # Stage and validate both artifacts before changing either tracked output.
        staged_readme = write_temp(ROOT, ".md", new_readme)
        if not staged_gif.is_file() or staged_gif.stat().st_size < 100:
            raise RuntimeError("Staged GIF failed validation.")
        os.replace(staged_gif, GIF)
        try:
            os.replace(staged_readme, README)
        except Exception:
            if old_gif is None:
                GIF.unlink(missing_ok=True)
            else:
                rollback = write_temp(ASSETS, ".gif", old_gif)
                os.replace(rollback, GIF)
            raise
    finally:
        for path in (staged_gif, staged_readme):
            if path and path.exists():
                path.unlink()


def main():
    try:
        repositories = eligible_repositories()
        totals = language_totals(repositories)
        if not repositories or not totals:
            raise RuntimeError("No eligible repositories or language data; preserving previous outputs.")
        publish_outputs(totals, len(repositories))
        print(f"Updated aggregate language stats for {len(repositories)} eligible public repositories.")
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
