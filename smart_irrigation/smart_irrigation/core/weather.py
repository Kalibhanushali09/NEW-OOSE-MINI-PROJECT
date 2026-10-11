"""Weather integration (Open-Meteo: free, no API key). Falls back gracefully when offline."""
import requests

DEFAULT_COORDS = (16.7050, 74.2433)  # Kolhapur, Maharashtra (sugarcane belt)
TIMEOUT = 8


def geocode(place):
    """Return (lat, lon) for a village / town name, or None."""
    try:
        r = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": place, "count": 1, "country": "IN"}, timeout=TIMEOUT)
        res = r.json().get("results")
        if res:
            return float(res[0]["latitude"]), float(res[0]["longitude"])
    except Exception:
        pass
    return None


def fetch_weather(lat=None, lon=None):
    """Returns (data_dict, error_message). data has temperature, humidity, rainfall (3-day forecast mm),
    wind_speed (km/h)."""
    lat = lat if lat is not None else DEFAULT_COORDS[0]
    lon = lon if lon is not None else DEFAULT_COORDS[1]
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
                    "daily": "precipitation_sum", "forecast_days": 3, "timezone": "auto"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        j = r.json()
        cur = j["current"]
        rain = sum(x or 0 for x in j["daily"]["precipitation_sum"])
        return {
            "temperature": float(cur["temperature_2m"]),
            "humidity": float(cur["relative_humidity_2m"]),
            "rainfall": round(float(rain), 1),
            "wind_speed": float(cur["wind_speed_10m"]),
            "source": "Open-Meteo live",
        }, None
    except Exception as e:  # network down, API change, etc.
        return None, f"Weather service unavailable ({type(e).__name__}). Enter weather manually below."
