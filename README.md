# APBA Pro Basketball 1989 Simulator

## Overview

A statistical simulation engine for the **1988-89 NBA season** inspired by classic APBA-style pro basketball games. The simulator uses real historical player data from `stats.csv` and now includes a more realistic gameplay model, position-aware rotations, season records, and a retro-modern presentation preview inspired by old DOS basketball sims.

This is a standard-library Python project: no `pip install` required.

## Major Features

### Gameplay Realism

- 1988-89 benchmark tuning for points, FG%, 3PA, FT%, rebounds, assists, turnovers, and fouls.
- Real player 3-point tendency from `3PA/FGA` instead of a simple yes/no shooter flag.
- Separate 2P% and 3P% shot resolution when data exists.
- Improved turnover model tuned toward late-80s basketball.
- Team foul tracking and bonus free throws.
- Shooting fouls, 3-shot fouls, and and-one chances.
- Offensive rebounds can retain possession.
- Offensive and defensive strategies influence tempo, turnovers, fouls, shot quality, and rebounding.

### Substitutions and Minutes

- Position-aware starting lineups using PG/SG/SF/PF/C slots.
- Position-compatible substitutions so lineups stay basketball-plausible.
- Target minutes derived from real player MPG.
- Fatigue/stint handling.
- Foul-trouble substitutions.
- Crunch-time star return logic.
- Garbage-time bench usage.

### Retro-Modern Presentation

- DOS-style black-background layout inspired by classic PC basketball sims.
- Left/right roster panels with player points, fouls, and minutes.
- Top-center scoreboard with team names, score, quarter, clock, and shot clock.
- Timeout and team-foul side panels.
- Modernized terminal court with paint, arcs, center-court marker, and bottom play-by-play feed.

Use menu option **6. Retro-Modern Play Mode** to play possession-by-possession inside the presentation shell.

### Season Stats and Records

- SQLite season database via Python's built-in `sqlite3` module.
- Game result persistence to `season.sqlite3`.
- Team standings.
- Player stat leaders.
- Standings export to CSV.

Use menu option **5. Season Records / Standings** to view or export records.

## Installation

```bash
git clone https://github.com/clhforensics/apba-1989-sim.git
cd apba-1989-sim
```

## Usage

```bash
python3 main.py
```

Make sure `stats.csv` is in the same directory as `main.py`.

## Menu Options

1. **Play-by-Play** — manually advance each possession.
2. **Quarter-by-Quarter** — classic coaching mode with quarter breaks.
3. **Fast Sim** — instant game result.
4. **DevTools / League Benchmark** — simulate many games and compare to 1988-89 NBA averages.
5. **Season Records / Standings** — view standings, scoring leaders, or export standings CSV.
6. **Retro-Modern Play Mode** — play possession-by-possession in the screenshot-inspired court/shell layout.

## Controls

| Key | Action |
|-----|--------|
| ENTER | Advance play in PBP mode |
| S | Change coaching strategy on the fly |
| Q | Quit to main menu |

## Validation Targets

The benchmark suite compares simulated team/game averages against real 1988-89 NBA baselines:

| Stat | 1988-89 NBA Target |
|------|-------------------:|
| PTS | 109.2 |
| FG% | .477 |
| 3PA | 6.6 |
| 3P% | .323 |
| FT% | .768 |
| TRB | 43.9 |
| AST | 25.9 |
| STL | 9.1 |
| TOV | 16.6 |
| PF | 22.7 |

Recent validation on the gameplay-realism branch produced:

| Stat | Sim Result |
|------|-----------:|
| PTS | 110.9 |
| FG% | .478 |
| 3PA | 5.4 |
| 3P% | .341 |
| FT% | .773 |
| REB | 45.5 |
| AST | 25.9 |
| TOV | 17.2 |
| PF | 21.7 |

## Running Tests

```bash
python3 -m unittest tests.test_gameplay_realism tests.test_presentation_and_season -v
```

## Tech Stack

- Python 3
- Standard library only:
  - `random`
  - `time`
  - `csv`
  - `copy`
  - `sqlite3`
  - `datetime`
  - `unittest` for tests

## Note

This is a fan project created for educational and entertainment purposes. It is not affiliated with, endorsed by, or sponsored by the APBA Game Company.
