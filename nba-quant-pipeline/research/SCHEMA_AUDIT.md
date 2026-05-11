# NBA Quant Pipeline — Schema & Data Audit

**Generated from:** `migrations/001_create_schema.sql`, `002_seed_teams.sql`, `003_extend_odds_snapshots.sql`

---

## Table Inventory

| Table | Purpose | PK | Est. Scale |
|---|---|---|---|
| `teams` | Reference: 30 NBA franchises | `abbreviation` (VARCHAR 5) | 30 rows |
| `historical_games` | Game outcomes backfilled from nba_api | `game_id` (VARCHAR 20) | ~11k rows (9 seasons × ~1230 games) |
| `odds_snapshots` | Live sportsbook odds captured by Rust scraper | `id` (BIGSERIAL) | Growing — multi-book × multi-market × snapshots over time |
| `team_stats` | Season-level team aggregate stats | `(team_name, game_date)` | 30 per snapshot day |
| `player_stats` | Season-level player aggregate stats | `(player_name, game_date)` | ~450 per snapshot day |
| `pipeline_runs` | Job observability / tracking | `id` (BIGSERIAL) | One per scrape cycle |

---

## Detailed Column Inventory

### `teams`
| Column | Type | Constraints |
|---|---|---|
| `abbreviation` | VARCHAR(5) | **PK** |
| `full_name` | VARCHAR(100) | NOT NULL, UNIQUE |
| `city` | VARCHAR(50) | NOT NULL |
| `conference` | VARCHAR(4) | NOT NULL, CHECK East/West |

### `historical_games`
| Column | Type | Constraints |
|---|---|---|
| `game_id` | VARCHAR(20) | **PK** |
| `season` | VARCHAR(10) | NOT NULL |
| `game_date` | DATE | NOT NULL |
| `home_team` | VARCHAR(5) | NOT NULL, **FK → teams** |
| `away_team` | VARCHAR(5) | NOT NULL, **FK → teams** |
| `home_score` | INTEGER | NOT NULL |
| `away_score` | INTEGER | NOT NULL |
| `home_win` | BOOLEAN | NOT NULL |
| `actual_spread` | INTEGER | NOT NULL (home_score - away_score) |
| `actual_total` | INTEGER | NOT NULL (home_score + away_score) |

**Indexes:** `game_date`, `season`, `home_team`, `away_team`

### `odds_snapshots`
| Column | Type | Constraints |
|---|---|---|
| `id` | BIGSERIAL | **PK** |
| `game_id` | VARCHAR(64) | NOT NULL (Odds API game ID) |
| `commence_time` | TIMESTAMPTZ | NOT NULL |
| `home_team` | VARCHAR(5) | NOT NULL, **FK → teams** |
| `away_team` | VARCHAR(5) | NOT NULL, **FK → teams** |
| `bookmaker` | VARCHAR(50) | NOT NULL |
| `market_type` | VARCHAR(20) | NOT NULL (h2h / spreads / totals) |
| `outcome_name` | VARCHAR(100) | NOT NULL |
| `price` | DOUBLE PRECISION | NOT NULL (American odds) |
| `point` | DOUBLE PRECISION | nullable (spread/total line) |
| `captured_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| `sport` | VARCHAR(50) | NOT NULL, DEFAULT 'basketball_nba' |
| `historical_game_id` | VARCHAR(20) | nullable, **FK → historical_games** |

**Indexes:** `game_id`, `captured_at`, `market_type`, `(bookmaker, market_type)`, `sport`, `historical_game_id`

### `team_stats`
| Column | Type | Constraints |
|---|---|---|
| `team_name` | VARCHAR(100) | **PK (composite)** — full name, not abbreviation |
| `game_date` | DATE | **PK (composite)** |
| `season` | VARCHAR(10) | NOT NULL |
| `wins` | INTEGER | |
| `losses` | INTEGER | |
| `win_pct` | DOUBLE PRECISION | |
| `pts_per_game` | DOUBLE PRECISION | |
| `plus_minus` | DOUBLE PRECISION | |
| `fg3a` | DOUBLE PRECISION | |
| `fg3_pct` | DOUBLE PRECISION | |
| `off_rating` | DOUBLE PRECISION | |
| `def_rating` | DOUBLE PRECISION | |
| `net_rating` | DOUBLE PRECISION | |
| `pace` | DOUBLE PRECISION | |

**Note:** `team_name` uses full names (e.g. "Boston Celtics") — requires join through `teams.full_name` to link to other tables.

### `player_stats`
| Column | Type | Constraints |
|---|---|---|
| `player_name` | VARCHAR(100) | **PK (composite)** |
| `team_name` | VARCHAR(10) | NOT NULL (abbreviation here) |
| `game_date` | DATE | **PK (composite)** |
| `season` | VARCHAR(10) | NOT NULL |
| `pts_per_game` | DOUBLE PRECISION | |
| `reb_per_game` | DOUBLE PRECISION | |
| `ast_per_game` | DOUBLE PRECISION | |
| `minutes_per_game` | DOUBLE PRECISION | |
| `plus_minus` | DOUBLE PRECISION | |
| `fg3_pct` | DOUBLE PRECISION | |

### `pipeline_runs`
| Column | Type | Constraints |
|---|---|---|
| `id` | BIGSERIAL | **PK** |
| `job_name` | VARCHAR(100) | NOT NULL |
| `started_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| `ended_at` | TIMESTAMPTZ | |
| `rows_in` | INTEGER | |
| `rows_out` | INTEGER | |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'running' |
| `error` | TEXT | |

---

## Join Paths

```
historical_games.home_team ──FK──→ teams.abbreviation
historical_games.away_team ──FK──→ teams.abbreviation
odds_snapshots.home_team   ──FK──→ teams.abbreviation
odds_snapshots.away_team   ──FK──→ teams.abbreviation
odds_snapshots.historical_game_id ──FK──→ historical_games.game_id
team_stats.team_name       ──via──→ teams.full_name (implicit, no FK)
player_stats.team_name     ──via──→ teams.abbreviation (implicit, no FK)
```

### Key Join for Modeling

The **critical join** is `odds_snapshots.historical_game_id → historical_games.game_id`:
- Links live odds data to actual game outcomes
- Populated by the Rust scraper's fuzzy date-matching logic
- May be NULL for games that couldn't be matched
- This is the foundation for the modeling dataset

### Secondary Joins
- `team_stats` → `teams` via `team_stats.team_name = teams.full_name`
- Then to `historical_games` via `teams.abbreviation = historical_games.home_team|away_team`

---

## Tables Usable for Modeling

| Data Type | Table | Key Columns |
|---|---|---|
| **Targets** | `historical_games` | `home_win`, `actual_spread`, `home_score`, `away_score` |
| **Odds features** | `odds_snapshots` | `price`, `point`, `market_type`, `bookmaker`, `captured_at`, `commence_time` |
| **Team strength** | `team_stats` | `off_rating`, `def_rating`, `net_rating`, `pace`, `win_pct` |
| **Player context** | `player_stats` | `pts_per_game`, `plus_minus` (future use) |
| **Reference** | `teams` | Name resolution between tables |

---

## Known Schema Quirks

1. **team_stats.team_name is full name** while most other tables use abbreviation — must join through `teams` table
2. **odds_snapshots.game_id is the Odds API ID** (64-char), not the NBA API game_id — linking relies on `historical_game_id`
3. **actual_spread is INTEGER** — stored as `home_score - away_score`, positive means home won
4. **odds prices are American format** — need conversion to implied probability
5. **team_stats are point-in-time snapshots**, not rolling per-game — they capture season-to-date aggregates on the snapshot date
6. **historical_game_id on odds_snapshots may be NULL** — not all odds snapshots successfully link to historical games
