use anyhow::Result;
use dotenv::dotenv;
use serde::{Deserialize, Serialize};
use std::env;

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

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    tracing_subscriber::fmt::init();

    let api_key = env::var("ODDS_API_KEY").expect("ODDS_API_KEY not set");
    let client = reqwest::Client::new();

    let url = format!(
        "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={}&regions=us&markets=h2h,spreads,totals&oddsFormat=american",
        api_key
    );

    tracing::info!("Fetching NBA odds...");

    let response = client.get(&url).send().await?;

    let remaining = response
        .headers()
        .get("x-requests-remaining")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("unknown")
        .to_string();

    tracing::info!("Requests remaining: {}", remaining);

    let games: Vec<Game> = response.json().await?;

    tracing::info!("Found {} games", games.len());

    for game in &games {
        println!("\n{} vs {} ({})", game.away_team, game.home_team, &game.commence_time[..10]);
        for book in &game.bookmakers {
            for market in &book.markets {
                if market.key == "h2h" {
                    let odds: Vec<String> = market.outcomes.iter()
                        .map(|o| format!("{}: {}", o.name, o.price))
                        .collect();
                    println!("  [{}] {}", book.title, odds.join(" | "));
                }
            }
        }
    }

    Ok(())
}