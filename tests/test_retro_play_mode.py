import contextlib
import copy
import importlib.util
import io
import os
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sim", ROOT / "main.py")
assert spec is not None and spec.loader is not None
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
retro = sim.play_retro_game.__globals__["render_retro_game_screen"]


def load_rosters_quiet():
    cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        with contextlib.redirect_stdout(io.StringIO()):
            return sim.load_data()
    finally:
        os.chdir(cwd)


class RetroPlayModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rosters = load_rosters_quiet()

    def test_retro_screen_matches_reference_shape_and_colors(self):
        sas = sim.Team("SAS", copy.deepcopy(self.rosters["SAS"]))
        bos = sim.Team("BOS", copy.deepcopy(self.rosters["BOS"]))
        sas.score = 4
        bos.score = 8
        sas.team_fouls = 1
        bos.team_fouls = 0
        screen = retro(
            sas,
            bos,
            quarter=1,
            time_remaining=551,
            shot_clock=24,
            pbp_lines=[
                "GAMBLE leaves it for LEWIS.",
                "LEWIS drives to the hole... Pulls up... Whistle... Traveling... LEWIS",
                "AVERY JOHNSON comes onto the floor for PRESSEY.",
            ],
        )
        self.assertIn("\033[38;5;208mSan Antonio", screen)
        self.assertIn("\033[92mBoston", screen)
        self.assertIn("\033[48;5;130m", screen)  # brown/orange court fill, not plain gray
        self.assertIn("\033[44m", screen)        # blue paint blocks like the reference
        self.assertIn("GAMBLE leaves it for LEWIS", screen)
        self.assertIn("Qtr", screen)
        self.assertIn(":24", screen)
        self.assertLess(screen.find("San Antonio"), screen.find("Boston"))
        self.assertLess(screen.find("Team\x1b[0m"), screen.find("GAMBLE leaves it"))

    def test_play_retro_game_advances_until_quit_without_exiting_immediately(self):
        random.seed(7)
        sas = sim.Team("SAS", copy.deepcopy(self.rosters["SAS"]))
        bos = sim.Team("BOS", copy.deepcopy(self.rosters["BOS"]))
        inputs = iter(["", "", "q"])

        def fake_input(prompt):
            print(prompt, end="")
            return next(inputs)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sim.play_retro_game(sas, bos, input_fn=fake_input)
        rendered = out.getvalue()
        self.assertIn("[ENTER] Next Play", rendered)
        self.assertGreater(rendered.count("Spurs"), 1)
        self.assertGreater(sas.score + bos.score + sum(p.shots for p in sas.roster + bos.roster), 0)
        self.assertNotIn("FINAL BOX SCORE", rendered)  # q exits retro flow, not a completed game


if __name__ == "__main__":
    unittest.main()
