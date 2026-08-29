import contextlib
import copy
import importlib.util
import io
import os
import random
import statistics
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sim", ROOT / "main.py")
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


class GameplayRealismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rosters = load_rosters_quiet()

    def simulate_games(self, n=24):
        random.seed(1989)
        teams = list(self.rosters)
        metrics = []
        minute_rows = []
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(n):
                a, b = random.sample(teams, 2)
                v = sim.Team(a, copy.deepcopy(self.rosters[a]))
                h = sim.Team(b, copy.deepcopy(self.rosters[b]))
                sim.play_game(v, h, game_mode=4, silent=True)
                for t in (v, h):
                    metrics.append(t.get_team_stats())
                    minute_rows.extend((p.name, p.pos, p.mpg, p.stat_minutes) for p in t.roster if p.stat_minutes > 0.1)
        return metrics, minute_rows

    def test_player_profiles_use_real_three_point_and_free_throw_rates(self):
        jordan = next(p for p in self.rosters["CHI"] if p.name == "Michael Jordan")
        self.assertTrue(hasattr(jordan, "three_attempt_rate"))
        self.assertGreater(jordan.free_throw_rate, 0.35)
        self.assertAlmostEqual(jordan.three_attempt_rate, 98 / 1795, delta=0.02)

    def test_team_starts_positionally_balanced_lineup(self):
        bulls = sim.Team("CHI", copy.deepcopy(self.rosters["CHI"]))
        positions = [p.lineup_pos for p in bulls.get_lineup()]
        self.assertEqual(len(positions), 5)
        self.assertIn("PG", positions)
        self.assertIn("C", positions)
        self.assertLessEqual(positions.count("G") + positions.count("PG") + positions.count("SG"), 3)

    def test_benchmark_stats_land_near_1989_targets(self):
        metrics, _ = self.simulate_games(30)
        avg = lambda k: sum(m[k] for m in metrics) / len(metrics)
        fg_pct = sum(m["FGM"] for m in metrics) / max(1, sum(m["FGA"] for m in metrics))
        three_pct = sum(m["3PM"] for m in metrics) / max(1, sum(m["3PA"] for m in metrics))
        self.assertGreater(avg("PTS"), 103)
        self.assertLess(avg("PTS"), 116)
        self.assertGreater(fg_pct, 0.445)
        self.assertLess(fg_pct, 0.505)
        self.assertGreater(avg("3PA"), 4.5)
        self.assertLess(avg("3PA"), 9.0)
        self.assertGreater(three_pct, 0.285)
        self.assertLess(three_pct, 0.365)
        self.assertGreater(avg("TOV"), 12.0)
        self.assertLess(avg("TOV"), 20.5)
        self.assertGreater(avg("PF"), 18.0)
        self.assertLess(avg("PF"), 27.0)

    def test_rotation_minutes_are_plausible(self):
        _, minute_rows = self.simulate_games(18)
        star_rows = [mins for _, _, mpg, mins in minute_rows if mpg >= 32]
        deep_bench_rows = [mins for _, _, mpg, mins in minute_rows if mpg < 12]
        self.assertTrue(star_rows)
        self.assertLess(max(star_rows), 43.0)
        self.assertGreater(statistics.mean(star_rows), 28.0)
        if deep_bench_rows:
            self.assertLess(statistics.mean(deep_bench_rows), 10.0)


if __name__ == "__main__":
    unittest.main()
