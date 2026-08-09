"""
Transfer Suggester
--------------------
Unlike squad_builder.py (which builds a squad from scratch - only correct for
your very first squad or a Wildcard/Free Hit week), this works from your
ACTUAL current squad and answers the real weekly question: what's the best
single swap using your free transfer, and is a second transfer (-4 points)
ever worth it?

Rules modeled:
  - 1 free transfer per week (any additional transfer costs -4 points)
  - "Bank" = budget leftover from your total £100.0m that isn't tied up in
    your current squad - if your squad already totals exactly £100.0m,
    bank is £0.0m, meaning a replacement must cost <= the player it's
    replacing.
  - Max 3 players from any one real-life team, checked against your
    resulting squad after the swap.

This intentionally does NOT auto-suggest chip usage (Wildcard, Free Hit,
Bench Boost, Triple Captain) - those are one-off strategic calls, not a
weekly optimization. It flags when your squad's quality has dropped enough
that a Wildcard might be worth considering, as a nudge, not a directive.
"""

import json
from differential_picks import build_rankings, POSITION_NAMES
from fixture_difficulty import build_team_difficulty_map, difficulty_multiplier, load_fixtures
from fpl_weekly_pipeline import load_players_from_bootstrap, current_gameweek
from squad_builder import quality_score


# Your current 15 - name must match the FPL "web_name" exactly (short display name)
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
    {"web_name": "Tzolis", "bench": True},
    {"web_name": "Enzo", "bench": False},
    {"web_name": "Szoboszlai", "bench": True},
    {"web_name": "Thiago", "bench": True},
    {"web_name": "Watkins", "bench": False},
    {"web_name": "Calvert-Lewin", "bench": False},
]

BANK = 0.0  # money left in the bank beyond your squad's current £100.0m total - adjust if you have any spare


def match_current_squad(current_squad_list, all_players):
    """Matches your squad's web_names against the live scored player pool."""
    by_name = {p["web_name"]: p for p in all_players}
    matched = []
    unmatched = []
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


def suggest_transfers(current_squad, all_players, bank=0.0, top_n=3):
    """
    For each player in your current squad, finds the best available
    replacement in the same position, respecting budget (their price + bank)
    and the max-3-per-team rule against your resulting squad.
    Returns a list of {out, in, score_gain, cost_diff} sorted by score_gain.
    """
    current_names = set(p["web_name"] for p in current_squad)
    team_counts = {}
    for p in current_squad:
        team_counts[p["team_name"]] = team_counts.get(p["team_name"], 0) + 1

    suggestions = []
    for out_player in current_squad:
        pos = out_player["element_type"]
        budget = out_player["now_cost"] + int(bank * 10)
        out_score = quality_score(out_player, out_player.get("fixture_multiplier", 1.0))

        candidates = [
            p for p in all_players
            if p["element_type"] == pos
            and p["web_name"] not in current_names
            and p["now_cost"] <= budget
        ]

        # enforce max 3 per team after the swap
        resulting_team_counts = dict(team_counts)
        resulting_team_counts[out_player["team_name"]] -= 1

        for cand in candidates:
            new_count = resulting_team_counts.get(cand["team_name"], 0) + 1
            if new_count > 3:
                continue
            cand_score = quality_score(cand, cand.get("fixture_multiplier", 1.0))
            gain = cand_score - out_score
            if gain > 0:
                suggestions.append({
                    "out": out_player,
                    "in": cand,
                    "score_gain": round(gain, 1),
                    "cost_diff": round((cand["now_cost"] - out_player["now_cost"]) / 10, 1),
                })

    suggestions.sort(key=lambda s: -s["score_gain"])
    return suggestions[:top_n]


def best_second_transfer(suggestions, first_pick):
    """Finds the best suggestion that swaps out a DIFFERENT player than the
    first pick - doing two transfers in one week means two different
    outgoing players, not the same slot twice."""
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
    print(f"  OUT: {best['out']['web_name']} ({best['out']['team_name']}, £{best['out']['cost_m']:.1f}m)")
    print(f"  IN:  {best['in']['web_name']} ({best['in']['team_name']}, £{best['in']['cost_m']:.1f}m)")
    print(f"  Cost change: {'+' if best['cost_diff']>=0 else ''}{best['cost_diff']:.1f}m")
    print(f"  Quality score gain: +{best['score_gain']:.1f}")

    second = best_second_transfer(all_suggestions, best)
    if second is not None:
        HIT_COST_IN_SCORE_TERMS = 15  # conservative: only suggest a hit for a clear, sizeable gain
        print(f"\nADDITIONAL TRANSFER (-4 hit, different player) - {'WORTH IT' if second['score_gain'] > HIT_COST_IN_SCORE_TERMS else 'PROBABLY NOT WORTH IT'}:")
        print(f"  OUT: {second['out']['web_name']} ({second['out']['team_name']}, £{second['out']['cost_m']:.1f}m)")
        print(f"  IN:  {second['in']['web_name']} ({second['in']['team_name']}, £{second['in']['cost_m']:.1f}m)")
        print(f"  Quality score gain: +{second['score_gain']:.1f} (a -4 hit costs roughly {HIT_COST_IN_SCORE_TERMS} points of quality-score equivalent to break even)")
        if second['score_gain'] <= HIT_COST_IN_SCORE_TERMS:
            print(f"  -> Recommendation: hold this one, take only the free transfer above.")
    else:
        print(f"\nNo distinct second transfer opportunity found beyond the free transfer above.")


def squad_health_check(current_squad):
    """Simple nudge: flags if your squad's average fixture multiplier has
    dropped noticeably, which is the kind of signal that precedes 'this
    might be a Wildcard week' - not a directive, just a flag."""
    avg_mult = sum(p.get("fixture_multiplier", 1.0) for p in current_squad) / len(current_squad)
    if avg_mult < 0.92:
        print(f"\nNote: your squad's average fixture multiplier is {avg_mult:.2f} (below neutral) - "
              f"a chunk of your squad is heading into a tougher fixture run. Worth keeping an eye on "
              f"whether a Wildcard makes sense in the next few weeks, though one bad multiplier alone "
              f"isn't a strong enough signal to act on by itself.")


if __name__ == "__main__":
    from fpl_weekly_pipeline import download_data

    bootstrap, fixtures = download_data()
    players = load_players_from_bootstrap(bootstrap)
    team_names = {t["id"]: t["name"] for t in bootstrap["teams"]}
    next_gw = current_gameweek(bootstrap)
    diff_map = build_team_difficulty_map(fixtures, list(team_names.keys()), n_games=5, from_event=next_gw)
    team_difficulty = {team_names[tid]: difficulty_multiplier(avg) for tid, (avg, run) in diff_map.items()}

    by_value, by_differential = build_rankings(players, min_minutes=450, team_difficulty=team_difficulty)

    matched, unmatched = match_current_squad(CURRENT_SQUAD, by_value)
    if unmatched:
        print(f"Warning: couldn't match these names to live data: {unmatched}")
        print("(they may have low minutes this early, or the name format differs slightly)\n")

    print(f"Matched {len(matched)}/{len(CURRENT_SQUAD)} squad players")

    suggestions = suggest_transfers(matched, by_value, bank=BANK, top_n=15)
    print_suggestions(suggestions, BANK)
    squad_health_check(matched)
