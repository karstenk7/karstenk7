use anyhow::Result;
use chrono::{DateTime, FixedOffset, NaiveDate, Utc};
use dotenv::dotenv;
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use tokio::time::{sleep, Duration};
use tokio_postgres::{Client, NoTls};

// ---------------------------------------------------------------------------
// Odds API response types
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize, Serialize)]
struct Game {
    id: String,
    sport_key: String,
    commence_time: String,
    home_team: String,
    away_team: String,
    bookmakers: Vec<Bookmaker>,
}

#[derive(Debug, Deserialize, Serialize)]
struct Bookmaker {
    key: String,
    title: String,
    last_update: String,
    markets: Vec<Market>,
}

#[derive(Debug, Deserialize, Serialize)]
struct Market {
    key: String,
    last_update: String,
    outcomes: Vec<Outcome>,
}

#[derive(Debug, Deserialize, Serialize)]
struct Outcome {
    name: String,
    price: f64,
    point: Option<f64>,
}

// ---------------------------------------------------------------------------
// Configuration (all from environment, with sensible defaults)
// ---------------------------------------------------------------------------

struct Config {
    api_key: String,
    sport: String,
    poll_interval_secs: u64,
    dedup_window_secs: i64,
}

impl Config {
    fn from_env() -> Self {
        Self {
            api_key: env::var("ODDS_API_KEY").expect("ODDS_API_KEY not set"),
            sport: env::var("ODDS_SPORT").unwrap_or_else(|_| "basketball_nba".into()),
            poll_interval_secs: env::var("ODDS_POLL_INTERVAL_SECS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(300),
            dedup_window_secs: env::var("ODDS_DEDUP_WINDOW_SECS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(120),
        }
    }

    fn api_url(&self) -> String {
        format!(
            "https://api.the-odds-api.com/v4/sports/{}/odds/\
             ?apiKey={}&regions=us&markets=h2h,spreads,totals&oddsFormat=american",
            self.sport, self.api_key
        )
    }
}

// ---------------------------------------------------------------------------
// Team name → abbreviation lookup
// ---------------------------------------------------------------------------

fn build_team_lookup() -> HashMap<&'static str, &'static str> {
    HashMap::from([
        ("Atlanta Hawks", "ATL"),
        ("Boston Celtics", "BOS"),
        ("Brooklyn Nets", "BKN"),
        ("Charlotte Hornets", "CHA"),
        ("Chicago Bulls", "CHI"),
        ("Cleveland Cavaliers", "CLE"),
        ("Dallas Mavericks", "DAL"),
        ("Denver Nuggets", "DEN"),
        ("Detroit Pistons", "DET"),
        ("Golden State Warriors", "GSW"),
        ("Houston Rockets", "HOU"),
        ("Indiana Pacers", "IND"),
        ("Los Angeles Clippers", "LAC"),
        ("LA Clippers", "LAC"),
        ("Los Angeles Lakers", "LAL"),
        ("LA Lakers", "LAL"),
        ("Memphis Grizzlies", "MEM"),
        ("Miami Heat", "MIA"),
        ("Milwaukee Bucks", "MIL"),
        ("Minnesota Timberwolves", "MIN"),
        ("New Orleans Pelicans", "NOP"),
        ("New York Knicks", "NYK"),
        ("Oklahoma City Thunder", "OKC"),
        ("Orlando Magic", "ORL"),
        ("Philadelphia 76ers", "PHI"),
        ("Phoenix Suns", "PHX"),
        ("Portland Trail Blazers", "POR"),
        ("Sacramento Kings", "SAC"),
        ("San Antonio Spurs", "SAS"),
        ("Toronto Raptors", "TOR"),
        ("Utah Jazz", "UTA"),
        ("Washington Wizards", "WAS"),
    ])
}

fn resolve_team<'a>(full_name: &str, lookup: &'a HashMap<&str, &str>) -> Option<&'a str> {
    lookup.get(full_name).copied()
}

// ---------------------------------------------------------------------------
// Database connection
// ---------------------------------------------------------------------------

async fn connect_db() -> Result<Client> {
    let db_url = env::var("DATABASE_URL").expect("DATABASE_URL not set");
    let (client, connection) = tokio_postgres::connect(&db_url, NoTls).await?;

    tokio::spawn(async move {
        if let Err(e) = connection.await {
            tracing::error!("Postgres connection error: {:?}", e);
        }
    });

    Ok(client)
}

// ---------------------------------------------------------------------------
// Historical game mapping
//
// Attempts to link an Odds API game to a historical_games row by matching
// home/away abbreviations and date.  Returns None (and logs) when the
// match is missing or ambiguous — the odds row is still inserted.
// ---------------------------------------------------------------------------

async fn resolve_historical_game_id(
    db: &Client,
    home_abbr: &str,
    away_abbr: &str,
    commence: &DateTime<FixedOffset>,
) -> Option<String> {
    let game_date = commence.date_naive();

    let rows = db
        .query(
            "SELECT game_id FROM historical_games \
             WHERE home_team = $1 AND away_team = $2 AND game_date = $3",
            &[&home_abbr, &away_abbr, &game_date],
        )
        .await
        .ok()?;

    if rows.len() == 1 {
        return Some(rows[0].get(0));
    }
    if rows.len() > 1 {
        tracing::warn!(
            "Ambiguous game mapping: {} rows for {} @ {} on {}",
            rows.len(),
            away_abbr,
            home_abbr,
            game_date
        );
        return None;
    }

    // Fuzzy: ±1 day to handle timezone drift between APIs
    let day_before = game_date - chrono::Duration::days(1);
    let day_after = game_date + chrono::Duration::days(1);
    let rows = db
        .query(
            "SELECT game_id, game_date FROM historical_games \
             WHERE home_team = $1 AND away_team = $2 \
             AND game_date BETWEEN $3 AND $4",
            &[&home_abbr, &away_abbr, &day_before, &day_after],
        )
        .await
        .ok()?;

    if rows.len() == 1 {
        let matched: NaiveDate = rows[0].get(1);
        tracing::info!(
            "Fuzzy date match: {} @ {} on {} → historical {}",
            away_abbr,
            home_abbr,
            game_date,
            matched
        );
        return Some(rows[0].get(0));
    }

    if rows.len() > 1 {
        tracing::warn!(
            "Ambiguous fuzzy match: {} rows for {} @ {} near {}",
            rows.len(),
            away_abbr,
            home_abbr,
            game_date
        );
    }

    None
}

// ---------------------------------------------------------------------------
// Dedup: load the most recent snapshot per unique key so we can skip
// unchanged lines and only record actual line movement.
// ---------------------------------------------------------------------------

type SnapKey = (String, String, String, String);
type SnapVal = (f64, Option<f64>);

async fn load_recent_snapshots(
    db: &Client,
    dedup_window_secs: i64,
) -> HashMap<SnapKey, SnapVal> {
    let cutoff = Utc::now() - chrono::Duration::seconds(dedup_window_secs);
    let rows = db
        .query(
            "SELECT DISTINCT ON (game_id, bookmaker, market_type, outcome_name) \
                    game_id, bookmaker, market_type, outcome_name, price, point \
             FROM odds_snapshots \
             WHERE captured_at > $1 \
             ORDER BY game_id, bookmaker, market_type, outcome_name, captured_at DESC",
            &[&cutoff],
        )
        .await
        .unwrap_or_default();

    let mut map = HashMap::with_capacity(rows.len());
    for row in &rows {
        let key: SnapKey = (row.get(0), row.get(1), row.get(2), row.get(3));
        let val: SnapVal = (row.get(4), row.get(5));
        map.insert(key, val);
    }
    map
}

fn points_match(a: &Option<f64>, b: &Option<f64>) -> bool {
    match (a, b) {
        (None, None) => true,
        (Some(x), Some(y)) => (x - y).abs() < 0.001,
        _ => false,
    }
}

// ---------------------------------------------------------------------------
// Pipeline run tracking (writes to pipeline_runs table)
// ---------------------------------------------------------------------------

async fn start_run(db: &Client, job: &str) -> Option<i64> {
    db.query_one(
        "INSERT INTO pipeline_runs (job_name) VALUES ($1) RETURNING id",
        &[&job],
    )
    .await
    .ok()
    .map(|r| r.get(0))
}

async fn finish_run(
    db: &Client,
    id: i64,
    rows_in: i32,
    rows_out: i32,
    status: &str,
    err: Option<&str>,
) {
    let _ = db
        .execute(
            "UPDATE pipeline_runs \
             SET ended_at = NOW(), rows_in = $2, rows_out = $3, status = $4, error = $5 \
             WHERE id = $1",
            &[&id, &rows_in, &rows_out, &status, &err],
        )
        .await;
}

// ---------------------------------------------------------------------------
// Core scrape cycle
// ---------------------------------------------------------------------------

struct ScrapeStats {
    games_found: i32,
    inserted: i32,
    deduped: i32,
    skipped_teams: i32,
    skipped_validation: i32,
}

async fn fetch_and_store_odds(
    http: &reqwest::Client,
    db: &Client,
    config: &Config,
    team_lookup: &HashMap<&str, &str>,
) -> Result<ScrapeStats> {
    let url = config.api_url();
    tracing::info!("Fetching {} odds...", config.sport);

    let response = http.get(&url).send().await?;

    let remaining = response
        .headers()
        .get("x-requests-remaining")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("unknown");
    tracing::info!("API requests remaining: {}", remaining);

    if !response.status().is_success() {
        anyhow::bail!("API returned status {}", response.status());
    }

    let games: Vec<Game> = response.json().await?;
    let batch_time = Utc::now();

    tracing::info!("Found {} games", games.len());

    let recent = load_recent_snapshots(db, config.dedup_window_secs).await;
    tracing::info!("Loaded {} recent snapshot keys for dedup", recent.len());

    let mut stats = ScrapeStats {
        games_found: games.len() as i32,
        inserted: 0,
        deduped: 0,
        skipped_teams: 0,
        skipped_validation: 0,
    };

    for game in &games {
        let home_abbr = match resolve_team(&game.home_team, team_lookup) {
            Some(a) => a,
            None => {
                tracing::warn!("Unknown home team: '{}'", game.home_team);
                stats.skipped_teams += 1;
                continue;
            }
        };
        let away_abbr = match resolve_team(&game.away_team, team_lookup) {
            Some(a) => a,
            None => {
                tracing::warn!("Unknown away team: '{}'", game.away_team);
                stats.skipped_teams += 1;
                continue;
            }
        };

        let commence = match DateTime::parse_from_rfc3339(&game.commence_time) {
            Ok(dt) => dt,
            Err(e) => {
                tracing::warn!(
                    "Bad commence_time '{}' for game {}: {}",
                    game.commence_time,
                    game.id,
                    e
                );
                stats.skipped_validation += 1;
                continue;
            }
        };

        let hist_id: Option<String> =
            resolve_historical_game_id(db, home_abbr, away_abbr, &commence).await;

        for book in &game.bookmakers {
            for market in &book.markets {
                if !["h2h", "spreads", "totals"].contains(&market.key.as_str()) {
                    tracing::warn!("Skipping unexpected market type: {}", market.key);
                    continue;
                }

                for outcome in &market.outcomes {
                    if outcome.name.is_empty() {
                        tracing::warn!(
                            "Empty outcome name for game {} / {} / {}",
                            game.id,
                            book.key,
                            market.key
                        );
                        stats.skipped_validation += 1;
                        continue;
                    }

                    let key = (
                        game.id.clone(),
                        book.key.clone(),
                        market.key.clone(),
                        outcome.name.clone(),
                    );
                    if let Some((prev_price, prev_point)) = recent.get(&key) {
                        if (prev_price - outcome.price).abs() < 0.001
                            && points_match(prev_point, &outcome.point)
                        {
                            stats.deduped += 1;
                            continue;
                        }
                    }

                    match db
                        .execute(
                            "INSERT INTO odds_snapshots \
                             (game_id, commence_time, home_team, away_team, bookmaker, \
                              market_type, outcome_name, price, point, captured_at, \
                              sport, historical_game_id) \
                             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
                            &[
                                &game.id,
                                &commence,
                                &home_abbr,
                                &away_abbr,
                                &book.key,
                                &market.key,
                                &outcome.name,
                                &outcome.price,
                                &outcome.point,
                                &batch_time,
                                &config.sport,
                                &hist_id,
                            ],
                        )
                        .await
                    {
                        Ok(_) => stats.inserted += 1,
                        Err(e) => {
                            tracing::error!(
                                "Insert failed: game={} book={} market={} outcome={}: {:?}",
                                game.id,
                                book.key,
                                market.key,
                                outcome.name,
                                e
                            );
                        }
                    }
                }
            }
        }

        tracing::info!(
            "{} @ {} | {} | hist={}",
            away_abbr,
            home_abbr,
            &game.commence_time[..10],
            hist_id.as_deref().unwrap_or("none")
        );
    }

    Ok(stats)
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    tracing_subscriber::fmt::init();

    let config = Config::from_env();
    let http = reqwest::Client::new();
    let db = connect_db().await?;
    let team_lookup = build_team_lookup();

    tracing::info!(
        "Starting odds scraper: sport={}, poll_interval={}s, dedup_window={}s",
        config.sport,
        config.poll_interval_secs,
        config.dedup_window_secs
    );

    loop {
        let job_name = format!("odds_scraper_{}", config.sport);
        let run_id = start_run(&db, &job_name).await;

        match fetch_and_store_odds(&http, &db, &config, &team_lookup).await {
            Ok(stats) => {
                tracing::info!(
                    "Cycle complete: games={} inserted={} deduped={} skipped_teams={} skipped_validation={}",
                    stats.games_found,
                    stats.inserted,
                    stats.deduped,
                    stats.skipped_teams,
                    stats.skipped_validation
                );
                if let Some(id) = run_id {
                    finish_run(&db, id, stats.games_found, stats.inserted, "success", None)
                        .await;
                }
            }
            Err(e) => {
                tracing::error!("Scrape cycle failed: {:?}", e);
                if let Some(id) = run_id {
                    let msg = format!("{:?}", e);
                    finish_run(&db, id, 0, 0, "error", Some(&msg)).await;
                }
            }
        }

        let mut rng = rand::thread_rng();
        let jitter = rng.gen_range(0..30);
        let sleep_secs = config.poll_interval_secs + jitter;
        tracing::info!("Sleeping {}s until next poll...", sleep_secs);
        sleep(Duration::from_secs(sleep_secs)).await;
    }
}
