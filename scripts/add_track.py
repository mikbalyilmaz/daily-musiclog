import sys
from pathlib import Path
import re
import argparse
import subprocess
from datetime import date
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts.utils import extract_video_id, make_thumbnail, get_video_title
from scripts.update_readme import update_readme

DATA = Path("data")
DOCS = Path("docs")
csv_path = DATA / "daily_tracks.csv"
jsonl_path = DATA / "daily_tracks.jsonl"
archive_path = DOCS / "archive.md"

PROFILE_REPO = Path.home() / "Desktop" / "mikbalyilmaz"

def update_profile_readme(title, url, thumb):
    profile_readme = PROFILE_REPO / "README.md"
    if not profile_readme.exists():
        return False

    content = profile_readme.read_text(encoding="utf-8")
    new_block = f"""### Chosen from the list today;

<a href="{url}" target="_blank" rel="noopener noreferrer">
<img src="{thumb}" width="320" alt="{title}"/>
</a>
<br/>
🎵
<a href="{url}" target="_blank" rel="noopener noreferrer">
<b>{title}</b>
</a>"""

    pattern = r"### Chosen from the list today;[\s\S]*?(?=\n# Muhammed İkbal Yılmaz|\Z)"
    if re.search(pattern, content):
        updated_content = re.sub(pattern, new_block + "\n\n", content, count=1)
        if updated_content != content:
            profile_readme.write_text(updated_content, encoding="utf-8")
            print("✅ Profil README güncellendi!")
            return True
    return False

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    args = p.parse_args()

    today = date.today().isoformat()
    url = args.url
    video_id = extract_video_id(url)
    title = get_video_title(video_id)

    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=["date","title","url","video_id"])

    new_row = pd.DataFrame([{"date": today, "title": title, "url": url, "video_id": video_id}])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(csv_path, index=False)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for _, r in df.iterrows():
            f.write(pd.Series(r).to_json(force_ascii=False) + "\n")

    thumb = make_thumbnail(video_id)
    update_readme(title, url, thumb)

    line = f"- **{today}** — [{title}]({url})\n"
    if not archive_path.exists(): 
        archive_path.write_text("# Archive\n\n")
    content = archive_path.read_text(encoding="utf-8")
    if line not in content:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(line)

    print(f"🚀 daily-musiclog güncelleniyor: {title}")
    try:
        subprocess.run(["git", "add", "."], check=True)
        res = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if res.returncode != 0:
            subprocess.run(["git", "commit", "-m", f"Add track: {title}"], check=True)
            subprocess.run(["git", "pull", "--rebase"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ daily-musiclog başarıyla yüklendi!")
        else:
            print("ℹ️ daily-musiclog için yeni bir değişiklik yok.")
    except Exception as e:
        print(f"❌ daily-musiclog Git hatası: {e}")

    if PROFILE_REPO.exists():
        changed = update_profile_readme(title, url, thumb)
        if changed:
            print("🚀 Profil reposu güncelleniyor...")
            try:
                subprocess.run(["git", "-C", str(PROFILE_REPO), "add", "."], check=True)
                subprocess.run(["git", "-C", str(PROFILE_REPO), "commit", "-m", f"Update daily track: {title}"], check=True)
                subprocess.run(["git", "-C", str(PROFILE_REPO), "pull", "--rebase"], check=True)
                subprocess.run(["git", "-C", str(PROFILE_REPO), "push"], check=True)
                print("✅ Profil sayfası başarıyla güncellendi!")
            except Exception as e:
                print(f"❌ Profil Git hatası: {e}")
        else:
            print("ℹ️ Profil sayfasında bu şarkı zaten seçili.")

if __name__ == "__main__":
    main()
