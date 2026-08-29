import os
import random
import re

RESET = "\033[0m"
WHITE = "\033[97m"
CYAN = "\033[96m"
SPURS = "\033[38;5;208m"
CELTICS = "\033[92m"
HARDWOOD = "\033[48;5;130m"
LINE = "\033[38;5;250m\033[48;5;130m"
PAINT = "\033[44m\033[97m"

TEAM_NAMES = {
    "ATL": "Hawks", "BOS": "Celtics", "CHH": "Hornets", "CHI": "Bulls",
    "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets", "DET": "Pistons",
    "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers",
    "LAL": "Lakers", "MIA": "Heat", "MIL": "Bucks", "NJN": "Nets",
    "NYK": "Knicks", "PHI": "76ers", "PHO": "Suns", "POR": "Blazers",
    "SAC": "Kings", "SAS": "Spurs", "SEA": "Sonics", "UTA": "Jazz", "WSB": "Bullets",
}
CITY_NAMES = {"SAS": "San Antonio", "BOS": "Boston"}
MISS_TEXT = ["clanks it off the iron", "misses short", "bricks it", "can't get it to fall", "in and out"]
MAKE_TEXT = ["buries the jumper", "banks it in", "swishes it", "nails the shot", "scores"]
TO_TEXT = ["loses the handle", "throws it away", "stepped out of bounds", "bad pass"]


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", str(text))


def fit(text, width):
    text = str(text)
    raw = strip_ansi(text)
    if len(raw) <= width:
        return text + " " * (width - len(raw))
    return raw[: max(0, width - 1)] + "…"


def clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def tname(code):
    return TEAM_NAMES.get(code, code)


def roster_lines(team, color, city=None):
    name = city or CITY_NAMES.get(team.code, tname(team.code))
    lines = [f"{color}{fit(name, 13)} Pts PF{RESET}"]
    for i, p in enumerate(team.get_lineup(), 1):
        lines.append(f"{color}{i:<2}{fit(p.name.upper(), 12)} {p.points:>2} {p.fouls:>2}{RESET}")
    lines.append(" " * 20)
    for i, p in enumerate(team.get_bench()[:7]):
        lines.append(f"{color}{chr(65+i):<2}{fit(p.name.upper(), 12)} {p.points:>2} {p.fouls:>2}{RESET}")
    while len(lines) < 14:
        lines.append(" " * 20)
    return lines[:14]


def scoreboard(v_team, h_team, qtr, time_remaining, shot_clock):
    width = 48
    return [
        WHITE + "╔" + "═" * width + "╗" + RESET,
        f"{WHITE}║{RESET}{SPURS}{tname(v_team.code):^14}{RESET}{CYAN}{'Qtr':^8}{RESET}{CELTICS}{tname(h_team.code):^14}{RESET}{WHITE}║{RESET}",
        f"{WHITE}║{RESET}{SPURS}{v_team.score:^14}{RESET}{CYAN}{str(qtr):^8}{RESET}{CELTICS}{h_team.score:^14}{RESET}{WHITE}║{RESET}",
        f"{WHITE}║{RESET}{clock(time_remaining):^24}{(':'+str(shot_clock).zfill(2)):^24}{WHITE}║{RESET}",
        WHITE + "╚" + "═" * width + "╝" + RESET,
    ]


def retro_court(width=74):
    rows = [LINE + "┌" + "─" * (width - 2) + "┐" + RESET]
    for y in range(13):
        base = [" "] * width
        base[width // 2] = "│"
        row = "".join(base)
        if 4 <= y <= 8:
            left = HARDWOOD + row[:3]
            paint_l = PAINT + ("┌────────────┐" if y == 4 else "│            │" if y in (5, 6, 7) else "└────────────┘")
            mid = HARDWOOD + row[17: width - 17]
            paint_r = PAINT + ("┌────────────┐" if y == 4 else "│            │" if y in (5, 6, 7) else "└────────────┘")
            right = HARDWOOD + row[width - 3:]
            rows.append(left + paint_l + mid + paint_r + right + RESET)
        else:
            rows.append(HARDWOOD + row + RESET)
    rows.append(LINE + "└" + "─" * (width - 2) + "┘" + RESET)
    return rows


def render_retro_game_screen(v_team, h_team, quarter, time_remaining, shot_clock=24, pbp_lines=None):
    pbp = list(pbp_lines or ["Line"])[-7:]
    left = roster_lines(v_team, SPURS)
    right = roster_lines(h_team, CELTICS)
    board = scoreboard(v_team, h_team, quarter, time_remaining, shot_clock)
    lines = []
    for i in range(5):
        lines.append(f"{left[i]:<25}{board[i]:^54}{right[i]:>25}")
    lines.extend([
        f"{SPURS}{'Time':<10}{RESET}{'':<90}{CELTICS}{'Time':>10}{RESET}",
        f"{SPURS}{'Outs':<10}{RESET}{'':<90}{CELTICS}{'Outs':>10}{RESET}",
        f"{SPURS}{str(v_team.timeouts):<10}{RESET}{'':<90}{CELTICS}{str(h_team.timeouts):>10}{RESET}",
        f"{SPURS}{'Team':<10}{RESET}{'':<90}{CELTICS}{'Team':>10}{RESET}",
        f"{SPURS}{'Fouls':<10}{RESET}{'':<90}{CELTICS}{'Fouls':>10}{RESET}",
        f"{SPURS}{str(v_team.team_fouls):<10}{RESET}{'':<90}{CELTICS}{str(h_team.team_fouls):>10}{RESET}",
    ])
    for row in retro_court(74):
        lines.append(f"{'':<14}{row}")
    lines.append(f"{SPURS}{'─'*20}{RESET}  {CELTICS}{'Line':<6}{RESET}{WHITE}{'─'*66}{RESET}  {CELTICS}{'─'*20}{RESET}")
    for i in range(7):
        msg = pbp[i] if i < len(pbp) else ""
        l = left[6+i] if 6+i < len(left) else " " * 20
        r = right[6+i] if 6+i < len(right) else " " * 20
        lines.append(f"{l:<20} {CELTICS}{fit(msg, 74)}{RESET} {r:>20}")
    return "\n".join(lines)


def add_log(lines, msg):
    lines.append(msg)
    del lines[:-7]


def one_possession(possession, defense, time_remaining, pbp):
    pace = {1: 10, 2: 13, 3: 18}.get(possession.off_strategy, 13)
    shooter = possession.get_shooter()
    elapsed = pace / 60.0
    for p in possession.get_lineup() + defense.get_lineup():
        p.stat_minutes += elapsed
        p.current_fatigue += elapsed
    possession.recover_bench(elapsed)
    defense.recover_bench(elapsed)
    if random.random() < min(0.24, max(0.06, 0.105 + shooter.to_rate * 0.55)):
        shooter.turnovers += 1
        add_log(pbp, f"{shooter.name.upper()} {random.choice(TO_TEXT)}.")
        return defense, max(0, time_remaining - pace)
    is_three = shooter.has_3pt and random.random() < min(0.42, shooter.three_attempt_rate)
    foul = random.random() < min(0.16, 0.08 + shooter.free_throw_rate * 0.08)
    if foul:
        fouler = defense.get_rebounder()
        fouler.fouls += 1
        defense.team_fouls += 1
        attempts = 3 if is_three else 2
        made = sum(1 for _ in range(attempts) if random.random() < shooter.ft_pct)
        shooter.ft_attempts += attempts
        shooter.ft_made += made
        shooter.points += made
        possession.score += made
        add_log(pbp, f"Whistle... {shooter.name.upper()} shoots {made}/{attempts}.")
        return defense, max(0, time_remaining - pace)
    shooter.shots += 1
    if is_three:
        shooter.threes_att += 1
    pct = shooter.three_pct if is_three else shooter.two_pct
    if random.random() < pct:
        pts = 3 if is_three else 2
        possession.score += pts
        shooter.points += pts
        shooter.makes += 1
        if is_three:
            shooter.threes_made += 1
        passer = possession.get_assister(shooter)
        if passer and random.random() < 0.62:
            passer.assists += 1
            add_log(pbp, f"{passer.name.upper()} leaves it for {shooter.name.upper()}.")
        add_log(pbp, f"{shooter.name.upper()} {'from DOWNTOWN!' if is_three else random.choice(MAKE_TEXT)}")
        return defense, max(0, time_remaining - pace)
    add_log(pbp, f"{shooter.name.upper()} {random.choice(MISS_TEXT)}.")
    if random.random() < 0.72:
        r = defense.get_rebounder(); r.rebounds += 1
        add_log(pbp, f"{r.name.upper()} pulls down the rebound.")
        return defense, max(0, time_remaining - pace)
    r = possession.get_rebounder(); r.rebounds += 1
    add_log(pbp, f"{r.name.upper()} grabs the OFFENSIVE board!")
    return possession, max(0, time_remaining - 5)


def clear_screen():
    print("\033[2J\033[H", end="")


def play_retro_game(team_v, team_h, input_fn=input):
    pbp = ["Line"]
    possession = team_v
    quarter = 1
    time_remaining = 720
    team_v.team_fouls = 0
    team_h.team_fouls = 0
    while quarter <= 4:
        shot_clock = min(24, int(time_remaining) if time_remaining < 24 else 24)
        clear_screen()
        print(render_retro_game_screen(team_v, team_h, quarter, time_remaining, shot_clock, pbp))
        choice = input_fn("\n[ENTER] Next Play | [S] Strategy | [Q] Quit > ")
        if choice.lower() == "q":
            return False
        defense = team_h if possession == team_v else team_v
        possession, time_remaining = one_possession(possession, defense, time_remaining, pbp)
        if int(time_remaining) % 60 < 15:
            team_v.sub_check(quarter, quiet=True, time_remaining=time_remaining, score_diff=team_v.score - team_h.score)
            team_h.sub_check(quarter, quiet=True, time_remaining=time_remaining, score_diff=team_h.score - team_v.score)
        if time_remaining <= 0:
            quarter += 1
            time_remaining = 720
            team_v.team_fouls = 0
            team_h.team_fouls = 0
            add_log(pbp, f"End of quarter {quarter-1}.")
    clear_screen()
    print(render_retro_game_screen(team_v, team_h, 4, 0, 0, pbp + ["FINAL HORN."]))
    return True
