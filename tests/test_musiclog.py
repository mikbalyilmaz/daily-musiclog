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
            ("ARCHIVE_PATH", "docs/archive.md"), ("README_PATH", "README.md"), ("ROOT", "."),
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
        rows = [{"date": "2026-13-01", "video_id": "bad", "title": "", "channel": "", "url": "x"}]
        self.assertGreaterEqual(len(m.problems(rows)), 3)


if __name__ == "__main__":
    unittest.main()
