#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# NBA Quant Research Pipeline — Bootstrap
#
# Run this on the Debian box where Postgres is running:
#   cd /path/to/nba-quant-pipeline
#   bash research/bootstrap.sh
#
# It will:
#   1. Verify Postgres is reachable
#   2. Set up a Python venv with all research deps
#   3. Run the live schema inspection
#   4. Build the modeling dataset
#   5. Train baseline models and generate evaluation report
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo " NBA Quant Research Pipeline — Bootstrap"
echo "============================================"
echo ""
echo "Project root: $PROJECT_ROOT"

# --- Load .env ---
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "[OK] Loaded .env"
else
    echo "[ERROR] No .env file found. Create one with DATABASE_URL."
    exit 1
fi

# --- Check Postgres ---
echo ""
echo "--- Step 0: Checking Postgres connection ---"
if command -v pg_isready &>/dev/null; then
    if pg_isready -q; then
        echo "[OK] Postgres is running"
    else
        echo "[WARN] pg_isready failed — Postgres may not be running."
        echo "       Start it with: sudo systemctl start postgresql"
        echo "       Then re-run this script."
        exit 1
    fi
else
    echo "[INFO] pg_isready not found, will test connection via Python"
fi

# --- Python venv ---
echo ""
echo "--- Step 1: Setting up Python environment ---"
PYTHON_CMD=""
for cmd in python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "[ERROR] No Python 3 found. Install python3 first."
    exit 1
fi

echo "Using: $PYTHON_CMD ($($PYTHON_CMD --version))"

if [ ! -d "venv" ]; then
    echo "Creating venv..."
    $PYTHON_CMD -m venv venv
fi

source venv/bin/activate
echo "[OK] Activated venv"

echo ""
echo "--- Step 2: Installing dependencies ---"
pip install --upgrade pip -q
pip install -r research/requirements.txt -q
echo "[OK] Dependencies installed"

# --- Test DB connection ---
echo ""
echo "--- Step 3: Testing database connection ---"
python -c "
import psycopg2, os
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM historical_games')
    count = cur.fetchone()[0]
    print(f'[OK] Connected. historical_games has {count:,} rows')
    conn.close()
except Exception as e:
    print(f'[ERROR] Cannot connect to DB: {e}')
    exit(1)
"

# --- Schema inspection ---
echo ""
echo "--- Step 4: Inspecting live schema ---"
python -m research.pipelines.inspect_schema
echo "[OK] Schema inspection saved to research/outputs/schema_inspection.txt"

# --- Build dataset ---
echo ""
echo "--- Step 5: Building modeling dataset ---"
python -m research.run_baseline -v

echo ""
echo "============================================"
echo " DONE — Check research/outputs/ for results"
echo "============================================"
echo ""
echo "Key outputs:"
echo "  research/outputs/schema_inspection.txt   — Live schema audit"
echo "  research/outputs/modeling_dataset.parquet — Canonical dataset"
echo "  research/outputs/dataset_summary.txt     — Dataset diagnostics"
echo "  research/outputs/evaluation_report.txt   — Model evaluation"
echo ""
echo "If odds data was sparse, re-run without odds:"
echo "  python -m research.run_baseline --no-odds -v"
echo ""
echo "To explore interactively, feed research/CURSOR_PROMPT.md to Cursor."
