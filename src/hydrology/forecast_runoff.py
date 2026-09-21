import json
from datetime import datetime, timezone
from src.config import WEATHER_FILE, DISTRICT_CN_FILE, FORECAST_RUNOFF_FILE
from src.config import (
    WEATHER_FILE as CONFIG_WEATHER_FILE,
    DISTRICT_CN_FILE,
    FORECAST_RUNOFF_FILE,
)


WEATHER_FILE = CONFIG_WEATHER_FILE
CN_FILE = DISTRICT_CN_FILE
OUTPUT_FILE = FORECAST_RUNOFF_FILE

# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# EXISTING PRAVAH SCS-CN LOGIC
# Same formula/behavior as rainfall_features.py
# ============================================================

def calculate_scs_cn_runoff(rainfall_mm, cn):

    rainfall_mm = safe_float(rainfall_mm)
    cn = safe_float(cn)

    if rainfall_mm is None:
        return None

    if cn is None:
        return None

    if rainfall_mm <= 0:
        return 0.0

    if cn <= 0 or cn >= 100:
        return None

    S = (25400 / cn) - 254

    initial_abstraction = 0.2 * S

    if rainfall_mm <= initial_abstraction:
        return 0.0

    runoff = (
        (rainfall_mm - initial_abstraction) ** 2
        / (rainfall_mm + 0.8 * S)
    )

    return round(runoff, 3)


# ============================================================
# LOAD FILES
# ============================================================

print("=" * 80)
print("PRAVAH - FORECAST RUNOFF")
print("=" * 80)

print("\nLoading weather forecast...")
with open(WEATHER_FILE, "r") as f:
    weather_data = json.load(f)

print("Loading district Curve Numbers...")
with open(CN_FILE, "r") as f:
    cn_data = json.load(f)


# ============================================================
# BUILD CN LOOKUP
# ============================================================

cn_lookup = {}

# district_cn.json may be a list or a dictionary.
if isinstance(cn_data, list):

    for record in cn_data:

        district = record.get("district")

        if district:
            cn_lookup[district.strip().lower()] = (
                safe_float(record.get("cn_average"))
            )

elif isinstance(cn_data, dict):

    # Handle {"districts": [...]}
    if isinstance(cn_data.get("districts"), list):

        for record in cn_data["districts"]:

            district = record.get("district")

            if district:
                cn_lookup[district.strip().lower()] = (
                    safe_float(record.get("cn_average"))
                )

    # Handle {"Taplejung": {"cn_average": 71.34}, ...}
    else:

        for district, record in cn_data.items():

            if isinstance(record, dict):

                cn_lookup[district.strip().lower()] = (
                    safe_float(record.get("cn_average"))
                )


print(f"Curve Number records: {len(cn_lookup)}")


# ============================================================
# WEATHER DISTRICTS
# ============================================================

weather_districts = weather_data.get("districts", {})

print(f"Weather forecast districts: {len(weather_districts)}")


# ============================================================
# FORECAST RUNOFF
# ============================================================

output = {
    "project": "PRAVAH",
    "pipeline_version": "forecast_runoff_v1",

    "generated_at_utc": (
        datetime.now(timezone.utc).isoformat()
    ),

    "source_file": str(WEATHER_FILE),
    "curve_number_source": str(CN_FILE),

    "method": "SCS-CN",

    "forecast_horizons_hours": [
        6,
        12,
        24,
        48
    ],

    "district_count": 0,

    "districts": {}
}


processed = 0
missing_cn = 0
missing_forecast = 0


for district_name, forecast in weather_districts.items():

    district_key = district_name.strip().lower()

    cn = cn_lookup.get(district_key)

    if cn is None:
        missing_cn += 1

    # --------------------------------------------------------
    # Forecast rainfall
    # --------------------------------------------------------

    rain_6h = safe_float(
        forecast.get("rain_6h_mm")
    )

    rain_12h = safe_float(
        forecast.get("rain_12h_mm")
    )

    rain_24h = safe_float(
        forecast.get("rain_24h_mm")
    )

    rain_48h = safe_float(
        forecast.get("rain_48h_mm")
    )

    # --------------------------------------------------------
    # Forecast runoff
    # Same SCS-CN calculation for every horizon.
    # --------------------------------------------------------

    runoff_6h = calculate_scs_cn_runoff(
        rain_6h,
        cn
    )

    runoff_12h = calculate_scs_cn_runoff(
        rain_12h,
        cn
    )

    runoff_24h = calculate_scs_cn_runoff(
        rain_24h,
        cn
    )

    runoff_48h = calculate_scs_cn_runoff(
        rain_48h,
        cn
    )

    # --------------------------------------------------------
    # Store
    # --------------------------------------------------------

    output["districts"][district_name] = {

        "pcode": forecast.get("pcode"),

        "curve_number": cn,

        "forecast_rainfall": {

            "rain_6h_mm": rain_6h,

            "rain_12h_mm": rain_12h,

            "rain_24h_mm": rain_24h,

            "rain_48h_mm": rain_48h
        },

        "forecast_runoff": {

            "runoff_6h_mm": runoff_6h,

            "runoff_12h_mm": runoff_12h,

            "runoff_24h_mm": runoff_24h,

            "runoff_48h_mm": runoff_48h
        },

        "method": "SCS-CN",

        "curve_number_source": str(CN_FILE),

        "forecast_source": "Open-Meteo ECMWF IFS HRES"
    }

    processed += 1


# ============================================================
# FINALIZE
# ============================================================

output["district_count"] = processed

output["summary"] = {

    "processed": processed,

    "missing_curve_number": missing_cn,

    "missing_forecast_data": missing_forecast
}


# ============================================================
# SAVE
# ============================================================

with open(OUTPUT_FILE, "w") as f:

    json.dump(
        output,
        f,
        indent=2
    )


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("FORECAST RUNOFF COMPLETE")
print("=" * 80)

print(f"Districts processed       : {processed}")
print(f"Missing Curve Number      : {missing_cn}")
print(f"Output                    : {OUTPUT_FILE}")

print("\nTOP 10 BY 24H FORECAST RUNOFF")

ranked = []

for district, data in output["districts"].items():

    runoff = data["forecast_runoff"]["runoff_24h_mm"]

    if runoff is not None:

        ranked.append(
            (district, runoff)
        )

ranked.sort(
    key=lambda x: x[1],
    reverse=True
)

for district, runoff in ranked[:10]:

    rain = output["districts"][district][
        "forecast_runoff"
    ]

    rainfall = output["districts"][district][
        "forecast_rainfall"
    ]

    print(
        f"{district:<20} "
        f"Rain 24h: {rainfall['rain_24h_mm']:>6.2f} mm | "
        f"Runoff: {runoff:>6.2f} mm"
    )

print("=" * 80)
