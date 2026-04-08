from nba_api.stats.endpoints import leaguedashteamstats, leaguedashplayerstats, teamestimatedmetrics
import pandas as pd
import time

def test_team_stats():
    print("Fetching team stats...")
    time.sleep(1)
    stats = leaguedashteamstats.LeagueDashTeamStats(
        season="2024-25"
    ).get_data_frames()[0]

    print(f"\nGot {len(stats)} teams")
    print(stats[['TEAM_NAME', 'W', 'L', 'W_PCT', 'PTS', 'PLUS_MINUS', 'FG3A', 'FG3_PCT']].head(10))

def test_advanced_stats():
    print("\nFetching advanced team metrics...")
    time.sleep(1)
    stats = teamestimatedmetrics.TeamEstimatedMetrics(
        season="2024-25"
    ).get_data_frames()[0]

    print(f"\nColumns: {stats.columns.tolist()}")
    print(stats.head(5))

def test_player_stats():
    print("\nFetching player stats...")
    time.sleep(1)
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2024-25"
    ).get_data_frames()[0]

    print(f"\nGot {len(stats)} players")
    print(stats[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'PTS', 'REB', 'AST', 'MIN', 'PLUS_MINUS', 'FG3_PCT']].head(10))

if __name__ == "__main__":
    test_team_stats()
    test_advanced_stats()
    test_player_stats()