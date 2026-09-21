import json
import requests
from pathlib import Path
from datetime import datetime

from shapely.geometry import shape
from src.config import GEOJSON_PATH, WEATHER_FILE

# ============================================================
# CONFIG
# ============================================================

OUTPUT_PATH = WEATHER_FILE


API_URL = "https://api.open-meteo.com/v1/ecmwf"

REQUEST_TIMEOUT = 60

FORECAST_HOURS = 48

# Kathmandu time
TIMEZONE = "Asia/Kathmandu"


# ============================================================
# LOAD DISTRICTS
# ============================================================

def load_districts():
    print("Loading Nepal districts...")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    districts = []

    for feature in geojson["features"]:
        properties = feature.get("properties", {})
        geometry = feature.get("geometry")

        if not geometry:
            continue

        district_name = (
            properties.get("adm2_name")
            or properties.get("name")
            or properties.get("district")
        )

        district_pcode = (
            properties.get("adm2_pcode")
            or properties.get("pcode")
        )

        if not district_name:
            continue

        polygon = shape(geometry)

        # Representative point guaranteed to be inside polygon
        point = polygon.representative_point()

        districts.append({
            "district": district_name,
            "pcode": district_pcode,
            "latitude": point.y,
            "longitude": point.x,
        })

    print(f"Districts loaded: {len(districts)}")

    return districts


# ============================================================
# OPEN-METEO REQUEST
# ============================================================

def fetch_weather(districts):

    latitudes = ",".join(
        str(round(d["latitude"], 6))
        for d in districts
    )

    longitudes = ",".join(
        str(round(d["longitude"], 6))
        for d in districts
    )

    params = {
        "latitude": latitudes,
        "longitude": longitudes,

        "hourly": (
            "precipitation,"
            "rain,"
            "precipitation_probability"
        ),

        "forecast_hours": FORECAST_HOURS,

        "timezone": TIMEZONE,

        "precipitation_unit": "mm",

        "cell_selection": "land",
    }

    print()
    print("Requesting Open-Meteo ECMWF forecast...")
    print(f"Coordinates: {len(districts)}")
    print(f"Forecast hours: {FORECAST_HOURS}")

    response = requests.get(
        API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    print("Status:", response.status_code)

    response.raise_for_status()

    data = response.json()

    return data


# ============================================================
# PROCESS FORECAST
# ============================================================

def process_forecast(districts, data):

    # Multiple coordinates return a list
    if isinstance(data, dict):
        data = [data]

    if len(data) != len(districts):
        raise RuntimeError(
            f"Expected {len(districts)} forecast results, "
            f"received {len(data)}"
        )

    output = {}

    for district, forecast in zip(districts, data):

        hourly = forecast.get("hourly", {})

        times = hourly.get("time", [])
        precipitation = hourly.get("precipitation", [])
        rain = hourly.get("rain", [])
        probability = hourly.get(
            "precipitation_probability",
            []
        )

        if not precipitation:
            print(
                f"WARNING: No precipitation data for "
                f"{district['district']}"
            )
            continue

        # ----------------------------------------------------
        # Rainfall totals
        # ----------------------------------------------------

        rain_6h = sum(precipitation[:6])
        rain_12h = sum(precipitation[:12])
        rain_24h = sum(precipitation[:24])
        rain_48h = sum(precipitation[:48])

        # ----------------------------------------------------
        # Peak hourly rainfall
        # ----------------------------------------------------

        peak_rain = max(precipitation)

        peak_index = precipitation.index(peak_rain)

        peak_time = (
            times[peak_index]
            if peak_index < len(times)
            else None
        )

        # ----------------------------------------------------
        # Maximum precipitation probability
        # ----------------------------------------------------

        max_probability = (
            max(probability)
            if probability
            else None
        )

        # ----------------------------------------------------
        # Store
        # ----------------------------------------------------

        output[district["district"]] = {

            "pcode": district["pcode"],

            "latitude": district["latitude"],
            "longitude": district["longitude"],

            "forecast_model": "ECMWF IFS HRES",

            "forecast_hours": len(times),

            "forecast_start": (
                times[0]
                if times
                else None
            ),

            "forecast_end": (
                times[-1]
                if times
                else None
            ),

            "rain_6h_mm": round(rain_6h, 2),
            "rain_12h_mm": round(rain_12h, 2),
            "rain_24h_mm": round(rain_24h, 2),
            "rain_48h_mm": round(rain_48h, 2),

            "peak_hourly_precipitation_mm": round(
                peak_rain,
                2
            ),

            "peak_precipitation_time": peak_time,

            "max_precipitation_probability_pct": (
                max_probability
            ),

            "hourly": [
                {
                    "time": times[i],
                    "precipitation_mm": precipitation[i],
                    "rain_mm": (
                        rain[i]
                        if i < len(rain)
                        else None
                    ),
                    "precipitation_probability_pct": (
                        probability[i]
                        if i < len(probability)
                        else None
                    ),
                }
                for i in range(len(times))
            ],
        }

    return output


# ============================================================
# SAVE
# ============================================================

def save_output(output):

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),

        "source": "Open-Meteo",

        "model": "ECMWF IFS HRES",

        "forecast_horizon_hours": FORECAST_HOURS,

        "district_count": len(output),

        "districts": output,
    }

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            payload,
            f,
            indent=2
        )

    print()
    print(f"Output saved: {OUTPUT_PATH}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - OPEN-METEO WEATHER FORECAST")
    print("=" * 80)

    districts = load_districts()

    if len(districts) != 77:
        print(
            f"WARNING: Expected 77 districts, "
            f"found {len(districts)}"
        )

    data = fetch_weather(districts)

    output = process_forecast(
        districts,
        data
    )

    save_output(output)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("WEATHER FORECAST SUMMARY")
    print("=" * 80)

    print(
        f"Districts processed: {len(output)}"
    )

    print()

    # Show highest 24h rainfall districts

    ranked = sorted(
        output.items(),
        key=lambda x: x[1]["rain_24h_mm"],
        reverse=True
    )

    print("TOP 10 DISTRICTS BY FORECAST 24H RAINFALL")
    print("-" * 80)

    for district, data in ranked[:10]:

        print(
            f"{district:20s} "
            f"24h: {data['rain_24h_mm']:7.2f} mm | "
            f"48h: {data['rain_48h_mm']:7.2f} mm | "
            f"Peak: {data['peak_hourly_precipitation_mm']:6.2f} mm"
        )

    print()
    print("=" * 80)
    print("OPEN-METEO FORECAST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
