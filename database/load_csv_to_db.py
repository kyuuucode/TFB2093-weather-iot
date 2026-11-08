"""
Load Icha's CSV files into weather.db (Sarah's schema, via weather_db.py).

Usage:  python load_csv_to_db.py [data_dir]
Expects in data_dir:
    hourly_observations.csv   columns: time, temperature_c, humidity_pct, rainfall_mm,
                                       wind_speed_kmh, rain_probability_pct
    forecast_snapshots.csv    same columns plus fetched_at (when the forecast was fetched)

Safe to run many times: observations are updated (latest value wins),
forecasts are append-only (rows that already exist are skipped).
Keep this file in the same folder as weather_db.py.
"""
import csv
import os
import sys

import weather_db as w

LOCATION = "Seri Iskandar"
DEFAULT_DATA_DIR = os.path.join(w.BASE_DIR, "..", "backend", "data")


def num(x):
    """CSV text 'None' / empty -> NULL, otherwise float."""
    return None if x in (None, "", "None") else float(x)


def to_record(row):
    """CSV row -> record with exactly Icha's FIELDS (numbers converted)."""
    return {k: (row[k] if k == "time" else num(row.get(k))) for k in w.FIELDS}


def load_observations(conn, data_dir):
    n = 0
    with open(os.path.join(data_dir, "hourly_observations.csv"), newline="") as f:
        for row in csv.DictReader(f):
            w.insert_observation_record(conn, LOCATION, to_record(row))
            n += 1
    return n


def load_forecasts(conn, data_dir):
    n = skipped = 0
    with open(os.path.join(data_dir, "forecast_snapshots.csv"), newline="") as f:
        for row in csv.DictReader(f):
            ok = w.insert_forecast_record(conn, LOCATION, row["fetched_at"], to_record(row))
            n += 1
            skipped += 0 if ok else 1
    return n, skipped


def main(data_dir=None):
    data_dir = data_dir or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_DIR)
    w.init_db()
    with w.get_conn() as conn:
        o = load_observations(conn, data_dir)
        fc, skipped = load_forecasts(conn, data_dir)
    print(f"Read {o} observation rows and {fc} forecast rows from {data_dir}")
    if skipped:
        print(f"Skipped {skipped} forecast rows whose target hour is before the fetch time")
    with w.get_conn() as conn:
        for t in ("observations", "forecast_snapshots"):
            print(t, conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "rows in DB")


if __name__ == "__main__":
    main()