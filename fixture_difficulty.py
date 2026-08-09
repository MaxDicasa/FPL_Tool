"""
Computes fixture difficulty for each team over their next N gameweeks.
FPL's own Fixture Difficulty Rating (FDR) is 1 (easiest) to 5 (hardest),
set by FPL's own team, from the perspective of the team being difficulty-rated.

A team's "next N" difficulty is the average of team_h_difficulty (when they're
home) or team_a_difficulty (when they're away) across their next N scheduled,
unfinished fixtures.
"""

import json
from collections import defaultdict


def load_fixtures(path: str):
    with open(path) as f:
        return json.load(f)


def team_upcoming_difficulty(fixtures, team_id: int, n_games: int = 5, from_event: int = 1):
    """Average FDR across a team's next n_games fixtures from from_event onward."""
    team_fixtures = []
    for f in fixtures:
        if f["finished"]:
            continue
        if f["event"] is None or f["event"] < from_event:
            continue
        if f["team_h"] == team_id:
            team_fixtures.append((f["event"], f["team_h_difficulty"]))
        elif f["team_a"] == team_id:
            team_fixtures.append((f["event"], f["team_a_difficulty"]))

    team_fixtures.sort(key=lambda x: x[0])
    upcoming = team_fixtures[:n_games]
    if not upcoming:
        return 3.0, []  # neutral default if no fixtures found
    avg = sum(d for _, d in upcoming) / len(upcoming)
    return round(avg, 2), [d for _, d in upcoming]


def build_team_difficulty_map(fixtures, team_ids, n_games=5, from_event=1):
    """Returns {team_id: (avg_difficulty, [next_n_difficulties])} for every team."""
    return {
        tid: team_upcoming_difficulty(fixtures, tid, n_games, from_event)
        for tid in team_ids
    }


def difficulty_multiplier(avg_difficulty: float) -> float:
    """
    Converts average FDR (1=easiest, 5=hardest) into a score multiplier.
    FDR 2 (easy run) -> multiplier > 1 (boosts differential score)
    FDR 3 (neutral)   -> multiplier = 1.0 (no adjustment)
    FDR 4+ (hard run)  -> multiplier < 1 (penalizes differential score)
    """
    # linear scale centered on neutral=3: each point of difficulty above/below
    # 3 shifts the multiplier by 15%, capped so a brutal run doesn't zero a player out
    return max(0.5, min(1.5, 1.0 + (3.0 - avg_difficulty) * 0.15))


if __name__ == "__main__":
    fixtures = load_fixtures("/home/claude/fpl_tool/data/fixtures_raw.json")
    with open("/mnt/user-data/uploads/fpl_bootstrap.json") as f:
        bootstrap = json.load(f)
    team_ids = [t["id"] for t in bootstrap["teams"]]
    team_names = {t["id"]: t["name"] for t in bootstrap["teams"]}

    diff_map = build_team_difficulty_map(fixtures, team_ids, n_games=5, from_event=1)

    print(f"{'Team':<16}{'Avg FDR (next 5)':<18}{'Fixture run':<20}{'Multiplier':<10}")
    for tid in sorted(diff_map, key=lambda t: diff_map[t][0]):
        avg, run = diff_map[tid]
        mult = difficulty_multiplier(avg)
        print(f"{team_names[tid]:<16}{avg:<18}{str(run):<20}{mult:<10}")
