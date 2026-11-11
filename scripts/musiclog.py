"""daily-musiclog: one YouTube link a day, kept as a small dataset.

The CSV file data/daily_tracks.csv is the only source of truth. Everything else (data/daily_tracks.jsonl,
docs/archive.md, docs/stats.md, docs/calendar.svg, the "current selection" block of README.md and of the GitHub
profile README) is generated
from it, so it can always be rebuilt with `render`.

Usage, from the repository root:

    python3 scripts/musiclog.py add "https://www.youtube.com/watch?v=..."   # add today's track, render, push
    python3 scripts/musiclog.py add URL --date 2026-10-11 --title "..."      # other date, or own title
    python3 scripts/musiclog.py add URL --no-push                            # only write files
    python3 scripts/musiclog.py render                                       # rebuild generated files
    python3 scripts/musiclog.py check                                        # validate the dataset
    python3 scripts/musiclog.py backfill                                     # fetch missing channel names
    python3 scripts/musiclog.py set 2026-10-11 --artist "..." --work "..."   # correct the artist or work of an entry
    python3 scripts/musiclog.py links                                        # ask YouTube whether every video still exists

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
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "daily_tracks.csv"
JSONL_PATH = ROOT / "data" / "daily_tracks.jsonl"
ARCHIVE_PATH = ROOT / "docs" / "archive.md"
STATS_PATH = ROOT / "docs" / "stats.md"
CALENDAR_PATH = ROOT / "docs" / "calendar.svg"
README_PATH = ROOT / "README.md"
PROFILE_REPO = Path(os.environ.get("MUSICLOG_PROFILE_REPO", Path.home() / "Desktop" / "mikbalyilmaz"))

FIELDS = ["date", "video_id", "title", "artist", "work", "channel", "url"]
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


# ------------------------------------------------------------------------------------------ artist, work
NOISE_RE = re.compile(r"official|video|audio|\bhd\b|\bhq\b|\b4k\b|lyric|remaster|upscaled|high quality|rəsmi", re.I)
SEPARATORS = (" - ", " – ", " — ", ": ", " : ", " | ")


def clean_title(title):
    """Title without a file extension and without bracketed remarks such as (Official Video) or [HD]."""
    title = re.sub(r"\.(wmv|mp4|avi|mov|flv)$", "", title.strip(), flags=re.I)
    title = re.sub(r"\s*[\(\[]([^\)\]]*)[\)\]]", lambda g: "" if NOISE_RE.search(g.group(1)) else g.group(0), title)
    return re.sub(r"\s{2,}", " ", title).strip(" -–—|")


def split_title(title, channel=""):
    """A first guess of (artist, work) from a YouTube title of the form "Artist - Work".

    It is only a suggestion: titles of the form "Work - Artist" come out reversed, and many titles name no artist.
    For an auto-generated "<Artist> - Topic" channel the artist is taken from the channel. Correct with `set`.
    """
    text = clean_title(title)
    topic = channel[:-len(" - Topic")].strip() if channel.endswith(" - Topic") else ""
    cuts = [(text.find(s), s) for s in SEPARATORS if s in text]
    if not cuts:
        return topic, text
    at, sep = min(cuts)
    artist, work = text[:at].strip(), text[at + len(sep):].strip()
    if topic and artist.casefold() != topic.casefold():
        return topic, text
    return artist, work


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


def day_counts(rows):
    return Counter(r["date"] for r in rows)


def longest_run(days):
    """(length, first day, last day) of the longest run of consecutive days with an entry."""
    best = (0, None, None)
    start = prev = None
    for d in sorted(date.fromisoformat(x) for x in days):
        if prev is None or d - prev != timedelta(days=1):
            start = d
        prev = d
        if (d - start).days + 1 > best[0]:
            best = ((d - start).days + 1, start, d)
    return best


def md_table(head, body):
    return ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] + ["---:"] * (len(head) - 1)) + "|"] + \
           ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in body]


def stats_page(rows):
    counts = day_counts(rows)
    days = sorted(counts)
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    span = (last - first).days + 1
    run, run_a, run_b = longest_run(days)
    L = ["# Statistics", "", "Generated from `data/daily_tracks.csv`.", "", stats_block(rows), "",
         f"- Days without an entry: {span - len(days)} of {span}.",
         f"- Longest run of consecutive days with an entry: {run} ({run_a} to {run_b}).",
         f"- Days with more than one entry: {sum(1 for c in counts.values() if c > 1)}.", "",
         "![Entries per day](calendar.svg)", "", "## By month", ""]
    months = sorted({d[:7] for d in days})
    L += md_table(["Month", "Entries", "Days with an entry"],
                  [[m, sum(c for d, c in counts.items() if d[:7] == m), sum(1 for d in days if d[:7] == m)] for m in months])
    named = [r for r in rows if r["artist"]]
    by_artist = Counter(r["artist"] for r in named)
    L += ["", "## Artists with two or more entries", "",
          f"The artist is the name given in the title of the video or by its channel (composer or performer); {len(rows) - len(named)} of "
          f"{len(rows)} entries name none. {len(by_artist)} different names.", ""]
    L += md_table(["Artist", "Entries"], [[a, c] for a, c in sorted(by_artist.items(), key=lambda x: (-x[1], x[0].casefold())) if c > 1])
    by_channel = Counter(r["channel"] for r in rows if r["channel"])
    L += ["", "## Channels with two or more entries", ""]
    L += md_table(["Channel", "Entries"], [[a, c] for a, c in sorted(by_channel.items(), key=lambda x: (-x[1], x[0].casefold())) if c > 1])
    seen = {}
    for r in rows:
        seen.setdefault(r["video_id"], []).append(r)
    twice = [v for v in seen.values() if len(v) > 1]
    L += ["", "## Videos entered more than once", ""]
    L += [f"- [{md_escape(v[0]['title'])}]({v[0]['url']}): " + ", ".join(r["date"] for r in v) for v in twice] or ["None."]
    return "\n".join(L) + "\n"


def calendar_svg(rows):
    """Entries per day as a grid of weeks (columns, Monday first) from the first to the last entry."""
    counts = day_counts(rows)
    first, last = date.fromisoformat(min(counts)), date.fromisoformat(max(counts))
    start = first - timedelta(days=first.weekday())
    weeks = (last - start).days // 7 + 1
    cell, gap, left, top = 11, 2, 26, 16
    colour = lambda n: ("#ebedf0", "#9bb3e0", "#4d73c4", "#0033a0")[min(n, 3)]      # noqa: E731
    width, height = left + weeks * (cell + gap) + 2, top + 7 * (cell + gap) + 22
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           f'role="img" aria-label="Entries per day, {first} to {last}">',
           '<style>text{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:9px;fill:#57606a}</style>']
    for row, name in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
        out.append(f'<text x="0" y="{top + row * (cell + gap) + 9}">{name}</text>')
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    for w in range(weeks):
        monday = start + timedelta(days=7 * w)
        month_start = next((monday + timedelta(days=i) for i in range(7) if (monday + timedelta(days=i)).day == 1), None)
        if month_start and first <= month_start <= last or w == 0:
            label = names[(month_start or first).month - 1]
            out.append(f'<text x="{left + w * (cell + gap)}" y="10">{label}</text>')
        for i in range(7):
            d = monday + timedelta(days=i)
            if first <= d <= last:
                out.append(f'<rect x="{left + w * (cell + gap)}" y="{top + i * (cell + gap)}" width="{cell}" height="{cell}" '
                           f'rx="2" fill="{colour(counts.get(d.isoformat(), 0))}"/>')
    y = top + 7 * (cell + gap) + 6
    out.append(f'<text x="{left}" y="{y + 9}">Entries per day:</text>')
    for k, name in enumerate(("0", "1", "2", "3+")):
        x = left + 78 + k * 34
        out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{colour(k)}"/>'
                   f'<text x="{x + cell + 3}" y="{y + 9}">{name}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


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
    if rows:
        write(STATS_PATH, stats_page(rows))
        write(CALENDAR_PATH, calendar_svg(rows))

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
GENERATED = [CSV_PATH, JSONL_PATH, ARCHIVE_PATH, STATS_PATH, CALENDAR_PATH, README_PATH]


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
    earlier = sorted({r["date"] for r in rows if r["video_id"] == video_id})
    if earlier:
        print(f"Note: this video was already entered on {', '.join(earlier)}; added again for {day}.")
    guess_artist, guess_work = split_title(title, channel)
    artist = guess_artist if args.artist is None else args.artist.strip()
    work = guess_work if args.work is None else args.work.strip()
    row = {"date": day, "video_id": video_id, "title": title, "artist": artist, "work": work, "channel": channel,
           "url": canonical_url(video_id)}
    rows = write_rows(rows + [row])
    found = problems(rows)
    if found:
        sys.exit("Dataset check failed:\n  " + "\n  ".join(found))
    render(rows)
    print(f"Added {day}: {title}" + (f" ({channel})" if channel else ""))
    print(f"  artist: {artist or '(none)'} | work: {work or '(none)'}")
    if args.artist is None or args.work is None:
        print(f'  read from the title; to correct: python3 scripts/musiclog.py set {day} --artist "..." --work "..."')

    latest = rows[-1]
    profile_changed = update_profile(latest)
    if args.no_push:
        print("Files written; nothing committed (--no-push).")
        return
    commit_and_push(ROOT, GENERATED, f"Add track {day}: {title}")
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


def cmd_set(args):
    """Correct the artist, work or title of an entry: the last entry of the day, or the one with --video."""
    rows = read_rows()
    hits = [r for r in rows if r["date"] == args.date and (args.video is None or r["video_id"] == args.video)]
    if not hits:
        sys.exit(f"No entry on {args.date}" + (f" with video id {args.video}." if args.video else "."))
    if args.artist is None and args.work is None and args.title is None:
        sys.exit("Nothing to change: give --artist, --work or --title.")
    row = hits[-1]
    for key in ("artist", "work", "title"):
        value = getattr(args, key)
        if value is not None:
            row[key] = value.strip()
    rows = write_rows(rows)
    found = problems(rows)
    if found:
        sys.exit("Dataset check failed:\n  " + "\n  ".join(found))
    render(rows)
    print(f"{row['date']} {row['video_id']}: artist: {row['artist'] or '(none)'} | work: {row['work'] or '(none)'}")
    profile_changed = update_profile(rows[-1])
    if args.no_push:
        print("Files written; nothing committed (--no-push).")
        return
    commit_and_push(ROOT, GENERATED, f"Correct entry {row['date']}: {row['title']}")
    if profile_changed:
        commit_and_push(PROFILE_REPO, [PROFILE_REPO / "README.md"], f"Music log: {rows[-1]['title']}")


def link_status(video_id):
    """'ok', 'not found' (HTTP 400 or 404), 'refused' (HTTP 401 or 403) or 'unknown', from the oEmbed endpoint."""
    try:
        fetch_metadata(video_id)
        return "ok"
    except urllib.error.HTTPError as error:
        return "not found" if error.code in (400, 404) else "refused" if error.code in (401, 403) else "unknown"
    except Exception:
        return "unknown"


def cmd_links(args):
    """Ask YouTube's oEmbed endpoint about every video. Exit status 1 if a video is not found."""
    rows = read_rows()
    first = {}
    for r in rows:
        first.setdefault(r["video_id"], r)
    result = Counter()
    for video_id, r in first.items():
        status = link_status(video_id)
        result[status] += 1
        if status != "ok":
            print(f"{status}: {r['date']} {r['url']} {r['title']}")
        time.sleep(args.pause)
    print(f"{len(first)} videos: " + ", ".join(f"{n} {s}" for s, n in sorted(result.items())) + ".")
    print("not found: YouTube has no such video (deleted). refused: the video is private or does not allow embedding; "
          "open the link to see which. unknown: no answer (network, rate limit); run again.")
    sys.exit(1 if result["not found"] else 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="One YouTube link a day, kept as a small dataset.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add", help="add a track (today by default), render the files, commit and push")
    p.add_argument("url")
    p.add_argument("--date", help="YYYY-MM-DD; default: today")
    p.add_argument("--title", help="use this title instead of the YouTube title")
    p.add_argument("--artist", help="artist (default: read from the title)")
    p.add_argument("--work", help="name of the piece (default: read from the title)")
    p.add_argument("--no-push", action="store_true", help="write the files but do not commit or push")
    p.set_defaults(func=cmd_add)
    sub.add_parser("render", help="rebuild the generated files from the CSV").set_defaults(func=cmd_render)
    sub.add_parser("check", help="validate the dataset").set_defaults(func=cmd_check)
    sub.add_parser("backfill", help="fetch missing channel names").set_defaults(func=cmd_backfill)
    p = sub.add_parser("set", help="correct the artist, work or title of an entry")
    p.add_argument("date", help="YYYY-MM-DD")
    p.add_argument("--video", help="video id, if the day has more than one entry (default: the last one)")
    p.add_argument("--artist")
    p.add_argument("--work")
    p.add_argument("--title")
    p.add_argument("--no-push", action="store_true", help="write the files but do not commit or push")
    p.set_defaults(func=cmd_set)
    p = sub.add_parser("links", help="ask YouTube whether every video still exists")
    p.add_argument("--pause", type=float, default=0.3, help="seconds between two requests (default 0.3)")
    p.set_defaults(func=cmd_links)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
