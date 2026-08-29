import random
import time
import csv
import os
import sys
import copy
import sqlite3
from datetime import datetime
from retro_play import render_retro_game_screen, play_retro_game

# ==========================================
# CONFIGURATION
# ==========================================
POSSIBLE_FILES = ["88-89 stats.csv", "stats.csv", "data.csv"]

# REAL 1988-89 NBA AVERAGES (Per Team Per Game)
# Used for DevTools benchmarking comparisons
NBA_1989_STATS = {
    "PTS": 109.2,
    "FG%": 0.477,
    "3PA": 6.6,
    "3P%": 0.323,
    "FT%": 0.768,
    "ORB": 14.0,
    "TRB": 43.9,
    "AST": 25.9,
    "STL": 9.1,
    "TOV": 16.6,
    "PF":  22.7
}

# ANSI COLORS
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

# PBP TEXT TEMPLATES
TEXT_MISS = ["clanks it off the iron", "misses short", "bricks it", "can't get it to fall", "in and out", "forces the shot... miss"]
TEXT_MAKE = ["buries the jumper", "banks it in", "swishes it", "nails the shot", "hits the fadeaway", "scores!"]
TEXT_DUNK = ["throws it down!", "jams it home!", "with the thunderous dunk!", "slams it in!", "rattles the rim!"]
TEXT_3PT  = ["from DOWNTOWN!", "for three... YES!", "from long range!", "drills the triple!", "from the parking lot!"]
TEXT_TO   = ["loses the handle", "throws it away", "stepped out of bounds", "offensive foul", "bad pass", "stripped!"]
TEXT_STL  = ["picks his pocket!", "intercepts the pass!", "jumps the passing lane!", "swipes the ball!"]
TEXT_REB  = ["grabs the board", "cleans the glass", "snatches the rebound", "pulls it down", "fight for the rebound... got it"]

# STRATEGY DEFINITIONS
STRATEGIES = {
    "OFFENSE": {
        1: {"name": "Run and Shoot", "desc": "Fast pace, 3PT focus",         "pace": 10, "to_mod": 1.15, "reb_mod": 0.90, "fatigue_mod": 1.5, "3pt_bonus": 0.25},
        2: {"name": "Normal Flow",   "desc": "Balanced pace",                 "pace": 13, "to_mod": 1.00, "reb_mod": 1.00, "fatigue_mod": 1.0, "3pt_bonus": 0.00},
        3: {"name": "Slow and Low",  "desc": "Slow pace, Paint focus",        "pace": 18, "to_mod": 0.90, "reb_mod": 1.05, "fatigue_mod": 0.8, "3pt_bonus": -0.15},
    },
    "DEFENSE": {
        1: {"name": "Aggressive",    "desc": "Pressurizing (High TOs/Fouls)", "opp_to_mult": 1.25, "foul_bonus": 0.04, "fatigue_cost": 1.3, "opp_fg_mod": 0.94},
        2: {"name": "Normal Set",    "desc": "Balanced Defense",              "opp_to_mult": 1.00, "foul_bonus": 0.00, "fatigue_cost": 1.0, "opp_fg_mod": 1.00},
        3: {"name": "Loose/Zone",    "desc": "Protects Paint (High Reb)",     "opp_to_mult": 0.90, "foul_bonus": -0.05, "fatigue_cost": 0.8, "opp_fg_mod": 1.05, "reb_bonus": 1.20},
    }
}

# ==========================================
# CLASS DEFINITIONS
# ==========================================

class Player:
    def __init__(self, row):
        row = {k.strip(): v.strip() for k, v in row.items() if k}
        
        self.name = row.get('Player', 'Unknown').split("\\")[0] 
        self.team = row.get('Team', 'FA')
        self.pos = row.get('Pos', 'G')
        
        try:
            self.games = int(row.get('G', 1))
            self.minutes_total = int(row.get('MP', 10))
            
            fg_val = row.get('FG%', '0.45')
            self.fg_pct = float(fg_val) if fg_val else 0.45
            
            ft_val = row.get('FT%', '0.70')
            self.ft_pct = float(ft_val) if ft_val else 0.70
            
            p3_att = row.get('3PA', '0')
            threes_att = int(p3_att) if p3_att else 0
            self.has_3pt = True if threes_att > 10 else False
            self.threes_season_att = threes_att
            self.threes_season_made = int(row.get('3P', 0)) if row.get('3P') else 0
            p3_pct_val = row.get('3P%', '')
            self.three_pct = float(p3_pct_val) if p3_pct_val else max(0.24, min(0.39, self.fg_pct - 0.12))
            two_pct_val = row.get('2P%', '')
            self.two_pct = float(two_pct_val) if two_pct_val else min(0.62, self.fg_pct + 0.025)
            
            # Rate Stats
            mp = max(1, self.minutes_total)
            self.mpg = mp / max(1, self.games)
            self.target_minutes = self.mpg
            
            fga = int(row.get('FGA', 0)) if row.get('FGA') else 0
            fgm = int(row.get('FG', 0)) if row.get('FG') else 0
            fta = int(row.get('FTA', 0)) if row.get('FTA') else 0
            pts = int(row.get('PTS', 0)) if row.get('PTS') else 0
            tov = int(row.get('TOV', 0)) if row.get('TOV') else 0
            ast = int(row.get('AST', 0)) if row.get('AST') else 0
            orb = int(row.get('ORB', 0)) if row.get('ORB') else 0
            drb = int(row.get('DRB', 0)) if row.get('DRB') else 0
            trb = int(row.get('TRB', 0)) if row.get('TRB') else 0
            stl = int(row.get('STL', 0)) if row.get('STL') else 0
            
            self.fga_season = fga
            self.fgm_season = fgm
            self.fta_season = fta
            self.points_season = pts
            self.three_attempt_rate = threes_att / max(1, fga)
            self.free_throw_rate = fta / max(1, fga)
            self.orb_share = orb / max(1, trb)
            self.lineup_pos = self.normalize_position(self.pos)
            
            # Derived Rates (per minute)
            self.usage_rate = (fga + tov + (0.44 * fta)) / mp
            self.reb_rate = trb / mp
            self.to_rate = tov / mp
            self.ast_rate = ast / mp
            self.stl_rate = stl / mp
            self.points_rate = pts / mp
            
        except Exception as e:
            self.fg_pct = 0.40
            self.mpg = 10
            self.usage_rate = 0.2
            self.reb_rate = 0.1
            self.to_rate = 0.05
            self.ast_rate = 0.05
            self.stl_rate = 0.02
            self.points_rate = 0.2
            self.has_3pt = False
            self.threes_season_att = 0
            self.threes_season_made = 0
            self.three_pct = 0.30
            self.two_pct = 0.45
            self.three_attempt_rate = 0.0
            self.free_throw_rate = 0.25
            self.orb_share = 0.30
            self.target_minutes = self.mpg
            self.lineup_pos = self.normalize_position(self.pos)

        self.stat_minutes = 0.0    
        self.current_fatigue = 0.0 
        self.stint_limit = 5.5 + min(3.5, self.mpg / 12.0)
        
        self.is_fatigued = False
        self.fouled_out = False
        
        self.points = 0
        self.shots = 0
        self.makes = 0
        self.threes_made = 0
        self.threes_att = 0 # Track attempts for analytics
        self.ft_attempts = 0
        self.ft_made = 0
        self.rebounds = 0
        self.turnovers = 0
        self.assists = 0
        self.steals = 0
        self.fouls = 0

        self.card = self.generate_card()

    def normalize_position(self, pos):
        pos = (pos or 'G').upper()
        if 'PG' in pos: return 'PG'
        if 'SG' in pos: return 'SG'
        if 'SF' in pos: return 'SF'
        if 'PF' in pos: return 'PF'
        if 'C' in pos: return 'C'
        if pos == 'G': return 'PG'
        if pos == 'F': return 'SF'
        return 'G'

    def generate_card(self):
        card_data = {}
        valid_rolls = [(d1*10)+d2 for d1 in range(1,7) for d2 in range(1,7)]
        total_makes = int(36 * self.fg_pct)
        
        for i, roll in enumerate(valid_rolls):
            if i < total_makes:
                if self.has_3pt and (roll == 11 or roll == 66 or roll == 12):
                    card_data[roll] = "GOAL_3"
                else:
                    card_data[roll] = "GOAL_2"
            else:
                card_data[roll] = "MISS"
        return card_data
    
    def recover_stamina(self, amount):
        self.current_fatigue = max(0.0, self.current_fatigue - amount)
        if self.current_fatigue < self.stint_limit:
            self.is_fatigued = False

class Team:
    def __init__(self, code, player_list):
        self.code = code
        self.roster = sorted(player_list, key=lambda p: p.mpg, reverse=True)[:12]
        self.roster = self.build_position_balanced_rotation(self.roster)
        self.score = 0
        self.timeouts = 6 
        self.off_strategy = 2
        self.def_strategy = 2
        self.team_fouls = 0
        self.usage_bucket = []
        self.rebuild_usage_bucket()

    def build_position_balanced_rotation(self, players):
        slots = ['PG', 'SG', 'SF', 'PF', 'C']
        starters, used = [], set()
        def fits(slot, p):
            pos = p.lineup_pos
            if slot == pos: return True
            if slot == 'PG': return pos in ('PG', 'G')
            if slot == 'SG': return pos in ('SG', 'PG', 'G', 'SF')
            if slot == 'SF': return pos in ('SF', 'SG', 'PF', 'F')
            if slot == 'PF': return pos in ('PF', 'SF', 'C', 'F')
            if slot == 'C': return pos in ('C', 'PF')
            return False
        for slot in slots:
            candidates = [p for p in players if id(p) not in used and fits(slot, p)]
            if not candidates:
                candidates = [p for p in players if id(p) not in used]
            if candidates:
                pick = max(candidates, key=lambda p: (p.mpg, p.usage_rate))
                pick.lineup_pos = slot
                starters.append(pick); used.add(id(pick))
        bench = [p for p in players if id(p) not in used]
        return starters + bench

    def can_cover_slot(self, bench_p, slot):
        pos = bench_p.lineup_pos
        if pos == slot: return True
        return (slot, pos) in {
            ('PG','SG'), ('SG','PG'), ('SG','SF'), ('SF','SG'),
            ('SF','PF'), ('PF','SF'), ('PF','C'), ('C','PF')
        }

    def rebuild_usage_bucket(self):
        self.usage_bucket = []
        for p in self.roster[:5]:
            weight = int(p.usage_rate * 100)
            if p.is_fatigued: weight = int(weight * 0.5)
            weight = max(1, weight)
            for _ in range(weight):
                self.usage_bucket.append(p)

    def get_lineup(self):
        return self.roster[:5]
    
    def get_bench(self):
        return self.roster[5:]

    def get_shooter(self):
        self.rebuild_usage_bucket()
        if not self.usage_bucket: return self.roster[0]
        return random.choice(self.usage_bucket)

    def sub_check(self, quarter, quiet=True, time_remaining=None, score_diff=0):
        lineup = self.get_lineup()
        subs_made = False
        elapsed_game_min = ((quarter - 1) * 12) + ((720 - time_remaining) / 60.0 if time_remaining is not None else 0)
        close_late = quarter == 4 and (time_remaining or 720) <= 300 and abs(score_diff) <= 10
        garbage_time = quarter == 4 and (time_remaining or 720) <= 360 and abs(score_diff) >= 18

        for i, p in enumerate(list(lineup)):
            force_sub_out = False
            reason = None
            if p.fouls >= 6:
                p.fouled_out = True
                force_sub_out = True; reason = "Fouls"
            elif quarter <= 2 and p.fouls >= 3:
                force_sub_out = True; reason = "Foul Trouble"
            elif quarter == 3 and p.fouls >= 4:
                force_sub_out = True; reason = "Foul Trouble"
            elif p.current_fatigue > p.stint_limit:
                p.is_fatigued = True
                force_sub_out = True; reason = "Fatigue"
            elif not close_late and p.stat_minutes > (p.target_minutes + 2.5):
                force_sub_out = True; reason = "Target Minutes"
            elif garbage_time and p.mpg >= 30 and p.stat_minutes >= max(22, p.target_minutes - 6):
                force_sub_out = True; reason = "Garbage Time"

            # In close final minutes, get the best available player back in each slot.
            if close_late and not force_sub_out:
                best_idx = -1
                for j, bench_p in enumerate(self.roster[5:], start=5):
                    if bench_p.fouled_out or bench_p.current_fatigue > bench_p.stint_limit * 1.25: continue
                    if not self.can_cover_slot(bench_p, p.lineup_pos): continue
                    if bench_p.mpg > p.mpg + 5:
                        best_idx = j; break
                if best_idx != -1:
                    sub_in = self.roster[best_idx]
                    sub_in.lineup_pos = p.lineup_pos
                    if not quiet: print(f"{Colors.CYAN}   [ROTATION] {self.code}: {sub_in.name} returns for {p.name}{Colors.RESET}")
                    self.roster[i], self.roster[best_idx] = self.roster[best_idx], self.roster[i]
                    subs_made = True
                    continue

            if force_sub_out:
                best_sub_idx = -1
                best_score = -999
                slot = p.lineup_pos
                for j, bench_p in enumerate(self.roster[5:], start=5):
                    if bench_p.fouled_out: continue
                    if quarter <= 3 and bench_p.fouls >= 4: continue
                    if not self.can_cover_slot(bench_p, slot): continue
                    under_target = bench_p.target_minutes - bench_p.stat_minutes
                    fatigue_penalty = bench_p.current_fatigue * 1.7
                    garbage_bonus = 12 if garbage_time and bench_p.mpg < 18 else 0
                    score = under_target + (bench_p.mpg * 0.12) - fatigue_penalty + garbage_bonus
                    if score > best_score:
                        best_score = score; best_sub_idx = j
                if best_sub_idx == -1:
                    for j, bench_p in enumerate(self.roster[5:], start=5):
                        if not bench_p.fouled_out:
                            best_sub_idx = j; break
                if best_sub_idx != -1:
                    sub_in = self.roster[best_sub_idx]
                    sub_in.lineup_pos = slot
                    if not quiet: print(f"{Colors.CYAN}   [SUB] {self.code}: {sub_in.name} IN, {p.name} OUT ({reason}){Colors.RESET}")
                    self.roster[i], self.roster[best_sub_idx] = self.roster[best_sub_idx], self.roster[i]
                    subs_made = True
        if subs_made:
            self.rebuild_usage_bucket()

    def get_rebounder(self, strategy_mult=1.0):
        bucket = []
        for p in self.get_lineup():
            weight = int(p.reb_rate * 100 * strategy_mult)
            weight = max(1, weight)
            for _ in range(weight):
                bucket.append(p)
        if not bucket: return self.roster[0]
        return random.choice(bucket)

    def get_assister(self, shooter):
        bucket = []
        for p in self.get_lineup():
            if p.name == shooter.name: continue
            weight = int(p.ast_rate * 100)
            weight = max(1, weight)
            for _ in range(weight):
                bucket.append(p)
        if not bucket: return None
        return random.choice(bucket)

    def get_stealer(self):
        bucket = []
        for p in self.get_lineup():
            weight = int(p.stl_rate * 100)
            weight = max(1, weight)
            for _ in range(weight):
                bucket.append(p)
        if not bucket: return self.roster[0]
        return random.choice(bucket)
    
    def call_timeout(self):
        if self.timeouts > 0:
            self.timeouts -= 1
            for p in self.get_lineup():
                p.recover_stamina(4.0) 
            return True
        return False
        
    def recover_bench(self, minutes):
        for p in self.get_bench():
            p.current_fatigue = max(0.0, p.current_fatigue - (minutes * 2.0))
            if p.current_fatigue < p.stint_limit:
                p.is_fatigued = False
    
    def get_team_stats(self):
        # Helper for DevTools
        s = {"PTS": self.score, "FGA": 0, "FGM": 0, "3PA": 0, "3PM": 0, "FTA": 0, "FTM": 0, "REB": 0, "AST": 0, "STL": 0, "TOV": 0, "PF": 0}
        for p in self.roster:
            s["FGA"] += p.shots
            s["FGM"] += p.makes
            s["3PA"] += p.threes_att
            s["3PM"] += p.threes_made
            s["FTA"] += p.ft_attempts
            s["FTM"] += p.ft_made
            s["REB"] += p.rebounds
            s["AST"] += p.assists
            s["STL"] += p.steals
            s["TOV"] += p.turnovers
            s["PF"]  += p.fouls
        return s

# ==========================================
# DATA LOADER
# ==========================================

def find_stats_file():
    for f in POSSIBLE_FILES:
        if os.path.exists(f): return f
    return None

def load_data():
    filepath = find_stats_file()
    if not filepath:
        print(f"{Colors.RED}CRITICAL ERROR: Could not find stats file {POSSIBLE_FILES}{Colors.RESET}")
        sys.exit(1)
    
    print(f"{Colors.BLUE}Loading {filepath}...{Colors.RESET}")
    teams = {} 
    
    try:
        with open(filepath, mode='r', encoding='utf-8-sig', errors='replace') as f:
            lines = f.readlines()
            start_index = 0
            for i, line in enumerate(lines):
                if "Player" in line and "Team" in line:
                    start_index = i
                    break

            valid_data = lines[start_index:]
            reader = csv.DictReader(valid_data)
            for row in reader:
                if row.get('Player') == 'Player': continue
                t_code = row.get('Team')
                if not t_code or t_code == 'TOT': continue

                p = Player(row)
                if t_code not in teams: teams[t_code] = []
                teams[t_code].append(p)

    except FileNotFoundError:
        print(f"{Colors.RED}Error: Could not find stats.csv. Please ensure the data file is in the same directory as main.py.{Colors.RESET}")
        sys.exit(1)
    except csv.Error as e:
        print(f"{Colors.RED}Error: Malformed CSV data in {filepath}. {e}{Colors.RESET}")
        print(f"{Colors.RED}Please ensure the CSV file is properly formatted.{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}Read Error: {e}{Colors.RESET}")
        sys.exit(1)

    return {k: v for k, v in teams.items() if len(v) >= 5}

# ==========================================
# UTILS & DISPLAY
# ==========================================

def print_pbp(msg, type="NORMAL"):
    prefix = "  > "
    color = Colors.RESET
    if type == "SCORE": color = Colors.GREEN
    elif type == "MISS": color = Colors.RED + Colors.DIM
    elif type == "TO": color = Colors.RED
    elif type == "STL": color = Colors.CYAN
    elif type == "FOUL": color = Colors.YELLOW
    elif type == "REB": color = Colors.BLUE + Colors.DIM
    elif type == "ALERT": color = Colors.MAGENTA + Colors.BOLD
    print(f"{color}{prefix}{msg}{Colors.RESET}")

def scoreboard(v_team, h_team, quarter, time_rem):
    mins = int(time_rem // 60)
    secs = int(time_rem % 60)
    print(f"\n{Colors.BLUE}" + "*"*40)
    print(f"  Q{quarter} | {mins:02d}:{secs:02d} | {v_team.code}: {v_team.score} - {h_team.code}: {h_team.score}")
    print("*"*40 + f"{Colors.RESET}\n")

def quarter_break_menu(v_team, h_team, next_q, game_mode):
    if game_mode >= 3: return
    print(f"\n{Colors.BOLD}=== END OF QUARTER {next_q - 1} ==={Colors.RESET}")
    print(f"SCORE: {v_team.code} {v_team.score} - {h_team.code} {h_team.score}")
    print(f"\n{Colors.YELLOW}--- COACHING ADJUSTMENTS FOR Q{next_q} ---{Colors.RESET}")
    print(f"\n[VISITOR] {v_team.code} Strategy:")
    print(f"Current: Off={STRATEGIES['OFFENSE'][v_team.off_strategy]['name']}, Def={STRATEGIES['DEFENSE'][v_team.def_strategy]['name']}")
    ch = input("Change? (y/n): ")
    if ch.lower() == 'y':
        try: v_team.off_strategy = int(input("Offense (1-Run, 2-Norm, 3-Slow): "))
        except: pass
        try: v_team.def_strategy = int(input("Defense (1-Aggr, 2-Norm, 3-Loose): "))
        except: pass
    print(f"\n[HOME] {h_team.code} Strategy:")
    print(f"Current: Off={STRATEGIES['OFFENSE'][h_team.off_strategy]['name']}, Def={STRATEGIES['DEFENSE'][h_team.def_strategy]['name']}")
    ch = input("Change? (y/n): ")
    if ch.lower() == 'y':
        try: h_team.off_strategy = int(input("Offense (1-Run, 2-Norm, 3-Slow): "))
        except: pass
        try: h_team.def_strategy = int(input("Defense (1-Aggr, 2-Norm, 3-Loose): "))
        except: pass
    print("\nResuming Game...")
    time.sleep(1)

def change_strategy_menu(team):
    print(f"\n{Colors.YELLOW}--- CHANGE STRATEGY: {team.code} ---{Colors.RESET}")
    print(f"Current: Off={STRATEGIES['OFFENSE'][team.off_strategy]['name']}, Def={STRATEGIES['DEFENSE'][team.def_strategy]['name']}")
    print("1. Change Offense")
    print("2. Change Defense")
    print("3. Cancel")
    ch = input("Choice: ")
    if ch == '1':
        print("1. Run and Shoot  2. Normal Flow  3. Slow and Low")
        try: team.off_strategy = int(input("Select: "))
        except: pass
    elif ch == '2':
        print("1. Aggressive  2. Normal Set  3. Loose/Zone")
        try: team.def_strategy = int(input("Select: "))
        except: pass

def print_box_score(team_v, team_h):
    print(f"\n{Colors.BOLD}{'='*100}")
    print(f"FINAL BOX SCORE | {team_v.code} {team_v.score} - {team_h.code} {team_h.score}")
    print(f"{'='*100}{Colors.RESET}")
    for t in [team_v, team_h]:
        print(f"\n{Colors.BOLD}--- {t.code} ({t.score} pts) ---{Colors.RESET}")
        print(f"{'PLAYER':<20} {'PTS':<4} {'REB':<4} {'AST':<4} {'STL':<4} {'TO':<4} {'3PM':<4} {'FT':<6} {'PF':<4} {'MIN'}")
        print("-" * 95)
        display_roster = sorted(t.roster, key=lambda x: x.points, reverse=True)
        for p in display_roster:
            if p.stat_minutes > 0.5: 
                ft = f"{p.ft_made}-{p.ft_attempts}"
                print(f"{p.name:<20} {p.points:<4} {p.rebounds:<4} {p.assists:<4} {p.steals:<4} {p.turnovers:<4} {p.threes_made:<4} {ft:<6} {p.fouls:<4} {int(p.stat_minutes)}")
    print("\n")


# ==========================================
# RETRO-MODERN PRESENTATION LAYER
# ==========================================

TEAM_NAMES = {
    "ATL": "Hawks", "BOS": "Celtics", "CHH": "Hornets", "CHI": "Bulls",
    "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets", "DET": "Pistons",
    "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers",
    "LAL": "Lakers", "MIA": "Heat", "MIL": "Bucks", "NJN": "Nets",
    "NYK": "Knicks", "PHI": "76ers", "PHO": "Suns", "POR": "Blazers",
    "SAC": "Kings", "SAS": "Spurs", "SEA": "Sonics", "UTA": "Jazz", "WSB": "Bullets",
}


def team_display_name(code):
    return TEAM_NAMES.get(code, code)


def format_clock(time_remaining):
    mins = int(time_remaining // 60)
    secs = int(time_remaining % 60)
    return f"{mins}:{secs:02d}"


def fit_text(text, width):
    text = str(text)
    if len(text) <= width:
        return text.ljust(width)
    return text[:max(0, width - 1)] + "…"


def roster_panel(team, title_width=30):
    """Return old-PC style roster lines with starters and bench plus Pts/PF/Min."""
    lines = [f"{team_display_name(team.code):<{title_width-11}} {'Pts':>3} {'PF':>2} {'Min':>3}"]
    lineup = team.get_lineup()
    bench = team.get_bench()
    for idx, p in enumerate(lineup, start=1):
        lines.append(f"{idx:<2}{fit_text(p.name.upper(), title_width-15)} {p.points:>3} {p.fouls:>2} {int(p.stat_minutes):>3}")
    lines.append("─" * title_width)
    for idx, p in enumerate(bench[:7]):
        label = chr(ord('A') + idx)
        lines.append(f"{label:<2}{fit_text(p.name.upper(), title_width-15)} {p.points:>3} {p.fouls:>2} {int(p.stat_minutes):>3}")
    while len(lines) < 14:
        lines.append("".ljust(title_width))
    return [line[:title_width].ljust(title_width) for line in lines]


def render_modern_court(width=64):
    """Modernized terminal hardwood inside a retro DOS frame."""
    inner = width - 2
    center = inner // 2
    court = []
    court.append("╔" + "═" * inner + "╗")
    court.append("║" + fit_text("MODERN NBA COURT", inner).center(inner) + "║")
    rows = [list(" " * inner) for _ in range(15)]
    # midcourt and center logo
    for y in range(len(rows)):
        rows[y][center] = "│"
    rows[7][center-1:center+2] = list("◎│")[:3]
    # paint boxes
    for side_x in (4, inner - 17):
        rows[4][side_x:side_x+13] = list("┌───────────┐")
        rows[5][side_x:side_x+13] = list("│   PAINT   │")
        rows[6][side_x:side_x+13] = list("│           │")
        rows[7][side_x:side_x+13] = list("└───────────┘")
    # modern arc/restricted-area impression
    left_arc = [
        (2, 20, "╭"), (3, 18, "╭"), (4, 17, "│"), (5, 17, "│"),
        (6, 18, "╰"), (7, 20, "╰"),
    ]
    right_arc = [(y, inner - x - 1, ch.replace("╭", "╮").replace("╰", "╯")) for y, x, ch in left_arc]
    for y, x, ch in left_arc + right_arc:
        if 0 <= y < len(rows) and 0 <= x < inner:
            rows[y][x] = ch
    rows[6][10] = "◦"; rows[6][inner-11] = "◦"
    rows[7][11] = "◦"; rows[7][inner-12] = "◦"
    for row in rows:
        court.append("║" + "".join(row) + "║")
    court.append("╚" + "═" * inner + "╝")
    return court


def render_scoreboard(v_team, h_team, quarter, time_remaining, shot_clock=24):
    return [
        "┌──────────────────────── SCOREBOARD ────────────────────────┐",
        f"│ {team_display_name(v_team.code):<16} {v_team.score:>3}   Qtr {quarter:^3}   {team_display_name(h_team.code):>16} {h_team.score:>3} │",
        f"│ {'':<20} {format_clock(time_remaining):^11}  :{shot_clock:02d} {'':>20} │",
        "└────────────────────────────────────────────────────────────┘",
    ]


def render_game_screen(v_team, h_team, quarter, time_remaining, shot_clock=24, pbp_lines=None):
    """Render the screenshot-inspired DOS shell with a modern NBA court.

    The reference screenshot uses black space, side roster panels, a top scoreboard,
    side timeout/foul blocks, and a bottom PBP crawl. This keeps that old-PC
    layout while making the court more modern and readable in a terminal.
    """
    pbp_lines = list(pbp_lines or [])[-8:]
    left = roster_panel(v_team)
    right = roster_panel(h_team)
    board = render_scoreboard(v_team, h_team, quarter, time_remaining, shot_clock)
    court = render_modern_court()
    blank = " " * 30
    lines = []
    for i in range(max(len(left), len(right), len(board))):
        l = left[i] if i < len(left) else blank
        mid = board[i] if i < len(board) else " " * len(board[0])
        r = right[i] if i < len(right) else blank
        lines.append(f"{l} {mid} {r}")
    lines.append(f"{'Time':<30} {'':^64} {'Time':>30}")
    lines.append(f"{'Outs':<30} {'':^64} {'Outs':>30}")
    lines.append(f"{v_team.timeouts:<30} {'':^64} {h_team.timeouts:>30}")
    lines.append(f"{'Team':<30} {'':^64} {'Team':>30}")
    lines.append(f"{'Fouls':<30} {'':^64} {'Fouls':>30}")
    lines.append(f"{v_team.team_fouls:<30} {'':^64} {h_team.team_fouls:>30}")
    for row in court:
        lines.append(" " * 32 + row)
    lines.append("┌" + "─" * 96 + "┐")
    lines.append("│" + "PLAY-BY-PLAY".center(96) + "│")
    for msg in pbp_lines:
        lines.append("│ " + fit_text(msg, 94) + " │")
    while len(pbp_lines) < 6:
        pbp_lines.append("")
        lines.append("│ " + " " * 94 + " │")
    lines.append("└" + "─" * 96 + "┘")
    return "\n".join(lines)


# ==========================================
# SEASON STATS / RECORDS
# ==========================================

class SeasonStore:
    def __init__(self, db_path="season.sqlite3"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_schema()

    def create_schema(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seasons (
                name TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_name TEXT NOT NULL,
                played_at TEXT NOT NULL,
                visitor TEXT NOT NULL,
                home TEXT NOT NULL,
                visitor_score INTEGER NOT NULL,
                home_score INTEGER NOT NULL,
                winner TEXT NOT NULL,
                loser TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_game_stats (
                game_id INTEGER NOT NULL,
                season_name TEXT NOT NULL,
                team TEXT NOT NULL,
                opponent TEXT NOT NULL,
                points INTEGER NOT NULL,
                fgm INTEGER, fga INTEGER, three_pm INTEGER, three_pa INTEGER,
                ftm INTEGER, fta INTEGER, rebounds INTEGER, assists INTEGER,
                steals INTEGER, turnovers INTEGER, fouls INTEGER,
                win INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS player_game_stats (
                game_id INTEGER NOT NULL,
                season_name TEXT NOT NULL,
                team TEXT NOT NULL,
                player TEXT NOT NULL,
                minutes REAL NOT NULL,
                PTS INTEGER, REB INTEGER, AST INTEGER, STL INTEGER, TOV INTEGER,
                FGM INTEGER, FGA INTEGER, TPM INTEGER, TPA INTEGER, FTM INTEGER,
                FTA INTEGER, PF INTEGER
            )
        """)
        self.conn.commit()

    def start_season(self, name="1988-89"):
        self.conn.execute(
            "INSERT OR IGNORE INTO seasons(name, created_at) VALUES (?, ?)",
            (name, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def record_game(self, visitor_team, home_team, season_name="1988-89"):
        self.start_season(season_name)
        winner = visitor_team.code if visitor_team.score >= home_team.score else home_team.code
        loser = home_team.code if winner == visitor_team.code else visitor_team.code
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO games(season_name, played_at, visitor, home, visitor_score, home_score, winner, loser)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (season_name, datetime.now().isoformat(timespec="seconds"), visitor_team.code, home_team.code,
             visitor_team.score, home_team.score, winner, loser),
        )
        game_id = cur.lastrowid
        for team, opponent in ((visitor_team, home_team), (home_team, visitor_team)):
            stats = team.get_team_stats()
            cur.execute(
                """INSERT INTO team_game_stats(game_id, season_name, team, opponent, points, fgm, fga, three_pm, three_pa,
                   ftm, fta, rebounds, assists, steals, turnovers, fouls, win)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (game_id, season_name, team.code, opponent.code, team.score, stats["FGM"], stats["FGA"], stats["3PM"],
                 stats["3PA"], stats["FTM"], stats["FTA"], stats["REB"], stats["AST"], stats["STL"], stats["TOV"],
                 stats["PF"], 1 if team.code == winner else 0),
            )
            for p in team.roster:
                if p.stat_minutes <= 0 and p.points == 0 and p.rebounds == 0 and p.assists == 0:
                    continue
                cur.execute(
                    """INSERT INTO player_game_stats(game_id, season_name, team, player, minutes, PTS, REB, AST, STL, TOV,
                       FGM, FGA, TPM, TPA, FTM, FTA, PF)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (game_id, season_name, team.code, p.name, p.stat_minutes, p.points, p.rebounds, p.assists, p.steals,
                     p.turnovers, p.makes, p.shots, p.threes_made, p.threes_att, p.ft_made, p.ft_attempts, p.fouls),
                )
        self.conn.commit()
        return int(game_id)

    def get_standings(self, season_name="1988-89"):
        rows = self.conn.execute(
            """
            SELECT team,
                   SUM(win) AS wins,
                   SUM(CASE WHEN win=1 THEN 0 ELSE 1 END) AS losses,
                   SUM(points) AS points_for,
                   SUM((SELECT points FROM team_game_stats t2 WHERE t2.game_id=t.game_id AND t2.team=t.opponent)) AS points_against
            FROM team_game_stats t
            WHERE season_name=?
            GROUP BY team
            ORDER BY wins DESC, losses ASC, team ASC
            """,
            (season_name,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_player_leaders(self, stat="PTS", season_name="1988-89", limit=10):
        allowed = {"PTS", "REB", "AST", "STL", "TOV", "FGM", "FGA", "TPM", "TPA", "FTM", "FTA", "PF"}
        stat = stat.upper()
        if stat not in allowed:
            raise ValueError(f"Unsupported stat: {stat}")
        rows = self.conn.execute(
            f"""
            SELECT player, team, COUNT(*) AS GP, SUM(minutes) AS MIN, SUM({stat}) AS {stat}
            FROM player_game_stats
            WHERE season_name=?
            GROUP BY player, team
            ORDER BY SUM({stat}) DESC, player ASC
            LIMIT ?
            """,
            (season_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def export_standings_csv(self, path, season_name="1988-89"):
        rows = self.get_standings(season_name)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["team", "wins", "losses", "points_for", "points_against"])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def close(self):
        self.conn.close()


def print_standings(rows):
    print(f"\n{Colors.BOLD}TEAM STANDINGS{Colors.RESET}")
    print(f"{'TEAM':<6} {'W':>3} {'L':>3} {'PF':>6} {'PA':>6}")
    print("-" * 28)
    for r in rows:
        print(f"{r['team']:<6} {r['wins']:>3} {r['losses']:>3} {r['points_for']:>6} {r['points_against']:>6}")


def print_player_leaders(rows, stat="PTS"):
    print(f"\n{Colors.BOLD}PLAYER LEADERS - {stat.upper()}{Colors.RESET}")
    print(f"{'PLAYER':<22} {'TM':<4} {'GP':>3} {stat.upper():>6}")
    print("-" * 40)
    for r in rows:
        print(f"{r['player']:<22} {r['team']:<4} {r['GP']:>3} {int(r[stat.upper()] or 0):>6}")

# ==========================================
# DEVTOOLS & BENCHMARKING
# ==========================================

def run_benchmark_suite(rosters):
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}=== APBA LEAGUE BENCHMARK SUITE ==={Colors.RESET}")
    try:
        n_games = int(input("How many games to simulate? (e.g. 100): "))
    except: n_games = 100
    
    print(f"Simulating {n_games} games... (This may take a moment)")
    
    start_time = time.time()
    
    # Accumulators
    total_pts = 0
    total_fgm = 0
    total_fga = 0
    total_3pm = 0
    total_3pa = 0
    total_ftm = 0
    total_fta = 0
    total_reb = 0
    total_ast = 0
    total_stl = 0
    total_tov = 0
    total_pf = 0
    
    team_codes = list(rosters.keys())
    
    for _ in range(n_games):
        # Pick 2 random teams
        c1, c2 = random.sample(team_codes, 2)
        v = Team(c1, copy.deepcopy(rosters[c1]))
        h = Team(c2, copy.deepcopy(rosters[c2]))
        
        # Randomize Strategies for variety
        v.off_strategy = random.randint(1, 3)
        v.def_strategy = random.randint(1, 3)
        h.off_strategy = random.randint(1, 3)
        h.def_strategy = random.randint(1, 3)
        
        # Run silent game (Mode 4 = Silent)
        play_game(v, h, game_mode=4, silent=True)
        
        # Harvest Stats
        vs = v.get_team_stats()
        hs = h.get_team_stats()
        
        for s in [vs, hs]:
            total_pts += s["PTS"]
            total_fgm += s["FGM"]
            total_fga += s["FGA"]
            total_3pm += s["3PM"]
            total_3pa += s["3PA"]
            total_ftm += s["FTM"]
            total_fta += s["FTA"]
            total_reb += s["REB"]
            total_ast += s["AST"]
            total_stl += s["STL"]
            total_tov += s["TOV"]
            total_pf  += s["PF"]

    end_time = time.time()
    duration = end_time - start_time
    total_teams_played = n_games * 2
    
    # Calculate Averages (Per Team Per Game)
    avg_pts = total_pts / total_teams_played
    avg_fga = total_fga / total_teams_played
    avg_fgm = total_fgm / total_teams_played
    avg_fg_pct = avg_fgm / avg_fga if avg_fga > 0 else 0
    
    avg_3pa = total_3pa / total_teams_played
    avg_3pm = total_3pm / total_teams_played
    avg_3p_pct = avg_3pm / avg_3pa if avg_3pa > 0 else 0
    
    avg_fta = total_fta / total_teams_played
    avg_ftm = total_ftm / total_teams_played
    avg_ft_pct = avg_ftm / avg_fta if avg_fta > 0 else 0
    
    avg_reb = total_reb / total_teams_played
    avg_ast = total_ast / total_teams_played
    avg_stl = total_stl / total_teams_played
    avg_tov = total_tov / total_teams_played
    avg_pf  = total_pf  / total_teams_played
    
    # REPORT
    print(f"\n{Colors.GREEN}{Colors.BOLD}--- BENCHMARK REPORT ---{Colors.RESET}")
    print(f"Total Time: {duration:.2f}s ({n_games/duration:.1f} games/sec)")
    print(f"{'STAT':<10} {'SIM AVG':<10} {'1989 AVG':<10} {'DIFF':<10}")
    print("-" * 45)
    
    def print_stat(label, sim_val, real_val, is_pct=False):
        if is_pct:
            diff = (sim_val - real_val) * 100
            print(f"{label:<10} {sim_val:.3f}      {real_val:.3f}      {diff:+.1f}%")
        else:
            diff = sim_val - real_val
            print(f"{label:<10} {sim_val:<10.1f} {real_val:<10.1f} {diff:+.1f}")
            
    print_stat("PTS", avg_pts, NBA_1989_STATS["PTS"])
    print_stat("FG%", avg_fg_pct, NBA_1989_STATS["FG%"], True)
    print_stat("3PA", avg_3pa, NBA_1989_STATS["3PA"])
    print_stat("3P%", avg_3p_pct, NBA_1989_STATS["3P%"], True)
    print_stat("FT%", avg_ft_pct, NBA_1989_STATS["FT%"], True)
    print_stat("REB", avg_reb, NBA_1989_STATS["TRB"])
    print_stat("AST", avg_ast, NBA_1989_STATS["AST"])
    print_stat("STL", avg_stl, NBA_1989_STATS["STL"])
    print_stat("TOV", avg_tov, NBA_1989_STATS["TOV"])
    print_stat("PF",  avg_pf,  NBA_1989_STATS["PF"])
    
    print("-" * 45)
    print("NOTE: Diff shows variance from real 1989 league stats.")
    input("\nPress Enter to return to menu...")

# ==========================================
# MAIN GAME LOOP
# ==========================================

def play_game(team_v, team_h, game_mode, silent=False):
    if not silent:
        print(f"\n{Colors.BOLD}*** TIP OFF: {team_v.code} vs {team_h.code} ***{Colors.RESET}")
    
    # Strategy Input (Skip if silent)
    if not silent:
        print(f"\n{Colors.YELLOW}--- PRE-GAME COACHING ---{Colors.RESET}")
        print(f"[VISITOR] {team_v.code}")
        print("Offense (1-Run, 2-Norm, 3-Slow): ", end="")
        try: team_v.off_strategy = int(input())
        except: team_v.off_strategy = 2
        print("Defense (1-Aggr, 2-Norm, 3-Loose): ", end="")
        try: team_v.def_strategy = int(input())
        except: team_v.def_strategy = 2

        print(f"\n[HOME] {team_h.code}")
        print("Offense (1-Run, 2-Norm, 3-Slow): ", end="")
        try: team_h.off_strategy = int(input())
        except: team_h.off_strategy = 2
        print("Defense (1-Aggr, 2-Norm, 3-Loose): ", end="")
        try: team_h.def_strategy = int(input())
        except: team_h.def_strategy = 2

    possession = team_v
    defense = team_h
    
    home_momentum_streak = 0
    crowd_active = False

    for quarter in range(1, 5):
        time_remaining = 720
        team_v.team_fouls = 0
        team_h.team_fouls = 0
        if game_mode < 3 and not silent:
            scoreboard(team_v, team_h, quarter, 720)
        
        while time_remaining > 0:
            
            # Interactive Mode Logic
            if game_mode == 1 and not silent:
                user_in = input(f"{Colors.DIM}[ENTER] Next Play | [S] Strategy | [Q] Quit > {Colors.RESET}")
                if user_in.lower() == 's':
                    print("Which team?")
                    print(f"1. {team_v.code}")
                    print(f"2. {team_h.code}")
                    tm_ch = input("Choice: ")
                    if tm_ch == '1': change_strategy_menu(team_v)
                    elif tm_ch == '2': change_strategy_menu(team_h)
                elif user_in.lower() == 'q':
                    return 

            defense = team_h if possession == team_v else team_v
            
            # Momentum / Crowd
            if possession == team_h:
                if home_momentum_streak >= 3:
                    if not crowd_active:
                        if not silent and game_mode != 3: print_pbp("!!! THE CROWD ERUPTS !!! (Defense Bonus Active)", "ALERT")
                        crowd_active = True
            else:
                if crowd_active:
                    if team_v.timeouts > 0:
                        if random.random() < 0.40:
                            if team_v.call_timeout():
                                if not silent and game_mode != 3: print_pbp(f"[TIMEOUT] {team_v.code} calls timeout to SILENCE the crowd!", "ALERT")
                                crowd_active = False
                                home_momentum_streak = 0
            
            off_strat = STRATEGIES["OFFENSE"][possession.off_strategy]
            def_strat = STRATEGIES["DEFENSE"][defense.def_strategy]
            pace = off_strat["pace"]
            
            shooter = possession.get_shooter()
            
            elapsed_mins = pace / 60.0
            
            # Stats updates
            for p in possession.get_lineup(): 
                p.stat_minutes += elapsed_mins
                p.current_fatigue += elapsed_mins
            for p in defense.get_lineup():    
                p.stat_minutes += elapsed_mins
                p.current_fatigue += elapsed_mins
            
            possession.recover_bench(elapsed_mins)
            defense.recover_bench(elapsed_mins)
            
            retain_possession = False

            # Non-shooting defensive foul / hand-check. In the bonus, it becomes free throws.
            non_shoot_foul = 0.058 + def_strat["foul_bonus"] * 0.35
            if random.random() < max(0.015, non_shoot_foul):
                fouler = defense.get_rebounder()
                fouler.fouls += 1
                defense.team_fouls += 1
                if not silent and game_mode != 3: print_pbp(f"{defense.code}: Foul away from the shot on {fouler.name}.", "FOUL")
                if defense.team_fouls >= 5:
                    made = sum(1 for _ in range(2) if random.random() < shooter.ft_pct)
                    possession.score += made
                    shooter.points += made
                    shooter.ft_made += made
                    shooter.ft_attempts += 2
                    if not silent and game_mode != 3: print_pbp(f"Bonus free throws for {shooter.name}: {made}/2", "SCORE" if made else "MISS")
                    possession = defense
                    time_remaining -= pace
                    continue

            # Turnover Check -- tuned to 1988-89 basketball (more turnovers than modern NBA).
            to_chance = (0.105 + shooter.to_rate * 0.55) * off_strat["to_mod"] * def_strat["opp_to_mult"]
            if crowd_active and possession == team_v: to_chance *= 1.08
            to_chance = min(0.245, max(0.055, to_chance))
            if random.random() < to_chance:
                shooter.turnovers += 1
                if random.random() < 0.56:
                    stealer = defense.get_stealer()
                    stealer.steals += 1
                    msg = random.choice(TEXT_STL)
                    if not silent and game_mode != 3: print_pbp(f"{possession.code}: {shooter.name} {msg} (Stl: {stealer.name})", "STL")
                else:
                    msg = random.choice(TEXT_TO)
                    if not silent and game_mode != 3: print_pbp(f"{possession.code}: {shooter.name} {msg}. Turnover.", "TO")
                if possession == team_h:
                    home_momentum_streak = 0
                    if crowd_active:
                        if not silent and game_mode != 3: print_pbp("(The crowd groans... quieted)", "ALERT")
                        crowd_active = False
                else:
                    home_momentum_streak += 1
                possession = defense
                time_remaining -= pace
                continue

            # Shot selection based on real 3PA/FGA rates, nudged by coaching strategy.
            three_mult = 1.45 if possession.off_strategy == 1 else (0.62 if possession.off_strategy == 3 else 1.0)
            three_chance = min(0.42, shooter.three_attempt_rate * three_mult)
            is_three = shooter.has_3pt and random.random() < three_chance
            drive_or_post = random.random() < (0.38 + min(0.18, shooter.free_throw_rate * 0.18))

            # Shooting foul before release. Three-point fouls get 3 shots; drives/posts draw more contact.
            foul_prob = 0.092 + min(0.065, shooter.free_throw_rate * 0.09) + def_strat["foul_bonus"]
            if drive_or_post: foul_prob += 0.025
            if is_three: foul_prob -= 0.025
            foul_prob = max(0.025, min(0.18, foul_prob))
            if random.random() < foul_prob:
                fouler = defense.get_rebounder()
                fouler.fouls += 1
                defense.team_fouls += 1
                ft_count = 3 if is_three else 2
                made = sum(1 for _ in range(ft_count) if random.random() < shooter.ft_pct)
                possession.score += made
                shooter.points += made
                shooter.ft_made += made
                shooter.ft_attempts += ft_count
                if not silent and game_mode != 3: print_pbp(f"{defense.code}: Shooting foul. {shooter.name} shoots {made}/{ft_count}.", "FOUL")
                if possession == team_h: home_momentum_streak = 0
                possession = defense
                time_remaining -= pace
                continue

            # Resolve field goal with era stats and defensive pressure.
            shooter.shots += 1
            if is_three: shooter.threes_att += 1
            base_pct = shooter.three_pct if is_three else shooter.two_pct
            if shooter.is_fatigued: base_pct -= 0.035
            if drive_or_post and not is_three and possession.off_strategy == 3: base_pct += 0.015
            if crowd_active and possession == team_v: base_pct -= 0.018
            # Aggressive defense contests shots; loose defense concedes cleaner jumpers but fewer fouls.
            if def_strat["opp_fg_mod"] < 1.0: base_pct -= 0.018
            elif def_strat["opp_fg_mod"] > 1.0: base_pct += 0.012
            make_chance = max(0.24 if is_three else 0.34, min(0.67, base_pct))
            made_fg = random.random() < make_chance

            if made_fg:
                pts = 3 if is_three else 2
                possession.score += pts
                shooter.points += pts
                shooter.makes += 1
                if is_three: shooter.threes_made += 1

                # And-one chance, mostly on drives/posts.
                and_one_chance = 0.022 + (0.025 if drive_or_post and not is_three else 0.0) + max(0, def_strat["foul_bonus"] * 0.25)
                if random.random() < and_one_chance:
                    fouler = defense.get_rebounder()
                    fouler.fouls += 1
                    defense.team_fouls += 1
                    shooter.ft_attempts += 1
                    if random.random() < shooter.ft_pct:
                        shooter.ft_made += 1
                        shooter.points += 1
                        possession.score += 1
                    if not silent and game_mode != 3: print_pbp("   And one!", "FOUL")

                assist_msg = ""
                if random.random() < 0.62:
                    assister = possession.get_assister(shooter)
                    if assister:
                        assister.assists += 1
                        assist_msg = f" (Ast: {assister.name})"
                if is_three:
                    msg = random.choice(TEXT_3PT)
                elif drive_or_post and shooter.fg_pct > 0.48 and random.random() < 0.33:
                    msg = random.choice(TEXT_DUNK)
                else:
                    msg = random.choice(TEXT_MAKE)
                if not silent and game_mode != 3: print_pbp(f"{possession.code}: {shooter.name} {msg} {assist_msg}", "SCORE")
                if possession == team_h: home_momentum_streak += 1
                else:
                    home_momentum_streak = 0
                    if crowd_active:
                        if not silent and game_mode != 3: print_pbp(f">>> {shooter.name} SILENCES THE CROWD!", "ALERT")
                        crowd_active = False
            else:
                msg = random.choice(TEXT_MISS)
                if not silent and game_mode != 3: print_pbp(f"{possession.code}: {shooter.name} {msg}.", "MISS")
                def_reb_advantage = 0.705 * def_strat.get("reb_bonus", 1.0) / max(0.85, off_strat["reb_mod"])
                def_reb_advantage = max(0.60, min(0.82, def_reb_advantage))
                if random.random() < def_reb_advantage:
                    r = defense.get_rebounder()
                    r.rebounds += 1
                    msg_r = random.choice(TEXT_REB)
                    if not silent and game_mode != 3: print_pbp(f"   {defense.code}: {r.name} {msg_r}.", "REB")
                    if possession == team_v: home_momentum_streak += 1
                else:
                    r = possession.get_rebounder(strategy_mult=1.15)
                    r.rebounds += 1
                    retain_possession = True
                    if not silent and game_mode != 3: print_pbp(f"   {possession.code}: {r.name} grabs the OFFENSIVE board!", "REB")
                    if possession == team_v: home_momentum_streak = 0
            possession = possession if retain_possession else defense
            time_remaining -= (5 if retain_possession else pace)
            
            # Subs Check
            quiet_subs = True if (game_mode == 3 or silent) else False
            if int(time_remaining) % 60 < 15:
                team_v.sub_check(quarter, quiet=quiet_subs, time_remaining=time_remaining, score_diff=team_v.score - team_h.score)
                team_h.sub_check(quarter, quiet=quiet_subs, time_remaining=time_remaining, score_diff=team_h.score - team_v.score)
        
        if not silent and quarter < 4:
            quarter_break_menu(team_v, team_h, quarter + 1, game_mode)
            
    if not silent:
        print_box_score(team_v, team_h)

def main():
    print(f"\n{Colors.BOLD}==================================")
    print(" APBA PRO BASKETBALL SIMULATOR v7.0")
    print(f"=================================={Colors.RESET}")
    
    rosters = load_data()
    teams = sorted(list(rosters.keys()))
    if not teams: sys.exit(1)
    
    print("\nSelect Game Mode:")
    print("1. Play-by-Play (Manual advance)")
    print("2. Quarter-by-Quarter (Classic Sim)")
    print("3. Fast Sim (Instant Result)")
    print("4. DevTools / League Benchmark")
    print("5. Season Records / Standings")
    print("6. Retro-Modern Play Mode")
    try:
        mode = int(input("Mode (1-6): "))
    except:
        mode = 2 

    if mode == 4:
        run_benchmark_suite(rosters)
        return
    if mode == 5:
        store = SeasonStore()
        print("1. View Standings")
        print("2. View Scoring Leaders")
        print("3. Export Standings CSV")
        ch = input("Choice: ")
        if ch == '1': print_standings(store.get_standings())
        elif ch == '2': print_player_leaders(store.get_player_leaders("PTS"), "PTS")
        elif ch == '3': print(f"Exported: {store.export_standings_csv('standings.csv')}")
        input("Press Enter to return...")
        return
    if mode == 6:
        from retro_play import play_retro_game
        print("\nRetro-Modern Play Mode")
        print("Enter Team Codes (default: SAS at BOS).")
        v = input("Visitor: ").upper() or "SAS"
        h = input("Home:    ").upper() or "BOS"
        if v in rosters and h in rosters:
            v_team = Team(v, copy.deepcopy(rosters[v]))
            h_team = Team(h, copy.deepcopy(rosters[h]))
            completed = play_retro_game(v_team, h_team)
            if completed:
                print_box_score(v_team, h_team)
                game_id = SeasonStore().record_game(v_team, h_team)
                print(f"{Colors.GREEN}[SEASON] Saved game #{game_id} to season.sqlite3{Colors.RESET}")
        else:
            print("Invalid.")
        return

    while True:
        print("\nAvailable Teams:")
        for i in range(0, len(teams), 6):
            print("  ".join(teams[i:i+6]))
            
        print("\nEnter Team Codes (e.g. CHI, DET) or 'Q' to quit.")
        v = input("Visitor: ").upper()
        if v == 'Q': break
        h = input("Home:    ").upper()
        
        if v in rosters and h in rosters:
            v_team = Team(v, copy.deepcopy(rosters[v]))
            h_team = Team(h, copy.deepcopy(rosters[h]))
            play_game(v_team, h_team, mode)
            if v_team.score or h_team.score:
                game_id = SeasonStore().record_game(v_team, h_team)
                print(f"{Colors.GREEN}[SEASON] Saved game #{game_id} to season.sqlite3{Colors.RESET}")
        else:
            print("Invalid.")

if __name__ == "__main__":
    main()