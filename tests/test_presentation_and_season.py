import contextlib
import copy
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sim", ROOT / "main.py")
assert spec is not None and spec.loader is not None
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


def load_rosters_quiet():
    cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        with contextlib.redirect_stdout(io.StringIO()):
            return sim.load_data()
    finally:
        os.chdir(cwd)


class PresentationAndSeasonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rosters = load_rosters_quiet()

    def test_render_game_screen_has_reference_layout_and_modern_court(self):
        spurs = sim.Team("SAS", copy.deepcopy(self.rosters["SAS"]))
        celtics = sim.Team("BOS", copy.deepcopy(self.rosters["BOS"]))
        screen = sim.render_game_screen(
            spurs,
            celtics,
            quarter=1,
            time_remaining=551,
            shot_clock=24,
            pbp_lines=["GAMBLE leaves it for LEWIS.", "LEWIS drives to the hole."],
        )
        self.assertIn("Spurs", screen)
        self.assertIn("Celtics", screen)
        self.assertIn("Qtr", screen)
        self.assertIn("9:11", screen)
        self.assertIn(":24", screen)
        self.assertIn("Time\nOuts", screen)
        self.assertIn("Team\nFouls", screen)
        self.assertIn("PLAY-BY-PLAY", screen)
        self.assertIn("GAMBLE leaves it for LEWIS", screen)
        # Modernized court geometry: arc/restricted-area-ish glyphs, center circle, paint labels.
        self.assertIn("MODERN NBA COURT", screen)
        self.assertIn("╭", screen)
        self.assertIn("PAINT", screen)
        self.assertIn("◎", screen)

    def test_season_store_records_game_standings_and_leaders(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "season.sqlite3"
            store = sim.SeasonStore(str(db_path))
            store.start_season("test-season")
            bulls = sim.Team("CHI", copy.deepcopy(self.rosters["CHI"]))
            pistons = sim.Team("DET", copy.deepcopy(self.rosters["DET"]))
            bulls.score = 101
            pistons.score = 97
            jordan = next(p for p in bulls.roster if p.name == "Michael Jordan")
            jordan.points = 31
            jordan.rebounds = 7
            jordan.assists = 6
            jordan.shots = 22
            jordan.makes = 12
            game_id = store.record_game(bulls, pistons, season_name="test-season")
            self.assertIsInstance(game_id, int)
            standings = store.get_standings("test-season")
            self.assertEqual(standings[0]["team"], "CHI")
            self.assertEqual(standings[0]["wins"], 1)
            self.assertEqual(standings[1]["team"], "DET")
            self.assertEqual(standings[1]["losses"], 1)
            leaders = store.get_player_leaders("PTS", season_name="test-season", limit=3)
            self.assertEqual(leaders[0]["player"], "Michael Jordan")
            self.assertEqual(leaders[0]["PTS"], 31)
            csv_path = Path(td) / "standings.csv"
            store.export_standings_csv(str(csv_path), "test-season")
            self.assertTrue(csv_path.exists())
            self.assertIn("team,wins,losses", csv_path.read_text())


if __name__ == "__main__":
    unittest.main()
