"""daily-musiclog: one YouTube link a day, kept as a small dataset.

The CSV file data/daily_tracks.csv is the only source of truth. Everything else (data/daily_tracks.jsonl,
docs/archive.md, the "current selection" block of README.md and of the GitHub profile README) is generated
from it, so it can always be rebuilt with `render`.

Usage, from the repository root:

    python3 scripts/musiclog.py add "https://www.youtube.com/watch?v=..."   # add today's track, render, push
    python3 scripts/musiclog.py add URL --date 2026-10-11 --title "..."      # other date, or own title
    python3 scripts/musiclog.py add URL --no-push                            # only write files
    python3 scripts/musiclog.py render                                       # rebuild generated files
    python3 scripts/musiclog.py check                                        # validate the dataset
    python3 scripts/musiclog.py backfill                                     # fetch missing channel names

Titles and channel names come from YouTube's public oEmbed endpoint, which needs no API key.
Only the Python standard library is used.

Author: Muhammed Ikbal Yilmaz
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "daily_tracks.csv"
JSONL_PATH = ROOT / "data" / "daily_tracks.jsonl"
ARCHIVE_PATH = ROOT / "docs" / "archive.md"
README_PATH = ROOT / "README.md"
PROFILE_REPO = Path(os.environ.get("MUSICLOG_PROFILE_REPO", Path.home() / "Desktop" / "mikbalyilmaz"))

FIELDS = ["date", "video_id", "title", "channel", "url"]
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
README_MARKERS = ("<!-- CHOSEN_TODAY:START -->", "<!-- CHOSEN_TODAY:END -->")
STATS_MARKERS = ("<!-- STATS:START -->", "<!-- STATS:END -->")
PROFILE_MARKERS = ("<!-- MUSICLOG:START -->", "<!-- MUSICLOG:END -->")


# ------------------------------------------------------------------------------------------------ links
def extract_video_id(url):
    """Video id from a youtube.com/watch, youtu.be, /shorts/, /embed/ or /live/ link; None if there is none.

    Backslashes that a shell adds when a link is pasted (watch\\?v\\=...) are removed first.
    """
    url = url.strip().replace("\\", "")
    if ID_RE.match(url):
        return url
    parts = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("music.")
    candidate = None
    if host == "youtu.be":
        candidate = parts.path.strip("/").split("/")[0]
    elif host == "youtube.com":
        query = urllib.parse.parse_qs(parts.query)
        if "v" in query:
            candidate = query["v"][0]
        else:
            segments = [s for s in parts.path.split("/") if s]
            if len(segments) >= 2 and segments[0] in ("shorts", "embed", "live", "v"):
                candidate = segments[1]
    return candidate if candidate and ID_RE.match(candidate) else None


def canonical_url(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def thumbnail(video_id, size="hqdefault"):
    # hqdefault exists for every video; maxresdefault does not.
    return f"https://img.youtube.com/vi/{video_id}/{size}.jpg"


def fetch_metadata(video_id):
    """(title, channel) from YouTube's oEmbed endpoint."""
    query = urllib.parse.urlencode({"url": canonical_url(video_id), "format": "json"})
    with urllib.request.urlopen(f"https://www.youtube.com/oembed?{query}", timeout=15) as response:
        data = json.load(response)
    return data["title"].strip(), data.get("author_name", "").strip()


# ---------------------------------------------------------------------------------------------- dataset
def read_rows(path=None):
    path = path or CSV_PATH
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (row.get(k) or "").strip() for k in FIELDS} for row in csv.DictReader(f)]


def write_rows(rows, path=None):
    path = path or CSV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r["date"])  # stable: entries of one day keep their order
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def problems(rows):
    """List of human-readable problems in the dataset; empty if it is valid."""
    found, seen = [], set()
    for i, r in enumerate(rows, start=2):  # line 1 is the header
        if not DATE_RE.match(r["date"]):
            found.append(f"line {i}: date {r['date']!r} is not YYYY-MM-DD")
        else:
            try:
                date.fromisoformat(r["date"])
            except ValueError:
                found.append(f"line {i}: {r['date']} is not a calendar date")
        if not ID_RE.match(r["video_id"]):
            found.append(f"line {i}: video id {r['video_id']!r} is not 11 characters of [A-Za-z0-9_-]")
        elif r["url"] != canonical_url(r["video_id"]):
            found.append(f"line {i}: url is not {canonical_url(r['video_id'])}")
        if not r["title"]:
            found.append(f"line {i}: empty title")
        if (r["date"], r["video_id"]) in seen:
            found.append(f"line {i}: {r['video_id']} is already listed on {r['date']}")
        seen.add((r["date"], r["video_id"]))
    if [r["date"] for r in rows] != sorted(r["date"] for r in rows):
        found.append("rows are not in date order")
    return found


# --------------------------------------------------------------------------------------- generated files
def replace_between(text, markers, block):
    start, end = markers
    if start not in text or end not in text:
        raise ValueError(f"markers {start} ... {end} not found")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return f"{before}{start}\n{block.strip()}\n{end}{after}"


def md_escape(text):
    return text.replace("[", "\\[").replace("]", "\\]")


def current_block(row, width=320, size="hqdefault"):
    channel = f" · {row['channel']}" if row["channel"] else ""
    return (f'<a href="{row["url"]}">\n  <img src="{thumbnail(row["video_id"], size)}" width="{width}" '
            f'alt="{row["title"].replace(chr(34), "&quot;")}">\n</a>\n\n'
            f"**{row['date']}**: [{md_escape(row['title'])}]({row['url']}){channel}")


def stats_block(rows):
    days = sorted({r["date"] for r in rows})
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    span = (last - first).days + 1
    return (f"{len(rows)} entries on {len(days)} days between {days[0]} and {days[-1]} "
            f"({span} calendar days); {len({r['video_id'] for r in rows})} distinct videos.")


def render(rows):
    """Rewrite every generated file from the rows. Returns the list of files that changed."""
    changed = []

    def write(path, text):
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            changed.append(path)

    write(JSONL_PATH, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    lines = ["# Archive", "", "Generated from `data/daily_tracks.csv`; newest first.", ""]
    for r in reversed(rows):
        channel = f" · {r['channel']}" if r["channel"] else ""
        lines.append(f"- **{r['date']}**: [{md_escape(r['title'])}]({r['url']}){channel}")
    write(ARCHIVE_PATH, "\n".join(lines) + "\n")

    if rows and README_PATH.exists():
        text = README_PATH.read_text(encoding="utf-8")
        text = replace_between(text, README_MARKERS, current_block(rows[-1]))
        text = replace_between(text, STATS_MARKERS, stats_block(rows))
        write(README_PATH, text)
    return changed


def update_profile(row):
    """Update the music block of the profile README, if that repository is present. Returns True if changed."""
    path = PROFILE_REPO / "README.md"
    if not path.exists():
        print(f"Profile repository not found at {PROFILE_REPO}; skipped.")
        return False
    text = path.read_text(encoding="utf-8")
    if PROFILE_MARKERS[0] not in text:
        print(f"No {PROFILE_MARKERS[0]} marker in {path}; skipped.")
        return False
    new = replace_between(text, PROFILE_MARKERS, current_block(row, width=200, size="mqdefault"))
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


# ------------------------------------------------------------------------------------------------- git
def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True)


def commit_and_push(repo, paths, message):
    git(repo, "add", "--", *[str(p) for p in paths])
    staged = subprocess.run(["git", "-C", str(repo), "diff", "--staged", "--quiet"])
    if staged.returncode == 0:
        print(f"{repo.name}: nothing to commit.")
        return
    git(repo, "commit", "-m", message)
    git(repo, "pull", "--rebase")
    git(repo, "push")
    print(f"{repo.name}: pushed.")


# ---------------------------------------------------------------------------------------------- commands
def cmd_add(args):
    video_id = extract_video_id(args.url)
    if video_id is None:
        sys.exit(f"Not a YouTube video link: {args.url}")
    day = args.date or date.today().isoformat()
    if not DATE_RE.match(day):
        sys.exit("--date must be YYYY-MM-DD")
    rows = read_rows()
    if any(r["date"] == day and r["video_id"] == video_id for r in rows):
        sys.exit(f"{video_id} is already listed on {day}.")
    title, channel = args.title, ""
    try:
        fetched_title, channel = fetch_metadata(video_id)
        title = title or fetched_title
    except Exception as error:  # no network, private video, ...
        if not title:
            sys.exit(f"Could not fetch the title ({error}); pass it with --title.")
        print(f"Could not fetch the channel name ({error}); left empty.")
    row = {"date": day, "video_id": video_id, "title": title, "channel": channel, "url": canonical_url(video_id)}
    rows = write_rows(rows + [row])
    found = problems(rows)
    if found:
        sys.exit("Dataset check failed:\n  " + "\n  ".join(found))
    render(rows)
    print(f"Added {day}: {title}" + (f" ({channel})" if channel else ""))

    latest = rows[-1]
    profile_changed = update_profile(latest)
    if args.no_push:
        print("Files written; nothing committed (--no-push).")
        return
    commit_and_push(ROOT, [CSV_PATH, JSONL_PATH, ARCHIVE_PATH, README_PATH], f"Add track {day}: {title}")
    if profile_changed:
        commit_and_push(PROFILE_REPO, [PROFILE_REPO / "README.md"], f"Music log: {latest['title']}")


def cmd_render(_):
    rows = read_rows()
    changed = render(rows)
    print("Changed: " + (", ".join(str(p.relative_to(ROOT)) for p in changed) if changed else "nothing"))


def cmd_check(_):
    rows = read_rows()
    found = problems(rows)
    for line in found:
        print(line)
    print(f"{len(rows)} rows, {len(found)} problem(s).")
    sys.exit(1 if found else 0)


def cmd_backfill(_):
    rows = read_rows()
    missing = [r for r in rows if not r["channel"]]
    for r in missing:
        try:
            _, r["channel"] = fetch_metadata(r["video_id"])
            print(f"{r['date']} {r['video_id']}: {r['channel']}")
        except Exception as error:
            print(f"{r['date']} {r['video_id']}: not available ({error})")
    write_rows(rows)
    render(rows)
    print(f"Filled {sum(1 for r in missing if r['channel'])} of {len(missing)} missing channel names.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="One YouTube link a day, kept as a small dataset.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add", help="add a track (today by default), render the files, commit and push")
    p.add_argument("url")
    p.add_argument("--date", help="YYYY-MM-DD; default: today")
    p.add_argument("--title", help="use this title instead of the YouTube title")
    p.add_argument("--no-push", action="store_true", help="write the files but do not commit or push")
    p.set_defaults(func=cmd_add)
    sub.add_parser("render", help="rebuild the generated files from the CSV").set_defaults(func=cmd_render)
    sub.add_parser("check", help="validate the dataset").set_defaults(func=cmd_check)
    sub.add_parser("backfill", help="fetch missing channel names").set_defaults(func=cmd_backfill)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
