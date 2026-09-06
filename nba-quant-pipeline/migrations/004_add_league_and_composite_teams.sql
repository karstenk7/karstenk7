-- Add a league discriminator to `teams` and switch its primary key to
-- (league, abbreviation). NBA and NFL share several standard abbreviations
-- (ATL, CHI, CLE, DAL, DEN, DET, HOU, IND, LAC, MIA, MIN, PHI, WAS all
-- collide between the two leagues' team lists), so a single-column PK on
-- `abbreviation` cannot hold both. Seeds the 32 NFL teams.
-- Run: psql -U postgres -d nba_quant -f migrations/004_add_league_and_composite_teams.sql

BEGIN;

ALTER TABLE teams
    ADD COLUMN IF NOT EXISTS league VARCHAR(10) NOT NULL DEFAULT 'nba';

-- Widen the conference check to cover NFL's AFC/NFC before touching the PK.
ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_conference_check;
ALTER TABLE teams ADD CONSTRAINT teams_conference_check
    CHECK (conference IN ('East', 'West', 'AFC', 'NFC'));

-- Switch the PK from (abbreviation) to (league, abbreviation). Guarded so
-- this is safe to re-run: only acts if the PK is still the old single-column
-- form. CASCADE drops the two dependent FK constraints on historical_games
-- and odds_snapshots; migration 005 recreates them as composite FKs.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'teams_pkey'
          AND conrelid = 'teams'::regclass
          AND array_length(conkey, 1) = 1
    ) THEN
        ALTER TABLE teams DROP CONSTRAINT teams_pkey CASCADE;
        ALTER TABLE teams ADD CONSTRAINT teams_pkey PRIMARY KEY (league, abbreviation);
    END IF;
END $$;

INSERT INTO teams (abbreviation, full_name, city, conference, league) VALUES
    ('ARI', 'Arizona Cardinals',      'Phoenix',          'NFC', 'nfl'),
    ('ATL', 'Atlanta Falcons',        'Atlanta',          'NFC', 'nfl'),
    ('BAL', 'Baltimore Ravens',       'Baltimore',        'AFC', 'nfl'),
    ('BUF', 'Buffalo Bills',          'Buffalo',          'AFC', 'nfl'),
    ('CAR', 'Carolina Panthers',      'Charlotte',        'NFC', 'nfl'),
    ('CHI', 'Chicago Bears',          'Chicago',          'NFC', 'nfl'),
    ('CIN', 'Cincinnati Bengals',     'Cincinnati',       'AFC', 'nfl'),
    ('CLE', 'Cleveland Browns',       'Cleveland',        'AFC', 'nfl'),
    ('DAL', 'Dallas Cowboys',         'Dallas',           'NFC', 'nfl'),
    ('DEN', 'Denver Broncos',         'Denver',           'AFC', 'nfl'),
    ('DET', 'Detroit Lions',          'Detroit',          'NFC', 'nfl'),
    ('GB',  'Green Bay Packers',      'Green Bay',        'NFC', 'nfl'),
    ('HOU', 'Houston Texans',         'Houston',          'AFC', 'nfl'),
    ('IND', 'Indianapolis Colts',     'Indianapolis',     'AFC', 'nfl'),
    ('JAX', 'Jacksonville Jaguars',   'Jacksonville',     'AFC', 'nfl'),
    ('KC',  'Kansas City Chiefs',     'Kansas City',      'AFC', 'nfl'),
    ('LAC', 'Los Angeles Chargers',   'Los Angeles',      'AFC', 'nfl'),
    ('LAR', 'Los Angeles Rams',       'Los Angeles',      'NFC', 'nfl'),
    ('LV',  'Las Vegas Raiders',      'Las Vegas',        'AFC', 'nfl'),
    ('MIA', 'Miami Dolphins',         'Miami',            'AFC', 'nfl'),
    ('MIN', 'Minnesota Vikings',      'Minneapolis',      'NFC', 'nfl'),
    ('NE',  'New England Patriots',   'Foxborough',       'AFC', 'nfl'),
    ('NO',  'New Orleans Saints',     'New Orleans',      'NFC', 'nfl'),
    ('NYG', 'New York Giants',        'East Rutherford',  'NFC', 'nfl'),
    ('NYJ', 'New York Jets',          'East Rutherford',  'AFC', 'nfl'),
    ('PHI', 'Philadelphia Eagles',    'Philadelphia',     'NFC', 'nfl'),
    ('PIT', 'Pittsburgh Steelers',    'Pittsburgh',       'AFC', 'nfl'),
    ('SEA', 'Seattle Seahawks',       'Seattle',          'NFC', 'nfl'),
    ('SF',  'San Francisco 49ers',    'Santa Clara',      'NFC', 'nfl'),
    ('TB',  'Tampa Bay Buccaneers',   'Tampa',            'NFC', 'nfl'),
    ('TEN', 'Tennessee Titans',       'Nashville',        'AFC', 'nfl'),
    ('WAS', 'Washington Commanders',  'Landover',         'NFC', 'nfl')
ON CONFLICT (league, abbreviation) DO NOTHING;

COMMIT;
