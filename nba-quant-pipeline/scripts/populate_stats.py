from nba_api.stats.endpoints import leaguedashteamstats, leaguedashplayerstats, teamestimatedmetrics
import psycopg2
import os
import time
from datetime import date
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

SEASON = "2024-25"

def populate_team_stats():
    print("Fetching team stats...")
    time.sleep(1)

    basic = leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON
    ).get_data_frames()[0]

    time.sleep(1)
    advanced = teamestimatedmetrics.TeamEstimatedMetrics(
        season=SEASON
    ).get_data_frames()[0]

    # Merge on team name
    merged = basic.merge(advanced[['TEAM_NAME', 'E_OFF_RATING', 'E_DEF_RATING', 'E_NET_RATING', 'E_PACE']], on='TEAM_NAME')

    for _, row in merged.iterrows():
        cur.execute("""
            INSERT INTO team_stats (
                team_name, game_date, season,
                wins, losses, win_pct,
                pts_per_game, plus_minus,
                fg3a, fg3_pct,
                off_rating, def_rating, net_rating, pace
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (team_name, game_date) DO UPDATE SET
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses,
                net_rating = EXCLUDED.net_rating,
                pace = EXCLUDED.pace
        """, (
            row['TEAM_NAME'], date.today(), SEASON,
            row['W'], row['L'], row['W_PCT'],
            row['PTS'], row['PLUS_MINUS'],
            row['FG3A'], row['FG3_PCT'],
            row['E_OFF_RATING'], row['E_DEF_RATING'],
            row['E_NET_RATING'], row['E_PACE']
        ))

    conn.commit()
    print(f"Inserted {len(merged)} team records")

def populate_player_stats():
    print("Fetching player stats...")
    time.sleep(1)

    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON
    ).get_data_frames()[0]

    for _, row in stats.iterrows():
        cur.execute("""
            INSERT INTO player_stats (
                player_name, team_name, game_date, season,
                pts_per_game, reb_per_game, ast_per_game,
                minutes_per_game, plus_minus, fg3_pct
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_name, game_date) DO UPDATE SET
                pts_per_game = EXCLUDED.pts_per_game,
                minutes_per_game = EXCLUDED.minutes_per_game,
                plus_minus = EXCLUDED.plus_minus
        """, (
            row['PLAYER_NAME'], row['TEAM_ABBREVIATION'],
            date.today(), SEASON,
            row['PTS'], row['REB'], row['AST'],
            row['MIN'], row['PLUS_MINUS'], row['FG3_PCT']
        ))

    conn.commit()
    print(f"Inserted {len(stats)} player records")

if __name__ == "__main__":
    populate_team_stats()
    populate_player_stats()
    cur.close()
    conn.close()
    print("Done.")