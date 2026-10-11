"""SQLite persistence layer (replaces the MongoDB collections from the SRS).

Tables mirror the SRS collections: farmers, farms, soil_tests, weather, predictions.
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("IRRIGATION_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "irrigation.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS farmers (
    farmer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mobile TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'farmer',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS farms (
    farm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL REFERENCES farmers(farmer_id),
    farm_name TEXT NOT NULL,
    village TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    area REAL NOT NULL,
    soil_type TEXT NOT NULL,
    crop_info TEXT DEFAULT 'Sugarcane'
);
CREATE TABLE IF NOT EXISTS soil_tests (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL REFERENCES farms(farm_id),
    ec REAL, ph REAL, moisture REAL,
    nitrogen REAL, phosphorus REAL, potassium REAL, organic_carbon REAL,
    crop_age INTEGER,
    tested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS weather (
    weather_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER REFERENCES farms(farm_id),
    temperature REAL, humidity REAL, rainfall REAL, wind_speed REAL,
    source TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER REFERENCES soil_tests(test_id),
    farm_id INTEGER NOT NULL REFERENCES farms(farm_id),
    soil_health_score REAL,
    salinity_level TEXT,
    suitability TEXT,
    nutrient_deficiency TEXT,
    fertilizer_recommendation TEXT,
    next_irrigation_date TEXT,
    irrigation_in_days INTEGER,
    irrigation_duration_hours REAL,
    irrigation_need TEXT,
    recommendation TEXT,
    prediction_date TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as c:
        c.executescript(SCHEMA)


def query(sql, params=()):
    with get_conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def execute(sql, params=()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        return cur.lastrowid
