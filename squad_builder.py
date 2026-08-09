"""
FPL Squad Builder
-------------------
Builds a valid, budget-legal 15-man squad using integer linear programming
(via PuLP) rather than a greedy heuristic - this guarantees the best possible
squad under the real constraints, not just a "good enough" one.

Real FPL squad rules enforced:
  - Exactly 15 players: 2 GKP, 5 DEF, 5 MID, 3 FWD
  - Total cost <= £100.0m
  - Max 3 players from any single real-life team

Two objective modes:
  - "balanced":     maximize pure underlying quality (ICT + xGI, fixture-
                     adjusted), ignoring ownership - the strongest possible
                     squad regardless of how popular the picks are
  - "differential": maximize the same quality score but weighted down for
                     high-ownership players - a more contrarian squad, higher
                     variance, better for climbing mini-leagues from behind

After building the 15, also suggests a starting XI + captain: the highest-
scoring valid 11 (1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD) from within the squad.
"""

import pulp
from differential_picks import POSITION_NAMES

BUDGET = 1000  # £100.0m in tenths, matching now_cost's units
SQUAD_REQUIREMENTS = {1: 2, 2: 5, 3: 5, 4: 3}  # GKP, DEF, MID, FWD
MAX_PER_TEAM = 3


def quality_score(p, fixture_multiplier=1.0):
    """Ownership-agnostic underlying quality: ICT index plus heavily-weighted
    expected goal involvements, adjusted for upcoming fixture ease."""
    return (p["ict_index"] + p["expected_goal_involvements"] * 10) * fixture_multiplier


def build_squad(players, mode="balanced", budget=BUDGET, min_minutes=450):
    """
    players: list of player dicts, each already carrying 'fixture_multiplier'
             and 'differential_score' from build_rankings().
    mode: "balanced" or "differential"
    Returns (squad_list, total_cost, total_score) or (None, None, None) if
    no feasible squad exists under the constraints.
    """
    eligible = [p for p in players if p["minutes"] >= min_minutes and p["status"] == "a"]

    prob = pulp.LpProblem("fpl_squad", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(eligible))}

    # objective
    if mode == "differential":
        scores = [p["differential_score"] for p in eligible]
    else:  # balanced
        scores = [quality_score(p, p.get("fixture_multiplier", 1.0)) for p in eligible]
    prob += pulp.lpSum(x[i] * scores[i] for i in range(len(eligible)))

    # position constraints
    for pos_id, count in SQUAD_REQUIREMENTS.items():
        prob += pulp.lpSum(x[i] for i, p in enumerate(eligible) if p["element_type"] == pos_id) == count

    # budget constraint
    prob += pulp.lpSum(x[i] * eligible[i]["now_cost"] for i in range(len(eligible))) <= budget

    # squad size
    prob += pulp.lpSum(x[i] for i in range(len(eligible))) == 15

    # max 3 per real team
    teams = set(p["team_name"] for p in eligible)
    for team in teams:
        prob += pulp.lpSum(x[i] for i, p in enumerate(eligible) if p["team_name"] == team) <= MAX_PER_TEAM

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != "Optimal":
        return None, None, None

    squad = [eligible[i] for i in range(len(eligible)) if x[i].value() == 1]
    total_cost = sum(p["now_cost"] for p in squad) / 10
    total_score = sum(scores[i] for i in range(len(eligible)) if x[i].value() == 1)
    return squad, total_cost, total_score


def pick_starting_xi(squad, mode="balanced"):
    """
    From the 15-man squad, picks the highest-scoring valid starting XI:
    1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD, totaling 11. Also flags the captain
    (highest scorer in the XI - doubles their points in real FPL).
    """
    prob = pulp.LpProblem("starting_xi", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"y_{i}", cat="Binary") for i in range(len(squad))}

    score_key = "differential_score" if mode == "differential" else None
    if score_key:
        scores = [p[score_key] for p in squad]
    else:
        scores = [quality_score(p, p.get("fixture_multiplier", 1.0)) for p in squad]

    prob += pulp.lpSum(x[i] * scores[i] for i in range(len(squad)))
    prob += pulp.lpSum(x[i] for i in range(len(squad))) == 11
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 1) == 1
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 2) >= 3
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 2) <= 5
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 3) >= 2
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 3) <= 5
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 4) >= 1
    prob += pulp.lpSum(x[i] for i, p in enumerate(squad) if p["element_type"] == 4) <= 3

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    starting = [squad[i] for i in range(len(squad)) if x[i].value() == 1]
    bench = [p for p in squad if p not in starting]
    captain = max(starting, key=lambda p: scores[squad.index(p)])
    return starting, bench, captain


def print_squad(squad, total_cost, total_score, mode):
    print(f"\n{'='*70}\nSQUAD ({mode} mode) - £{total_cost:.1f}m spent of £100.0m\n{'='*70}")
    for pos_id, pos_name in POSITION_NAMES.items():
        pos_players = [p for p in squad if p["element_type"] == pos_id]
        print(f"\n{pos_name}:")
        for p in sorted(pos_players, key=lambda p: -p["now_cost"]):
            print(f"  {p['web_name']:<16} {p['team_name']:<14} £{p['cost_m']:<5.1f} own={p['selected_by_percent']:<5}%")

    starting, bench, captain = pick_starting_xi(squad, mode)
    print(f"\n{'='*70}\nSUGGESTED STARTING XI (captain marked with C)\n{'='*70}")
    for pos_id, pos_name in POSITION_NAMES.items():
        pos_players = [p for p in starting if p["element_type"] == pos_id]
        if pos_players:
            names = ", ".join(f"{p['web_name']}{' (C)' if p is captain else ''}" for p in pos_players)
            print(f"  {pos_name}: {names}")
    print(f"\n  Bench: {', '.join(p['web_name'] for p in bench)}")


if __name__ == "__main__":
    import json
    from differential_picks import build_rankings
    from fixture_difficulty import build_team_difficulty_map, difficulty_multiplier, load_fixtures
    from fpl_weekly_pipeline import load_players_from_bootstrap, current_gameweek

    with open("/mnt/user-data/uploads/fpl_bootstrap.json", encoding="utf-8") as f:
        bootstrap = json.load(f)
    fixtures = load_fixtures("data/fixtures_raw.json")

    players = load_players_from_bootstrap(bootstrap)
    team_names = {t["id"]: t["name"] for t in bootstrap["teams"]}
    next_gw = current_gameweek(bootstrap)
    diff_map = build_team_difficulty_map(fixtures, list(team_names.keys()), n_games=5, from_event=next_gw)
    team_difficulty = {team_names[tid]: difficulty_multiplier(avg) for tid, (avg, run) in diff_map.items()}

    by_value, by_differential = build_rankings(players, min_minutes=450, team_difficulty=team_difficulty)

    for mode in ["balanced", "differential"]:
        squad, cost, score = build_squad(by_value, mode=mode)
        if squad is None:
            print(f"No feasible squad found for mode={mode}")
            continue
        print_squad(squad, cost, score, mode)
