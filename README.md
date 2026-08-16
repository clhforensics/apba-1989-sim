# APBA Pro Basketball 1989 Simulator (v7.0)

## Overview

A statistical simulation engine for the **1988-89 NBA season**. This project brings the classic mechanics of the APBA Pro Basketball board game into Python. It uses real historical data (`stats.csv`) to simulate NBA games with play-by-play accuracy, momentum physics, fatigue systems, and coaching strategies.

## Features

- **Three Game Modes:**
  - **Play-by-Play:** Watch the game unfold possession by possession.
  - **Quarter-by-Quarter:** Classic coaching mode with strategy adjustments.
  - **Fast Sim:** Instant results for quick testing.
- **DevTools Suite:** Benchmark the engine by simulating 100+ games instantly to verify statistical accuracy against real 1989 league averages.
- **Dynamic Physics:**
  - "The Crowd Erupts" — Home momentum impacts visitor shooting percentages.
  - "The Jordan Rule" — Advanced substitution logic keeps stars on the floor in crunch time.
  - Realistic pace — Strategy settings (Run & Shoot vs. Slow & Low) alter game tempo and possession counts.
- **Coaching Strategies:** Adjust your team's approach on the fly during games.

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

### Controls

| Key | Action |
|-----|--------|
| ENTER | Advance play in PBP mode |
| S | Change coaching strategy on the fly |
| Q | Quit to main menu |

## Tech Stack

- **Language:** Python 3
- **Libraries:** Standard Library only (`random`, `time`, `csv`) — no `pip install` required

## Note

This is a fan project created for educational and entertainment purposes. It is not affiliated with, endorsed by, or sponsored by the APBA Game Company.
