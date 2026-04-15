use anyhow::Result;
use dotenv::dotenv;
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use tokio::time::{sleep, Duration};
use tokio_postgres::{Client, NoTls};

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

fn resolve_team<'a>(
    full_name: &str,
    lookup: &'a HashMap<&str, &str>,
) -> Option<&'a str> {
    lookup.get(full_name).copied()
}

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

async fn fetch_and_store_odds(
    http: &reqwest::Client,
    db: &Client,
    api_key: &str,
    team_lookup: &HashMap<&str, &str>,
) -> Result<()> {
    let url = format!(
        "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/\
         ?apiKey={}&regions=us&markets=h2h,spreads,totals&oddsFormat=american",
        api_key
    );

    tracing::info!("Fetching NBA odds...");
    let response = http.get(&url).send().await?;

    let remaining = response
        .headers()
        .get("x-requests-remaining")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("unknown");
    tracing::info!("API requests remaining: {}", remaining);

    let games: Vec<Game> = response.json().await?;
    tracing::info!("Found {} games", games.len());

    let mut inserted: u64 = 0;
    let mut skipped: u64 = 0;

    for game in &games {
        let home_abbr = match resolve_team(&game.home_team, team_lookup) {
            Some(a) => a,
            None => {
                tracing::warn!("Unknown home team: {}", game.home_team);
                skipped += 1;
                continue;
            }
        };
        let away_abbr = match resolve_team(&game.away_team, team_lookup) {
            Some(a) => a,
            None => {
                tracing::warn!("Unknown away team: {}", game.away_team);
                skipped += 1;
                continue;
            }
        };

        let commence = chrono::DateTime::parse_from_rfc3339(&game.commence_time)
            .unwrap_or_else(|_| {
                chrono::DateTime::parse_from_rfc3339("1970-01-01T00:00:00Z").unwrap()
            });

        for book in &game.bookmakers {
            for market in &book.markets {
                for outcome in &market.outcomes {
                    db.execute(
                        "INSERT INTO odds_snapshots \
                         (game_id, commence_time, home_team, away_team, \
                          bookmaker, market_type, outcome_name, price, point) \
                         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
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
                        ],
                    )
                    .await?;
                    inserted += 1;
                }
            }
        }

        println!(
            "{} ({}) vs {} ({}) | {}",
            game.away_team,
            away_abbr,
            game.home_team,
            home_abbr,
            &game.commence_time[..10]
        );
    }

    tracing::info!(
        "Stored {} odds rows, skipped {} games (unknown teams)",
        inserted,
        skipped
    );

    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    tracing_subscriber::fmt::init();

    let api_key = env::var("ODDS_API_KEY").expect("ODDS_API_KEY not set");
    let http = reqwest::Client::new();
    let db = connect_db().await?;
    let team_lookup = build_team_lookup();

    tracing::info!("Starting NBA odds polling service...");

    loop {
        match fetch_and_store_odds(&http, &db, &api_key, &team_lookup).await {
            Ok(_) => tracing::info!("Scrape cycle complete"),
            Err(e) => tracing::error!("Scrape cycle failed: {:?}", e),
        }

        let mut rng = rand::thread_rng();
        let jitter = rng.gen_range(0..10);
        let sleep_time = 60 + jitter;

        tracing::info!("Sleeping {}s until next poll...", sleep_time);
        sleep(Duration::from_secs(sleep_time)).await;
    }
}
