"""
Transfer Suggester (standalone version)
------------------------------------------
Self-contained: only needs `pip install requests`. No other project files
required, so this one script can be copied to any machine and just work.

Given your actual current squad, finds the best single free transfer, and
flags whether a second, point-costing transfer is worth taking.

Rules modeled:
  - 1 free transfer per week (any additional transfer costs -4 points)
  - "Bank" = leftover budget beyond what's tied up in your current squad
  - Max 3 players from any one real-life team
  - Minutes-played eligibility threshold scales with how far into the
    season we are, so it means the same thing in gameweek 2 as gameweek 30
    (a fixed 450-minute bar would filter out every player early in a season)

Does NOT auto-suggest chip usage (Wildcard, Free Hit, Bench Boost, Triple
Captain) - those stay a manual call, this only handles routine transfers.
"""

import json
import requests

BASE = "https://fantasy.premierleague.com/api"
POSITION_NAMES = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# ============================================================================
# EDIT THIS to match your actual current squad before running.
# Name must match the FPL "web_name" exactly (the short display name).
# ============================================================================
CURRENT_SQUAD = [
    {"web_name": "Verbruggen", "bench": True},
    {"web_name": "Dubravka", "bench": False},
    {"web_name": "Virgil", "bench": False},
    {"web_name": "O'Reilly", "bench": False},
    {"web_name": "Pedro Porro", "bench": False},
    {"web_name": "Van Hecke", "bench": True},
    {"web_name": "N.Williams", "bench": True},
    {"web_name": "B.Fernandes", "bench": False, "captain": True},
    {"web_name": "Mbeumo", "bench": False},
    {"web_name": "Szoboszlai", "bench": False},
    {"web_name": "Enzo", "bench": False},
    {"web_name": "Gakpo", "bench": True},
    {"web_name": "Thiago", "bench": False},
    {"web_name": "Watkins", "bench": False},
    {"web_name": "Calvert-Lewin", "bench": False},
]

BANK = 0.0  # money left in the bank beyond your squad's current total - edit if you have any spare


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def download_data():
    print("Downloading bootstrap-static (players, teams)...")
    bootstrap = requests.get(f"{BASE}/bootstrap-static/").json()
    print(f"  {len(bootstrap['elements'])} players, {len(bootstrap['teams'])} teams")
    print("Downloading fixtures...")
    fixtures = requests.get(f"{BASE}/fixtures/").json()
    print(f"  {len(fixtures)} fixtures")
    return bootstrap, fixtures


def load_players_from_bootstrap(bootstrap):
    team_names = {t["id"]: t["name"] for t in bootstrap["teams"]}
    players = []
    for e in bootstrap["elements"]:
        try:
            players.append({
                "web_name": e["web_name"],
                "team_name": team_names.get(e["team"], "Unknown"),
                "element_type": e["element_type"],
                "now_cost": e["now_cost"],
                "total_points": e["total_points"],
                "selected_by_percent": float(e["selected_by_percent"]),
                "ict_index": float(e["ict_index"]),
                "expected_goal_involvements": float(e["expected_goal_involvements"]),
                "minutes": e["minutes"],
                "status": e["status"],
            })
        except (ValueError, KeyError, TypeError):
            continue
    return players


def current_gameweek(bootstrap):
    for event in bootstrap["events"]:
        if event.get("is_next"):
            return event["id"]
    return 1


def completed_gameweeks(bootstrap):
    return sum(1 for event in bootstrap["events"] if event.get("finished"))


def dynamic_min_minutes(bootstrap, target_starter_fraction=0.5):
    """Scales the eligibility bar to how far into the season we are - a
    fixed 450-minute threshold filters out every player early in a season."""
    gws_done = completed_gameweeks(bootstrap)
    if gws_done == 0:
        return 45
    return max(45, int(gws_done * 90 * target_starter_fraction))


# ---------------------------------------------------------------------------
# Fixture difficulty
# ---------------------------------------------------------------------------

def team_upcoming_difficulty(fixtures, team_id, n_games=5, from_event=1):
    team_fixtures = []
    for f in fixtures:
        if f["finished"] or f["event"] is None or f["event"] < from_event:
            continue
        if f["team_h"] == team_id:
            team_fixtures.append((f["event"], f["team_h_difficulty"]))
        elif f["team_a"] == team_id:
            team_fixtures.append((f["event"], f["team_a_difficulty"]))
    team_fixtures.sort(key=lambda x: x[0])
    upcoming = team_fixtures[:n_games]
    if not upcoming:
        return 3.0
    return sum(d for _, d in upcoming) / len(upcoming)


def difficulty_multiplier(avg_difficulty):
    return max(0.5, min(1.5, 1.0 + (3.0 - avg_difficulty) * 0.15))


def build_team_difficulty(fixtures, bootstrap, n_games=5):
    team_names = {t["id"]: t["name"] for t in bootstrap["teams"]}
    next_gw = current_gameweek(bootstrap)
    return {
        team_names[tid]: difficulty_multiplier(team_upcoming_difficulty(fixtures, tid, n_games, next_gw))
        for tid in team_names
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def quality_score(p):
    """Ownership-agnostic underlying quality, fixture-adjusted."""
    return (p["ict_index"] + p["expected_goal_involvements"] * 10) * p.get("fixture_multiplier", 1.0)


def score_all_players(players, team_difficulty, min_minutes):
    eligible = [p for p in players if p["minutes"] >= min_minutes and p["status"] == "a"]
    for p in eligible:
        p["fixture_multiplier"] = team_difficulty.get(p["team_name"], 1.0)
        p["quality_score"] = quality_score(p)
    return eligible


# ---------------------------------------------------------------------------
# Transfer logic
# ---------------------------------------------------------------------------

def match_current_squad(current_squad_list, all_players):
    by_name = {p["web_name"]: p for p in all_players}
    matched, unmatched = [], []
    for entry in current_squad_list:
        p = by_name.get(entry["web_name"])
        if p is None:
            unmatched.append(entry["web_name"])
            continue
        p = dict(p)
        p["bench"] = entry["bench"]
        p["captain"] = entry.get("captain", False)
        matched.append(p)
    return matched, unmatched


def suggest_transfers(current_squad, all_players, bank=0.0, top_n=15):
    current_names = set(p["web_name"] for p in current_squad)
    team_counts = {}
    for p in current_squad:
        team_counts[p["team_name"]] = team_counts.get(p["team_name"], 0) + 1

    suggestions = []
    for out_player in current_squad:
        pos = out_player["element_type"]
        budget = out_player["now_cost"] + int(bank * 10)
        out_score = out_player["quality_score"]

        candidates = [
            p for p in all_players
            if p["element_type"] == pos and p["web_name"] not in current_names and p["now_cost"] <= budget
        ]

        resulting_team_counts = dict(team_counts)
        resulting_team_counts[out_player["team_name"]] -= 1

        for cand in candidates:
            new_count = resulting_team_counts.get(cand["team_name"], 0) + 1
            if new_count > 3:
                continue
            gain = cand["quality_score"] - out_score
            if gain > 0:
                suggestions.append({
                    "out": out_player, "in": cand, "score_gain": round(gain, 1),
                    "cost_diff": round((cand["now_cost"] - out_player["now_cost"]) / 10, 1),
                })

    suggestions.sort(key=lambda s: -s["score_gain"])
    return suggestions[:top_n]


def best_second_transfer(suggestions, first_pick):
    for s in suggestions:
        if s["out"]["web_name"] != first_pick["out"]["web_name"]:
            return s
    return None


def print_suggestions(all_suggestions, bank):
    if not all_suggestions:
        print("No upgrades found - your squad already looks well-optimized for the current fixture window.")
        return

    print(f"\n{'='*72}\nTOP TRANSFER SUGGESTIONS (bank: £{bank:.1f}m)\n{'='*72}")
    best = all_suggestions[0]
    print(f"\nFREE TRANSFER (recommended):")
    print(f"  OUT: {best['out']['web_name']} ({best['out']['team_name']}, £{best['out']['now_cost']/10:.1f}m)")
    print(f"  IN:  {best['in']['web_name']} ({best['in']['team_name']}, £{best['in']['now_cost']/10:.1f}m)")
    print(f"  Cost change: {'+' if best['cost_diff']>=0 else ''}{best['cost_diff']:.1f}m")
    print(f"  Quality score gain: +{best['score_gain']:.1f}")

    second = best_second_transfer(all_suggestions, best)
    if second is not None:
        HIT_COST = 15
        print(f"\nADDITIONAL TRANSFER (-4 hit, different player) - {'WORTH IT' if second['score_gain'] > HIT_COST else 'PROBABLY NOT WORTH IT'}:")
        print(f"  OUT: {second['out']['web_name']} ({second['out']['team_name']}, £{second['out']['now_cost']/10:.1f}m)")
        print(f"  IN:  {second['in']['web_name']} ({second['in']['team_name']}, £{second['in']['now_cost']/10:.1f}m)")
        print(f"  Quality score gain: +{second['score_gain']:.1f} (a -4 hit needs roughly {HIT_COST}+ to break even)")
        if second['score_gain'] <= HIT_COST:
            print(f"  -> Recommendation: hold this one, take only the free transfer above.")
    else:
        print(f"\nNo distinct second transfer opportunity found beyond the free transfer above.")


def squad_health_check(current_squad):
    avg_mult = sum(p.get("fixture_multiplier", 1.0) for p in current_squad) / len(current_squad)
    if avg_mult < 0.92:
        print(f"\nNote: your squad's average fixture multiplier is {avg_mult:.2f} (below neutral) - "
              f"a chunk of your squad is heading into a tougher fixture run. Worth keeping an eye on "
              f"whether a Wildcard makes sense soon, though this alone isn't a strong signal to act on.")


if __name__ == "__main__":
    bootstrap, fixtures = download_data()
    players = load_players_from_bootstrap(bootstrap)

    min_minutes = dynamic_min_minutes(bootstrap)
    print(f"Using dynamic minutes threshold: {min_minutes} ({completed_gameweeks(bootstrap)} gameweek(s) completed)")

    team_difficulty = build_team_difficulty(fixtures, bootstrap)
    scored_players = score_all_players(players, team_difficulty, min_minutes)
    print(f"{len(scored_players)} players eligible")

    matched, unmatched = match_current_squad(CURRENT_SQUAD, scored_players)
    if unmatched:
        print(f"\nWarning: couldn't match these names to live data: {unmatched}")
        print("(check spelling matches their FPL short name exactly, or they may be below the minutes threshold)\n")
    print(f"Matched {len(matched)}/{len(CURRENT_SQUAD)} squad players")

    suggestions = suggest_transfers(matched, scored_players, bank=BANK, top_n=15)
    print_suggestions(suggestions, BANK)
    squad_health_check(matched)
