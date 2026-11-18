"""Create draft _publications entries for papers on Semantic Scholar that the site does not list yet.

Usage: python .github/scripts/fetch_publications.py [--dry-run]
"""
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

AUTHOR_ID = "2037781514"  # https://www.semanticscholar.org/author/Hyeontaek-Hwang/2037781514
API = (f"https://api.semanticscholar.org/graph/v1/author/{AUTHOR_ID}/papers"
       "?fields=title,year,venue,publicationDate,externalIds,authors&limit=1000")
ROOT = pathlib.Path(__file__).resolve().parents[2]
PUB_DIR = ROOT / "_publications"
# One Semantic Scholar paperId per line; papers listed here are never added (e.g. misattributed ones).
IGNORE_FILE = ROOT / ".github" / "publications-ignore.txt"


def fetch():
    for attempt in range(5):
        try:
            with urllib.request.urlopen(API, timeout=30) as r:
                return json.load(r)["data"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(30 * (attempt + 1))  # shared rate limit without an API key


def norm_title(t):
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)  # drop venue suffix like "(WACV 2027)"
    return re.sub(r"[^a-z0-9]", "", t.lower())


def existing():
    text, titles = "", set()
    for f in PUB_DIR.rglob("*.md"):
        s = f.read_text(encoding="utf-8")
        text += s.lower()
        m = re.search(r'^title:\s*"(.*)"', s, re.M)
        if m:
            titles.add(norm_title(m.group(1)))
    return text, titles


def is_listed(p, text, titles):
    ids = p.get("externalIds") or {}
    for key in ("ArXiv", "DOI"):
        if ids.get(key) and ids[key].lower() in text:
            return True
    return norm_title(p["title"]) in titles


def entry(p):
    ids = p.get("externalIds") or {}
    year = p.get("year") or int((p.get("publicationDate") or "1970")[:4])
    date = p.get("publicationDate") or f"{year}-01-01"
    arxiv = ids.get("ArXiv")
    venue = p.get("venue") or ""
    if not venue or venue == "arXiv.org":
        venue = f"arXiv preprint arXiv:{arxiv}" if arxiv else "TODO: venue"
    link = f"https://arxiv.org/abs/{arxiv}" if arxiv else (f"https://doi.org/{ids['DOI']}" if ids.get("DOI") else None)
    title = p["title"].replace('"', '\\"')
    lines = [
        "---",
        f'title:          "{title}"',
        f"date:           {date} 00:01:00 +0900  # auto-added from Semantic Scholar; check date and venue",
        "selected:       false",
        f'pub:            "{venue}"',
        f'pub_date:       "{year}"',
        "authors:",
        *[f"- {a['name']}" for a in p["authors"]],
    ]
    if link:
        lines += ["links:", f"  Paper: {link}"]
    lines.append("---")
    slug = "-".join(re.findall(r"[a-z0-9]+", p["title"].lower())[:4])
    return PUB_DIR / str(year) / f"{year}-{slug}.md", "\n".join(lines) + "\n"


def main():
    dry = "--dry-run" in sys.argv
    ignore = set(IGNORE_FILE.read_text().split()) if IGNORE_FILE.exists() else set()
    text, titles = existing()
    new = [p for p in fetch() if p["paperId"] not in ignore and not is_listed(p, text, titles)]
    for p in new:
        path, body = entry(p)
        print(f"NEW: {path.relative_to(ROOT)}  (paperId {p['paperId']})")
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
    if not new:
        print("No new papers.")


if __name__ == "__main__":
    main()
