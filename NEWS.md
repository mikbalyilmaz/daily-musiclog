# Changes

## 2026-10-11

- One script, `scripts/musiclog.py`, replaces `add_track.py`, `update_readme.py` and `utils.py`. It uses only the
  Python standard library; `requirements.txt` and the virtual environment are no longer needed.
- Titles and channel names come from YouTube's public oEmbed endpoint. The YouTube Data API and its key are no
  longer used.
- The CSV is the only source of truth; `daily_tracks.jsonl`, `docs/archive.md` and the README block are generated
  from it (`render`). New commands: `check` (validation, also run on GitHub Actions) and `backfill`.
- New column `channel`; columns are now `date, video_id, title, channel, url`.
- Links are stored in one form, `https://www.youtube.com/watch?v=<id>`. Five links had backslashes from the shell
  (`watch\?v\=...`) and many carried playlist parameters.
- Four entries that were in the archive but missing from the CSV were restored: Dede Efendi (2026-02-02),
  Philip Glass (2026-03-25), Gemide and İnci Tanem (2026-04-04). Two test lines and one broken duplicate line of the archive were dropped.
- The README began with the shell command that had written it (`cat << 'EOF' > ...`) and ended inside an unclosed
  code block; it is rewritten. Thumbnails use `hqdefault.jpg`, which exists for every video (`maxresdefault.jpg`
  does not).
- The profile README is updated between `<!-- MUSICLOG:START -->` and `<!-- MUSICLOG:END -->` instead of by matching
  its headings.
- Adding the same video twice on the same day is refused. `.gitignore` had a broken line.
