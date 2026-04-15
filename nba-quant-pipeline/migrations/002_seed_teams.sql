-- Seed the 30 NBA teams into the reference table.
-- Run: psql -U postgres -d nba_quant -f migrations/002_seed_teams.sql

BEGIN;

INSERT INTO teams (abbreviation, full_name, city, conference) VALUES
    ('ATL', 'Atlanta Hawks',          'Atlanta',        'East'),
    ('BOS', 'Boston Celtics',         'Boston',         'East'),
    ('BKN', 'Brooklyn Nets',          'Brooklyn',       'East'),
    ('CHA', 'Charlotte Hornets',      'Charlotte',      'East'),
    ('CHI', 'Chicago Bulls',          'Chicago',        'East'),
    ('CLE', 'Cleveland Cavaliers',    'Cleveland',      'East'),
    ('DAL', 'Dallas Mavericks',       'Dallas',         'West'),
    ('DEN', 'Denver Nuggets',         'Denver',         'West'),
    ('DET', 'Detroit Pistons',        'Detroit',        'East'),
    ('GSW', 'Golden State Warriors',  'San Francisco',  'West'),
    ('HOU', 'Houston Rockets',        'Houston',        'West'),
    ('IND', 'Indiana Pacers',         'Indianapolis',   'East'),
    ('LAC', 'Los Angeles Clippers',   'Los Angeles',    'West'),
    ('LAL', 'Los Angeles Lakers',     'Los Angeles',    'West'),
    ('MEM', 'Memphis Grizzlies',      'Memphis',        'West'),
    ('MIA', 'Miami Heat',             'Miami',          'East'),
    ('MIL', 'Milwaukee Bucks',        'Milwaukee',      'East'),
    ('MIN', 'Minnesota Timberwolves', 'Minneapolis',    'West'),
    ('NOP', 'New Orleans Pelicans',   'New Orleans',    'West'),
    ('NYK', 'New York Knicks',        'New York',       'East'),
    ('OKC', 'Oklahoma City Thunder',  'Oklahoma City',  'West'),
    ('ORL', 'Orlando Magic',          'Orlando',        'East'),
    ('PHI', 'Philadelphia 76ers',     'Philadelphia',   'East'),
    ('PHX', 'Phoenix Suns',           'Phoenix',        'West'),
    ('POR', 'Portland Trail Blazers', 'Portland',       'West'),
    ('SAC', 'Sacramento Kings',       'Sacramento',     'West'),
    ('SAS', 'San Antonio Spurs',      'San Antonio',    'West'),
    ('TOR', 'Toronto Raptors',        'Toronto',        'East'),
    ('UTA', 'Utah Jazz',              'Salt Lake City', 'West'),
    ('WAS', 'Washington Wizards',     'Washington',     'East')
ON CONFLICT (abbreviation) DO NOTHING;

COMMIT;
