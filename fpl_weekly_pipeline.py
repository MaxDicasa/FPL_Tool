"""
FPL WEEKLY PIPELINE - run this one script to go from raw data to a finished report.

Usage (run locally where you have internet access):
    pip install requests
    python fpl_weekly_pipeline.py

This does everything in one command:
  1. Downloads fresh bootstrap-static (players) and fixtures data from the FPL API
  2. Computes each team's fixture difficulty over their next 5 gameweeks
  3. Scores every player on value and differential potential, adjusted for
     how easy/hard their upcoming fixtures are
  4. Generates the styled HTML report, saved with the current date in the filename

Run this weekly (or before any deadline) to get fresh picks - nothing here
needs to be done by hand.
"""

import json
import argparse
import requests
from datetime import datetime

from differential_picks import build_rankings, POSITION_NAMES
from fixture_difficulty import build_team_difficulty_map, difficulty_multiplier
from generate_report import build_report
from squad_builder import build_squad, pick_starting_xi

BASE = "https://fantasy.premierleague.com/api"


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
                "points_per_game": float(e["points_per_game"]),
                "selected_by_percent": float(e["selected_by_percent"]),
                "form": float(e["form"]) if e["form"] else 0.0,
                "ict_index": float(e["ict_index"]),
                "expected_goal_involvements": float(e["expected_goal_involvements"]),
                "minutes": e["minutes"],
                "status": e["status"],
                "news": e.get("news", ""),
            })
        except (ValueError, KeyError, TypeError):
            continue
    return players


def current_gameweek(bootstrap):
    for event in bootstrap["events"]:
        if event.get("is_next"):
            return event["id"]
    return 1


def run_pipeline(n_fixture_games=5, min_minutes=450, squad_mode="balanced", output_path=None):
    bootstrap, fixtures = download_data()

    players = load_players_from_bootstrap(bootstrap)
    team_names = {t["id"]: t["name"] for t in bootstrap["teams"]}
    team_ids = list(team_names.keys())
    next_gw = current_gameweek(bootstrap)

    print(f"\nComputing fixture difficulty (next {n_fixture_games} GWs from GW{next_gw})...")
    diff_map = build_team_difficulty_map(fixtures, team_ids, n_games=n_fixture_games, from_event=next_gw)
    team_difficulty = {
        team_names[tid]: difficulty_multiplier(avg)
        for tid, (avg, run) in diff_map.items()
    }

    print("Scoring players (value + fixture-adjusted differential)...")
    by_value, by_differential = build_rankings(players, min_minutes=min_minutes, team_difficulty=team_difficulty)
    print(f"  {len(by_value)} players eligible ({min_minutes}+ minutes, available status)")

    print(f"Building optimal squad ({squad_mode} mode)...")
    squad, squad_cost, squad_score = build_squad(by_value, mode=squad_mode, min_minutes=min_minutes)
    starting_xi, bench, captain = (None, None, None)
    if squad is not None:
        starting_xi, bench, captain = pick_starting_xi(squad, mode=squad_mode)
        print(f"  Squad built: £{squad_cost:.1f}m spent, captain pick: {captain['web_name']}")
    else:
        print("  No feasible squad found under current constraints - skipping squad section")

    report_data = {
        "total_players": len(players),
        "eligible_count": len(by_value),
        "top_value": by_value[:12],
        "top_differentials": by_differential[:15],
        "by_position": {
            pos_name: [p for p in by_differential if p["element_type"] == pos_id][:6]
            for pos_id, pos_name in POSITION_NAMES.items()
        },
        "squad": squad,
        "squad_cost": squad_cost,
        "squad_mode": squad_mode,
        "starting_xi": starting_xi,
        "bench": bench,
        "captain_name": captain["web_name"] if captain else None,
        "pulled_note": f"gameweek {next_gw}, pulled {datetime.now().strftime('%Y-%m-%d')}",
    }

    data_path = "fpl_report_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    date_str = datetime.now().strftime("%Y%m%d")
    final_output_path = output_path or f"fpl_report_gw{next_gw}_{date_str}.html"
    build_report(data_path, final_output_path)

    print(f"\nDone. Report saved to {final_output_path}")
    print(f"Top differential: {by_differential[0]['web_name']} ({by_differential[0]['differential_score']:.0f}, "
          f"{by_differential[0]['selected_by_percent']}% owned, fixture multiplier {by_differential[0]['fixture_multiplier']})")

    return final_output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the FPL weekly pipeline")
    parser.add_argument("--output", type=str, default=None,
                         help="Output file path (default: dated filename, e.g. fpl_report_gw1_20260809.html). "
                              "Use a fixed path like docs/index.html for automated/hosted runs.")
    parser.add_argument("--squad-mode", type=str, default="balanced", choices=["balanced", "differential"],
                         help="Squad optimization mode (default: balanced)")
    args = parser.parse_args()
    run_pipeline(output_path=args.output, squad_mode=args.squad_mode)
