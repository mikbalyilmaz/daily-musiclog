# daily-musiclog

One piece of music a day, kept as a small dataset. Each entry is a YouTube video with its date, title and channel;
the newest entry is shown below and on my [GitHub profile](https://github.com/mikbalyilmaz).

## Latest entry

<!-- CHOSEN_TODAY:START -->
<a href="https://www.youtube.com/watch?v=a-u-HmJqYIg">
  <img src="https://img.youtube.com/vi/a-u-HmJqYIg/hqdefault.jpg" width="320" alt="1) Neyzen Niyazi Sayın & Tanbûri Necdet Yaşar">
</a>

**2026-10-10**: [1) Neyzen Niyazi Sayın & Tanbûri Necdet Yaşar](https://www.youtube.com/watch?v=a-u-HmJqYIg)
<!-- CHOSEN_TODAY:END -->

<!-- STATS:START -->
62 entries on 56 days between 2026-01-29 and 2026-10-10 (255 calendar days); 60 distinct videos.
<!-- STATS:END -->
Full list, newest first: [docs/archive.md](docs/archive.md).

## The dataset

`data/daily_tracks.csv` is the only file edited by hand or by the script; everything else is generated from it.

| Column | Content |
|---|---|
| `date` | Day of the entry, `YYYY-MM-DD`. A day can have more than one entry. |
| `video_id` | YouTube video id (11 characters) |
| `title` | Title of the video on YouTube, unless a different one was given |
| `channel` | Name of the YouTube channel; empty for entries whose channel has not been fetched yet |
| `url` | `https://www.youtube.com/watch?v=<video_id>` |

`data/daily_tracks.jsonl` holds the same rows as JSON lines. The selections range from Turkish makam music
(Dede Efendi, Bekir Sıtkı Sezgin, Niyazi Sayın) to twentieth-century and contemporary composers (Penderecki,
Messiaen, Ligeti, Górecki, Pärt), jazz and world music (Anouar Brahem, Rabih Abou-Khalil, Dhafer Youssef) and
popular songs.

## Adding a track

From the repository root (Python 3.9 or newer; no packages to install):

```bash
python3 scripts/musiclog.py add "https://www.youtube.com/watch?v=..."
```

The script takes the video id from the link (any YouTube link form works, also one pasted with backslashes),
fetches the title and channel from YouTube's public oEmbed endpoint (no API key), appends the row, rebuilds the
generated files, updates the music block of the profile README if that repository is in `~/Desktop/mikbalyilmaz`,
and commits and pushes both repositories.

| Option | Effect |
|---|---|
| `--date 2026-10-11` | Entry for another day |
| `--title "..."` | Use this title instead of the YouTube title |
| `--no-push` | Write the files, do not commit or push |

Other commands: `render` rebuilds the generated files from the CSV, `check` validates the dataset (date format and
order, video ids, links, duplicates), `backfill` fetches missing channel names. The `check` also runs on GitHub
Actions at every push.
