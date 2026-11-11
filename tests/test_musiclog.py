"""Offline tests: python3 -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import musiclog as m  # noqa: E402

ID = "a-u-HmJqYIg"


class Links(unittest.TestCase):
    def test_link_forms(self):
        for url in (f"https://www.youtube.com/watch?v={ID}",
                    f"https://www.youtube.com/watch?v={ID}&list=RD{ID}&start_radio=1",
                    f"https://www.youtube.com/watch\\?v\\={ID}\\&list\\=RD{ID}\\&start_radio\\=1",
                    f"https://youtu.be/{ID}?si=abc", f"youtube.com/shorts/{ID}", f"https://m.youtube.com/watch?v={ID}",
                    f"https://music.youtube.com/watch?v={ID}", f"https://www.youtube.com/embed/{ID}", ID):
            self.assertEqual(m.extract_video_id(url), ID, url)

    def test_not_a_video(self):
        for url in ("https://www.youtube.com/", "https://example.com/watch?v=" + ID, "watch?v=short", ""):
            self.assertIsNone(m.extract_video_id(url), url)


class Dataset(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "README.md").write_text(
            "x\n<!-- CHOSEN_TODAY:START -->\nold\n<!-- CHOSEN_TODAY:END -->\n"
            "<!-- STATS:START -->\n<!-- STATS:END -->\ny\n", encoding="utf-8")
        self.patches = [mock.patch.object(m, name, self.tmp / rel) for name, rel in (
            ("CSV_PATH", "data/daily_tracks.csv"), ("JSONL_PATH", "data/daily_tracks.jsonl"),
            ("ARCHIVE_PATH", "docs/archive.md"), ("STATS_PATH", "docs/stats.md"), ("CALENDAR_PATH", "docs/calendar.svg"),
            ("README_PATH", "README.md"), ("ROOT", "."),
            ("PROFILE_REPO", "profile"))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def add(self, url, day, title="T"):
        with mock.patch.object(m, "fetch_metadata", return_value=(title, "Channel")):
            m.main(["add", url, "--date", day, "--no-push"])

    def test_add_render_and_check(self):
        self.add(f"https://youtu.be/{ID}", "2026-10-11", "Second")
        self.add("https://www.youtube.com/watch?v=RW8SBwGNcF8", "2026-01-29", "First")
        rows = m.read_rows(m.CSV_PATH)
        self.assertEqual([r["date"] for r in rows], ["2026-01-29", "2026-10-11"])
        self.assertEqual(m.problems(rows), [])
        readme = m.README_PATH.read_text(encoding="utf-8")
        self.assertIn("**2026-10-11**: [Second]", readme)
        self.assertNotIn("old", readme)
        self.assertIn("2 entries on 2 days", readme)
        self.assertEqual(len(m.JSONL_PATH.read_text(encoding="utf-8").splitlines()), 2)
        self.assertEqual(m.render(rows), [])  # rendering again changes nothing

    def test_same_video_twice_on_one_day_is_refused(self):
        self.add(f"https://youtu.be/{ID}", "2026-10-11")
        with self.assertRaises(SystemExit):
            self.add(f"https://www.youtube.com/watch?v={ID}", "2026-10-11")

    def test_profile_block(self):
        profile = self.tmp / "profile"
        profile.mkdir()
        (profile / "README.md").write_text("a\n<!-- MUSICLOG:START -->\n<!-- MUSICLOG:END -->\nb\n", encoding="utf-8")
        self.add(f"https://youtu.be/{ID}", "2026-10-11", "Piece")
        text = (profile / "README.md").read_text(encoding="utf-8")
        self.assertIn("mqdefault.jpg", text)
        self.assertIn("[Piece]", text)
        self.assertTrue(text.startswith("a\n") and text.endswith("b\n"))

    def test_problems_are_found(self):
        rows = [{"date": "2026-13-01", "video_id": "bad", "title": "", "artist": "", "work": "", "channel": "", "url": "x"}]
        self.assertGreaterEqual(len(m.problems(rows)), 3)

    def test_artist_and_work(self):
        self.add(f"https://youtu.be/{ID}", "2026-10-11", "Otis Redding - Try A Little Tenderness (Official Video) [HD]")
        row = m.read_rows(m.CSV_PATH)[-1]
        self.assertEqual((row["artist"], row["work"]), ("Otis Redding", "Try A Little Tenderness"))
        m.main(["set", "2026-10-11", "--artist", "O. Redding", "--no-push"])
        row = m.read_rows(m.CSV_PATH)[-1]
        self.assertEqual((row["artist"], row["work"]), ("O. Redding", "Try A Little Tenderness"))
        with self.assertRaises(SystemExit):
            m.main(["set", "2026-10-12", "--artist", "x", "--no-push"])      # no entry on that day

    def test_same_video_on_another_day_is_allowed(self):
        self.add(f"https://youtu.be/{ID}", "2026-10-11")
        self.add(f"https://youtu.be/{ID}", "2026-10-12")
        self.assertEqual(len(m.read_rows(m.CSV_PATH)), 2)

    def test_old_file_without_the_new_columns(self):
        m.CSV_PATH.parent.mkdir(parents=True)
        m.CSV_PATH.write_text("date,video_id,title,channel,url\n"
                              f"2026-10-11,{ID},T,C,https://www.youtube.com/watch?v={ID}\n", encoding="utf-8")
        rows = m.read_rows(m.CSV_PATH)
        self.assertEqual((rows[0]["artist"], rows[0]["work"]), ("", ""))
        self.assertEqual(m.problems(rows), [])

    def test_statistics_and_calendar(self):
        for day in ("2026-10-10", "2026-10-11", "2026-10-12", "2026-10-20"):
            self.add("https://youtu.be/" + ID[:-2] + day[-2:], day, "A - B")
        rows = m.read_rows(m.CSV_PATH)
        self.assertEqual(m.longest_run({r["date"] for r in rows})[0], 3)
        text = m.STATS_PATH.read_text(encoding="utf-8")
        self.assertIn("Days without an entry: 7 of 11.", text)
        self.assertIn("| A | 4 |", text)
        svg = m.CALENDAR_PATH.read_text(encoding="utf-8")
        self.assertEqual(svg.count("<rect"), 11 + 4)       # one cell per day of the span and four of the legend
        self.assertEqual(m.render(rows), [])


class Titles(unittest.TestCase):
    def test_split(self):
        for title, channel, want in (
                ("Moondog - Bird's Lament", "x", ("Moondog", "Bird's Lament")),
                ("Eleni Karaindrou – The Weeping Meadow", "x", ("Eleni Karaindrou", "The Weeping Meadow")),
                ("Penderecki: Threnody for the Victims of Hiroshima", "x", ("Penderecki", "Threnody for the Victims of Hiroshima")),
                ("MFÖ - Sakın Gelme (Official Video)", "", ("MFÖ", "Sakın Gelme")),
                ("Gymnopédie No. 1", "Erik Satie - Topic", ("Erik Satie", "Gymnopédie No. 1")),
                ("The Godfather Suite", "Hunter McCarville", ("", "The Godfather Suite")),
                ("Eagles - Hotel California (Live 1977) (Official Video) [HD]", "Eagles", ("Eagles", "Hotel California (Live 1977)"))):
            self.assertEqual(m.split_title(title, channel), want, title)


class LinkCheck(unittest.TestCase):
    def test_status(self):
        import urllib.error
        def fail(code):
            return mock.patch.object(m, "fetch_metadata", side_effect=urllib.error.HTTPError("u", code, "x", None, None))
        with mock.patch.object(m, "fetch_metadata", return_value=("T", "C")):
            self.assertEqual(m.link_status(ID), "ok")
        for code, want in ((404, "not found"), (401, "refused"), (403, "refused"), (500, "unknown")):
            with fail(code):
                self.assertEqual(m.link_status(ID), want)
        with mock.patch.object(m, "fetch_metadata", side_effect=OSError("no network")):
            self.assertEqual(m.link_status(ID), "unknown")


if __name__ == "__main__":
    unittest.main()
