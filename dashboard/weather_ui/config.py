"""Constants shared across the dashboard."""

REPO_DB_URL = ("https://raw.githubusercontent.com/kyuuucode/"
               "TFB2093-weather-iot/main/database/weather.db")

# Seri Iskandar, Perak
LAT, LON = 4.37, 100.97
TZ_NAME = "Asia/Kuala_Lumpur"
TZ_OFFSET_H = 8

# label -> (column, unit, colour, forecast column, observation column)
PARAMS = {
    "Temperature": ("temperature_c", "°C", "#ff8a5c", "fc_temp", "obs_temp"),
    "Humidity": ("humidity_pct", "%", "#4dd0e1", "fc_humidity", "obs_humidity"),
    "Rainfall": ("rainfall_mm", "mm", "#7c83ff", "fc_rain", "obs_rain"),
    "Wind speed": ("wind_speed_kmh", "km/h", "#b388ff", "fc_wind", "obs_wind"),
}
