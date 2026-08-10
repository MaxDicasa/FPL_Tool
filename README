FPL Tool

A fully automated Fantasy Premier League analytics pipeline: pulls live data from the official FPL API, scores every player on underlying quality and fixture difficulty, optimizes a budget-legal 15-man squad using integer linear programming, and publishes a self-updating report — no manual steps required after setup.

Live report: https://maxdicasa.github.io/FPL_Tool/

What it does
Pulls live data directly from the official Fantasy Premier League API — no scraping, no static datasets
Scores every player on underlying performance metrics (ICT Index, Expected Goal Involvements) rather than raw points or reputation, so undervalued/low-ownership players surface naturally
Adjusts for fixture difficulty — a player's score is weighted up or down based on how easy or hard their next 5 fixtures are, using FPL's own difficulty ratings
Builds an optimal squad using integer linear programming (PuLP) — guarantees the mathematically best possible 15-man squad under real constraints (£100m budget, valid position split, max 3 players per club), not just a greedy approximation
Suggests a starting XI and captain from within that squad
Runs itself weekly via GitHub Actions on a schedule, publishing a fresh HTML report to GitHub Pages automatically — the live link above is never stale by more than a few days
Tech stack
Python — data pipeline, scoring logic, optimization
PuLP — integer linear programming for constrained squad optimization
GitHub Actions — scheduled automation, no server required
GitHub Pages — free static hosting for the published report
Fantasy Premier League API — live player, team, and fixture data
How it works
FPL API (players + fixtures)
        │
        ▼
 fixture_difficulty.py    →  each team's next-5-gameweek difficulty rating
        │
        ▼
 differential_picks.py    →  value score + fixture-adjusted differential score per player
        │
        ▼
 squad_builder.py         →  ILP solver picks the optimal 15-man squad + starting XI
        │
        ▼
 generate_report.py       →  renders the styled HTML report
        │
        ▼
 fpl_weekly_pipeline.py   →  orchestrates all of the above end to end
        │
        ▼
 GitHub Actions (weekly)  →  runs the pipeline, commits docs/index.html
        │
        ▼
 GitHub Pages             →  serves the live report
Running it locally
bash
pip install -r requirements.txt
python fpl_weekly_pipeline.py

This downloads fresh data, scores every player, builds the optimal squad, and writes a dated HTML report to the current folder. Pass --output docs/index.html to overwrite the file the live site serves instead.

Transfer suggestions for an existing squad

transfer_suggester.py is a separate tool for in-season use: given a squad you already own, it finds the best single free transfer (and flags whether a second, point-costing transfer is worth it) rather than rebuilding from scratch. Edit the CURRENT_SQUAD list at the top of the file to match your actual team before running it.

bash
python transfer_suggester.py
Repository structure
fpl_weekly_pipeline.py     # orchestrator - run this for the full pipeline
differential_picks.py      # value + differential scoring model
fixture_difficulty.py      # fixture difficulty ratings per team
squad_builder.py           # ILP-based optimal squad construction
generate_report.py         # HTML report rendering
transfer_suggester.py      # in-season transfer recommendations (run locally)
.github/workflows/         # scheduled automation config
docs/                      # published report (served by GitHub Pages)
Possible future directions
Interactive web app allowing squad updates and transfer suggestions from mobile, rather than editing a Python file
Automated chip-timing suggestions (Wildcard/Free Hit) based on squad quality trends
Historical tracking of suggested picks vs. actual gameweek outcomes
