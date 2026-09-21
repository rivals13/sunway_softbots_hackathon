import json
from datetime import datetime, timezone
from shapely.geometry import Point, shape
from shapely.prepared import prep

from src.config import GEOJSON_PATH
from src.config import (
    RAINFALL_FILE as CONFIG_RAINFALL_FILE,
    RIVER_FILE as CONFIG_RIVER_FILE,
    FORECAST_RUNOFF_FILE as CONFIG_FORECAST_RUNOFF_FILE,
    GEOGLOWS_FILE as CONFIG_GEOGLOWS_FILE,
    HYDROLOGY_FILE as CONFIG_HYDROLOGY_FILE,
)

# ============================================================
# PRAVAH - HYDROLOGY FEATURE FUSION V3
# ============================================================


RAIN_FILE = CONFIG_RAINFALL_FILE
RIVER_FILE = CONFIG_RIVER_FILE
FORECAST_RUNOFF_FILE = CONFIG_FORECAST_RUNOFF_FILE
GEOGLOWS_FILE = CONFIG_GEOGLOWS_FILE
OUTPUT_FILE = CONFIG_HYDROLOGY_FILE

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default




def load_pravah_districts():
    """
    Load the same authoritative PRAVAH Admin-2 GeoJSON
    used by the rainfall fusion engine.

    District IDs must remain identical across PRAVAH modules.
    """
    print("Loading PRAVAH district boundaries for GEOGLOWS mapping...")

    with GEOJSON_PATH.open("r", encoding="utf-8") as f:
        geo = json.load(f)

    districts = []

    next_district_id = 1

    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if not geom:
            continue

        name = (
            props.get("adm2_name")
            or props.get("NAME_2")
            or props.get("name")
            or f"District {next_district_id}"
        )

        geom_shape = shape(geom)

        districts.append({
            "district_id": next_district_id,
            "district": str(name),
            "geometry": geom_shape,
            "prepared": prep(geom_shape),
        })

        next_district_id += 1

    print(
        f"PRAVAH district boundaries loaded: "
        f"{len(districts)}"
    )

    return districts

def map_geoglows_stations_to_districts(geoglows_stations):
    """
    Assign a PRAVAH district_id to GEOGLOWS stations using
    station longitude/latitude and the authoritative
    Admin-2 district polygons.
    """

    districts = load_pravah_districts()

    mapped = 0
    unmapped = 0

    for station in geoglows_stations:
        lon = safe_float(station.get("longitude"))
        lat = safe_float(station.get("latitude"))

        if lon is None or lat is None:
            unmapped += 1
            continue

        point = Point(lon, lat)

        station["district_id"] = None

        for district in districts:
            if district["prepared"].contains(point):
                station["district_id"] = district["district_id"]
                mapped += 1
                break

        if station["district_id"] is None:
            unmapped += 1

    print()
    print("=" * 70)
    print("GEOGLOWS DISTRICT MAPPING")
    print("=" * 70)
    print(f"GEOGLOWS stations received : {len(geoglows_stations)}")
    print(f"GEOGLOWS stations mapped   : {mapped}")
    print(f"GEOGLOWS stations unmapped : {unmapped}")
    print("=" * 70)

    # Explicit Taplejung verification
    for station in geoglows_stations:
        if station.get("station_name") == "Tamor River at Taplejung":
            print()
            print("Taplejung GEOGLOWS verification:")
            print(f"  Station   : {station.get('station_name')}")
            print(f"  Longitude : {station.get('longitude')}")
            print(f"  Latitude  : {station.get('latitude')}")
            print(f"  district_id: {station.get('district_id')}")
            break

    return geoglows_stations



def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


# ------------------------------------------------------------
# Threshold-aware river pressure
# ------------------------------------------------------------

def calculate_river_pressure(
    danger_utilization,
    warning_utilization,
    rising_station_count,
    station_count
):
    """
    Prototype river-pressure indicator.

    Uses danger utilization as the primary signal because
    it directly represents how close the observed river
    level is to the danger threshold.

    The response becomes stronger as the river approaches
    the warning/danger thresholds.
    """

    if danger_utilization is None:
        return 0.0

    d = clamp(danger_utilization)

    # --------------------------------------------------------
    # Danger utilization bands
    # --------------------------------------------------------

    if d < 0.70:

        pressure = d * 0.30

    elif d < 0.85:

        pressure = 0.21 + (
            (d - 0.70) / 0.15
        ) * 0.19

    elif d < 0.95:

        pressure = 0.40 + (
            (d - 0.85) / 0.10
        ) * 0.30

    elif d < 1.00:

        pressure = 0.70 + (
            (d - 0.95) / 0.05
        ) * 0.30

    else:

        pressure = 1.0

    # --------------------------------------------------------
    # Warning utilization gives additional evidence
    # --------------------------------------------------------

    if warning_utilization is not None:

        w = clamp(warning_utilization)

        if w >= 1.0:
            pressure += 0.10

        elif w >= 0.95:
            pressure += 0.07

        elif w >= 0.90:
            pressure += 0.04

    # --------------------------------------------------------
    # Rising stations
    # --------------------------------------------------------

    if (
        rising_station_count > 0
        and station_count > 0
    ):

        rising_ratio = (
            rising_station_count / station_count
        )

        pressure += clamp(
            rising_ratio
        ) * 0.10

    return clamp(pressure)


# ============================================================
# LOAD INPUT FILES
# ============================================================

print("=" * 80)
print("PRAVAH - HYDROLOGY FEATURE FUSION V3")
print("=" * 80)


# ------------------------------------------------------------
# Rainfall
# ------------------------------------------------------------

print("\nLoading rainfall features:")
print(RAIN_FILE)

with open(
    RAIN_FILE,
    "r",
    encoding="utf-8"
) as f:

    rainfall_data = json.load(f)


# ------------------------------------------------------------
# River
# ------------------------------------------------------------

print("\nLoading river features:")
print(RIVER_FILE)

with open(
    RIVER_FILE,
    "r",
    encoding="utf-8"
) as f:

    river_data = json.load(f)


# ------------------------------------------------------------
# Forecast runoff
# ------------------------------------------------------------

print("\nLoading forecast runoff:")
print(FORECAST_RUNOFF_FILE)

with open(
    FORECAST_RUNOFF_FILE,
    "r",
    encoding="utf-8"
) as f:

    forecast_runoff_data = json.load(f)


# ------------------------------------------------------------
# GEOGLOWS
# ------------------------------------------------------------

print("\nLoading GEOGLOWS features:")
print(GEOGLOWS_FILE)

with open(
    GEOGLOWS_FILE,
    "r",
    encoding="utf-8"
) as f:

    geoglows_data = json.load(f)


# ============================================================
# EXTRACT DATA
# ============================================================

rainfall_districts = rainfall_data.get(
    "districts",
    []
)

river_districts = river_data.get(
    "districts",
    []
)

forecast_runoff_districts = (
    forecast_runoff_data.get(
        "districts",
        {}
    )
)

geoglows_stations = (
    geoglows_data.get(
        "stations",
        []
    )
)

# ============================================================
# MAP GEOGLOWS STATIONS TO PRAVAH DISTRICTS
# ============================================================

geoglows_stations = map_geoglows_stations_to_districts(
    geoglows_stations
)


print(
    f"\nRainfall districts received        : "
    f"{len(rainfall_districts)}"
)

print(
    f"River districts received           : "
    f"{len(river_districts)}"
)

print(
    f"Forecast runoff districts received : "
    f"{len(forecast_runoff_districts)}"
)

print(
    f"GEOGLOWS stations received         : "
    f"{len(geoglows_stations)}"
)


# ============================================================
# RIVER LOOKUP
# ============================================================

river_lookup = {}

for district in river_districts:

    district_id = district.get(
        "district_id"
    )

    if district_id is not None:

        river_lookup[
            str(district_id)
        ] = district


# ============================================================
# FORECAST RUNOFF LOOKUP
# ============================================================

forecast_lookup = {}

for district_name, district_data in (
    forecast_runoff_districts.items()
):

    if district_name:

        forecast_lookup[
            district_name.strip().lower()
        ] = district_data


# ============================================================
# GEOGLOWS DISTRICT AGGREGATION
# ============================================================

geoglows_lookup = {}

for station in geoglows_stations:

    district_id = station.get(
        "district_id"
    )

    if district_id is None:
        continue

    district_key = str(
        district_id
    )

    geoglows = station.get(
        "geoglows",
        {}
    )

    current_flow = safe_float(
        geoglows.get(
            "current_flow_m3s"
        )
    )

    peak_flow = safe_float(
        geoglows.get(
            "forecast_peak_flow_m3s"
        )
    )

    forecast_rise = safe_float(
        geoglows.get(
            "forecast_rise_m3s"
        )
    )

    upper_peak = safe_float(
        geoglows.get(
            "forecast_upper_peak_m3s"
        )
    )

    lower_peak = safe_float(
        geoglows.get(
            "forecast_lower_peak_m3s"
        )
    )

    peak_time = geoglows.get(
        "peak_time"
    )

    observed_at = station.get(
        "observed_at"
    )

    # --------------------------------------------------------
    # Actual forecast lead time
    #
    # GEOGLOWS hours_to_peak is not treated as actual
    # lead time because it is not consistently relative to
    # the station observed_at timestamp.
    # --------------------------------------------------------

    lead_time_hours = None

    if observed_at and peak_time:

        try:

            observed_dt = datetime.fromisoformat(
                str(observed_at).replace(
                    "Z",
                    "+00:00"
                )
            )

            peak_dt = datetime.fromisoformat(
                str(peak_time).replace(
                    "Z",
                    "+00:00"
                )
            )

            lead_time_hours = (
                peak_dt - observed_dt
            ).total_seconds() / 3600.0

            # A peak already in the past is not a
            # future warning lead time.
            lead_time_hours = max(
                0.0,
                lead_time_hours
            )

        except (
            ValueError,
            TypeError
        ):

            lead_time_hours = None

    # --------------------------------------------------------
    # Forecast rise percentage
    #
    # Keep this as supporting context. Do not use percentage
    # alone because tiny current-flow baselines can produce
    # misleadingly large percentages.
    # --------------------------------------------------------

    rise_pct = None

    if (
        current_flow is not None
        and current_flow > 0
        and forecast_rise is not None
    ):

        rise_pct = (
            forecast_rise
            / current_flow
        ) * 100.0

    # --------------------------------------------------------
    # Create district record
    # --------------------------------------------------------

    if district_key not in geoglows_lookup:

        geoglows_lookup[district_key] = {

            "station_count": 0,

            "current_flow_m3s": None,

            "forecast_peak_flow_m3s": None,

            "forecast_rise_m3s": None,

            "forecast_rise_pct": None,

            "hours_to_peak": None,

            "lead_time_hours": None,

            "peak_time": None,

            "forecast_upper_peak_m3s": None,

            "forecast_lower_peak_m3s": None,

            "representative_station": None,

            "representative_station_id": None,

            "representative_rise_m3s": None
        }

    record = geoglows_lookup[
        district_key
    ]

    record["station_count"] += 1

    # --------------------------------------------------------
    # Select one coherent representative station
    #
    # Primary criterion:
    #     largest absolute forecast rise (m3/s)
    #
    # This avoids selecting a station purely because its
    # percentage rise is large due to a tiny baseline.
    # --------------------------------------------------------

    if forecast_rise is not None:

        current_best = safe_float(
            record.get(
                "representative_rise_m3s"
            )
        )

        should_select = (
            current_best is None
            or
            forecast_rise > current_best
        )

        if should_select:

            record[
                "representative_rise_m3s"
            ] = forecast_rise

            record[
                "current_flow_m3s"
            ] = current_flow

            record[
                "forecast_peak_flow_m3s"
            ] = peak_flow

            record[
                "forecast_rise_m3s"
            ] = forecast_rise

            record[
                "forecast_rise_pct"
            ] = rise_pct

            record[
                "lead_time_hours"
            ] = lead_time_hours

            # Keep this field for backward compatibility
            # with downstream code.
            record[
                "hours_to_peak"
            ] = lead_time_hours

            record[
                "peak_time"
            ] = peak_time

            record[
                "forecast_upper_peak_m3s"
            ] = upper_peak

            record[
                "forecast_lower_peak_m3s"
            ] = lower_peak

            record[
                "representative_station"
            ] = station.get(
                "station_name"
            )

            record[
                "representative_station_id"
            ] = station.get(
                "station_id"
            )

    # --------------------------------------------------------
    # If a station has no usable forecast rise but contains
    # forecast information, preserve it as a fallback.
    # --------------------------------------------------------

    elif (
        record[
            "representative_station"
        ] is None
        and
        (
            current_flow is not None
            or
            peak_flow is not None
        )
    ):

        record[
            "current_flow_m3s"
        ] = current_flow

        record[
            "forecast_peak_flow_m3s"
        ] = peak_flow

        record[
            "forecast_rise_m3s"
        ] = forecast_rise

        record[
            "forecast_rise_pct"
        ] = rise_pct

        record[
            "lead_time_hours"
        ] = lead_time_hours

        record[
            "hours_to_peak"
        ] = lead_time_hours

        record[
            "peak_time"
        ] = peak_time

        record[
            "forecast_upper_peak_m3s"
        ] = upper_peak

        record[
            "forecast_lower_peak_m3s"
        ] = lower_peak

        record[
            "representative_station"
        ] = station.get(
            "station_name"
        )

        record[
            "representative_station_id"
        ] = station.get(
            "station_id"
        )


# ============================================================
# COUNTERS
# ============================================================


processed = 0

missing_river = 0
river_data_available = 0

forecast_data_available = 0
geoglows_data_available = 0

strong_signal = 0
moderate_signal = 0
weak_signal = 0

near_warning_count = 0
near_danger_count = 0

warning_crossed_count = 0
danger_crossed_count = 0


fused_districts = []


# ============================================================
# PROCESS DISTRICTS
# ============================================================

for rain_district in rainfall_districts:

    district_id = rain_district.get(
        "district_id"
    )

    district_name = rain_district.get(
        "district"
    )

    if district_id is None:
        continue

    district_key = str(
        district_id
    )


    # ========================================================
    # FORECAST EVIDENCE
    # ========================================================

    forecast = forecast_lookup.get(
        str(district_name).strip().lower(),
        {}
    )

    forecast_rainfall = (
        forecast.get(
            "forecast_rainfall",
            {}
        )
    )

    forecast_runoff = (
        forecast.get(
            "forecast_runoff",
            {}
        )
    )


    forecast_rain_6h = safe_float(
        forecast_rainfall.get(
            "rain_6h_mm"
        )
    )

    forecast_rain_12h = safe_float(
        forecast_rainfall.get(
            "rain_12h_mm"
        )
    )

    forecast_rain_24h = safe_float(
        forecast_rainfall.get(
            "rain_24h_mm"
        )
    )

    forecast_rain_48h = safe_float(
        forecast_rainfall.get(
            "rain_48h_mm"
        )
    )


    forecast_runoff_6h = safe_float(
        forecast_runoff.get(
            "runoff_6h_mm"
        )
    )

    forecast_runoff_12h = safe_float(
        forecast_runoff.get(
            "runoff_12h_mm"
        )
    )

    forecast_runoff_24h = safe_float(
        forecast_runoff.get(
            "runoff_24h_mm"
        )
    )

    forecast_runoff_48h = safe_float(
        forecast_runoff.get(
            "runoff_48h_mm"
        )
    )


    forecast_available = any([
        forecast_rain_6h is not None,
        forecast_rain_12h is not None,
        forecast_rain_24h is not None,
        forecast_rain_48h is not None,
        forecast_runoff_6h is not None,
        forecast_runoff_12h is not None,
        forecast_runoff_24h is not None,
        forecast_runoff_48h is not None
    ])

    if forecast_available:

        forecast_data_available += 1


    # ========================================================
    # GEOGLOWS EVIDENCE
    # ========================================================

    geoglows = geoglows_lookup.get(
        district_key,
        {}
    )


    geoglows_station_count = safe_int(
        geoglows.get(
            "station_count"
        )
    )

    geoglows_current_flow = safe_float(
        geoglows.get(
            "current_flow_m3s"
        )
    )

    geoglows_peak_flow = safe_float(
        geoglows.get(
            "forecast_peak_flow_m3s"
        )
    )

    geoglows_rise = safe_float(
        geoglows.get(
            "forecast_rise_m3s"
        )
    )

    geoglows_hours_to_peak = safe_float(
        geoglows.get(
            "hours_to_peak"
        )
    )

    geoglows_peak_time = geoglows.get(
        "peak_time"
    )

    geoglows_upper_peak = safe_float(
        geoglows.get(
            "forecast_upper_peak_m3s"
        )
    )

    geoglows_lower_peak = safe_float(
        geoglows.get(
            "forecast_lower_peak_m3s"
        )
    )


    if geoglows_station_count > 0:

        geoglows_data_available += 1


    # ========================================================
    # CURRENT RAINFALL FEATURES
    # ========================================================

    rainfall = rain_district.get(
        "rainfall",
        {}
    )

    hydro_features = (
        rain_district.get(
            "hydrological_features",
            {}
        )
    )

    scs_cn = rain_district.get(
        "scs_cn",
        {}
    )


    # --------------------------------------------------------
    # Current rainfall
    # --------------------------------------------------------

    rain_6h = safe_float(
        rainfall.get(
            "nasa_6h_mm"
        )
    )

    rain_12h = safe_float(
        rainfall.get(
            "nasa_12h_mm"
        )
    )

    rain_24h = safe_float(
        rainfall.get(
            "nasa_24h_mm"
        )
    )

    rain_3day = safe_float(
        rainfall.get(
            "nasa_3day_mm"
        )
    )

    rain_5day = safe_float(
        rainfall.get(
            "nasa_5day_mm"
        )
    )


    # --------------------------------------------------------
    # Current runoff
    # --------------------------------------------------------

    runoff_6h = safe_float(
        scs_cn.get(
            "runoff_mm"
        )
    )


    # --------------------------------------------------------
    # Rainfall features
    # --------------------------------------------------------

    rainfall_intensity = safe_float(
        hydro_features.get(
            "rainfall_intensity_6h_mm_per_hour"
        )
    )

    antecedent_indicator = safe_float(
        hydro_features.get(
            "antecedent_rainfall_indicator"
        )
    )

    rainfall_persistence = safe_float(
        hydro_features.get(
            "rainfall_persistence"
        )
    )

    intensity_class = hydro_features.get(
        "rainfall_intensity_class"
    )


    # ========================================================
    # CURRENT RIVER
    # ========================================================

    river_district = river_lookup.get(
        district_key
    )

    if river_district is None:

        missing_river += 1

        river = {}

    else:

        river = river_district.get(
            "river",
            {}
        )


    station_count = safe_int(
        river.get(
            "station_count"
        )
    )

    max_water_level = safe_float(
        river.get(
            "max_water_level_m"
        )
    )

    warning_utilization = safe_float(
        river.get(
            "max_warning_utilization"
        )
    )

    danger_utilization = safe_float(
        river.get(
            "max_danger_utilization"
        )
    )

    warning_station_count = safe_int(
        river.get(
            "warning_station_count"
        )
    )

    danger_station_count = safe_int(
        river.get(
            "danger_station_count"
        )
    )

    rising_station_count = safe_int(
        river.get(
            "rising_station_count"
        )
    )


    near_warning = bool(
        river.get(
            "near_warning",
            False
        )
    )

    near_danger = bool(
        river.get(
            "near_danger",
            False
        )
    )

    warning_crossed = bool(
        river.get(
            "warning_crossed",
            False
        )
    )

    danger_crossed = bool(
        river.get(
            "danger_crossed",
            False
        )
    )


    # --------------------------------------------------------
    # River data availability
    # --------------------------------------------------------

    if station_count > 0:

        river_data_available += 1

        river_status = river.get(
        "river_status",
        "UNKNOWN"
        )

    else:

        missing_river += 1

        river_status = "NO_DATA"


    # ========================================================
    # CURRENT RAINFALL SIGNAL
    # ========================================================

    rainfall_signal = 0.0


    if rain_6h is not None:

        rainfall_signal += (
            clamp(
                rain_6h / 50.0
            )
            * 0.35
        )


    if rain_24h is not None:

        rainfall_signal += (
            clamp(
                rain_24h / 150.0
            )
            * 0.25
        )


    if runoff_6h is not None:

        rainfall_signal += (
            clamp(
                runoff_6h / 50.0
            )
            * 0.25
        )


    if antecedent_indicator is not None:

        rainfall_signal += (
            clamp(
                antecedent_indicator / 150.0
            )
            * 0.15
        )


    rainfall_signal = clamp(
        rainfall_signal
    )


    # ========================================================
    # CURRENT RIVER SIGNAL
    # ========================================================

    if station_count > 0:

        river_signal = (
            calculate_river_pressure(
                danger_utilization,
                warning_utilization,
                rising_station_count,
                station_count
            )
        )

    else:

        river_signal = 0.0


    # ========================================================
    # CURRENT HYDROLOGICAL FUSION
    #
    # IMPORTANT:
    # Forecast and GEOGLOWS are not yet included in this
    # score. We first expose and validate them.
    # ========================================================

    if station_count > 0:

        hydrological_signal = (
            rainfall_signal * 0.45
            +
            river_signal * 0.55
        )

    else:

        hydrological_signal = (
            rainfall_signal * 0.60
        )


    hydrological_signal = clamp(
        hydrological_signal
    )


    # ========================================================
    # EVIDENCE AGREEMENT
    # ========================================================

    if station_count > 0:

        difference = abs(
            rainfall_signal -
            river_signal
        )

        if difference < 0.20:

            evidence_agreement = "HIGH"

        elif difference < 0.40:

            evidence_agreement = "MODERATE"

        else:

            evidence_agreement = "LOW"

    else:

        evidence_agreement = (
            "NO_RIVER_DATA"
        )


    # ========================================================
    # HYDROLOGICAL STATE
    # ========================================================

    if danger_crossed:

        hydrological_state = "DANGER"

        danger_crossed_count += 1

    elif warning_crossed:

        hydrological_state = "WARNING"

        warning_crossed_count += 1

    elif near_danger:

        hydrological_state = "NEAR_DANGER"

        near_danger_count += 1

    elif near_warning:

        hydrological_state = "NEAR_WARNING"

        near_warning_count += 1

    elif hydrological_signal >= 0.70:

        hydrological_state = (
            "HIGH_HYDROLOGICAL_PRESSURE"
        )

    elif hydrological_signal >= 0.40:

        hydrological_state = (
            "MODERATE_HYDROLOGICAL_PRESSURE"
        )

    else:

        hydrological_state = "NORMAL"


    # ========================================================
    # SIGNAL STRENGTH
    # ========================================================

    if hydrological_signal >= 0.70:

        signal_strength = "STRONG"

        strong_signal += 1

    elif hydrological_signal >= 0.40:

        signal_strength = "MODERATE"

        moderate_signal += 1

    else:

        signal_strength = "WEAK"

        weak_signal += 1


    # ========================================================
    # DATA QUALITY
    # ========================================================

    rainfall_available = (
        rain_6h is not None
        or
        rain_24h is not None
    )

    river_available = (
        station_count > 0
    )


    # ========================================================
    # OUTPUT RECORD
    # ========================================================

    fused_districts.append({

        # ----------------------------------------------------
        # Identity
        # ----------------------------------------------------

        "district_id":
            district_id,

        "district":
            district_name,


        # ----------------------------------------------------
        # CURRENT RAINFALL
        # ----------------------------------------------------

        "rainfall": {

            "rain_6h_mm":
                rain_6h,

            "rain_12h_mm":
                rain_12h,

            "rain_24h_mm":
                rain_24h,

            "rain_3day_mm":
                rain_3day,

            "rain_5day_mm":
                rain_5day,

            "rainfall_intensity_mm_per_hour":
                rainfall_intensity,

            "rainfall_intensity_class":
                intensity_class,

            "rainfall_persistence":
                rainfall_persistence,

            "antecedent_rainfall_indicator":
                antecedent_indicator,

            "scs_cn_runoff_6h_mm":
                runoff_6h
        },


        # ----------------------------------------------------
        # CURRENT RIVER
        # ----------------------------------------------------

        "river": {

            "station_count":
                station_count,

            "max_water_level_m":
                max_water_level,

            "max_warning_utilization":
                warning_utilization,

            "max_danger_utilization":
                danger_utilization,

            "warning_station_count":
                warning_station_count,

            "danger_station_count":
                danger_station_count,

            "rising_station_count":
                rising_station_count,

            "river_status":
                river_status,

            "near_warning":
                near_warning,

            "near_danger":
                near_danger,

            "warning_crossed":
                warning_crossed,

            "danger_crossed":
                danger_crossed
        },


        # ----------------------------------------------------
        # FUTURE WEATHER + RUNOFF
        # ----------------------------------------------------

        "forecast": {

            "rain_6h_mm":
                forecast_rain_6h,

            "rain_12h_mm":
                forecast_rain_12h,

            "rain_24h_mm":
                forecast_rain_24h,

            "rain_48h_mm":
                forecast_rain_48h,

            "runoff_6h_mm":
                forecast_runoff_6h,

            "runoff_12h_mm":
                forecast_runoff_12h,

            "runoff_24h_mm":
                forecast_runoff_24h,

            "runoff_48h_mm":
                forecast_runoff_48h
        },


        # ----------------------------------------------------
        # GEOGLOWS RIVER FORECAST
        #
        # IMPORTANT:
        # These are discharge/streamflow values.
        # They are NOT compared directly with BIPAD
        # water-level warning/danger thresholds.
        # ----------------------------------------------------

     "geoglows": {

    "station_count":
        geoglows_station_count,

    "current_flow_m3s":
        geoglows_current_flow,

    "forecast_peak_flow_m3s":
        geoglows_peak_flow,

    "forecast_rise_m3s":
        geoglows_rise,

    "forecast_rise_pct":
        geoglows.get(
            "forecast_rise_pct"
        ),

    "hours_to_peak":
        geoglows_hours_to_peak,

    "lead_time_hours":
        safe_float(
            geoglows.get(
                "lead_time_hours"
            )
        ),

    "peak_time":
        geoglows_peak_time,

    "forecast_upper_peak_m3s":
        geoglows_upper_peak,

    "forecast_lower_peak_m3s":
        geoglows_lower_peak,

    "representative_station":
        geoglows.get(
            "representative_station"
        ),

    "representative_station_id":
        geoglows.get(
            "representative_station_id"
        ),

    "representative_rise_m3s":
        safe_float(
            geoglows.get(
                "representative_rise_m3s"
            )
        )
},


        # ----------------------------------------------------
        # CURRENT HYDROLOGICAL FUSION
        # ----------------------------------------------------

        "hydrological_fusion": {

            "rainfall_signal":
                round(
                    rainfall_signal,
                    3
                ),

            "river_signal":
                round(
                    river_signal,
                    3
                ),

            "hydrological_signal":
                round(
                    hydrological_signal,
                    3
                ),

            "evidence_agreement":
                evidence_agreement,

            "hydrological_state":
                hydrological_state,

            "signal_strength":
                signal_strength
        },


        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        "data_quality": {

            "rainfall_available":
                rainfall_available,

            "river_available":
                river_available,

            "river_station_count":
                station_count,

            "forecast_available":
                forecast_available,

            "geoglows_available":
                geoglows_station_count > 0,

            "geoglows_station_count":
                geoglows_station_count
        }

    })


    processed += 1


# ============================================================
# FINAL OUTPUT
# ============================================================

output = {

    "project":
        "PRAVAH",

    "pipeline_version":
        "hydrology_fusion_v3",

    "generated_at_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),


    # --------------------------------------------------------
    # Source files
    # --------------------------------------------------------

    "source_files": {

    "rainfall":
        str(RAIN_FILE),

    "river":
        str(RIVER_FILE),

    "forecast_runoff":
        str(FORECAST_RUNOFF_FILE),

    "geoglows":
        str(GEOGLOWS_FILE)
},

    "district_count":
        len(fused_districts),


    # ========================================================
    # FEATURE SEMANTICS
    # ========================================================

    "feature_semantics": {

        "rainfall_signal":
            "Prototype indicator combining recent rainfall, rainfall intensity, estimated runoff, and antecedent rainfall.",

        "river_signal":
            "Threshold-aware prototype indicator based primarily on observed river danger-threshold utilization, warning utilization, and rising stations.",

        "forecast":
            "Future rainfall and SCS-CN runoff estimates from Open-Meteo ECMWF IFS HRES forecast.",

        "geoglows":
            "Forecast river discharge and streamflow evidence from GEOGLOWS matched to BIPAD river stations.",

        "hydrological_signal":
            "Current intermediate combined rainfall and observed river pressure indicator.",

        "evidence_agreement":
            "Indicates how closely current rainfall-derived and observed river-derived signals agree.",

        "hydrological_state":
            "Intermediate current hydrological state before final evidence fusion and risk assessment.",

        "important_note":
            "Forecast and GEOGLOWS evidence are currently exposed as additional features but are not yet included in the existing hydrological signal weights.",

        "geoglows_warning_note":
            "GEOGLOWS discharge values must not be directly compared with BIPAD observed water-level warning or danger thresholds."
    },


    # ========================================================
    # FUSION METHOD
    # ========================================================

    "fusion_method": {

        "rainfall_weight":
            0.45,

        "river_weight":
            0.55,

        "river_signal_method":
            "Threshold-aware piecewise pressure based primarily on observed river danger utilization.",

        "forecast_included_in_signal":
            False,

        "geoglows_included_in_signal":
            False,

        "note":
            "Current weights and signal thresholds are prototype values and should be calibrated using historical flood events before forecast evidence is incorporated."
    },


    # ========================================================
    # STATISTICS
    # ========================================================

    "statistics": {

        "districts_processed":
            processed,

        "river_data_available":
            river_data_available,

        "missing_river":
            missing_river,

        "forecast_data_available":
            forecast_data_available,

        "forecast_data_missing":
            processed -
            forecast_data_available,

        "geoglows_data_available":
            geoglows_data_available,

        "geoglows_data_missing":
            processed -
            geoglows_data_available,

        "geoglows_station_count":
            len(geoglows_stations),

        "strong_signal_districts":
            strong_signal,

        "moderate_signal_districts":
            moderate_signal,

        "weak_signal_districts":
            weak_signal,

        "near_warning_districts":
            near_warning_count,

        "near_danger_districts":
            near_danger_count,

        "warning_crossed_districts":
            warning_crossed_count,

        "danger_crossed_districts":
            danger_crossed_count
    },


    # ========================================================
    # DISTRICTS
    # ========================================================

    "districts":
        fused_districts
}


# ============================================================
# WRITE OUTPUT
# ============================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        indent=2
    )


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("HYDROLOGY FUSION V3 COMPLETE")
print("=" * 80)


print(
    f"\nDistricts processed        : "
    f"{processed}"
)

print(
    f"River data available      : "
    f"{river_data_available}/{processed}"
)

print(
    f"Missing river data        : "
    f"{missing_river}"
)

print(
    f"Forecast data available   : "
    f"{forecast_data_available}/{processed}"
)

print(
    f"GEOGLOWS data available   : "
    f"{geoglows_data_available}/{processed}"
)

print(
    f"GEOGLOWS stations         : "
    f"{len(geoglows_stations)}"
)

print(
    f"\nStrong hydro signal       : "
    f"{strong_signal}"
)

print(
    f"Moderate hydro signal     : "
    f"{moderate_signal}"
)

print(
    f"Weak hydro signal         : "
    f"{weak_signal}"
)

print(
    f"Near-warning districts    : "
    f"{near_warning_count}"
)

print(
    f"Near-danger districts     : "
    f"{near_danger_count}"
)

print(
    f"Warning crossed           : "
    f"{warning_crossed_count}"
)

print(
    f"Danger crossed            : "
    f"{danger_crossed_count}"
)


print("\nIntegrated features:")

print("  ✓ NASA/BIPAD current rainfall")
print("  ✓ Current SCS-CN runoff")
print("  ✓ BIPAD river observations")
print("  ✓ Threshold-aware river pressure")
print("  ✓ Open-Meteo forecast rainfall")
print("  ✓ Forecast SCS-CN runoff")
print("  ✓ GEOGLOWS river discharge forecast")
print("  ✓ GEOGLOWS district aggregation")
print("  ✓ Current rainfall/river fusion")
print("  ✓ Evidence agreement")
print("  ✓ Data quality indicators")


print("\nImportant:")

print(
    "  Forecast and GEOGLOWS evidence are exposed "
    "but not yet included in the current hydrological score."
)

print(
    "  GEOGLOWS discharge is NOT compared directly "
    "with BIPAD water-level thresholds."
)


print("\nOutput:")
print(
    f"  {OUTPUT_FILE}"
)

print("\nNext layer:")
print("  Evidence Fusion Engine")

print("=" * 80)
