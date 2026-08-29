import os
import random
import re
import shutil

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


def visible_len(text):
    return len(strip_ansi(text))


def fit(text, width):
    text = str(text)
    raw = strip_ansi(text)
    if len(raw) <= width:
        return text + " " * (width - len(raw))
    return raw[: max(0, width - 1)] + "…"


def color_fit(text, width, color):
    return color + fit(text, width) + RESET


def pad_visible(text, width, align="left"):
    raw_len = visible_len(text)
    if raw_len >= width:
        return text
    pad = width - raw_len
    if align == "right":
        return " " * pad + text
    if align == "center":
        left = pad // 2
        return " " * left + text + " " * (pad - left)
    return text + " " * pad


def clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def tname(code):
    return TEAM_NAMES.get(code, code)


def roster_lines(team, color, width, city=None, bench_count=7):
    name = city or CITY_NAMES.get(team.code, tname(team.code))
    name_w = max(8, width - 8)
    lines = [color + f"{fit(name, name_w)} Pts PF"[:width] + RESET]
    def player_line(label, p):
        return color + f"{label:<2}{fit(p.name.upper(), name_w-2)} {p.points:>2} {p.fouls:>2}"[:width] + RESET
    for i, p in enumerate(team.get_lineup(), 1):
        lines.append(player_line(str(i), p))
    lines.append(color + "─" * width + RESET)
    for i, p in enumerate(team.get_bench()[:bench_count]):
        lines.append(player_line(chr(65+i), p))
    while len(lines) < 6 + bench_count:
        lines.append(" " * width)
    return lines[:6 + bench_count]


def scoreboard(v_team, h_team, qtr, time_remaining, shot_clock, width):
    inner = max(34, width - 2)
    left_w = (inner - 8) // 2
    right_w = inner - 8 - left_w
    return [
        WHITE + "╔" + "═" * inner + "╗" + RESET,
        WHITE + "║" + SPURS + fit(tname(v_team.code), left_w) + RESET + CYAN + f"{'Qtr':^8}" + RESET + CELTICS + fit(tname(h_team.code), right_w) + RESET + WHITE + "║" + RESET,
        WHITE + "║" + SPURS + f"{v_team.score:^{left_w}}" + RESET + CYAN + f"{qtr:^8}" + RESET + CELTICS + f"{h_team.score:^{right_w}}" + RESET + WHITE + "║" + RESET,
        WHITE + "║" + f"{clock(time_remaining):^{inner//2}}" + f"{(':'+str(shot_clock).zfill(2)):^{inner - inner//2}}" + WHITE + "║" + RESET,
        WHITE + "╚" + "═" * inner + "╝" + RESET,
    ]


def retro_court(width, height=12):
    width = max(54, width)
    height = max(9, height)
    rows = [LINE + "┌" + "─" * (width - 2) + "┐" + RESET]
    mid = width // 2
    paint_w = max(10, min(14, width // 6))
    left_x = 3
    right_x = width - 3 - paint_w
    paint_top = max(3, height // 3)
    paint_bottom = min(height - 2, paint_top + 4)
    for y in range(height):
        chars = [" "] * width
        chars[mid] = "│"
        line = "".join(chars)
        if paint_top <= y <= paint_bottom:
            border = y == paint_top or y == paint_bottom
            paint_line = ("┌" + "─" * (paint_w - 2) + "┐") if y == paint_top else ("└" + "─" * (paint_w - 2) + "┘") if y == paint_bottom else ("│" + " " * (paint_w - 2) + "│")
            rows.append(
                HARDWOOD + line[:left_x] + PAINT + paint_line + HARDWOOD + line[left_x+paint_w:right_x] +
                PAINT + paint_line + HARDWOOD + line[right_x+paint_w:] + RESET
            )
        else:
            rows.append(HARDWOOD + line + RESET)
    rows.append(LINE + "└" + "─" * (width - 2) + "┘" + RESET)
    return rows


def compose_line(parts, width):
    raw = "".join(parts)
    plain = strip_ansi(raw)
    if len(plain) <= width:
        return raw + " " * (width - len(plain))
    # Avoid chopping through ANSI sequences: rebuild from plain if overflow happens.
    return plain[:width]


def render_retro_game_screen(v_team, h_team, quarter, time_remaining, shot_clock=24, pbp_lines=None, width=None, height=None):
    term = shutil.get_terminal_size((141, 37))
    width = max(100, min(width or term.columns, 180))
    height = max(30, min(height or term.lines, 60))
    pbp = list(pbp_lines or ["Line"])[-7:]

    side_w = max(18, min(22, (width - 60) // 2))
    gap = 1
    board_w = max(42, width - (side_w * 2) - (gap * 2))
    court_w = min(width - 2 * side_w - 6, 78)
    court_w = max(56, court_w)
    court_indent = side_w + 2
    pbp_w = width - 2 * side_w - 6
    pbp_w = max(48, pbp_w)

    left = roster_lines(v_team, SPURS, side_w, bench_count=7)
    right = roster_lines(h_team, CELTICS, side_w, bench_count=7)
    board = scoreboard(v_team, h_team, quarter, time_remaining, shot_clock, board_w)
    lines = []
    for i in range(5):
        lines.append(compose_line([left[i], " " * gap, pad_visible(board[i], board_w, "center"), " " * gap, right[i]], width))

    status = [
        ("Time", "Time"), ("Outs", "Outs"), (str(v_team.timeouts), str(h_team.timeouts)),
        ("Team", "Team"), ("Fouls", "Fouls"), (str(v_team.team_fouls), str(h_team.team_fouls)),
    ]
    for ltxt, rtxt in status:
        lines.append(compose_line([color_fit(ltxt, side_w, SPURS), " " * (width - 2 * side_w), color_fit(rtxt, side_w, CELTICS)], width))

    court_h = max(9, min(13, height - 24))
    for row in retro_court(court_w, court_h):
        lines.append(compose_line([" " * court_indent, row], width))

    divider_mid = max(20, pbp_w - 8)
    lines.append(compose_line([SPURS + "─" * side_w + RESET, "  ", CELTICS + fit("Line", 6) + RESET, WHITE + "─" * divider_mid + RESET, "  ", CELTICS + "─" * side_w + RESET], width))
    for i in range(7):
        msg = pbp[i] if i < len(pbp) else ""
        lidx = 7 + i
        left_text = left[lidx] if lidx < len(left) else " " * side_w
        right_text = right[lidx] if lidx < len(right) else " " * side_w
        lines.append(compose_line([left_text, " ", CELTICS + fit(msg, pbp_w) + RESET, " ", right_text], width))

    max_rows = max(1, height - 1)
    return "\n".join(lines[:max_rows])


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
        fouler = defense.get_rebounder(); fouler.fouls += 1; defense.team_fouls += 1
        attempts = 3 if is_three else 2
        made = sum(1 for _ in range(attempts) if random.random() < shooter.ft_pct)
        shooter.ft_attempts += attempts; shooter.ft_made += made; shooter.points += made; possession.score += made
        add_log(pbp, f"Whistle... {shooter.name.upper()} shoots {made}/{attempts}.")
        return defense, max(0, time_remaining - pace)
    shooter.shots += 1
    if is_three: shooter.threes_att += 1
    if random.random() < (shooter.three_pct if is_three else shooter.two_pct):
        pts = 3 if is_three else 2
        possession.score += pts; shooter.points += pts; shooter.makes += 1
        if is_three: shooter.threes_made += 1
        passer = possession.get_assister(shooter)
        if passer and random.random() < 0.62:
            passer.assists += 1; add_log(pbp, f"{passer.name.upper()} leaves it for {shooter.name.upper()}.")
        add_log(pbp, f"{shooter.name.upper()} {'from DOWNTOWN!' if is_three else random.choice(MAKE_TEXT)}")
        return defense, max(0, time_remaining - pace)
    add_log(pbp, f"{shooter.name.upper()} {random.choice(MISS_TEXT)}.")
    if random.random() < 0.72:
        r = defense.get_rebounder(); r.rebounds += 1; add_log(pbp, f"{r.name.upper()} pulls down the rebound.")
        return defense, max(0, time_remaining - pace)
    r = possession.get_rebounder(); r.rebounds += 1; add_log(pbp, f"{r.name.upper()} grabs the OFFENSIVE board!")
    return possession, max(0, time_remaining - 5)


def clear_screen():
    print("\033[2J\033[H", end="")


def play_retro_game(team_v, team_h, input_fn=input):
    pbp = ["Line"]
    possession = team_v
    quarter = 1
    time_remaining = 720
    team_v.team_fouls = team_h.team_fouls = 0
    while quarter <= 4:
        term = shutil.get_terminal_size((141, 37))
        shot_clock = min(24, int(time_remaining) if time_remaining < 24 else 24)
        clear_screen()
        print(render_retro_game_screen(team_v, team_h, quarter, time_remaining, shot_clock, pbp, width=term.columns, height=term.lines))
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
            team_v.team_fouls = team_h.team_fouls = 0
            add_log(pbp, f"End of quarter {quarter-1}.")
    clear_screen()
    print(render_retro_game_screen(team_v, team_h, 4, 0, 0, pbp + ["FINAL HORN."]))
    return True
