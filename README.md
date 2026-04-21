# Karsten Kropp

M.S. Data Science @ University of Chicago

Building data systems and models that run end-to-end — from ingestion to evaluation.

---

## nfl-quant-pipeline

**Rust · PostgreSQL · Python**

A data pipeline for collecting and analyzing sports betting market data.

- Async Rust scraper ingests live odds on a fixed interval and stores them as time-series snapshots  
- PostgreSQL schema designed for tracking line movement across sportsbooks  
- Historical game data backfilled for modeling and evaluation  
- Pipeline run tracking and validation scripts for monitoring data quality  

**Current focus:**
- Reliable odds ingestion and game mapping  
- Feature generation from line movement and market behavior  
- Preparing for backtesting and model development  

---

## Notes

This repo reflects ongoing work on:
- data pipeline design (Rust + async systems)  
- relational storage and query patterns  
- building clean datasets for downstream modeling  

Related work includes building a database engine from scratch and experimenting with forecasting models, but those are separate projects.

---

## Stack

- Rust
- Python (Pandas, scikit-learn, numpy, etc)
- SQL  
- C++ 
- Docker 
- React
- PostgreSQL  
- Debian Linux  
- Tokio  

---

## Contact

- karstrich@gmail.com
- https://www.linkedin.com/in/karsten-kropp-49024a24a/