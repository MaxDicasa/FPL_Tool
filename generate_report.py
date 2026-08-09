"""
Generates the styled HTML FPL Differential Picks report from real bootstrap
data. Run generate_report_data.py first (or reuse report_data.json).
"""

import json
import os


def ownership_gauge_html(ownership_pct, max_scale=35):
    """Broadcast-style gauge bar: fill shows ownership %, marker shows the
    10% differential threshold. Lower fill relative to the marker = better
    differential (fewer managers have this player)."""
    fill_pct = min(100, (ownership_pct / max_scale) * 100)
    marker_pct = min(100, (10 / max_scale) * 100)
    return f'''<div class="gauge">
        <div class="gauge-track">
            <div class="gauge-fill" style="width:{fill_pct:.1f}%"></div>
            <div class="gauge-marker" style="left:{marker_pct:.1f}%"></div>
        </div>
        <span class="gauge-label">{ownership_pct:.1f}% owned</span>
    </div>'''


def player_card_html(p, rank):
    pos_class = p["position"].lower()
    news_flag = f'<span class="news-flag">{p["news"]}</span>' if p.get("news") else ""
    return f'''<div class="player-card">
        <div class="rank-num">{rank:02d}</div>
        <div class="card-main">
            <div class="card-top">
                <span class="pos-chip pos-{pos_class}">{p["position"]}</span>
                <span class="player-name">{p["web_name"]}</span>
                <span class="team-name">{p["team_name"]}</span>
                <span class="cost">£{p["cost_m"]:.1f}m</span>
            </div>
            {ownership_gauge_html(p["selected_by_percent"])}
            <div class="stat-row">
                <div class="stat"><span class="stat-val">{p["ict_index"]:.1f}</span><span class="stat-label">ICT</span></div>
                <div class="stat"><span class="stat-val">{p["expected_goal_involvements"]:.2f}</span><span class="stat-label">xGI</span></div>
                <div class="stat"><span class="stat-val">{p["total_points"]}</span><span class="stat-label">PTS 25/26</span></div>
                <div class="stat stat-score"><span class="stat-val">{p["differential_score"]:.0f}</span><span class="stat-label">SCORE</span></div>
            </div>
            {news_flag}
        </div>
    </div>'''


def value_row_html(p, rank):
    pos_class = p["position"].lower()
    return f'''<tr>
        <td class="rank-cell">{rank}</td>
        <td><span class="pos-chip pos-{pos_class} small">{p["position"]}</span></td>
        <td class="name-cell">{p["web_name"]}</td>
        <td class="team-cell">{p["team_name"]}</td>
        <td class="num-cell">£{p["cost_m"]:.1f}m</td>
        <td class="num-cell">{p["total_points"]}</td>
        <td class="num-cell highlight">{p["value_score"]:.1f}</td>
        <td class="num-cell">{p["selected_by_percent"]:.1f}%</td>
    </tr>'''


def squad_player_row_html(p, starting_names, captain_name):
    is_starting = p["web_name"] in starting_names
    is_captain = p["web_name"] == captain_name and is_starting
    badge = ' <span class="cap-badge">C</span>' if is_captain else ""
    bench_tag = '<span class="bench-tag">BENCH</span>' if not is_starting else ""
    row_class = "squad-player" if is_starting else "squad-player squad-player-bench"
    return f'''<div class="{row_class}">
        <span class="squad-player-name">{p["web_name"]}{badge}</span>
        <span class="squad-player-team">{p["team_name"]}</span>
        <span class="squad-player-cost">£{p["cost_m"]:.1f}m</span>
        {bench_tag}
    </div>'''


def squad_section_html(data):
    squad = data.get("squad")
    if not squad:
        return ""

    starting_xi = data.get("starting_xi") or []
    captain_name = data.get("captain_name")
    starting_names = set(p["web_name"] for p in starting_xi)

    blocks = ""
    for pos_name in ["GKP", "DEF", "MID", "FWD"]:
        pos_players = [p for p in squad if p["position"] == pos_name]
        if not pos_players:
            continue
        rows = "\n".join(
            squad_player_row_html(p, starting_names, captain_name)
            for p in sorted(pos_players, key=lambda p: -p["now_cost"])
        )
        blocks += f'''<div class="squad-pos-col">
            <h4 class="squad-pos-heading">{pos_name}</h4>
            {rows}
        </div>'''

    mode_label = "Balanced — best overall quality" if data.get("squad_mode") == "balanced" else "Differential — contrarian, low ownership"

    return f'''
  <section>
    <div class="section-head">
      <h2>Optimal Squad</h2>
      <span class="desc">£{data.get("squad_cost", 0):.1f}m of £100.0m · {mode_label} · Captain: {captain_name}</span>
    </div>
    <div class="squad-grid">
      {blocks}
    </div>
    <p class="squad-note">Starting XI shown in full color, bench dimmed and marked BENCH. Captain (C) doubles points in real FPL scoring.</p>
  </section>'''


def build_report(data_path: str, output_path: str):
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    top_diff_cards = "\n".join(
        player_card_html(p, i + 1) for i, p in enumerate(data["top_differentials"][:9])
    )
    value_rows = "\n".join(
        value_row_html(p, i + 1) for i, p in enumerate(data["top_value"][:12])
    )

    position_sections = ""
    for pos_name, players in data["by_position"].items():
        cards = "\n".join(player_card_html(p, i + 1) for i, p in enumerate(players[:4]))
        position_sections += f'''
        <div class="position-block">
            <h3 class="position-heading">{pos_name}</h3>
            <div class="card-grid">{cards}</div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>FPL Differential Picks — GW1</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --pitch: #0B2E1F;
    --pitch-deep: #072016;
    --card: #F5F7F2;
    --lime: #D4FF3F;
    --muted: #8FA89C;
    --flag: #FF5A3C;
    --text-dark: #0B2E1F;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--pitch);
    background-image:
      repeating-linear-gradient(0deg, transparent, transparent 79px, rgba(255,255,255,0.025) 79px, rgba(255,255,255,0.025) 80px);
    color: var(--card);
    font-family: 'Inter', sans-serif;
    padding: 0 0 80px;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 0 24px; }}

  header {{ padding: 64px 24px 48px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); }}
  .eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    color: var(--lime);
    letter-spacing: 0.15em;
    font-size: 13px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }}
  h1 {{
    font-family: 'Archivo Black', sans-serif;
    font-size: clamp(36px, 6vw, 64px);
    line-height: 1.0;
    letter-spacing: -0.01em;
    margin-bottom: 12px;
  }}
  h1 span {{ color: var(--lime); }}
  .subhead {{ color: var(--muted); font-size: 16px; max-width: 480px; margin: 0 auto; }}
  .deadline {{
    display: inline-block;
    margin-top: 28px;
    font-family: 'IBM Plex Mono', monospace;
    background: rgba(212,255,63,0.1);
    border: 1px solid rgba(212,255,63,0.3);
    color: var(--lime);
    padding: 8px 18px;
    border-radius: 4px;
    font-size: 13px;
  }}

  section {{ padding: 56px 0 0; }}
  .section-head {{ display: flex; align-items: baseline; gap: 14px; margin-bottom: 24px; }}
  .section-head h2 {{
    font-family: 'Archivo Black', sans-serif;
    font-size: 26px;
    text-transform: uppercase;
  }}
  .section-head .desc {{ color: var(--muted); font-size: 14px; }}

  .card-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
  @media (max-width: 720px) {{ .card-grid {{ grid-template-columns: 1fr; }} }}

  .player-card {{
    background: var(--card);
    color: var(--text-dark);
    border-radius: 6px;
    padding: 16px;
    display: flex;
    gap: 12px;
    position: relative;
    overflow: hidden;
  }}
  .rank-num {{
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    font-size: 13px;
    color: rgba(11,46,31,0.35);
    flex-shrink: 0;
  }}
  .card-main {{ flex: 1; min-width: 0; }}
  .card-top {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
  .pos-chip {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 3px;
    color: var(--pitch-deep);
  }}
  .pos-chip.small {{ font-size: 10px; }}
  .pos-gkp {{ background: #FFD84D; }}
  .pos-def {{ background: #8FE3C7; }}
  .pos-mid {{ background: #A8D4FF; }}
  .pos-fwd {{ background: var(--lime); }}
  .player-name {{ font-weight: 700; font-size: 15px; }}
  .team-name {{ color: #5A6E64; font-size: 12px; }}
  .cost {{ margin-left: auto; font-family: 'IBM Plex Mono', monospace; font-size: 13px; font-weight: 600; }}

  .gauge {{ margin-bottom: 10px; }}
  .gauge-track {{
    position: relative;
    height: 6px;
    background: rgba(11,46,31,0.12);
    border-radius: 3px;
    margin-bottom: 4px;
  }}
  .gauge-fill {{ position: absolute; height: 100%; background: var(--pitch); border-radius: 3px; }}
  .gauge-marker {{
    position: absolute;
    top: -2px;
    width: 2px;
    height: 10px;
    background: var(--flag);
  }}
  .gauge-label {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #5A6E64; }}

  .stat-row {{ display: flex; gap: 14px; padding-top: 6px; border-top: 1px solid rgba(11,46,31,0.08); }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat-val {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 15px; }}
  .stat-label {{ font-size: 9px; color: #5A6E64; letter-spacing: 0.05em; }}
  .stat-score {{ margin-left: auto; }}
  .stat-score .stat-val {{ color: #0B7A4B; }}
  .news-flag {{
    display: block;
    margin-top: 8px;
    font-size: 11px;
    color: var(--flag);
    font-style: italic;
  }}

  table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 6px; overflow: hidden; }}
  th {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #5A6E64;
    text-align: left;
    padding: 12px 14px;
    border-bottom: 2px solid rgba(11,46,31,0.1);
  }}
  td {{ padding: 11px 14px; color: var(--text-dark); font-size: 14px; border-bottom: 1px solid rgba(11,46,31,0.06); }}
  .rank-cell {{ font-family: 'IBM Plex Mono', monospace; color: #5A6E64; }}
  .name-cell {{ font-weight: 600; }}
  .team-cell {{ color: #5A6E64; }}
  .num-cell {{ font-family: 'IBM Plex Mono', monospace; text-align: right; }}
  .num-cell.highlight {{ color: #0B7A4B; font-weight: 600; }}
  th:nth-child(n+5), th:nth-child(n+5) {{ text-align: right; }}

  .position-heading {{
    font-family: 'IBM Plex Mono', monospace;
    color: var(--lime);
    font-size: 13px;
    letter-spacing: 0.1em;
    margin-bottom: 12px;
    padding-top: 32px;
  }}

  .squad-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
  @media (max-width: 720px) {{ .squad-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  .squad-pos-col {{ background: var(--card); border-radius: 6px; padding: 14px; }}
  .squad-pos-heading {{
    font-family: 'IBM Plex Mono', monospace;
    color: var(--pitch);
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(11,46,31,0.1);
  }}
  .squad-player {{
    display: flex;
    align-items: baseline;
    gap: 6px;
    flex-wrap: wrap;
    padding: 6px 0;
    color: var(--text-dark);
    font-size: 13px;
  }}
  .squad-player-bench {{ opacity: 0.45; }}
  .squad-player-name {{ font-weight: 700; }}
  .cap-badge {{
    display: inline-block;
    background: var(--lime);
    color: var(--pitch-deep);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
    margin-left: 2px;
  }}
  .squad-player-team {{ color: #5A6E64; font-size: 11px; }}
  .squad-player-cost {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; margin-left: auto; }}
  .bench-tag {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8px;
    letter-spacing: 0.05em;
    color: var(--flag);
    width: 100%;
  }}
  .squad-note {{ margin-top: 14px; font-size: 12px; color: var(--muted); }}

  footer {{
    margin-top: 64px;
    padding-top: 24px;
    border-top: 1px solid rgba(255,255,255,0.1);
    color: var(--muted);
    font-size: 12px;
    text-align: center;
    line-height: 1.6;
  }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="eyebrow">Fantasy Premier League — Pre-Season Report</div>
    <h1>Differentials <span>&amp;</span> Value<br>Before Gameweek 1</h1>
    <p class="subhead">{data["eligible_count"]} qualifying players scored on underlying output (ICT, expected goal involvements) weighted against ownership — the picks other managers aren't making yet.</p>
    <div class="deadline">GW1 DEADLINE · AUG 21, 2026 · 17:30 UTC</div>
  </div>
</header>

<div class="wrap">
  <section>
    <div class="section-head">
      <h2>Top Differentials</h2>
      <span class="desc">Strong underlying stats, low ownership</span>
    </div>
    <div class="card-grid">
      {top_diff_cards}
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Best Value</h2>
      <span class="desc">Points delivered per £m spent</span>
    </div>
    <table>
      <thead>
        <tr><th>#</th><th>Pos</th><th>Player</th><th>Team</th><th>Cost</th><th>Pts</th><th>Value</th><th>Own%</th></tr>
      </thead>
      <tbody>
        {value_rows}
      </tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h2>By Position</h2>
      <span class="desc">Top 4 differentials in each slot — build your squad</span>
    </div>
    {position_sections}
  </section>
  {squad_section_html(data)}
  <footer>
    Data: official Fantasy Premier League API, pulled {data.get("pulled_note", "pre-season 2026/27")}.<br>
    Stats reflect last completed season (2025/26) as the pre-season baseline — will update as 2026/27 gameweeks are played.<br>
    Not betting advice. Build your own squad, this is one input among many.
  </footer>
</div>
</body>
</html>'''

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    build_report("/home/claude/fpl_tool/report_data.json", "/home/claude/fpl_tool/fpl_report.html")
