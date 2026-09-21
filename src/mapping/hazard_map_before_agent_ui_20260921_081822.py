import json
import math
import html
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# PRAVAH HAZARD MAP V4
# ============================================================
#
# AUTHORITATIVE PIPELINE
#
# BIPAD + NASA IMERG
#        ↓
# Rainfall Features
#        ↓
# SCS-CN Runoff
#        ↓
# River / Hydrology
#        ↓
# Forecast + GeoGLOWS
#        ↓
# VIIRS EO Evidence
#        ↓
# Evidence Fusion
#        ↓
# PRAVAH Risk Engine
#
#
# VISUALIZATION
#
# Official Risk
#       ↓
# District fill
#
# Experimental Flood Pressure Index
#       ↓
# District border / glow
#
# River observations
#       ↓
# Buffered river corridors + stations
#
# Rain observations
#       ↓
# Rainfall markers + halos
#
# GeoGLOWS
#       ↓
# Forecast flow markers
#
# ============================================================


# ============================================================
# FILES
# ============================================================

from src.config import (
    GEOJSON_PATH,
    BIPAD_FILE as CONFIG_BIPAD_FILE,
    RAINFALL_FILE as CONFIG_RAINFALL_FILE,
    RUNOFF_FILE as CONFIG_RUNOFF_FILE,
    HYDROLOGY_FILE as CONFIG_HYDROLOGY_FILE,
    RIVER_FILE as CONFIG_RIVER_FILE,
    FORECAST_RUNOFF_FILE as CONFIG_FORECAST_RUNOFF_FILE,
    WEATHER_FILE as CONFIG_WEATHER_FILE,
    GEOGLOWS_FILE as CONFIG_GEOGLOWS_FILE,
    EO_FEATURES_FILE,
    EVIDENCE_FILE as CONFIG_EVIDENCE_FILE,
    RISK_FILE as CONFIG_RISK_FILE,
    HAZARD_MAP_FILE,
)

RISK_FILE = str(CONFIG_RISK_FILE)
BIPAD_FILE = str(CONFIG_BIPAD_FILE)
RAINFALL_FILE = str(CONFIG_RAINFALL_FILE)
RUNOFF_FILE = str(CONFIG_RUNOFF_FILE)
HYDROLOGY_FILE = str(CONFIG_HYDROLOGY_FILE)
RIVER_FILE = str(CONFIG_RIVER_FILE)
FORECAST_RUNOFF_FILE = str(CONFIG_FORECAST_RUNOFF_FILE)
WEATHER_FILE = str(CONFIG_WEATHER_FILE)
GEOGLOWS_FILE = str(CONFIG_GEOGLOWS_FILE)
EO_FILE = str(EO_FEATURES_FILE)
EVIDENCE_FILE = str(CONFIG_EVIDENCE_FILE)

GEOJSON_FILE = str(GEOJSON_PATH)

OUTPUT_FILE = str(HAZARD_MAP_FILE)


# ============================================================
# START
# ============================================================

print("=" * 100)
print("PRAVAH HAZARD MAP V4")
print("3D DISTRICTS + RIVER CORRIDORS + OBSERVATIONS")
print("=" * 100)


# ============================================================
# HELPERS
# ============================================================

def load_json(filename):

    path = Path(filename)

    if not path.exists():
        print(f"WARNING: {filename} not found")
        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as error:

        print(
            f"ERROR loading {filename}: {error}"
        )

        return {}


def safe_float(value):

    try:

        if value is None:
            return None

        result = float(value)

        if math.isnan(result):
            return None

        if math.isinf(result):
            return None

        return result

    except Exception:

        return None


def first_number(*values):

    for value in values:

        number = safe_float(value)

        if number is not None:
            return number

    return None


def clamp(
    value,
    minimum=0.0,
    maximum=100.0
):

    if value is None:
        return None

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


def normalize_name(name):

    if not name:
        return ""

    name = str(name).lower().strip()

    name = (
        name
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace("'", "")
        .replace(".", "")
    )

    aliases = {

        "chitawan": "chitwan",

        "tehrathum": "terhathum",
        "terathum": "terhathum",

        "sindhupalchowk": "sindhupalchok",

        "dhanusha": "dhanusa",

        "tanahun": "tanahu",

        "kapilvastu": "kapilbastu",

        "kavre": "kavrepalanchok",

        "ktm": "kathmandu",

        "nawalparasieast": "nawalparasieast",

        "nawalparasiwest": "nawalparasiwest",

        "rukumeast": "rukumeast",

        "rukumwest": "rukumwest"
    }

    return aliases.get(
        name,
        name
    )


def get_district_list(data):

    districts = data.get(
        "districts",
        []
    )

    if isinstance(
        districts,
        list
    ):

        return districts

    if isinstance(
        districts,
        dict
    ):

        result = []

        for key, value in districts.items():

            if not isinstance(
                value,
                dict
            ):
                continue

            item = dict(value)

            if "district_id" not in item:

                try:

                    item["district_id"] = int(key)

                except Exception:

                    pass

            result.append(item)

        return result

    return []


def district_lookup(data):

    result = {}

    for record in get_district_list(data):

        name = record.get(
            "district"
        )

        key = normalize_name(
            name
        )

        if key:

            result[key] = record

    return result


def district_id_lookup(data):

    result = {}

    for record in get_district_list(data):

        district_id = record.get(
            "district_id"
        )

        if district_id is None:
            continue

        try:

            result[
                int(district_id)
            ] = record

        except Exception:

            pass

    return result


def dict_district_lookup(data):

    result = {}

    districts = data.get(
        "districts",
        {}
    )

    if not isinstance(
        districts,
        dict
    ):

        return result

    for name, value in districts.items():

        if isinstance(
            value,
            dict
        ):

            result[
                normalize_name(name)
            ] = value

    return result


def js_json(data):

    """
    Safely embed Python JSON inside HTML/JavaScript.
    """

    text = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return (
        text
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


# ============================================================
# LOAD DATA
# ============================================================

print()
print("Loading PRAVAH data...")

risk_data = load_json(
    RISK_FILE
)

bipad_data = load_json(
    BIPAD_FILE
)

rainfall_data = load_json(
    RAINFALL_FILE
)

runoff_data = load_json(
    RUNOFF_FILE
)

hydrology_data = load_json(
    HYDROLOGY_FILE
)

river_data = load_json(
    RIVER_FILE
)

forecast_runoff_data = load_json(
    FORECAST_RUNOFF_FILE
)

weather_data = load_json(
    WEATHER_FILE
)

geoglows_data = load_json(
    GEOGLOWS_FILE
)

eo_data = load_json(
    EO_FILE
)

evidence_data = load_json(
    EVIDENCE_FILE
)

geojson = load_json(
    GEOJSON_FILE
)

features = geojson.get(
    "features",
    []
)

print(
    f"GeoJSON districts: {len(features)}"
)


# ============================================================
# LOOKUPS
# ============================================================

risk_by_name = district_lookup(
    risk_data
)

rainfall_by_name = district_lookup(
    rainfall_data
)

hydrology_by_name = district_lookup(
    hydrology_data
)

river_by_name = district_lookup(
    river_data
)

evidence_by_name = district_lookup(
    evidence_data
)

runoff_by_id = district_id_lookup(
    runoff_data
)

forecast_runoff_by_name = dict_district_lookup(
    forecast_runoff_data
)

weather_by_name = dict_district_lookup(
    weather_data
)

eo_by_name = dict_district_lookup(
    eo_data
)

geoglows_stations = geoglows_data.get(
    "stations",
    []
)

print(
    f"Risk districts: {len(risk_by_name)}"
)

print(
    f"Rainfall districts: {len(rainfall_by_name)}"
)

print(
    f"Hydrology districts: {len(hydrology_by_name)}"
)

print(
    f"River districts: {len(river_by_name)}"
)

print(
    f"EO districts: {len(eo_by_name)}"
)

print(
    f"GeoGLOWS stations: {len(geoglows_stations)}"
)


# ============================================================
# BIPAD REALTIME
# ============================================================

bipad_districts = bipad_data.get(
    "districts",
    {}
)

bipad_top = bipad_data.get(
    "top_monitoring_areas",
    []
)

bipad_by_id = {}

if isinstance(
    bipad_districts,
    dict
):

    for district_id, record in bipad_districts.items():

        if not isinstance(
            record,
            dict
        ):
            continue

        try:

            bipad_by_id[
                int(district_id)
            ] = record

        except Exception:

            pass


bipad_by_name = {}

if isinstance(
    bipad_top,
    list
):

    for record in bipad_top:

        if not isinstance(
            record,
            dict
        ):
            continue

        name = record.get(
            "district"
        )

        key = normalize_name(
            name
        )

        if key:

            bipad_by_name[
                key
            ] = record


# ============================================================
# EXTRACT RAIN STATIONS FROM BIPAD
#
# The realtime summary file may or may not contain station
# coordinates. We support several possible structures.
# ============================================================

rain_stations = []


def add_rain_station(
    station,
    district_name=None
):

    if not isinstance(
        station,
        dict
    ):
        return

    # --------------------------------------------
    # COORDINATES
    # --------------------------------------------

    coordinates = None

    for location_key in [
        "point",
        "geometry",
        "location"
    ]:

        location = station.get(
            location_key
        )

        if isinstance(
            location,
            dict
        ):

            coords = location.get(
                "coordinates"
            )

            if (
                isinstance(coords, list)
                and len(coords) >= 2
            ):

                coordinates = coords
                break

    if coordinates is None:

        coords = station.get(
            "coordinates"
        )

        if (
            isinstance(coords, list)
            and len(coords) >= 2
        ):

            coordinates = coords

    if coordinates is None:
        return

    lon = safe_float(
        coordinates[0]
    )

    lat = safe_float(
        coordinates[1]
    )

    if (
        lat is None
        or lon is None
    ):
        return

    # --------------------------------------------
    # RAIN VALUE
    # --------------------------------------------

    rain_1h = first_number(
        station.get("rain_1h_mm"),
        station.get("rain_1h"),
        station.get("value"),
        station.get("rainfall")
    )

    station_name = (
        station.get("station")
        or station.get("station_name")
        or station.get("name")
        or "Rain Gauge"
    )

    district = (
        station.get("district")
        or district_name
        or "Unknown"
    )

    rain_stations.append({

        "station":
            station_name,

        "district":
            district,

        "lat":
            lat,

        "lon":
            lon,

        "rain_1h_mm":
            rain_1h,

        "observed_at":
            station.get(
                "observed_at"
            )
            or station.get(
                "measured_on"
            )
            or "Unknown",

        "source":
            station.get(
                "source",
                "BIPAD"
            )

    })


# Search possible nested station structures
def recursively_find_rain_stations(
    obj,
    district_name=None,
    depth=0
):

    if depth > 5:
        return

    if isinstance(
        obj,
        dict
    ):

        # If this itself looks like a station
        if (
            "coordinates" in obj
            or "point" in obj
            or "geometry" in obj
        ):

            add_rain_station(
                obj,
                district_name
            )

        for key, value in obj.items():

            next_district = district_name

            if (
                key == "district"
                and isinstance(
                    value,
                    str
                )
            ):

                next_district = value

            recursively_find_rain_stations(
                value,
                next_district,
                depth + 1
            )

    elif isinstance(
        obj,
        list
    ):

        for item in obj:

            recursively_find_rain_stations(
                item,
                district_name,
                depth + 1
            )


recursively_find_rain_stations(
    bipad_data
)


# Remove duplicate rain stations
rain_seen = set()
clean_rain_stations = []

for station in rain_stations:

    key = (
        station["station"],
        round(station["lat"], 5),
        round(station["lon"], 5)
    )

    if key in rain_seen:
        continue

    rain_seen.add(key)

    clean_rain_stations.append(
        station
    )

rain_stations = clean_rain_stations


# ============================================================
# RIVER STATIONS
# ============================================================

river_stations = []

for record in get_district_list(
    river_data
):

    district_name = record.get(
        "district",
        "Unknown"
    )

    river = record.get(
        "river",
        {}
    )

    stations = river.get(
        "stations",
        []
    )

    if not isinstance(
        stations,
        list
    ):
        continue

    for station in stations:

        if not isinstance(
            station,
            dict
        ):
            continue

        river_stations.append({

            "district":
                district_name,

            "station":
                station.get(
                    "station",
                    "River Station"
                ),

            "water_level_m":
                safe_float(
                    station.get(
                        "water_level_m"
                    )
                ),

            "warning_level_m":
                safe_float(
                    station.get(
                        "warning_level_m"
                    )
                ),

            "danger_level_m":
                safe_float(
                    station.get(
                        "danger_level_m"
                    )
                ),

            "warning_utilization":
                safe_float(
                    station.get(
                        "warning_utilization"
                    )
                ),

            "danger_utilization":
                safe_float(
                    station.get(
                        "danger_utilization"
                    )
                ),

            "status":
                station.get(
                    "status",
                    "UNKNOWN"
                ),

            "trend":
                station.get(
                    "trend",
                    "UNKNOWN"
                ),

            "observed_at":
                station.get(
                    "observed_at",
                    "Unknown"
                ),

            "source":
                station.get(
                    "source",
                    "hydrology.gov.np"
                )

        })


# ============================================================
# MATCH RIVER STATIONS WITH GEOGLOWS
# ============================================================

print()
print(
    "Matching river stations with GeoGLOWS..."
)

geoglows_by_name = {}

for station in geoglows_stations:

    if not isinstance(
        station,
        dict
    ):
        continue

    station_name = station.get(
        "station_name"
    )

    if not station_name:
        continue

    geoglows_by_name[
        normalize_name(
            station_name
        )
    ] = station


river_mapped = 0

for river_station in river_stations:

    station_key = normalize_name(
        river_station["station"]
    )

    geo_station = geoglows_by_name.get(
        station_key
    )

    # Exact normalized match
    if geo_station:

        river_station["lat"] = safe_float(
            geo_station.get(
                "latitude"
            )
        )

        river_station["lon"] = safe_float(
            geo_station.get(
                "longitude"
            )
        )

        river_station[
            "geoglows_station"
        ] = True

        river_mapped += 1

    else:

        river_station["lat"] = None
        river_station["lon"] = None

        river_station[
            "geoglows_station"
        ] = False


print(
    f"River stations: {len(river_stations)}"
)

print(
    f"River stations with coordinates: {river_mapped}"
)


# ============================================================
# EXPERIMENTAL FLOOD PRESSURE INDEX
# ============================================================

def calculate_pressure_index(
    rainfall,
    hydrology,
    river,
    forecast_runoff,
    geoglows,
    eo
):

    """
    Experimental explanatory index.

    IMPORTANT:
    This does NOT replace the PRAVAH Risk Engine.

    It is only used to visualize combined hydrological
    pressure from multiple sources.

    The values below are scaling values, NOT official
    government warning thresholds.
    """

    components = []

    # --------------------------------------------------------
    # RAINFALL
    # --------------------------------------------------------

    rain = rainfall.get(
        "rainfall",
        {}
    )

    rain_values = []

    rain_1h = safe_float(
        rain.get(
            "bipad_1h_mm"
        )
    )

    rain_6h = safe_float(
        rain.get(
            "nasa_6h_mm"
        )
    )

    rain_24h = safe_float(
        rain.get(
            "nasa_24h_mm"
        )
    )

    if rain_1h is not None:

        rain_values.append(
            min(
                100,
                rain_1h / 25 * 100
            )
        )

    if rain_6h is not None:

        rain_values.append(
            min(
                100,
                rain_6h / 75 * 100
            )
        )

    if rain_24h is not None:

        rain_values.append(
            min(
                100,
                rain_24h / 150 * 100
            )
        )

    if rain_values:

        components.append(
            (
                max(rain_values),
                0.22
            )
        )

    # --------------------------------------------------------
    # ANTECEDENT
    # --------------------------------------------------------

    hydro_features = rainfall.get(
        "hydrological_features",
        {}
    )

    antecedent = safe_float(
        hydro_features.get(
            "antecedent_rainfall_indicator"
        )
    )

    if antecedent is not None:

        components.append(
            (
                min(
                    100,
                    antecedent / 150 * 100
                ),
                0.12
            )
        )

    # --------------------------------------------------------
    # RUNOFF
    # --------------------------------------------------------

    runoff = safe_float(
        hydro_features.get(
            "scs_cn_runoff_6h_mm"
        )
    )

    if runoff is not None:

        components.append(
            (
                min(
                    100,
                    runoff / 50 * 100
                ),
                0.16
            )
        )

    # --------------------------------------------------------
    # RIVER
    # --------------------------------------------------------

    river_local = river.get(
        "river",
        {}
    )

    river_values = []

    warning_utilization = safe_float(
        river_local.get(
            "max_warning_utilization"
        )
    )

    danger_utilization = safe_float(
        river_local.get(
            "max_danger_utilization"
        )
    )

    if warning_utilization is not None:

        river_values.append(
            min(
                100,
                warning_utilization * 100
            )
        )

    if danger_utilization is not None:

        river_values.append(
            min(
                100,
                danger_utilization * 100
            )
        )

    if river_local.get(
        "warning_crossed",
        False
    ):

        river_values.append(
            90
        )

    if river_local.get(
        "danger_crossed",
        False
    ):

        river_values.append(
            100
        )

    if river_values:

        components.append(
            (
                max(river_values),
                0.22
            )
        )

    # --------------------------------------------------------
    # FORECAST RUNOFF
    # --------------------------------------------------------

    forecast_values = []

    if isinstance(
        forecast_runoff,
        dict
    ):

        for key in [
            "runoff_6h_mm",
            "runoff_12h_mm",
            "runoff_24h_mm",
            "runoff_48h_mm"
        ]:

            value = safe_float(
                forecast_runoff.get(
                    key
                )
            )

            if value is not None:

                forecast_values.append(
                    value
                )

    if forecast_values:

        components.append(
            (
                min(
                    100,
                    max(forecast_values)
                    / 50
                    * 100
                ),
                0.10
            )
        )

    # --------------------------------------------------------
    # GEOGLOWS
    # --------------------------------------------------------

    if isinstance(
        geoglows,
        dict
    ):

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

        rise = safe_float(
            geoglows.get(
                "forecast_rise_m3s"
            )
        )

        geo_values = []

        if (
            current_flow is not None
            and current_flow > 0
            and rise is not None
        ):

            rise_ratio = (
                rise /
                current_flow
            )

            geo_values.append(
                min(
                    100,
                    rise_ratio * 50
                )
            )

        if (
            current_flow is not None
            and current_flow > 0
            and peak_flow is not None
        ):

            peak_ratio = (
                peak_flow /
                current_flow
            )

            geo_values.append(
                min(
                    100,
                    max(
                        0,
                        (peak_ratio - 1)
                        * 100
                    )
                )
            )

        if geo_values:

            components.append(
                (
                    max(geo_values),
                    0.08
                )
            )

    # --------------------------------------------------------
    # EO
    # --------------------------------------------------------

    if isinstance(
        eo,
        dict
    ):

        eo_observation = eo.get(
            "eo_observation",
            eo
        )

        eo_score = safe_float(
            eo_observation.get(
                "eo_score"
            )
        )

        if eo_score is not None:

            components.append(
                (
                    min(
                        100,
                        eo_score
                    ),
                    0.05
                )
            )

    # --------------------------------------------------------
    # WEIGHTED SCORE
    # --------------------------------------------------------

    if len(components) < 2:
        return None

    weighted = 0
    weight_total = 0

    for value, weight in components:

        weighted += (
            value * weight
        )

        weight_total += weight

    if weight_total <= 0:
        return None

    return round(
        clamp(
            weighted /
            weight_total
        ),
        1
    )


def pressure_class(score):

    if score is None:
        return "NO DATA"

    if score >= 75:
        return "CRITICAL"

    if score >= 55:
        return "WARNING"

    if score >= 30:
        return "WATCH"

    return "LOW"


# ============================================================
# RISK COUNTS
# ============================================================

risk_counts = {

    "LOW": 0,
    "WATCH": 0,
    "WARNING": 0,
    "CRITICAL": 0,
    "NO DATA": 0

}

matched = 0
unmatched = 0

pressure_values = []


# ============================================================
# BUILD DISTRICT PROPERTIES
# ============================================================

print()
print("=" * 100)
print("BUILDING DISTRICT MODEL")
print("=" * 100)


for feature in features:

    properties = feature.setdefault(
        "properties",
        {}
    )

    geo_name = properties.get(
        "adm2_name",
        "Unknown"
    )

    geo_key = normalize_name(
        geo_name
    )

    risk_record = risk_by_name.get(
        geo_key,
        {}
    )

    rainfall_record = rainfall_by_name.get(
        geo_key,
        {}
    )

    hydro_record = hydrology_by_name.get(
        geo_key,
        {}
    )

    river_record = river_by_name.get(
        geo_key,
        {}
    )

    evidence_record = evidence_by_name.get(
        geo_key,
        {}
    )

    eo_record = eo_by_name.get(
        geo_key,
        {}
    )

    # --------------------------------------------------------
    # DISTRICT ID
    # --------------------------------------------------------

    district_id = (
        risk_record.get(
            "district_id"
        )
        or rainfall_record.get(
            "district_id"
        )
        or hydro_record.get(
            "district_id"
        )
        or river_record.get(
            "district_id"
        )
    )

    # --------------------------------------------------------
    # RISK
    # --------------------------------------------------------

    risk = risk_record.get(
        "risk",
        {}
    )

    risk_level = str(
        risk.get(
            "level",
            "NO DATA"
        )
    ).upper()

    risk_score = safe_float(
        risk.get(
            "score"
        )
    )

    if risk_level in risk_counts:

        risk_counts[
            risk_level
        ] += 1

    else:

        risk_counts[
            "NO DATA"
        ] += 1

    if risk_record:

        matched += 1

    else:

        unmatched += 1

    # --------------------------------------------------------
    # EVIDENCE
    # --------------------------------------------------------

    evidence = risk_record.get(
        "evidence",
        evidence_record.get(
            "evidence",
            {}
        )
    )

    # --------------------------------------------------------
    # EO
    # --------------------------------------------------------

    eo_observation = risk_record.get(
        "eo_observation",
        evidence_record.get(
            "eo_observation",
            eo_record
        )
    )

    if not isinstance(
        eo_observation,
        dict
    ):

        eo_observation = {}

    # --------------------------------------------------------
    # RIVER
    # --------------------------------------------------------

    river_local = river_record.get(
        "river",
        {}
    )

    if not isinstance(
        river_local,
        dict
    ):

        river_local = {}

    # --------------------------------------------------------
    # FORECAST
    # --------------------------------------------------------

    forecast_runoff = (
        forecast_runoff_by_name.get(
            geo_key,
            {}
        )
    )

    if not isinstance(
        forecast_runoff,
        dict
    ):

        forecast_runoff = {}

    # --------------------------------------------------------
    # GEOGLOWS DISTRICT SUMMARY
    # --------------------------------------------------------

    station_matches = []

    for station in geoglows_stations:

        if not isinstance(
            station,
            dict
        ):
            continue

        station_district = station.get(
            "district_id"
        )

        if (
            district_id is not None
            and station_district is not None
        ):

            try:

                if int(
                    station_district
                ) == int(
                    district_id
                ):

                    station_matches.append(
                        station
                    )

            except Exception:

                pass

    geoglows_summary = {

        "station_count":
            len(station_matches),

        "current_flow_m3s":
            None,

        "forecast_peak_flow_m3s":
            None,

        "forecast_rise_m3s":
            None,

        "hours_to_peak":
            None,

        "peak_time":
            None

    }

    current_flows = []
    peak_flows = []
    rises = []
    peak_hours = []
    peak_times = []

    for station in station_matches:

        geo = station.get(
            "geoglows",
            {}
        )

        if not isinstance(
            geo,
            dict
        ):
            continue

        value = safe_float(
            geo.get(
                "current_flow_m3s"
            )
        )

        if value is not None:
            current_flows.append(
                value
            )

        value = safe_float(
            geo.get(
                "forecast_peak_flow_m3s"
            )
        )

        if value is not None:
            peak_flows.append(
                value
            )

        value = safe_float(
            geo.get(
                "forecast_rise_m3s"
            )
        )

        if value is not None:
            rises.append(
                value
            )

        value = safe_float(
            geo.get(
                "hours_to_peak"
            )
        )

        if value is not None:
            peak_hours.append(
                value
            )

        peak_time = geo.get(
            "peak_time"
        )

        if peak_time:
            peak_times.append(
                peak_time
            )

    if current_flows:

        geoglows_summary[
            "current_flow_m3s"
        ] = max(
            current_flows
        )

    if peak_flows:

        geoglows_summary[
            "forecast_peak_flow_m3s"
        ] = max(
            peak_flows
        )

    if rises:

        geoglows_summary[
            "forecast_rise_m3s"
        ] = max(
            rises
        )

    if peak_hours:

        geoglows_summary[
            "hours_to_peak"
        ] = min(
            peak_hours
        )

    if peak_times:

        geoglows_summary[
            "peak_time"
        ] = peak_times[0]

    # --------------------------------------------------------
    # PRESSURE
    # --------------------------------------------------------

    pressure_score = calculate_pressure_index(
        rainfall_record,
        hydro_record,
        river_record,
        forecast_runoff,
        geoglows_summary,
        eo_observation
    )

    pressure_level = pressure_class(
        pressure_score
    )

    if pressure_score is not None:

        pressure_values.append(
            pressure_score
        )

    # --------------------------------------------------------
    # BASIC
    # --------------------------------------------------------

    properties[
        "pravah_district_id"
    ] = district_id

    properties[
        "pravah_district_name"
    ] = (
        risk_record.get(
            "district"
        )
        or geo_name
    )

    properties[
        "pravah_risk"
    ] = risk_level

    properties[
        "pravah_score"
    ] = risk_score

    properties[
        "pravah_severity"
    ] = risk.get(
        "severity",
        "UNKNOWN"
    )

    properties[
        "pravah_drivers"
    ] = risk_record.get(
        "drivers",
        []
    )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = risk_record.get(
        "confidence",
        {}
    )

    properties[
        "pravah_confidence"
    ] = confidence.get(
        "level",
        "LOW"
    )

    properties[
        "pravah_confidence_score"
    ] = safe_float(
        confidence.get(
            "score"
        )
    )

    # --------------------------------------------------------
    # EVIDENCE
    # --------------------------------------------------------

    properties[
        "evidence_rainfall"
    ] = evidence.get(
        "rainfall",
        "NO_DATA"
    )

    properties[
        "evidence_runoff"
    ] = evidence.get(
        "runoff",
        "NO_DATA"
    )

    properties[
        "evidence_river"
    ] = evidence.get(
        "river",
        "NO_DATA"
    )

    properties[
        "evidence_antecedent"
    ] = evidence.get(
        "antecedent_rainfall",
        "NO_DATA"
    )

    properties[
        "evidence_eo"
    ] = evidence.get(
        "eo_flood",
        "NONE"
    )

    properties[
        "evidence_dominant_signal"
    ] = evidence.get(
        "dominant_signal",
        "NONE"
    )

    properties[
        "evidence_agreement"
    ] = evidence.get(
        "agreement",
        "UNKNOWN"
    )

    # --------------------------------------------------------
    # RAINFALL
    # --------------------------------------------------------

    rainfall = rainfall_record.get(
        "rainfall",
        {}
    )

    hydro_features = rainfall_record.get(
        "hydrological_features",
        {}
    )

    properties[
        "rain_1h_mm"
    ] = safe_float(
        rainfall.get(
            "bipad_1h_mm"
        )
    )

    properties[
        "rain_6h_mm"
    ] = safe_float(
        rainfall.get(
            "nasa_6h_mm"
        )
    )

    properties[
        "rain_12h_mm"
    ] = safe_float(
        rainfall.get(
            "nasa_12h_mm"
        )
    )

    properties[
        "rain_24h_mm"
    ] = safe_float(
        rainfall.get(
            "nasa_24h_mm"
        )
    )

    properties[
        "rain_3day_mm"
    ] = safe_float(
        rainfall.get(
            "nasa_3day_mm"
        )
    )

    properties[
        "rain_5day_mm"
    ] = safe_float(
        rainfall.get(
            "nasa_5day_mm"
        )
    )

    properties[
        "rainfall_intensity"
    ] = safe_float(
        hydro_features.get(
            "rainfall_intensity_6h_mm_per_hour"
        )
    )

    properties[
        "rainfall_intensity_class"
    ] = hydro_features.get(
        "rainfall_intensity_class",
        "UNKNOWN"
    )

    properties[
        "rainfall_persistence"
    ] = safe_float(
        hydro_features.get(
            "rainfall_persistence"
        )
    )

    properties[
        "antecedent_rainfall"
    ] = safe_float(
        hydro_features.get(
            "antecedent_rainfall_indicator"
        )
    )

    # --------------------------------------------------------
    # RUNOFF
    # --------------------------------------------------------

    properties[
        "scs_cn_runoff_6h_mm"
    ] = safe_float(
        hydro_features.get(
            "scs_cn_runoff_6h_mm"
        )
    )

    runoff_record = {}

    if district_id is not None:

        try:

            runoff_record = runoff_by_id.get(
                int(district_id),
                {}
            )

        except Exception:

            runoff_record = {}

    properties[
        "runoff_mm"
    ] = first_number(
        runoff_record.get(
            "runoff_mm"
        ),
        runoff_record.get(
            "scs_cn_runoff_mm"
        ),
        runoff_record.get(
            "runoff"
        )
    )

    # --------------------------------------------------------
    # RIVER
    # --------------------------------------------------------

    properties[
        "river_station_count"
    ] = river_local.get(
        "station_count",
        0
    )

    properties[
        "river_max_water_level_m"
    ] = safe_float(
        river_local.get(
            "max_water_level_m"
        )
    )

    properties[
        "river_warning_utilization"
    ] = safe_float(
        river_local.get(
            "max_warning_utilization"
        )
    )

    properties[
        "river_danger_utilization"
    ] = safe_float(
        river_local.get(
            "max_danger_utilization"
        )
    )

    properties[
        "river_warning_stations"
    ] = river_local.get(
        "warning_station_count",
        0
    )

    properties[
        "river_danger_stations"
    ] = river_local.get(
        "danger_station_count",
        0
    )

    properties[
        "river_rising_stations"
    ] = river_local.get(
        "rising_station_count",
        0
    )

    properties[
        "river_status"
    ] = river_local.get(
        "river_status",
        "UNKNOWN"
    )

    properties[
        "river_trend"
    ] = river_local.get(
        "trend",
        "UNKNOWN"
    )

    # --------------------------------------------------------
    # FORECAST RUNOFF
    # --------------------------------------------------------

    properties[
        "forecast_runoff_6h"
    ] = safe_float(
        forecast_runoff.get(
            "runoff_6h_mm"
        )
    )

    properties[
        "forecast_runoff_12h"
    ] = safe_float(
        forecast_runoff.get(
            "runoff_12h_mm"
        )
    )

    properties[
        "forecast_runoff_24h"
    ] = safe_float(
        forecast_runoff.get(
            "runoff_24h_mm"
        )
    )

    properties[
        "forecast_runoff_48h"
    ] = safe_float(
        forecast_runoff.get(
            "runoff_48h_mm"
        )
    )

    # --------------------------------------------------------
    # GEOGLOWS
    # --------------------------------------------------------

    properties[
        "geoglows_station_count"
    ] = geoglows_summary[
        "station_count"
    ]

    properties[
        "geoglows_current_flow"
    ] = geoglows_summary[
        "current_flow_m3s"
    ]

    properties[
        "geoglows_peak_flow"
    ] = geoglows_summary[
        "forecast_peak_flow_m3s"
    ]

    properties[
        "geoglows_forecast_rise"
    ] = geoglows_summary[
        "forecast_rise_m3s"
    ]

    properties[
        "geoglows_hours_to_peak"
    ] = geoglows_summary[
        "hours_to_peak"
    ]

    properties[
        "geoglows_peak_time"
    ] = geoglows_summary[
        "peak_time"
    ]

    # --------------------------------------------------------
    # EO
    # --------------------------------------------------------

    properties[
        "eo_available"
    ] = bool(
        eo_observation.get(
            "available",
            False
        )
    )

    properties[
        "eo_observation_date"
    ] = eo_observation.get(
        "observation_date"
    )

    properties[
        "eo_source"
    ] = eo_observation.get(
        "source"
    )

    properties[
        "eo_resolution"
    ] = eo_observation.get(
        "resolution"
    )

    properties[
        "eo_flood_pixels"
    ] = eo_observation.get(
        "flood_pixels"
    )

    properties[
        "eo_flood_ratio_pct"
    ] = safe_float(
        eo_observation.get(
            "flood_ratio_pct"
        )
    )

    properties[
        "eo_score"
    ] = safe_float(
        eo_observation.get(
            "eo_score"
        )
    )

    properties[
        "eo_temporal_role"
    ] = eo_observation.get(
        "temporal_role",
        "LAGGED_OBSERVATION"
    )

    # --------------------------------------------------------
    # FUTURE OUTLOOK
    # --------------------------------------------------------

    evidence_summary = evidence_record.get(
        "evidence_summary",
        {}
    )

    properties[
        "future_outlook"
    ] = (
        evidence_summary.get(
            "future_outlook"
        )
        or "UNKNOWN"
    )

    properties[
        "future_evidence_available"
    ] = evidence_summary.get(
        "future_evidence_available",
        False
    )

    # --------------------------------------------------------
    # HYDROLOGY
    # --------------------------------------------------------

    fusion = hydro_record.get(
        "hydrological_fusion",
        {}
    )

    properties[
        "hydrology_state"
    ] = fusion.get(
        "hydrological_state",
        "UNKNOWN"
    )

    properties[
        "hydrology_signal"
    ] = safe_float(
        fusion.get(
            "hydrological_signal"
        )
    )

    properties[
        "hydrology_strength"
    ] = fusion.get(
        "signal_strength",
        "UNKNOWN"
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    data_quality = risk_record.get(
        "data_quality",
        {}
    )

    properties[
        "data_quality"
    ] = data_quality.get(
        "overall",
        "UNKNOWN"
    )

    properties[
        "rainfall_available"
    ] = data_quality.get(
        "rainfall_available",
        False
    )

    properties[
        "river_available"
    ] = data_quality.get(
        "river_available",
        False
    )

    properties[
        "forecast_available"
    ] = data_quality.get(
        "forecast_available",
        False
    )

    properties[
        "geoglows_available"
    ] = data_quality.get(
        "geoglows_available",
        False
    )

    properties[
        "eo_data_available"
    ] = data_quality.get(
        "eo_available",
        False
    )

    # --------------------------------------------------------
    # PRESSURE
    # --------------------------------------------------------

    properties[
        "pressure_index"
    ] = pressure_score

    properties[
        "pressure_level"
    ] = pressure_level

    properties[
        "pressure_model"
    ] = "PRAVAH Composite Flood Pressure Index v1"


# ============================================================
# PRESSURE SUMMARY
# ============================================================

pressure_mean = (
    round(
        sum(pressure_values)
        / len(pressure_values),
        1
    )
    if pressure_values
    else 0
)

pressure_max = (
    round(
        max(pressure_values),
        1
    )
    if pressure_values
    else 0
)


# ============================================================
# RAIN / RIVER COUNTS
# ============================================================

rainfall_district_count = 0
rising_rivers = 0
warning_rivers = 0
danger_rivers = 0

for feature in features:

    props = feature.get(
        "properties",
        {}
    )

    if props.get(
        "rainfall_available",
        False
    ):

        rainfall_district_count += 1

    rising_rivers += int(
        props.get(
            "river_rising_stations",
            0
        )
        or 0
    )

    warning_rivers += int(
        props.get(
            "river_warning_stations",
            0
        )
        or 0
    )

    danger_rivers += int(
        props.get(
            "river_danger_stations",
            0
        )
        or 0
    )


# ============================================================
# GENERATED TIME
# ============================================================

generated_at = (
    risk_data.get(
        "metadata",
        {}
    ).get(
        "generated_at"
    )
)

if not generated_at:

    generated_at = risk_data.get(
        "generated_at"
    )

if not generated_at:

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# PRINT SUMMARY
# ============================================================

print()
print("=" * 100)
print("MODEL SUMMARY")
print("=" * 100)

print(
    f"Districts:              {len(features)}"
)

print(
    f"Risk matched:            {matched}"
)

print(
    f"Risk unmatched:          {unmatched}"
)

print(
    f"Rain stations:           {len(rain_stations)}"
)

print(
    f"River stations:          {len(river_stations)}"
)

print(
    f"River mapped:            {river_mapped}"
)

print(
    f"Rainfall districts:      {rainfall_district_count}"
)

print(
    f"Rising river stations:   {rising_rivers}"
)

print(
    f"Warning stations:        {warning_rivers}"
)

print(
    f"Danger stations:         {danger_rivers}"
)

print(
    f"Pressure districts:      {len(pressure_values)}"
)

print(
    f"Pressure mean:           {pressure_mean}"
)

print(
    f"Pressure max:            {pressure_max}"
)


# ============================================================
# JAVASCRIPT DATA
# ============================================================

geojson_js = js_json(
    geojson
)

river_stations_js = js_json(
    river_stations
)

rain_stations_js = js_json(
    rain_stations
)


# ============================================================
# HTML
# ============================================================

html_content = r"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>PRAVAH Flood Monitoring</title>


<link
    rel="stylesheet"
    href="../../src/mapping/vendor/leaflet/leaflet.css"
/>




<style>

/* ============================================================
   GLOBAL
   ============================================================ */

* {
    box-sizing: border-box;
}

html,
body {

    margin: 0;
    padding: 0;

    width: 100%;
    height: 100%;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    overflow: hidden;
}

#map {

    width: 100%;
    height: 100vh;

    background: #dce5e8;
}


/* ============================================================
   PRAVAH HEADER
   ============================================================ */

.header {

    position: absolute;

    top: 12px;
    left: 58px;

    z-index: 3000;

    background:
        rgba(255,255,255,0.94);

    padding:
        8px 13px;

    border-radius:
        8px;

    box-shadow:
        0 2px 10px
        rgba(0,0,0,0.18);

    min-width:
        205px;
}

.header h1 {

    margin: 0;

    font-size: 18px;

    letter-spacing:
        1.8px;
}

.header p {

    margin:
        2px 0 0;

    font-size: 9px;

    color: #666;
}


/* ============================================================
   COMPACT DASHBOARD
   ============================================================ */

.dashboard {

    position: absolute;

    top: 67px;
    left: 58px;

    z-index: 3000;

    width: 205px;

    background:
        rgba(255,255,255,0.94);

    padding:
        9px 11px;

    border-radius:
        8px;

    box-shadow:
        0 2px 10px
        rgba(0,0,0,0.18);
}

.dashboard-title {

    font-size: 9px;

    font-weight: bold;

    letter-spacing:
        0.8px;

    margin-bottom:
        5px;
}

.dashboard-grid {

    display: grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap: 4px;
}

.metric {

    background:
        #f4f5f5;

    border-radius:
        5px;

    padding:
        5px 2px;

    text-align:
        center;
}

.metric-number {

    font-size:
        14px;

    font-weight:
        bold;
}

.metric-label {

    font-size:
        7px;

    color:
        #777;

    margin-top:
        1px;
}

.metric.low .metric-number {
    color: #2e7d32;
}

.metric.watch .metric-number {
    color: #f9a825;
}

.metric.warning .metric-number {
    color: #ef6c00;
}

.metric.critical .metric-number {
    color: #c62828;
}

.observation-row {

    display:
        flex;

    justify-content:
        space-between;

    font-size:
        8px;

    margin-top:
        5px;

    color:
        #555;
}


/* ============================================================
   PRESSURE MINI PANEL
   ============================================================ */

.pressure-panel {

    position: absolute;

    top: 12px;
    right: 12px;

    z-index: 3000;

    width: 205px;

    background:
        rgba(255,255,255,0.94);

    padding:
        9px 11px;

    border-radius:
        8px;

    box-shadow:
        0 2px 10px
        rgba(0,0,0,0.18);
}

.pressure-title {

    font-size:
        9px;

    font-weight:
        bold;

    letter-spacing:
        0.5px;
}

.pressure-description {

    font-size:
        7px;

    color:
        #777;

    line-height:
        1.35;

    margin-top:
        3px;

    margin-bottom:
        6px;
}

.pressure-bar {

    height:
        7px;

    width:
        100%;

    background:
        #e4e6e6;

    border-radius:
        5px;

    overflow:
        hidden;
}

.pressure-fill {

    height:
        100%;

    width:
        PRESSURE_WIDTH%;

    background:
        #555;

    border-radius:
        5px;

    transition:
        width 0.4s ease;
}

.pressure-bottom {

    display:
        flex;

    justify-content:
        space-between;

    margin-top:
        4px;

    font-size:
        8px;

    font-weight:
        bold;
}


/* ============================================================
   MAP INFORMATION
   ============================================================ */

.map-note {

    position:
        absolute;

    bottom:
        13px;

    left:
        58px;

    z-index:
        3000;

    background:
        rgba(255,255,255,0.90);

    padding:
        5px 8px;

    border-radius:
        6px;

    font-size:
        7px;

    color:
        #555;

    box-shadow:
        0 2px 8px
        rgba(0,0,0,0.15);
}


/* ============================================================
   LEGEND
   ============================================================ */

.legend {

    position:
        absolute;

    right:
        12px;

    bottom:
        13px;

    z-index:
        3000;

    width:
        180px;

    background:
        rgba(255,255,255,0.94);

    padding:
        8px 10px;

    border-radius:
        8px;

    box-shadow:
        0 2px 10px
        rgba(0,0,0,0.18);

    font-size:
        8px;
}

.legend-title {

    font-size:
        9px;

    font-weight:
        bold;

    margin-bottom:
        5px;
}

.legend-section {

    font-size:
        7px;

    font-weight:
        bold;

    color:
        #777;

    margin-top:
        5px;

    margin-bottom:
        3px;
}

.legend-row {

    display:
        flex;

    align-items:
        center;

    margin:
        3px 0;
}

.legend-box {

    width:
        12px;

    height:
        12px;

    border-radius:
        2px;

    margin-right:
        5px;
}

.legend-circle {

    width:
        9px;

    height:
        9px;

    border-radius:
        50%;

    margin-right:
        7px;

    border:
        2px solid white;

    box-shadow:
        0 0 0 1px #777;
}


/* ============================================================
   LEAFLET CONTROLS
   ============================================================ */

.leaflet-control-layers {

    border:
        none !important;

    border-radius:
        7px !important;

    box-shadow:
        0 2px 10px
        rgba(0,0,0,0.20) !important;

    font-size:
        9px;

    background:
        rgba(255,255,255,0.96);
}

.leaflet-control-layers-toggle {

    width:
        30px !important;

    height:
        30px !important;
}


/* ============================================================
   3D DISTRICT LABEL
   ============================================================ */

.district-label {

    background:
        transparent;

    border:
        none;
}


/* ============================================================
   RIVER ANIMATION
   ============================================================ */

.river-flow {

    stroke-dasharray:
        8 10;

    animation:
        riverFlow 2s linear infinite;
}

@keyframes riverFlow {

    from {
        stroke-dashoffset:
            0;
    }

    to {
        stroke-dashoffset:
            -36;
    }
}


/* ============================================================
   RAINFALL HALO
   ============================================================ */

.rain-halo {

    border-radius:
        50%;

    opacity:
        0.18;

    animation:
        rainPulse 2.4s ease-in-out infinite;
}

@keyframes rainPulse {

    0% {
        transform:
            scale(0.8);

        opacity:
            0.10;
    }

    50% {
        transform:
            scale(1.15);

        opacity:
            0.24;
    }

    100% {
        transform:
            scale(0.8);

        opacity:
            0.10;
    }
}


/* ============================================================
   POPUP
   ============================================================ */

.popup {

    min-width:
        285px;

    max-width:
        360px;

    font-size:
        11px;

    line-height:
        1.4;

    color:
        #263238;

    font-family:
        Arial,
        Helvetica,
        sans-serif;
}

.popup-title {

    font-size:
        17px;

    font-weight:
        700;

    margin-bottom:
        2px;

    color:
        #172027;
}

.popup-subtitle {

    font-size:
        9px;

    color:
        #6b747b;

    margin-bottom:
        9px;
}

.popup-section {

    margin-top:
        11px;

    margin-bottom:
        5px;

    padding-bottom:
        4px;

    border-bottom:
        1px solid #d9dee1;

    font-size:
        10px;

    font-weight:
        700;

    text-transform:
        uppercase;

    letter-spacing:
        0.45px;

    color:
        #45545c;
}

.popup-row {

    display:
        flex;

    justify-content:
        space-between;

    gap:
        12px;

    margin:
        4px 0;

    line-height:
        1.35;
}

.popup-label {

    font-weight:
        600;

    color:
        #56636a;

    flex-shrink:
        0;
}

.popup-row > *:last-child {

    text-align:
        right;

    color:
        #263238;
}

.badge {

    display:
        inline-block;

    padding:
        3px 7px;

    border-radius:
        4px;

    color:
        white;

    font-size:
        9px;

    font-weight:
        700;

    letter-spacing:
        0.3px;
}

.driver {

    font-size:
        10px;

    margin:
        4px 0;

    padding:
        3px 0;

    color:
        #37474f;
}


/* ============================================================
   MOBILE
   ============================================================ */

@media (max-width: 700px) {

    .header {

        left:
            48px;

        top:
            7px;

        min-width:
            175px;
    }

    .dashboard {

        left:
            48px;

        top:
            57px;

        width:
            185px;
    }

    .pressure-panel {

        display:
            none;
    }

    .legend {

        width:
            155px;

        right:
            7px;

        bottom:
            7px;
    }

    .map-note {

        display:
            none;
    }
}

</style>

</head>


<body>


<!-- ============================================================
     HEADER
     ============================================================ -->

<div class="header">

    <h1>PRAVAH</h1>

    <p>
        Multi-Source Flood Monitoring
    </p>

</div>


<!-- ============================================================
     COMPACT DASHBOARD
     ============================================================ -->

<div class="dashboard">

    <div class="dashboard-title">
        LIVE RISK MONITOR
    </div>

    <div class="dashboard-grid">

        <div class="metric low">

            <div class="metric-number">
                LOW_COUNT
            </div>

            <div class="metric-label">
                LOW
            </div>

        </div>


        <div class="metric watch">

            <div class="metric-number">
                WATCH_COUNT
            </div>

            <div class="metric-label">
                WATCH
            </div>

        </div>


        <div class="metric warning">

            <div class="metric-number">
                WARNING_COUNT
            </div>

            <div class="metric-label">
                WARNING
            </div>

        </div>


        <div class="metric critical">

            <div class="metric-number">
                CRITICAL_COUNT
            </div>

            <div class="metric-label">
                CRITICAL
            </div>

        </div>

    </div>


    <div class="observation-row">

        <span>
            Districts
        </span>

        <strong>
            TOTAL_DISTRICTS
        </strong>

    </div>


    <div class="observation-row">

        <span>
            Rain gauges
        </span>

        <strong>
            RAIN_COUNT
        </strong>

    </div>


    <div class="observation-row">

        <span>
            River stations
        </span>

        <strong>
            RIVER_COUNT
        </strong>

    </div>


    <div class="observation-row">

        <span>
            Rising rivers
        </span>

        <strong>
            RISING_RIVERS
        </strong>

    </div>

</div>


<!-- ============================================================
     PRESSURE PANEL
     ============================================================ -->

<div class="pressure-panel">

    <div class="pressure-title">
        FLOOD PRESSURE INDEX
    </div>

    <div class="pressure-description">

        Experimental multi-source indicator.
        It does not replace the authoritative
        PRAVAH Risk Engine.

    </div>

    <div class="pressure-bar">

        <div
            class="pressure-fill"
            style="width: PRESSURE_WIDTH%;">
        </div>

    </div>

    <div class="pressure-bottom">

        <span>
            Mean
        </span>

        <span>
            PRESSURE_MEAN / 100
        </span>

    </div>

</div>


<!-- ============================================================
     MAP NOTE
     ============================================================ -->

<div class="map-note">

    Risk = PRAVAH Risk Engine
    &nbsp;•&nbsp;
    Glow = Experimental Pressure
    &nbsp;•&nbsp;
    VIIRS = Lagged Observation

</div>


<!-- ============================================================
     LEGEND
     ============================================================ -->

<div class="legend">

    <div class="legend-title">
        MAP LEGEND
    </div>


    <div class="legend-section">
        DISTRICT RISK
    </div>


    <div class="legend-row">

        <div
            class="legend-box"
            style="background:#2e7d32;">
        </div>

        LOW

    </div>


    <div class="legend-row">

        <div
            class="legend-box"
            style="background:#f9a825;">
        </div>

        WATCH

    </div>


    <div class="legend-row">

        <div
            class="legend-box"
            style="background:#ef6c00;">
        </div>

        WARNING

    </div>


    <div class="legend-row">

        <div
            class="legend-box"
            style="background:#c62828;">
        </div>

        CRITICAL

    </div>


    <div class="legend-section">
        HYDROLOGY
    </div>


    <div class="legend-row">

        <div
            class="legend-circle"
            style="background:#1565c0;">
        </div>

        Rain gauge

    </div>


    <div class="legend-row">

        <div
            class="legend-circle"
            style="background:#00838f;">
        </div>

        River station

    </div>


    <div class="legend-row">

        <div
            class="legend-circle"
            style="background:#7b1fa2;">
        </div>

        GeoGLOWS

    </div>


    <div class="legend-section">
        PRESSURE BORDER
    </div>


    <div class="legend-row">

        <div
            class="legend-box"
            style="
                background:white;
                border:3px solid #ef6c00;
            ">
        </div>

        Higher pressure

    </div>

</div>


<!-- ============================================================
     MAP
     ============================================================ -->

<div id="map"></div>


<script
    src="../../src/mapping/vendor/leaflet/leaflet.js">
</script>

<script
    src="../../src/mapping/vendor/leaflet/leaflet-geoman.min.js">
</script>

<script
    src="../../src/mapping/vendor/leaflet/turf.min.js">
</script>


<script>

/* ============================================================
   DATA
   ============================================================ */

const districtData =
    GEOJSON_DATA;

const riverStations =
    RIVER_DATA;

const rainStations =
    RAIN_DATA;


/* ============================================================
   MAP
   ============================================================ */

const map =
    L.map("map", {

        zoomControl:
            true,

        preferCanvas:
            true

    }).setView(

        [28.3949, 84.1240],

        7

    );



/* ============================================================
   BASEMAP
   ============================================================ */

/*
   PRAVAH uses a local-first map.
   No external tile server is required for the core demo.
*/

const baseMap = L.layerGroup();

baseMap.addTo(map);

/* ============================================================
   HELPERS
   ============================================================ */

function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return "N/A";

    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function fmt(
    value,
    decimals = 2
) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "N/A";
    }

    const number =
        Number(value);

    if (
        Number.isNaN(number)
    ) {

        return escapeHtml(value);
    }

    return number.toFixed(
        decimals
    );
}


/* ============================================================
   COLORS
   ============================================================ */

function riskColor(level) {

    switch (
        String(level)
            .toUpperCase()
    ) {

        case "LOW":
            return "#2e7d32";

        case "WATCH":
            return "#f9a825";

        case "WARNING":
            return "#ef6c00";

        case "CRITICAL":
            return "#c62828";

        default:
            return "#9e9e9e";
    }
}


function pressureColor(score) {

    if (
        score === null ||
        score === undefined
    ) {

        return "#9e9e9e";
    }

    score =
        Number(score);

    if (score >= 75)
        return "#c62828";

    if (score >= 55)
        return "#ef6c00";

    if (score >= 30)
        return "#f9a825";

    return "#2e7d32";
}


/* ============================================================
   PRESSURE BORDER WIDTH
   ============================================================ */

function pressureWeight(score) {

    if (
        score === null ||
        score === undefined
    ) {

        return 1;
    }

    if (score >= 75)
        return 5;

    if (score >= 55)
        return 4;

    if (score >= 30)
        return 3;

    return 1.5;
}


/* ============================================================
   3D DISTRICT SHADOW
   ============================================================ */

function create3DShadow(
    feature,
    layer
) {

    const risk =
        feature.properties.pravah_risk;

    const color =
        riskColor(risk);

    const shadow =
        L.geoJSON(

            feature,

            {

                style: {

                    fillColor:
                        "#263238",

                    color:
                        "#263238",

                    weight:
                        1,

                    opacity:
                        0.45,

                    fillOpacity:
                        0.25

                }

            }

        );


    /*
       Slight visual offset is achieved by placing
       the shadow behind the actual polygon.
    */

    shadow.eachLayer(
        function(shadowLayer) {

            shadowLayer.setStyle({

                fillColor:
                    "#263238",

                color:
                    "#263238",

                fillOpacity:
                    0.18,

                weight:
                    3

            });

        }
    );

    return shadow;
}


/* ============================================================
   RISK POPUP
   ============================================================ */

function createRiskPopup(
    p
) {

    const district =
        escapeHtml(
            p.pravah_district_name ||
            p.adm2_name ||
            "Unknown"
        );


    const risk =
        p.pravah_risk ||
        "NO DATA";


    const riskScore =
        fmt(
            p.pravah_score
        );


    const pressure =
        p.pressure_index;


    const pressureLevel =
        p.pressure_level ||
        "NO DATA";


    const confidence =
        escapeHtml(
            p.pravah_confidence ||
            "LOW"
        );


    const rainfallEvidence =
        escapeHtml(
            p.evidence_rainfall ||
            "NO_DATA"
        );


    const runoffEvidence =
        escapeHtml(
            p.evidence_runoff ||
            "NO_DATA"
        );


    const riverEvidence =
        escapeHtml(
            p.evidence_river ||
            "NO_DATA"
        );


    const dominant =
        escapeHtml(
            p.evidence_dominant_signal ||
            "NONE"
        );


    const agreement =
        escapeHtml(
            p.evidence_agreement ||
            "UNKNOWN"
        );


    const future =
        escapeHtml(
            p.future_outlook ||
            "UNKNOWN"
        );


    const drivers =
        Array.isArray(
            p.pravah_drivers
        )
        ? p.pravah_drivers
        : [];


    let driversHtml =
        "<div class='driver'>• No recorded driver</div>";


    if (
        drivers.length
    ) {

        driversHtml =
            drivers
            .map(
                function(driver) {

                    return `
                        <div class="driver">
                            • ${escapeHtml(driver)}
                        </div>
                    `;

                }
            )
            .join("");
    }


    const pressureBg =
        pressureColor(
            pressure
        );


    return `

        <div class="popup">

            <div class="popup-title">
                ${district}
            </div>


            <div class="popup-subtitle">

                District ID:
                ${escapeHtml(
                    p.pravah_district_id ||
                    "N/A"
                )}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    PRAVAH Risk:
                </span>

                <span
                    class="badge"
                    style="
                        background:${riskColor(risk)};
                    "
                >
                    ${escapeHtml(risk)}
                </span>

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Risk Score:
                </span>

                ${riskScore}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Confidence:
                </span>

                ${confidence}

                (${fmt(
                    p.pravah_confidence_score
                )})

            </div>


            <div class="popup-section">
                Flood Pressure
            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Index:
                </span>

                <span
                    class="badge"
                    style="
                        background:${pressureBg};
                    "
                >
                    ${fmt(
                        pressure,
                        1
                    )}
                </span>

                ${escapeHtml(
                    pressureLevel
                )}

            </div>


            <div class="popup-section">
                Rainfall
            </div>


            <div class="popup-row">
                <span class="popup-label">
                    BIPAD 1h:
                </span>

                ${fmt(
                    p.rain_1h_mm
                )} mm
            </div>


            <div class="popup-row">
                <span class="popup-label">
                    NASA 6h:
                </span>

                ${fmt(
                    p.rain_6h_mm
                )} mm
            </div>


            <div class="popup-row">
                <span class="popup-label">
                    NASA 24h:
                </span>

                ${fmt(
                    p.rain_24h_mm
                )} mm
            </div>


            <div class="popup-row">
                <span class="popup-label">
                    Persistence:
                </span>

                ${fmt(
                    p.rainfall_persistence
                )}
            </div>


            <div class="popup-row">
                <span class="popup-label">
                    Antecedent:
                </span>

                ${fmt(
                    p.antecedent_rainfall
                )} mm
            </div>


            <div class="popup-section">
                SCS-CN Runoff
            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Current 6h:
                </span>

                ${fmt(
                    p.scs_cn_runoff_6h_mm
                )} mm

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Forecast 24h:
                </span>

                ${fmt(
                    p.forecast_runoff_24h
                )} mm

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Forecast 48h:
                </span>

                ${fmt(
                    p.forecast_runoff_48h
                )} mm

            </div>


            <div class="popup-section">
                River
            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Status:
                </span>

                ${escapeHtml(
                    p.river_status ||
                    "UNKNOWN"
                )}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Max level:
                </span>

                ${fmt(
                    p.river_max_water_level_m
                )} m

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Warning utilization:
                </span>

                ${fmt(
                    p.river_warning_utilization
                    != null
                    ?
                    p.river_warning_utilization * 100
                    :
                    null
                )}%

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Rising:
                </span>

                ${p.river_rising_stations || 0}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Warning:
                </span>

                ${p.river_warning_stations || 0}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Danger:
                </span>

                ${p.river_danger_stations || 0}

            </div>


            <div class="popup-section">
                GeoGLOWS Forecast
            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Stations:
                </span>

                ${p.geoglows_station_count || 0}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Current flow:
                </span>

                ${fmt(
                    p.geoglows_current_flow
                )} m³/s

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Forecast peak:
                </span>

                ${fmt(
                    p.geoglows_peak_flow
                )} m³/s

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Forecast rise:
                </span>

                ${fmt(
                    p.geoglows_forecast_rise
                )} m³/s

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Hours to peak:
                </span>

                ${fmt(
                    p.geoglows_hours_to_peak
                )}

            </div>


            <div class="popup-section">
                Satellite Evidence
            </div>


            <div class="popup-row">

                <span class="popup-label">
                    VIIRS:
                </span>

                ${p.eo_available
                    ? "AVAILABLE"
                    : "NOT AVAILABLE"}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Observation:
                </span>

                ${escapeHtml(
                    p.eo_observation_date ||
                    "N/A"
                )}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Flood pixels:
                </span>

                ${p.eo_flood_pixels || "N/A"}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Flood ratio:
                </span>

                ${fmt(
                    p.eo_flood_ratio_pct
                )}%

            </div>


            <div class="popup-section">
                Evidence Fusion
            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Rainfall:
                </span>

                ${rainfallEvidence}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Runoff:
                </span>

                ${runoffEvidence}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    River:
                </span>

                ${riverEvidence}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Dominant:
                </span>

                ${dominant}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Agreement:
                </span>

                ${agreement}

            </div>


            <div class="popup-row">

                <span class="popup-label">
                    Future outlook:
                </span>

                ${future}

            </div>


            <div class="popup-section">
                Why?
            </div>


            ${driversHtml}

        </div>

    `;
}


/* ============================================================
   OFFICIAL RISK LAYER
   ============================================================ */

const riskLayer =
    L.geoJSON(

        districtData,

        {

            style:
                function(feature) {

                    const p =
                        feature.properties ||
                        {};

                    const risk =
                        p.pravah_risk ||
                        "NO DATA";

                    return {

                        fillColor:
                            riskColor(risk),

                        color:
                            "#37474f",

                        weight:
                            1,

                        opacity:
                            1,

                        fillOpacity:
                            0.55

                    };

                },


            onEachFeature:
                function(
                    feature,
                    layer
                ) {

                    layer.bindPopup(
                        createRiskPopup(
                            feature.properties
                        ),
                        {
                            maxWidth:
                                340
                        }
                    );


                    layer.on({

                        mouseover:
                            function(event) {

                                const target =
                                    event.target;

                                target.setStyle({

                                    weight:
                                        3,

                                    color:
                                        "#111",

                                    fillOpacity:
                                        0.72

                                });

                                target.bringToFront();

                            },


                        mouseout:
                            function(event) {

                                riskLayer.resetStyle(
                                    event.target
                                );

                            }

                    });

                }

        }

    );


riskLayer.addTo(
    map
);


/* ============================================================
   3D DISTRICT SHADOW LAYER
   ============================================================ */

const districtShadowLayer =
    L.layerGroup();


districtData.features.forEach(
    function(feature) {

        try {

            const shadow =
                create3DShadow(
                    feature
                );

            shadow.addTo(
                districtShadowLayer
            );

        } catch(error) {

            console.log(
                "Shadow error:",
                error
            );

        }

    }
);


/*
   Keep shadow behind official district layer.
*/

districtShadowLayer.addTo(
    map
);


/* ============================================================
   PRESSURE BORDER / GLOW
   ============================================================ */

const pressureGlowLayer =
    L.layerGroup();


districtData.features.forEach(
    function(feature) {

        const p =
            feature.properties ||
            {};

        const score =
            p.pressure_index;

        if (
            score === null ||
            score === undefined
        ) {

            return;
        }


        const color =
            pressureColor(
                score
            );


        /*
           Outer glow.
        */

        const glow =
            L.geoJSON(

                feature,

                {

                    style: {

                        color:
                            color,

                        weight:
                            pressureWeight(score) + 5,

                        opacity:
                            0.14,

                        fillOpacity:
                            0

                    }

                }

            );


        glow.addTo(
            pressureGlowLayer
        );


        /*
           Sharp pressure border.
        */

        const border =
            L.geoJSON(

                feature,

                {

                    style: {

                        color:
                            color,

                        weight:
                            pressureWeight(score),

                        opacity:
                            0.88,

                        fillOpacity:
                            0

                    }

                }

            );


        border.bindPopup(
            createRiskPopup(
                p
            )
        );


        border.addTo(
            pressureGlowLayer
        );

    }
);


pressureGlowLayer.addTo(
    map
);


/* ============================================================
   RIVER CORRIDOR LAYER
   ============================================================ */

const riverCorridorLayer =
    L.layerGroup();


const riverFlowLayer =
    L.layerGroup();


riverStations.forEach(
    function(station) {

        if (
            station.lat === null ||
            station.lon === null
        ) {

            return;
        }


        let color =
            "#00838f";


        const status =
            String(
                station.status ||
                ""
            ).toUpperCase();


        const trend =
            String(
                station.trend ||
                ""
            ).toUpperCase();


        if (
            status.includes(
                "DANGER"
            )
        ) {

            color =
                "#c62828";

        } else if (
            status.includes(
                "WARNING"
            )
        ) {

            color =
                "#ef6c00";

        } else if (
            trend.includes(
                "RISING"
            )
        ) {

            color =
                "#f9a825";
        }


        /*
           Wide corridor.
        */

        const corridor =
            L.circle(

                [
                    station.lat,
                    station.lon
                ],

                {

                    radius:
                        1200,

                    stroke:
                        true,

                    color:
                        color,

                    weight:
                        3,

                    opacity:
                        0.30,

                    fillColor:
                        color,

                    fillOpacity:
                        0.07

                }

            );


        corridor.bindPopup(`

            <div class="popup">

                <div class="popup-title">
                    River Corridor
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Station:
                    </span>

                    ${escapeHtml(
                        station.station
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        District:
                    </span>

                    ${escapeHtml(
                        station.district
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Status:
                    </span>

                    ${escapeHtml(
                        station.status
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Trend:
                    </span>

                    ${escapeHtml(
                        station.trend
                    )}

                </div>

            </div>

        `);


        corridor.addTo(
            riverCorridorLayer
        );


        /*
           Inner flow line.
           This gives the visual impression
           of a flowing river corridor.
        */

        const flowLine =
            L.circleMarker(

                [
                    station.lat,
                    station.lon
                ],

                {

                    radius:
                        3,

                    color:
                        "#ffffff",

                    weight:
                        1,

                    fillColor:
                        color,

                    fillOpacity:
                        1

                }

            );


        flowLine.bindTooltip(
            escapeHtml(
                station.station
            ),
            {
                direction:
                    "top",

                offset:
                    [0, -5]
            }
        );


        flowLine.addTo(
            riverFlowLayer
        );

    }
);


riverCorridorLayer.addTo(
    map
);


/* ============================================================
   RIVER STATION MARKERS
   ============================================================ */

const riverStationLayer =
    L.layerGroup();


riverStations.forEach(
    function(station) {

        if (
            station.lat === null ||
            station.lon === null
        ) {

            return;
        }


        let color =
            "#00838f";


        const status =
            String(
                station.status ||
                ""
            ).toUpperCase();


        const trend =
            String(
                station.trend ||
                ""
            ).toUpperCase();


        if (
            status.includes(
                "DANGER"
            )
        ) {

            color =
                "#c62828";

        } else if (
            status.includes(
                "WARNING"
            )
        ) {

            color =
                "#ef6c00";

        } else if (
            trend.includes(
                "RISING"
            )
        ) {

            color =
                "#f9a825";

        }


        const marker =
            L.circleMarker(

                [
                    station.lat,
                    station.lon
                ],

                {

                    radius:
                        6,

                    color:
                        "#ffffff",

                    weight:
                        2,

                    fillColor:
                        color,

                    fillOpacity:
                        0.95

                }

            );


        marker.bindPopup(`

            <div class="popup">

                <div class="popup-title">
                    River Station
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Station:
                    </span>

                    ${escapeHtml(
                        station.station
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        District:
                    </span>

                    ${escapeHtml(
                        station.district
                    )}

                </div>

                <div class="popup-section">
                    Observation
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Water level:
                    </span>

                    ${fmt(
                        station.water_level_m
                    )} m

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Warning:
                    </span>

                    ${fmt(
                        station.warning_level_m
                    )} m

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Danger:
                    </span>

                    ${fmt(
                        station.danger_level_m
                    )} m

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Status:
                    </span>

                    ${escapeHtml(
                        station.status
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Trend:
                    </span>

                    ${escapeHtml(
                        station.trend
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Observed:
                    </span>

                    ${escapeHtml(
                        station.observed_at
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Source:
                    </span>

                    ${escapeHtml(
                        station.source
                    )}

                </div>

            </div>

        `);


        marker.addTo(
            riverStationLayer
        );

    }
);


riverStationLayer.addTo(
    map
);


/* ============================================================
   RAINFALL LAYER
   ============================================================ */

const rainLayer =
    L.layerGroup();


function rainColor(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return "#1565c0";
    }

    value =
        Number(value);

    if (value >= 20)
        return "#c62828";

    if (value >= 10)
        return "#ef6c00";

    if (value >= 5)
        return "#f9a825";

    return "#1565c0";
}


rainStations.forEach(
    function(station) {

        if (
            station.lat === null ||
            station.lon === null
        ) {

            return;
        }


        const color =
            rainColor(
                station.rain_1h_mm
            );


        /*
           Halo.
        */

        const halo =
            L.circle(

                [
                    station.lat,
                    station.lon
                ],

                {

                    radius:
                        1800,

                    stroke:
                        false,

                    fillColor:
                        color,

                    fillOpacity:
                        0.10

                }

            );


        halo.addTo(
            rainLayer
        );


        /*
           Station.
        */

        const marker =
            L.circleMarker(

                [
                    station.lat,
                    station.lon
                ],

                {

                    radius:
                        5,

                    color:
                        "#ffffff",

                    weight:
                        2,

                    fillColor:
                        color,

                    fillOpacity:
                        0.95

                }

            );


        marker.bindPopup(`

            <div class="popup">

                <div class="popup-title">
                    Rain Gauge
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Station:
                    </span>

                    ${escapeHtml(
                        station.station
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        District:
                    </span>

                    ${escapeHtml(
                        station.district
                    )}

                </div>

                <div class="popup-section">
                    Rainfall Observation
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        1-hour rainfall:
                    </span>

                    ${fmt(
                        station.rain_1h_mm
                    )} mm

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Observed:
                    </span>

                    ${escapeHtml(
                        station.observed_at
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Source:
                    </span>

                    ${escapeHtml(
                        station.source
                    )}

                </div>

            </div>

        `);


        marker.addTo(
            rainLayer
        );

    }
);


/*
   Only add if stations actually exist.
*/

if (
    rainStations.length > 0
) {

    rainLayer.addTo(
        map
    );

}


/* ============================================================
   GEOGLOWS LAYER
   ============================================================ */

const geoglowsLayer =
    L.layerGroup();


geoglows_stations.forEach(
    function(station) {

        /*
           GeoGLOWS stations are embedded in Python
           only through the district data if desired.
           This section is populated using coordinates
           directly from the station file.
        */

    }
);


/*
   Build GeoGLOWS markers directly from the embedded
   district source through a compact generated object.
*/

const geoglowsStations =
    GEOGLOWS_DATA;


geoglowsStations.forEach(
    function(station) {

        if (
            station.latitude === null ||
            station.longitude === null ||
            station.latitude === undefined ||
            station.longitude === undefined
        ) {

            return;
        }


        const geo =
            station.geoglows ||
            {};


        const currentFlow =
            geo.current_flow_m3s;


        const peakFlow =
            geo.forecast_peak_flow_m3s;


        const rise =
            geo.forecast_rise_m3s;


        let markerColor =
            "#7b1fa2";


        if (
            rise !== null &&
            rise !== undefined &&
            currentFlow !== null &&
            currentFlow !== undefined &&
            Number(currentFlow) > 0
        ) {

            const ratio =
                Number(rise) /
                Number(currentFlow);


            if (ratio >= 1)
                markerColor = "#c62828";

            else if (ratio >= 0.5)
                markerColor = "#ef6c00";

            else if (ratio >= 0.2)
                markerColor = "#f9a825";

        }


        const marker =
            L.circleMarker(

                [
                    Number(
                        station.latitude
                    ),

                    Number(
                        station.longitude
                    )
                ],

                {

                    radius:
                        5,

                    color:
                        "#ffffff",

                    weight:
                        2,

                    fillColor:
                        markerColor,

                    fillOpacity:
                        0.92

                }

            );


        marker.bindPopup(`

            <div class="popup">

                <div class="popup-title">
                    GeoGLOWS Forecast
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Station:
                    </span>

                    ${escapeHtml(
                        station.station_name
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        District ID:
                    </span>

                    ${escapeHtml(
                        station.district_id
                    )}

                </div>

                <div class="popup-section">
                    Forecast
                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Current flow:
                    </span>

                    ${fmt(
                        currentFlow
                    )} m³/s

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Peak flow:
                    </span>

                    ${fmt(
                        peakFlow
                    )} m³/s

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Forecast rise:
                    </span>

                    ${fmt(
                        rise
                    )} m³/s

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Hours to peak:
                    </span>

                    ${fmt(
                        geo.hours_to_peak
                    )}

                </div>

                <div class="popup-row">

                    <span class="popup-label">
                        Peak time:
                    </span>

                    ${escapeHtml(
                        geo.peak_time ||
                        "N/A"
                    )}

                </div>

            </div>

        `);


        marker.addTo(
            geoglowsLayer
        );

    }
);


/* ============================================================
   DISTRICT LABELS
   ============================================================ */

const districtLabels =
    L.layerGroup();


districtData.features.forEach(
    function(feature) {

        const p =
            feature.properties ||
            {};

        const name =
            p.pravah_district_name ||
            p.adm2_name;


        if (!name)
            return;


        try {

            const temp =
                L.geoJSON(
                    feature
                );


            const center =
                temp
                .getBounds()
                .getCenter();


            L.marker(

                center,

                {

                    icon:
                        L.divIcon({

                            className:
                                "district-label",

                            html:
                                `
                                <div style="
                                    font-size:8px;
                                    font-weight:700;
                                    color:#263238;
                                    text-shadow:
                                        1px 1px 2px white,
                                        -1px -1px 2px white,
                                        0 0 2px white;
                                    white-space:nowrap;
                                ">
                                    ${escapeHtml(name)}
                                </div>
                                `,

                            iconSize:
                                [90, 12],

                            iconAnchor:
                                [45, 6]

                        }),

                    interactive:
                        false

                }

            ).addTo(
                districtLabels
            );

        } catch(error) {

            console.log(
                "Label error:",
                error
            );

        }

    }
);


districtLabels.addTo(
    map
);


/* ============================================================
   LAYER CONTROL
   ============================================================ */

const overlays = {

    "PRAVAH Risk":
        riskLayer,

    "Flood Pressure Border":
        pressureGlowLayer,

    "River Corridors":
        riverCorridorLayer,

    "River Stations":
        riverStationLayer,

    "Rainfall Gauges":
        rainLayer,

    "GeoGLOWS Forecast":
        geoglowsLayer,

    "District Labels":
        districtLabels

};


const baseMaps = {

    "OpenStreetMap":
        osm,

    "Terrain":
        terrain

};


L.control.layers(

    baseMaps,

    overlays,

    {

        collapsed:
            true,

        position:
            "topright"

    }

).addTo(
    map
);


/* ============================================================
   LAYER Z-ORDER
   ============================================================ */

map.on(
    "overlayadd",
    function(event) {

        if (
            event.name ===
            "PRAVAH Risk"
        ) {

            riskLayer.bringToFront();

        }

        if (
            event.name ===
            "Flood Pressure Border"
        ) {

            pressureGlowLayer.bringToFront();

        }

        if (
            event.name ===
            "River Corridors"
        ) {

            riverCorridorLayer.bringToFront();

        }

        if (
            event.name ===
            "River Stations"
        ) {

            riverStationLayer.bringToFront();

        }

    }
);


/* ============================================================
   DEFAULT MAP VIEW
   ============================================================ */

try {

    map.fitBounds(
        riskLayer.getBounds(),
        {

            padding:
                [20, 20]

        }
    );

} catch(error) {

    console.log(
        "Fit bounds error:",
        error
    );

}


/* ============================================================
   INITIAL Z-ORDER
   ============================================================ */

districtShadowLayer.bringToBack();

riskLayer.bringToFront();

pressureGlowLayer.bringToFront();

riverCorridorLayer.bringToFront();

riverStationLayer.bringToFront();

if (
    rainLayer
) {

    rainLayer.bringToFront();

}

</script>

</body>

</html>
"""


# ============================================================
# GEOGLOWS JAVASCRIPT DATA
# ============================================================

geoglows_for_map = []

for station in geoglows_stations:

    if not isinstance(
        station,
        dict
    ):
        continue

    lat = safe_float(
        station.get(
            "latitude"
        )
    )

    lon = safe_float(
        station.get(
            "longitude"
        )
    )

    if (
        lat is None
        or lon is None
    ):
        continue

    geoglows_for_map.append({

        "station_name":
            station.get(
                "station_name",
                "GeoGLOWS Station"
            ),

        "district_id":
            station.get(
                "district_id"
            ),

        "latitude":
            lat,

        "longitude":
            lon,

        "geoglows":
            station.get(
                "geoglows",
                {}
            )

    })


geoglows_js = js_json(
    geoglows_for_map
)


# ============================================================
# INSERT DATA
# ============================================================

html_content = html_content.replace(
    "GEOJSON_DATA",
    geojson_js
)

html_content = html_content.replace(
    "RIVER_DATA",
    river_stations_js
)

html_content = html_content.replace(
    "RAIN_DATA",
    rain_stations_js
)

html_content = html_content.replace(
    "GEOGLOWS_DATA",
    geoglows_js
)


# ============================================================
# DASHBOARD VALUES
# ============================================================

html_content = html_content.replace(
    "TOTAL_DISTRICTS",
    str(len(features))
)

html_content = html_content.replace(
    "LOW_COUNT",
    str(risk_counts["LOW"])
)

html_content = html_content.replace(
    "WATCH_COUNT",
    str(risk_counts["WATCH"])
)

html_content = html_content.replace(
    "WARNING_COUNT",
    str(risk_counts["WARNING"])
)

html_content = html_content.replace(
    "CRITICAL_COUNT",
    str(risk_counts["CRITICAL"])
)

html_content = html_content.replace(
    "RIVER_COUNT",
    str(len(river_stations))
)

html_content = html_content.replace(
    "RAIN_COUNT",
    str(len(rain_stations))
)

html_content = html_content.replace(
    "RISING_RIVERS",
    str(rising_rivers)
)

html_content = html_content.replace(
    "PRESSURE_MEAN",
    str(pressure_mean)
)

html_content = html_content.replace(
    "PRESSURE_WIDTH",
    str(
        max(
            0,
            min(
                100,
                pressure_mean
            )
        )
    )
)


# ============================================================
# SAVE HTML
# ============================================================

Path(
    OUTPUT_FILE
).write_text(
    html_content,
    encoding="utf-8"
)


# ============================================================
# FINAL REPORT
# ============================================================

print()
print("=" * 100)
print("PRAVAH HAZARD MAP V4 COMPLETE")
print("=" * 100)

print()
print("RISK DISTRIBUTION")

print(
    f"  LOW:       {risk_counts['LOW']}"
)

print(
    f"  WATCH:     {risk_counts['WATCH']}"
)

print(
    f"  WARNING:   {risk_counts['WARNING']}"
)

print(
    f"  CRITICAL:  {risk_counts['CRITICAL']}"
)

print(
    f"  NO DATA:   {risk_counts['NO DATA']}"
)

print()
print("OBSERVATIONS")

print(
    f"  Rain gauges:       {len(rain_stations)}"
)

print(
    f"  River stations:    {len(river_stations)}"
)

print(
    f"  River mapped:      {river_mapped}"
)

print(
    f"  GeoGLOWS stations: {len(geoglows_for_map)}"
)

print(
    f"  Rising rivers:     {rising_rivers}"
)

print()
print("PRESSURE MODEL")

print(
    f"  Modelled districts: {len(pressure_values)}"
)

print(
    f"  Mean index:         {pressure_mean}"
)

print(
    f"  Maximum index:      {pressure_max}"
)

print()
print("OUTPUT")

print(
    f"  {OUTPUT_FILE}"
)

print()
print("=" * 100)
print("OPEN prava_hazard_map.html IN YOUR BROWSER")
print("=" * 100)