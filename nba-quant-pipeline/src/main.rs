use anyhow::Result;
use dotenv::dotenv;
use serde::{Deserialize, Serialize};
use std::env;
use tokio::time::{sleep, Duration};
use rand::Rng;

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

// ---------------- FETCH FUNCTION ----------------

async fn fetch_odds(client: &reqwest::Client, api_key: &str) -> Result<()> {
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
        .unwrap_or("unknown");

    tracing::info!("Requests remaining: {}", remaining);

    let games: Vec<Game> = response.json().await?;

    tracing::info!("Found {} games", games.len());

    for game in &games {
        println!(
            "\n{} vs {} ({})",
            game.away_team,
            game.home_team,
            &game.commence_time[..10]
        );

        for book in &game.bookmakers {
            for market in &book.markets {
                if market.key == "h2h" {
                    let odds: Vec<String> = market
                        .outcomes
                        .iter()
                        .map(|o| format!("{}: {}", o.name, o.price))
                        .collect();

                    println!("  [{}] {}", book.title, odds.join(" | "));
                }
            }
        }
    }

    Ok(())
}

// ---------------- MAIN LOOP ----------------

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    tracing_subscriber::fmt::init();

    let api_key = env::var("ODDS_API_KEY").expect("ODDS_API_KEY not set");
    let client = reqwest::Client::new();

    tracing::info!("Starting NBA odds polling service...");

    loop {
        match fetch_odds(&client, &api_key).await {
            Ok(_) => tracing::info!("Scrape successful"),
            Err(e) => tracing::error!("Scrape failed: {:?}", e),
        }

        // Add jitter to avoid hitting API at exact same intervals
        let mut rng = rand::thread_rng();
        let jitter = rng.gen_range(0..10);

        let sleep_time = 60 + jitter;

        tracing::info!("Sleeping for {} seconds...", sleep_time);

        sleep(Duration::from_secs(sleep_time)).await;
    }
}