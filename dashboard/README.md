# Seri Iskandar Weather Dashboard (Streamlit)
Files: `app.py` (dashboard), `demo_data.py` (schema + demo DB), `requirements.txt`.

## Expected SQLite schema (`weather.db`) – confirm with Owner C
- `observations(timestamp, temperature, humidity, rainfall, wind_speed)`
- `forecasts(fetched_at, target_time, horizon_hours, temperature, humidity, rainfall, wind_speed)`
If Owner C's column/table names differ, edit the SQL in `load()` in app.py only.

## Run locally
    pip install -r requirements.txt
    streamlit run app.py
(No weather.db? The app auto-creates demo data and shows a warning banner.)

## Deploy (Streamlit Community Cloud, free)
1. Push app.py, demo_data.py, requirements.txt AND the real weather.db to a GitHub repo.
2. share.streamlit.io -> New app -> pick repo, branch, main file `app.py` -> Deploy.
3. Submit the *.streamlit.app URL. To update data, commit a new weather.db.
