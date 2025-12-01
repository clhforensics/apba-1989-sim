import random
import time
import csv
import os
import sys
import copy

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
        1: {"name": "Run and Shoot", "desc": "Fast pace, 3PT focus",         "pace": 12, "to_mod": 1.15, "reb_mod": 0.90, "fatigue_mod": 1.5, "3pt_bonus": 0.25},
        2: {"name": "Normal Flow",   "desc": "Balanced pace",                 "pace": 15, "to_mod": 1.00, "reb_mod": 1.00, "fatigue_mod": 1.0, "3pt_bonus": 0.00},
        3: {"name": "Slow and Low",  "desc": "Slow pace, Paint focus",        "pace": 22, "to_mod": 0.90, "reb_mod": 1.05, "fatigue_mod": 0.8, "3pt_bonus": -0.15},
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
            
            # Rate Stats
            mp = max(1, self.minutes_total)
            self.mpg = mp / max(1, self.games)
            
            fga = int(row.get('FGA', 0)) if row.get('FGA') else 0
            tov = int(row.get('TOV', 0)) if row.get('TOV') else 0
            ast = int(row.get('AST', 0)) if row.get('AST') else 0
            trb = int(row.get('TRB', 0)) if row.get('TRB') else 0
            stl = int(row.get('STL', 0)) if row.get('STL') else 0
            
            # Derived Rates (per minute)
            self.usage_rate = (fga + tov) / mp
            self.reb_rate = trb / mp
            self.to_rate = tov / mp
            self.ast_rate = ast / mp
            self.stl_rate = stl / mp
            
        except Exception as e:
            self.fg_pct = 0.40
            self.mpg = 10
            self.usage_rate = 0.2
            self.reb_rate = 0.1
            self.to_rate = 0.05
            self.ast_rate = 0.05
            self.stl_rate = 0.02
            self.has_3pt = False

        self.stat_minutes = 0.0    
        self.current_fatigue = 0.0 
        self.stint_limit = 6.0 + (self.mpg / 3.2)
        
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
        self.roster = sorted(player_list, key=lambda p: p.mpg, reverse=True)
        self.roster = self.roster[:12]
        self.score = 0
        self.timeouts = 6 
        self.off_strategy = 2
        self.def_strategy = 2
        self.usage_bucket = []
        self.rebuild_usage_bucket()

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

    def sub_check(self, quarter, quiet=True):
        lineup = self.get_lineup()
        subs_made = False
        
        for i, p in enumerate(lineup):
            force_sub_out = False
            
            # Foul Trouble Logic
            if p.fouls >= 6:
                p.fouled_out = True
                force_sub_out = True
                if not quiet and not p.fouled_out: print(f"{Colors.RED}   [FOUL OUT] {p.name} has 6 fouls!{Colors.RESET}")
            elif quarter <= 2 and p.fouls >= 3: force_sub_out = True
            elif quarter == 3 and p.fouls >= 4: force_sub_out = True
            
            if p.current_fatigue > p.stint_limit:
                p.is_fatigued = True
            
            # Star Return Logic
            better_sub_idx = -1
            if not force_sub_out and not p.is_fatigued:
                for j, bench_p in enumerate(self.roster[5:]):
                    if bench_p.mpg > (p.mpg + 8) and bench_p.current_fatigue < (bench_p.stint_limit * 0.3) and not bench_p.fouled_out:
                        if not (quarter <= 2 and bench_p.fouls >= 2):
                            better_sub_idx = 5 + j
                            break
            
            if better_sub_idx != -1:
                sub_in = self.roster[better_sub_idx]
                if not quiet: print(f"{Colors.CYAN}   [ROTATION] {self.code}: {sub_in.name} (Star) returns for {p.name}{Colors.RESET}")
                self.roster[i], self.roster[better_sub_idx] = self.roster[better_sub_idx], self.roster[i]
                subs_made = True
                continue 

            if p.is_fatigued or force_sub_out:
                best_sub_idx = -1
                lowest_fatigue = 999
                
                for j, bench_p in enumerate(self.roster[5:]):
                    if bench_p.fouled_out: continue
                    if quarter <= 3 and bench_p.fouls >= 4: continue
                    if bench_p.current_fatigue < lowest_fatigue:
                        lowest_fatigue = bench_p.current_fatigue
                        best_sub_idx = 5 + j
                
                if best_sub_idx == -1:
                    for j, bench_p in enumerate(self.roster[5:]):
                        if not bench_p.fouled_out:
                            best_sub_idx = 5 + j
                            break

                if best_sub_idx != -1:
                    sub_in = self.roster[best_sub_idx]
                    reason = "Fouls" if force_sub_out else "Fatigue"
                    if not quiet:
                        print(f"{Colors.CYAN}   [SUB] {self.code}: {sub_in.name} IN, {p.name} OUT ({reason}){Colors.RESET}")
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
            
            # Turnover Check
            base_prob = (shooter.to_rate * elapsed_mins) * 3.2
            to_chance = base_prob * off_strat["to_mod"] * def_strat["opp_to_mult"]
            if crowd_active and possession == team_v: to_chance *= 1.2 
            
            if random.random() < to_chance:
                shooter.turnovers += 1
                if random.random() < 0.50:
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
                    if possession == team_v: home_momentum_streak += 1

                possession = defense
                time_remaining -= pace
                continue
                
            # Shot Check
            d1, d2 = random.randint(1, 6), random.randint(1, 6)
            roll = (d1 * 10) + d2
            result = shooter.card.get(roll, "MISS")
            
            # 3PT Logic
            if off_strat["3pt_bonus"] > 0 and "GOAL_2" in result and shooter.has_3pt:
                if random.random() < off_strat["3pt_bonus"]: result = "GOAL_3"

            # Defense Logic
            if "GOAL" in result and def_strat["opp_fg_mod"] < 1.0:
                if random.random() > def_strat["opp_fg_mod"]: result = "MISS"
            
            # Crowd Logic
            if crowd_active and possession == team_v and "GOAL" in result:
                if random.random() < 0.15: 
                    result = "MISS"
                    if not silent and game_mode != 3: print_pbp(f"(Crowd noise forces the miss!)", "ALERT")

            # Foul Check
            foul_prob = 0.20 + def_strat["foul_bonus"]
            if random.random() < foul_prob:
                if not silent and game_mode != 3: print_pbp(f"{defense.code}: Foul called on the play.", "FOUL")
                
                fouler = defense.get_rebounder()
                fouler.fouls += 1
                if fouler.fouls == 6:
                    if not silent and game_mode != 3: print_pbp(f"   (Foul Trouble) {fouler.name} has fouled out!", "TO")
                    
                made = 0
                for _ in range(2):
                    if random.random() < shooter.ft_pct: made += 1
                possession.score += made
                shooter.points += made
                shooter.ft_made += made
                shooter.ft_attempts += 2
                
                if not silent and game_mode != 3: print_pbp(f"{shooter.name} shoots free throws... {made}/2", "SCORE" if made > 0 else "MISS")
                if possession == team_h: home_momentum_streak = 0
                
            elif "GOAL" in result:
                pts = 3 if "3" in result else 2
                possession.score += pts
                shooter.points += pts
                shooter.makes += 1
                shooter.shots += 1
                if pts == 3: 
                    shooter.threes_made += 1
                    shooter.threes_att += 1
                else:
                    shooter.threes_att += 0 # 2PA tracking not explicitly split in player class but inferred
                
                assist_msg = ""
                if random.random() < 0.60:
                    assister = possession.get_assister(shooter)
                    if assister:
                        assister.assists += 1
                        assist_msg = f" (Ast: {assister.name})"

                if pts == 3: 
                    msg = random.choice(TEXT_3PT)
                else:
                    if shooter.fg_pct > 0.48 and random.random() < 0.30:
                        msg = random.choice(TEXT_DUNK)
                    else:
                        msg = random.choice(TEXT_MAKE)
                
                if not silent and game_mode != 3: print_pbp(f"{possession.code}: {shooter.name} {msg} {assist_msg}", "SCORE")
                
                if possession == team_h: 
                    home_momentum_streak += 1
                else: 
                    home_momentum_streak = 0
                    if crowd_active:
                        if not silent and game_mode != 3: print_pbp(f">>> {shooter.name} SILENCES THE CROWD!", "ALERT")
                        crowd_active = False

            else:
                shooter.shots += 1
                if shooter.has_3pt and random.random() < 0.30: shooter.threes_att += 1 # Estimation of missed 3s
                
                msg = random.choice(TEXT_MISS)
                if not silent and game_mode != 3: print_pbp(f"{possession.code}: {shooter.name} {msg}.", "MISS")
                
                def_reb_advantage = 0.75 * def_strat.get("reb_bonus", 1.0) * off_strat["reb_mod"]
                if random.random() < def_reb_advantage:
                    r = defense.get_rebounder()
                    r.rebounds += 1
                    msg_r = random.choice(TEXT_REB)
                    if not silent and game_mode != 3: print_pbp(f"   {defense.code}: {r.name} {msg_r}.", "REB")
                    if possession == team_v: home_momentum_streak += 1
                else:
                    r = possession.get_rebounder()
                    r.rebounds += 1
                    if not silent and game_mode != 3: print_pbp(f"   {possession.code}: {r.name} grabs the OFFENSIVE board!", "REB")
                    if possession == team_v: home_momentum_streak = 0
            
            possession = defense
            time_remaining -= pace
            
            # Subs Check
            quiet_subs = True if (game_mode == 3 or silent) else False
            if int(time_remaining) % 60 < 15:
                team_v.sub_check(quarter, quiet=quiet_subs)
                team_h.sub_check(quarter, quiet=quiet_subs)
        
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
    try:
        mode = int(input("Mode (1-4): "))
    except:
        mode = 2 

    if mode == 4:
        run_benchmark_suite(rosters)
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
        else:
            print("Invalid.")

if __name__ == "__main__":
    main()