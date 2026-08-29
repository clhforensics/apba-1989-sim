import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sim", ROOT / "main.py")
assert spec is not None and spec.loader is not None
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
from retro_play import render_retro_game_screen, strip_ansi


class RetroResponsiveLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import contextlib, io, os
        cwd = Path.cwd()
        try:
            os.chdir(ROOT)
            with contextlib.redirect_stdout(io.StringIO()):
                cls.rosters = sim.load_data()
        finally:
            os.chdir(cwd)

    def test_141_column_layout_stays_aligned_and_visible(self):
        pacers = sim.Team("IND", copy.deepcopy(self.rosters["IND"]))
        bulls = sim.Team("CHI", copy.deepcopy(self.rosters["CHI"]))
        pacers.score = 28
        bulls.score = 22
        screen = render_retro_game_screen(
            pacers,
            bulls,
            quarter=2,
            time_remaining=720,
            shot_clock=24,
            pbp_lines=[
                "RIK SMITS buries the jumper",
                "CRAIG HODGES leaves it for JOHN PAXSON.",
                "JOHN PAXSON nails the shot",
                "SCOTT SKILES stepped out of bounds.",
                "BRAD SELLERS clanks it off the iron.",
                "DETLEF SCHREMPF pulls down the rebound.",
                "End of quarter 1.",
            ],
            width=141,
            height=37,
        )
        plain_lines = [strip_ansi(line) for line in screen.splitlines()]
        self.assertLessEqual(max(len(line) for line in plain_lines), 141)
        self.assertLessEqual(len(plain_lines), 36)  # leave row 37 for input prompt
        self.assertIn("Pacers", plain_lines[0])
        self.assertIn("Bulls", plain_lines[0])
        self.assertTrue(any("┌" in line and "┐" in line for line in plain_lines))
        court_rows = [i for i, line in enumerate(plain_lines) if "│" in line and "Pts PF" not in line]
        self.assertTrue(court_rows)
        # Court should start after top panels but before play-by-play.
        first_court = min(court_rows)
        pbp_row = next(i for i, line in enumerate(plain_lines) if "Line" in line and "─" in line)
        self.assertGreaterEqual(first_court, 10)
        self.assertLess(first_court, pbp_row)
        self.assertLess(pbp_row, 30)
        self.assertTrue(any("RIK SMITS" in line for line in plain_lines))


if __name__ == "__main__":
    unittest.main()
