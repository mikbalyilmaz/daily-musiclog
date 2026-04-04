import sys
from pathlib import Path

# Python'un klasörleri doğru bulması için:
sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse
import subprocess
from datetime import date
import pandas as pd
from scripts.utils import extract_video_id, make_thumbnail, get_video_title
from scripts.update_readme import update_readme

DATA = Path("data")
DOCS = Path("docs")
csv_path = DATA / "daily_tracks.csv"
jsonl_path = DATA / "daily_tracks.jsonl"
archive_path = DOCS / "archive.md"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    args = p.parse_args()

    today = date.today().isoformat()
    url = args.url
    video_id = extract_video_id(url)
    
    # Başlığı YouTube API üzerinden alıyoruz
    title = get_video_title(video_id)

    # Veri setini güncelleme
    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=["date","title","url","video_id"])

    df = df[df["date"] != today]
    df = pd.concat([df, pd.DataFrame([{"date": today, "title": title, "url": url, "video_id": video_id}])])
    df.to_csv(csv_path, index=False)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for _, r in df.iterrows():
            f.write(pd.Series(r).to_json(force_ascii=False) + "\n")

    # README güncelleme
    thumb = make_thumbnail(video_id)
    update_readme(title, url, thumb)

    # Arşiv güncelleme (HATA DÜZELTİLDİ)
    line = f"- **{today}** — [{title}]({url})\n"
    
    if not archive_path.exists(): archive_path.write_text("# Archive\n\n")
    content = archive_path.read_text(encoding="utf-8")
    if line not in content:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(line)

    # Otomatik GitHub Push
    print(f"🚀 GitHub'a yükleniyor: {title}")
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Add track: {title}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Her şey başarıyla güncellendi!")
    except Exception as e:
        print(f"❌ Git hatası (veya gönderilecek yeni bir şey yok): {e}")

if __name__ == "__main__":
    main()