import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))


import argparse
from datetime import date
from pathlib import Path
import pandas as pd

from scripts.utils import extract_video_id, make_thumbnail
from scripts.update_readme import update_readme

DATA = Path("data")
DOCS = Path("docs")

csv_path = DATA / "daily_tracks.csv"
jsonl_path = DATA / "daily_tracks.jsonl"
archive_path = DOCS / "archive.md"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--title", required=True)
    p.add_argument("--url", required=True)
    args = p.parse_args()

    today = date.today().isoformat()
    title = args.title
    url = args.url

    video_id = extract_video_id(url)

    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=["date","title","url","video_id"])

    df = df[df["date"] != today]
    df = pd.concat([df, pd.DataFrame([{
        "date": today,
        "title": title,
        "url": url,
        "video_id": video_id
    }])])

    df.to_csv(csv_path, index=False)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for _, r in df.iterrows():
            f.write(pd.Series(r).to_json(force_ascii=False) + "\n")

    thumb = make_thumbnail(video_id)
    update_readme(title, url, thumb)

    if not archive_path.exists():
        archive_path.write_text("# Archive\n\n")

    line = f"- **{today}** — [{title}]({url})\n"
    content = archive_path.read_text(encoding="utf-8")
    if line not in content:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(line)

    print("OK. Everything updated.")

if __name__ == "__main__":
    main()
import argparse
from datetime import date
from pathlib import Path
import pandas as pd

from scripts.utils import extract_video_id, make_thumbnail
from scripts.update_readme import update_readme

DATA = Path("data")
DOCS = Path("docs")

csv_path = DATA / "daily_tracks.csv"
jsonl_path = DATA / "daily_tracks.jsonl"
archive_path = DOCS / "archive.md"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--title", required=True)
    p.add_argument("--url", required=True)
    args = p.parse_args()

    today = date.today().isoformat()
    title = args.title
    url = args.url

    video_id = extract_video_id(url)

    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=["date","title","url","video_id"])

    df = df[df["date"] != today]
    df = pd.concat([df, pd.DataFrame([{
        "date": today,
        "title": title,
        "url": url,
        "video_id": video_id
    }])])

    df.to_csv(csv_path, index=False)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for _, r in df.iterrows():
            f.write(pd.Series(r).to_json(force_ascii=False) + "\n")

    thumb = make_thumbnail(video_id)
    update_readme(title, url, thumb)

    if not archive_path.exists():
        archive_path.write_text("# Archive\n\n")

    line = f"- **{today}** — [{title}]({url})\n"
    content = archive_path.read_text(encoding="utf-8")
    if line not in content:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(line)

    print("OK. Everything updated.")

if __name__ == "__main__":
    main()

