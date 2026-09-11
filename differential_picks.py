

 # 1. VALUE SCORE   - points delivered per unit of squad cost (who's cheap relative to output)
 # 2. DIFFERENTIAL SCORE - strong underlying numbers (ICT index, expected goal involvements) combined with LOW ownership. For example, players most other managers don't have, who look statistically live to outperform their price



 # Position codes: 1=GKP, 2=DEF, 3=MID, 4=FWD


import json

POSITION_NAMES = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def load_players(path: str):
    with open(path) as f:
        return json.load(f)


def value_score(player):
    """Points per million spent. now_cost is in tenths (e.g. 55 = £5.5m)."""
    cost_millions = player["now_cost"] / 10
    if cost_millions == 0:
        return 0
    return round(player["total_points"] / cost_millions, 2)


def differential_score(player):
    
    Combines underlying quality (ICT index, expected goal involvements with LOW ownership into a single score. Higher score means good stats that most managers are sleeping on.

    
    ownership = player["selected_by_percent"]
    ict = player["ict_index"]
    xgi = player["expected_goal_involvements"]

    underlying_quality = ict + (xgi * 10)  # weight xGI heavily - it's the more predictive stat

    if ownership <= 10:
        ownership_multiplier = 1.0
    else:
        # decay: at 30% ownership, multiplier is roughly 0.4
        ownership_multiplier = max(0.15, 1.0 - (ownership - 10) * 0.03)

    return round(underlying_quality * ownership_multiplier, 1)


def build_rankings(players, min_minutes=450, team_difficulty=None):
 
    eligible = [p for p in players if p["minutes"] >= min_minutes and p["status"] == "a"]
    for p in eligible:
        p["value_score"] = value_score(p)
        base_diff = differential_score(p)
        mult = 1.0
        if team_difficulty is not None:
            mult = team_difficulty.get(p["team_name"], 1.0)
        p["fixture_multiplier"] = mult
        p["differential_score"] = round(base_diff * mult, 1)
        p["differential_score_base"] = base_diff
        p["position"] = POSITION_NAMES[p["element_type"]]
        p["cost_m"] = p["now_cost"] / 10
    by_value = sorted(eligible, key=lambda p: -p["value_score"])
    by_differential = sorted(eligible, key=lambda p: -p["differential_score"])
    return by_value, by_differential


if __name__ == "__main__":
    players = load_players("/home/claude/fpl_tool/data/sample_players.json")
    by_value, by_differential = build_rankings(players)

    print("=" * 75)
    print(f"SAMPLE RUN — {len(players)} players (Arsenal + Aston Villa only)")
    print("This is a partial demo. Run download_fpl_data.py for all 700+ players.")
    print("=" * 75)

    print("\n" + "=" * 75)
    print("BEST VALUE PICKS (points per £m spent)")
    print("=" * 75)
    print(f"{'Player':<15}{'Pos':<5}{'Team':<12}{'Cost':<7}{'Pts':<6}{'Value':<8}{'Own%':<6}")
    for p in by_value[:10]:
        print(f"{p['web_name']:<15}{p['position']:<5}{p['team_name']:<12}£{p['cost_m']:<6.1f}{p['total_points']:<6}{p['value_score']:<8}{p['selected_by_percent']:<6}")

    print("\n" + "=" * 75)
    print("TOP DIFFERENTIALS (strong underlying stats, low ownership)")
    print("=" * 75)
    print(f"{'Player':<15}{'Pos':<5}{'Team':<12}{'Own%':<7}{'ICT':<8}{'xGI':<7}{'Diff Score':<10}")
    for p in by_differential[:10]:
        print(f"{p['web_name']:<15}{p['position']:<5}{p['team_name']:<12}{p['selected_by_percent']:<7}{p['ict_index']:<8}{p['expected_goal_involvements']:<7}{p['differential_score']:<10}")
