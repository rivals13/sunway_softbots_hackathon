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

<title>PRAVAH Intelligence</title>

<link
    rel="stylesheet"
    href="../../src/mapping/vendor/leaflet/leaflet.css"
/>

<style>

/* ============================================================
   PRAVAH INTELLIGENCE UI
   GIS FIRST / AGENT SECOND / DECORATION LAST
   ============================================================ */

:root {
    --bg: #eef1f2;
    --panel: #ffffff;
    --panel-soft: #f6f8f8;
    --border: #d5dcdf;
    --text: #263238;
    --muted: #69777d;
    --dark: #172126;
    --accent: #176b73;
    --accent-soft: #e4f0f1;

    --low: #2e7d32;
    --watch: #ef9f1c;
    --warning: #d85b32;
    --critical: #b83232;

    --shadow:
        0 3px 14px rgba(26, 39, 44, 0.12);
}

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    padding: 0;

    width: 100%;
    height: 100%;

    overflow: hidden;

    font-family:
        Inter,
        Arial,
        Helvetica,
        sans-serif;

    background: var(--bg);
    color: var(--text);
}

button,
input {
    font: inherit;
}

button {
    cursor: pointer;
}

#map {
    position: absolute;

    inset: 0;

    background:
        linear-gradient(
            135deg,
            #e7ecee,
            #dce4e6
        );
}


/* ============================================================
   TOP BAR
   ============================================================ */

.topbar {
    position: absolute;

    top: 0;
    left: 0;
    right: 0;

    height: 58px;

    z-index: 3000;

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding:
        0 18px;

    background:
        rgba(255,255,255,0.97);

    border-bottom:
        1px solid var(--border);

    box-shadow:
        0 2px 8px rgba(0,0,0,0.08);
}

.brand {
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-mark {
    width: 34px;
    height: 34px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 7px;

    background:
        var(--dark);

    color: white;

    font-size: 13px;
    font-weight: 800;

    letter-spacing: 1px;
}

.brand-name {
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 1.4px;
}

.brand-sub {
    margin-top: 1px;

    font-size: 9px;
    color: var(--muted);

    letter-spacing: 0.5px;
}

.system-status {
    display: flex;
    align-items: center;
    gap: 14px;

    font-size: 10px;
    color: var(--muted);
}

.live-status {
    display: flex;
    align-items: center;
    gap: 6px;

    font-weight: 700;
    color: #3d5a5e;
}

.live-dot {
    width: 7px;
    height: 7px;

    border-radius: 50%;

    background: #3f8a52;

    box-shadow:
        0 0 0 3px rgba(63,138,82,0.12);
}


/* ============================================================
   LEFT GIS CONTROL
   ============================================================ */

.left-panel {
    position: absolute;

    z-index: 2500;

    top: 72px;
    left: 14px;

    width: 205px;

    max-height:
        calc(100vh - 88px);

    overflow-y: auto;

    background:
        rgba(255,255,255,0.97);

    border:
        1px solid var(--border);

    border-radius: 8px;

    box-shadow:
        var(--shadow);
}

.panel-header {
    padding: 12px 13px 9px;

    border-bottom:
        1px solid var(--border);
}

.panel-kicker {
    font-size: 8px;

    text-transform: uppercase;

    letter-spacing: 1.1px;

    color: var(--muted);

    font-weight: 800;
}

.panel-title {
    margin-top: 3px;

    font-size: 13px;

    font-weight: 800;
}

.layer-group {
    padding: 9px 12px;
}

.layer-title {
    margin-bottom: 7px;

    font-size: 9px;

    text-transform: uppercase;

    letter-spacing: 0.8px;

    color: var(--muted);

    font-weight: 800;
}

.layer-row {
    display: flex;

    align-items: center;

    gap: 8px;

    min-height: 30px;

    font-size: 10px;

    color: #425158;
}

.layer-row input {
    accent-color: var(--accent);
}

.layer-row label {
    flex: 1;

    cursor: pointer;
}

.layer-note {
    font-size: 8px;
    color: #8a969b;

    margin-top: 5px;
    line-height: 1.4;
}

.legend-row {
    display: flex;
    align-items: center;

    gap: 8px;

    min-height: 24px;

    font-size: 10px;
}

.legend-swatch {
    width: 13px;
    height: 13px;

    border-radius: 3px;

    border: 1px solid rgba(0,0,0,0.14);
}


/* ============================================================
   RIGHT PRAVAH INTELLIGENCE PANEL
   ============================================================ */

.intelligence {
    position: absolute;

    z-index: 2500;

    top: 72px;
    right: 14px;
    bottom: 14px;

    width: 365px;

    display: flex;
    flex-direction: column;

    background:
        rgba(255,255,255,0.98);

    border:
        1px solid var(--border);

    border-radius: 9px;

    box-shadow:
        0 5px 22px rgba(26,39,44,0.16);

    overflow: hidden;
}

.intelligence-head {
    padding: 13px 15px;

    background:
        linear-gradient(
            180deg,
            #ffffff,
            #f7f9f9
        );

    border-bottom:
        1px solid var(--border);
}

.intelligence-label {
    font-size: 8px;

    text-transform: uppercase;

    letter-spacing: 1.2px;

    color: var(--accent);

    font-weight: 900;
}

.intelligence-title-row {
    display: flex;

    align-items: center;

    justify-content: space-between;

    gap: 10px;

    margin-top: 4px;
}

.intelligence-title {
    font-size: 18px;

    font-weight: 800;

    color: var(--dark);
}

.risk-badge {
    padding: 5px 9px;

    border-radius: 4px;

    color: white;

    font-size: 9px;

    font-weight: 800;

    letter-spacing: 0.5px;
}

.intelligence-subtitle {
    margin-top: 3px;

    font-size: 9px;

    color: var(--muted);
}

.intelligence-body {
    flex: 1;

    overflow-y: auto;

    padding: 12px 14px;
}


/* ============================================================
   EMPTY STATE
   ============================================================ */

.agent-empty {
    padding: 26px 12px;

    text-align: center;

    color: var(--muted);
}

.agent-orb {
    width: 46px;
    height: 46px;

    margin:
        4px auto 12px;

    border-radius: 50%;

    border:
        1px solid #b9cdd0;

    background:
        var(--accent-soft);

    display: flex;
    align-items: center;
    justify-content: center;

    color: var(--accent);

    font-weight: 900;
    font-size: 11px;
}

.agent-empty h3 {
    margin: 0 0 6px;

    font-size: 13px;

    color: var(--dark);
}

.agent-empty p {
    margin: 0 auto;

    max-width: 250px;

    font-size: 10px;

    line-height: 1.55;
}


/* ============================================================
   INTELLIGENCE CARDS
   ============================================================ */

.agent-section {
    margin-bottom: 13px;
}

.agent-section-title {
    margin-bottom: 7px;

    display: flex;

    align-items: center;

    gap: 6px;

    font-size: 9px;

    font-weight: 900;

    text-transform: uppercase;

    letter-spacing: 0.8px;

    color: #536168;
}

.agent-section-title::before {
    content: "";

    width: 3px;
    height: 12px;

    border-radius: 2px;

    background: var(--accent);
}

.reasoning-card {
    padding: 10px 11px;

    background:
        #f5f8f8;

    border:
        1px solid #dce4e5;

    border-radius: 6px;

    font-size: 10px;

    line-height: 1.55;
}

.reasoning-card strong {
    color: var(--dark);
}

.evidence-grid {
    display: grid;

    grid-template-columns:
        1fr 1fr;

    gap: 6px;
}

.evidence-card {
    padding: 8px;

    background:
        #f8fafb;

    border:
        1px solid #e0e5e7;

    border-radius: 5px;
}

.evidence-label {
    font-size: 8px;

    text-transform: uppercase;

    color: #78858a;

    font-weight: 800;

    letter-spacing: 0.4px;
}

.evidence-value {
    margin-top: 4px;

    font-size: 11px;

    font-weight: 700;

    color: var(--dark);
}

.evidence-small {
    margin-top: 2px;

    font-size: 8px;

    color: var(--muted);
}


/* ============================================================
   DRIVER ROWS
   ============================================================ */

.driver-row {
    display: flex;

    gap: 8px;

    padding: 7px 0;

    border-bottom:
        1px solid #edf0f1;

    font-size: 9px;

    line-height: 1.45;
}

.driver-icon {
    width: 18px;
    height: 18px;

    flex-shrink: 0;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 4px;

    background:
        var(--accent-soft);

    color:
        var(--accent);

    font-size: 8px;

    font-weight: 900;
}


/* ============================================================
   ML / SHAP
   ============================================================ */

.ml-box {
    padding: 10px;

    border:
        1px solid #d8e2e3;

    background:
        #f7faf9;

    border-radius: 6px;
}

.ml-header {
    display: flex;

    justify-content: space-between;

    align-items: center;
}

.ml-name {
    font-size: 10px;
    font-weight: 800;
}

.ml-tag {
    font-size: 7px;

    text-transform: uppercase;

    padding: 3px 5px;

    border-radius: 3px;

    background: #e6eef0;

    color: #52676c;

    font-weight: 800;
}

.ml-description {
    margin-top: 6px;

    font-size: 8px;

    line-height: 1.45;

    color: var(--muted);
}

.shap-row {
    margin-top: 8px;
}

.shap-label-row {
    display: flex;

    justify-content: space-between;

    font-size: 8px;

    color: #526067;
}

.shap-track {
    margin-top: 3px;

    height: 5px;

    background: #e2e7e8;

    border-radius: 4px;

    overflow: hidden;
}

.shap-fill {
    height: 100%;

    background:
        #477d83;

    border-radius: 4px;
}


/* ============================================================
   AGENT CHAT
   ============================================================ */

.agent-chat {
    border-top:
        1px solid var(--border);

    padding: 10px;

    background:
        #fafbfb;
}

.chat-status {
    display: flex;

    align-items: center;

    gap: 6px;

    margin-bottom: 7px;

    font-size: 8px;

    color: var(--muted);

    text-transform: uppercase;

    letter-spacing: 0.6px;

    font-weight: 800;
}

.chat-status-dot {
    width: 6px;
    height: 6px;

    border-radius: 50%;

    background: var(--accent);
}

.chat-row {
    display: flex;

    gap: 6px;
}

.chat-input {
    flex: 1;

    min-width: 0;

    height: 34px;

    border:
        1px solid #ccd5d8;

    border-radius: 5px;

    padding:
        0 9px;

    outline: none;

    background: white;

    font-size: 10px;
}

.chat-input:focus {
    border-color:
        #7aa8ac;

    box-shadow:
        0 0 0 2px rgba(23,107,115,0.08);
}

.chat-button {
    width: 34px;

    border: 0;

    border-radius: 5px;

    background:
        var(--dark);

    color: white;

    font-size: 10px;

    font-weight: 800;
}

.chat-suggestions {
    display: flex;

    flex-wrap: wrap;

    gap: 4px;

    margin-top: 7px;
}

.chat-suggestion {
    border:
        1px solid #d5dddf;

    background:
        white;

    color:
        #526168;

    border-radius: 4px;

    padding:
        5px 7px;

    font-size: 8px;
}

.chat-message {
    margin-bottom: 7px;

    padding: 7px 8px;

    border-radius: 5px;

    font-size: 9px;

    line-height: 1.5;
}

.chat-user {
    background:
        #edf3f4;

    color:
        #40565b;
}

.chat-agent {
    background:
        #f4f7f7;

    border-left:
        3px solid var(--accent);

    color:
        #33464b;
}


/* ============================================================
   MAP SELECTION
   ============================================================ */

.district-selected {
    filter:
        drop-shadow(
            0 0 5px
            rgba(23,107,115,0.7)
        );
}


/* ============================================================
   MAP TOOLS
   ============================================================ */

.map-toolbar {
    position: absolute;

    z-index: 2200;

    bottom: 16px;
    left: 230px;

    display: flex;

    gap: 5px;
}

.map-tool {
    height: 32px;

    padding:
        0 10px;

    border:
        1px solid #cfd7d9;

    border-radius: 5px;

    background:
        rgba(255,255,255,0.96);

    color:
        #44545a;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.10);

    font-size: 9px;

    font-weight: 700;
}


/* ============================================================
   LEAFLET OVERRIDES
   ============================================================ */

.leaflet-control-zoom {
    margin-top: 72px !important;
    margin-left: 225px !important;
}

.leaflet-control-attribution {
    font-size: 7px;
}


/* ============================================================
   RESPONSIVE
   ============================================================ */

@media (max-width: 900px) {

    .intelligence {
        width: 320px;
    }

    .left-panel {
        width: 175px;
    }

    .map-toolbar {
        left: 195px;
    }
}

@media (max-width: 700px) {

    .left-panel {
        display: none;
    }

    .intelligence {
        top: auto;
        left: 8px;
        right: 8px;
        bottom: 8px;

        width: auto;

        height: 43%;
    }

    .leaflet-control-zoom {
        margin-left: 8px !important;
        margin-top: 68px !important;
    }

    .map-toolbar {
        display: none;
    }

    .system-status {
        display: none;
    }
}

</style>

</head>


<body>


<!-- ============================================================
     MAP
     ============================================================ -->

<div id="map"></div>


<!-- ============================================================
     TOP BAR
     ============================================================ -->

<header class="topbar">

    <div class="brand">

        <div class="brand-mark">
            P
        </div>

        <div>

            <div class="brand-name">
                PRAVAH
            </div>

            <div class="brand-sub">
                FLOOD INTELLIGENCE &amp; DECISION SUPPORT
            </div>

        </div>

    </div>


    <div class="system-status">

        <div class="live-status">

            <span class="live-dot"></span>

            MONITORING

        </div>

        <span>
            77 DISTRICTS
        </span>

        <span id="selectedStatus">
            NO DISTRICT SELECTED
        </span>

    </div>

</header>


<!-- ============================================================
     LEFT GIS PANEL
     ============================================================ -->

<aside class="left-panel">

    <div class="panel-header">

        <div class="panel-kicker">
            Spatial intelligence
        </div>

        <div class="panel-title">
            Map Layers
        </div>

    </div>


    <div class="layer-group">

        <div class="layer-title">
            Risk
        </div>

        <div class="layer-row">

            <input
                id="layerRisk"
                type="checkbox"
                checked
            >

            <label for="layerRisk">
                Current PRAVAH Risk
            </label>

        </div>

        <div class="layer-row">

            <input
                id="layerPressure"
                type="checkbox"
                checked
            >

            <label for="layerPressure">
                Flood Pressure
            </label>

        </div>

        <div class="layer-row">

            <input
                id="layerFuture"
                type="checkbox"
            >

            <label for="layerFuture">
                Future Outlook
            </label>

        </div>

    </div>


    <div class="layer-group">

        <div class="layer-title">
            Evidence
        </div>

        <div class="layer-row">

            <input
                id="layerRain"
                type="checkbox"
                checked
            >

            <label for="layerRain">
                Rain Gauges
            </label>

        </div>

        <div class="layer-row">

            <input
                id="layerRiver"
                type="checkbox"
                checked
            >

            <label for="layerRiver">
                River Stations
            </label>

        </div>

        <div class="layer-row">

            <input
                id="layerCorridor"
                type="checkbox"
            >

            <label for="layerCorridor">
                River Influence
            </label>

        </div>

        <div class="layer-row">

            <input
                id="layerDrainage"
                type="checkbox"
            >

            <label for="layerDrainage">
                Terrain Drainage
            </label>

        </div>

    </div>


    <div class="layer-group">

        <div class="layer-title">
            Risk legend
        </div>

        <div class="legend-row">
            <span
                class="legend-swatch"
                style="background:#2e7d32"
            ></span>
            LOW
        </div>

        <div class="legend-row">
            <span
                class="legend-swatch"
                style="background:#ef9f1c"
            ></span>
            WATCH
        </div>

        <div class="legend-row">
            <span
                class="legend-swatch"
                style="background:#d85b32"
            ></span>
            WARNING
        </div>

        <div class="legend-row">
            <span
                class="legend-swatch"
                style="background:#b83232"
            ></span>
            CRITICAL
        </div>

        <div class="layer-note">
            District polygons represent the current PRAVAH
            deterministic risk state. Other evidence layers
            provide supporting context.
        </div>

    </div>

</aside>


<!-- ============================================================
     INTELLIGENCE PANEL
     ============================================================ -->

<aside class="intelligence" id="intelligencePanel">

    <div class="intelligence-head">

        <div class="intelligence-label">
            PRAVAH Intelligence Agent
        </div>

        <div class="intelligence-title-row">

            <div
                class="intelligence-title"
                id="districtTitle"
            >
                Select a district
            </div>

            <div
                class="risk-badge"
                id="districtRiskBadge"
                style="background:#78909c"
            >
                READY
            </div>

        </div>

        <div
            class="intelligence-subtitle"
            id="districtSubtitle"
        >
            Click any district polygon to inspect evidence
            and PRAVAH reasoning.
        </div>

    </div>


    <div
        class="intelligence-body"
        id="intelligenceBody"
    >

        <div class="agent-empty">

            <div class="agent-orb">
                AI
            </div>

            <h3>
                PRAVAH is ready
            </h3>

            <p>
                Select a district. The agent will combine
                rainfall, runoff, river conditions, forecasts,
                satellite evidence and learned patterns into
                an explainable risk assessment.
            </p>

        </div>

    </div>


    <div class="agent-chat">

        <div class="chat-status">

            <span class="chat-status-dot"></span>

            Evidence-grounded reasoning

        </div>


        <div
            id="chatMessages"
        ></div>


        <div class="chat-row">

            <input
                id="chatInput"
                class="chat-input"
                placeholder="Ask PRAVAH about the selected district..."
            >

            <button
                id="chatSend"
                class="chat-button"
                type="button"
            >
                →
            </button>

        </div>


        <div class="chat-suggestions">

            <button
                class="chat-suggestion"
                type="button"
                data-question="Why is this district at its current risk?"
            >
                Why this risk?
            </button>

            <button
                class="chat-suggestion"
                type="button"
                data-question="What evidence supports this assessment?"
            >
                Show evidence
            </button>

            <button
                class="chat-suggestion"
                type="button"
                data-question="What could happen next?"
            >
                What happens next?
            </button>

        </div>

    </div>

</aside>


<!-- ============================================================
     MAP TOOLBAR
     ============================================================ -->

<div class="map-toolbar">

    <button
        class="map-tool"
        id="fitNepal"
        type="button"
    >
        Nepal
    </button>

    <button
        class="map-tool"
        id="clearSelection"
        type="button"
    >
        Clear selection
    </button>

</div>


<script
    src="../../src/mapping/vendor/leaflet/leaflet.js">
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
    L.map(
        "map",
        {
            zoomControl: true,
            preferCanvas: true
        }
    ).setView(
        [28.3949, 84.1240],
        7
    );


/*
   Local-first map.

   There is intentionally no external tile dependency.
   The PRAVAH district geometry is the authoritative spatial
   foundation of the demo.
*/

const baseMap =
    L.layerGroup();

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

    return number.toFixed(decimals);
}


function upper(value) {

    return String(
        value || "UNKNOWN"
    ).toUpperCase();
}


function riskColor(level) {

    switch (
        upper(level)
    ) {

        case "LOW":
            return "#2e7d32";

        case "WATCH":
            return "#ef9f1c";

        case "WARNING":
            return "#d85b32";

        case "CRITICAL":
            return "#b83232";

        default:
            return "#78909c";
    }
}


function pressureColor(score) {

    if (
        score === null ||
        score === undefined ||
        score === ""
    ) {
        return "#78909c";
    }

    score = Number(score);

    if (score >= 75)
        return "#b83232";

    if (score >= 55)
        return "#d85b32";

    if (score >= 30)
        return "#ef9f1c";

    return "#2e7d32";
}


/* ============================================================
   CURRENT SELECTION
   ============================================================ */

let selectedLayer = null;
let selectedProperties = null;


/* ============================================================
   REASONING ENGINE
   ============================================================ */

function buildReasoning(p) {

    const district =
        p.pravah_district_name ||
        p.adm2_name ||
        "this district";

    const risk =
        upper(p.pravah_risk);

    const score =
        Number(p.pravah_score);

    const future =
        upper(p.future_outlook);

    const rainfall =
        upper(p.evidence_rainfall);

    const runoff =
        upper(p.evidence_runoff);

    const river =
        upper(p.evidence_river);

    const dominant =
        upper(p.evidence_dominant_signal);

    const agreement =
        upper(p.evidence_agreement);

    const drivers =
        Array.isArray(p.pravah_drivers)
            ? p.pravah_drivers
            : [];

    let assessment =
        "PRAVAH does not have enough evidence to make a strong assessment.";

    if (
        risk === "CRITICAL"
    ) {

        assessment =
            `${district} is currently classified as CRITICAL. ` +
            `Multiple evidence signals indicate conditions that ` +
            `require immediate attention.`;

    } else if (
        risk === "WARNING"
    ) {

        assessment =
            `${district} is currently classified as WARNING. ` +
            `The evidence indicates a meaningful increase in ` +
            `flood pressure and warrants close monitoring.`;

    } else if (
        risk === "WATCH"
    ) {

        assessment =
            `${district} is currently on WATCH. ` +
            `PRAVAH has detected enough evidence to move this ` +
            `district above the normal monitoring state, while ` +
            `the available evidence does not yet indicate a ` +
            `WARNING or CRITICAL state.`;

    } else {

        assessment =
            `${district} is currently LOW risk according to ` +
            `the deterministic PRAVAH risk engine. ` +
            `Supporting evidence should still be monitored ` +
            `because future conditions can change.`;
    }

    const futureText =
        future === "ELEVATED"
            ? "Future conditions are elevated, so the present low/warning state should not be interpreted as a forecast of safety."
            : future === "NORMAL"
                ? "The current forward-looking indicators remain broadly normal."
                : "The future outlook is not fully available.";

    return {
        district,
        risk,
        score,
        rainfall,
        runoff,
        river,
        dominant,
        agreement,
        future,
        futureText,
        drivers,
        assessment
    };
}


/* ============================================================
   INTELLIGENCE PANEL
   ============================================================ */

function renderIntelligence(p) {

    selectedProperties = p;

    const r =
        buildReasoning(p);

    const title =
        document.getElementById(
            "districtTitle"
        );

    const subtitle =
        document.getElementById(
            "districtSubtitle"
        );

    const badge =
        document.getElementById(
            "districtRiskBadge"
        );

    const body =
        document.getElementById(
            "intelligenceBody"
        );

    const selectedStatus =
        document.getElementById(
            "selectedStatus"
        );


    title.textContent =
        r.district;

    subtitle.textContent =
        `District ${p.pravah_district_id || "N/A"} · Evidence-grounded assessment`;

    badge.textContent =
        r.risk;

    badge.style.background =
        riskColor(r.risk);

    selectedStatus.textContent =
        `SELECTED: ${r.district.toUpperCase()}`;


    let driverHtml = "";

    if (
        r.drivers.length
    ) {

        driverHtml =
            r.drivers
                .slice(0, 5)
                .map(
                    function(driver) {

                        return `
                            <div class="driver-row">

                                <div class="driver-icon">
                                    +
                                </div>

                                <div>
                                    ${escapeHtml(driver)}
                                </div>

                            </div>
                        `;

                    }
                )
                .join("");

    } else {

        driverHtml = `
            <div class="driver-row">
                <div class="driver-icon">i</div>
                <div>
                    No explicit driver was recorded by
                    the deterministic engine.
                </div>
            </div>
        `;
    }


    /*
       ML values are deliberately read from properties if they
       exist. We do not fabricate an RF probability.
    */

    const mlProbability =
        p.ml_flood_probability ??
        p.rf_flood_probability ??
        null;

    const mlAvailable =
        mlProbability !== null &&
        mlProbability !== undefined &&
        mlProbability !== "";


    const shapRows = [
        ["24h rainfall", p.shap_rain_24h],
        ["12h rainfall", p.shap_rain_12h],
        ["6h rainfall", p.shap_rain_6h],
        ["3h rainfall", p.shap_rain_3h],
        ["1h rainfall", p.shap_rain_1h]
    ];

    let shapHtml = "";

    const validShap =
        shapRows.filter(
            function(row) {
                return row[1] !== null &&
                       row[1] !== undefined &&
                       row[1] !== "";
            }
        );

    if (validShap.length) {

        const maxAbs =
            Math.max(
                ...validShap.map(
                    function(row) {
                        return Math.abs(
                            Number(row[1])
                        );
                    }
                ),
                0.000001
            );

        shapHtml =
            validShap
                .map(
                    function(row) {

                        const value =
                            Number(row[1]);

                        const width =
                            Math.min(
                                100,
                                Math.abs(value)
                                / maxAbs
                                * 100
                            );

                        return `
                            <div class="shap-row">

                                <div class="shap-label-row">

                                    <span>
                                        ${escapeHtml(row[0])}
                                    </span>

                                    <span>
                                        ${value >= 0 ? "+" : ""}
                                        ${fmt(value, 3)}
                                    </span>

                                </div>

                                <div class="shap-track">

                                    <div
                                        class="shap-fill"
                                        style="width:${width}%"
                                    ></div>

                                </div>

                            </div>
                        `;

                    }
                )
                .join("");

    } else {

        shapHtml = `
            <div class="ml-description">
                SHAP values are not attached to this map
                snapshot yet. The ML model can be queried
                separately for district-level explanation.
            </div>
        `;
    }


    body.innerHTML = `

        <div class="agent-section">

            <div class="agent-section-title">
                PRAVAH assessment
            </div>

            <div class="reasoning-card">

                <strong>
                    What PRAVAH sees
                </strong>

                <br>

                ${escapeHtml(r.assessment)}

                <br><br>

                <strong>
                    Risk score:
                </strong>

                ${fmt(r.score, 1)}

            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                Evidence fusion
            </div>

            <div class="evidence-grid">

                <div class="evidence-card">

                    <div class="evidence-label">
                        Rainfall
                    </div>

                    <div class="evidence-value">
                        ${escapeHtml(r.rainfall)}
                    </div>

                    <div class="evidence-small">
                        BIPAD / NASA
                    </div>

                </div>


                <div class="evidence-card">

                    <div class="evidence-label">
                        Runoff
                    </div>

                    <div class="evidence-value">
                        ${escapeHtml(r.runoff)}
                    </div>

                    <div class="evidence-small">
                        SCS-CN
                    </div>

                </div>


                <div class="evidence-card">

                    <div class="evidence-label">
                        River
                    </div>

                    <div class="evidence-value">
                        ${escapeHtml(r.river)}
                    </div>

                    <div class="evidence-small">
                        DHM / BIPAD
                    </div>

                </div>


                <div class="evidence-card">

                    <div class="evidence-label">
                        Agreement
                    </div>

                    <div class="evidence-value">
                        ${escapeHtml(r.agreement)}
                    </div>

                    <div class="evidence-small">
                        Cross-source
                    </div>

                </div>

            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                Why this assessment?
            </div>

            <div class="reasoning-card">

                <div>
                    <strong>Dominant signal:</strong>
                    ${escapeHtml(r.dominant)}
                </div>

                <div style="margin-top:6px">

                    <strong>PRAVAH reasoning:</strong>

                    The engine evaluates the available
                    observations together rather than
                    treating any single sensor as the
                    complete picture.

                </div>

                <div style="margin-top:6px">

                    ${escapeHtml(r.futureText)}

                </div>

            </div>

            <div style="margin-top:6px">
                ${driverHtml}
            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                Hydrological evidence
            </div>

            <div class="evidence-grid">

                <div class="evidence-card">

                    <div class="evidence-label">
                        NASA 6h
                    </div>

                    <div class="evidence-value">
                        ${fmt(p.rain_6h_mm)} mm
                    </div>

                </div>


                <div class="evidence-card">

                    <div class="evidence-label">
                        BIPAD 1h
                    </div>

                    <div class="evidence-value">
                        ${fmt(p.rain_1h_mm)} mm
                    </div>

                </div>


                <div class="evidence-card">

                    <div class="evidence-label">
                        SCS-CN runoff
                    </div>

                    <div class="evidence-value">
                        ${fmt(p.scs_cn_runoff_6h_mm)} mm
                    </div>

                </div>


                <div class="evidence-card">

                    <div class="evidence-label">
                        Future 24h
                    </div>

                    <div class="evidence-value">
                        ${fmt(p.forecast_runoff_24h)} mm
                    </div>

                </div>

            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                River &amp; forecast
            </div>

            <div class="reasoning-card">

                <div>
                    <strong>River status:</strong>
                    ${escapeHtml(p.river_status || "UNKNOWN")}
                </div>

                <div style="margin-top:5px">
                    <strong>Rising stations:</strong>
                    ${p.river_rising_stations || 0}
                </div>

                <div style="margin-top:5px">
                    <strong>Warning stations:</strong>
                    ${p.river_warning_stations || 0}
                </div>

                <div style="margin-top:5px">
                    <strong>Danger stations:</strong>
                    ${p.river_danger_stations || 0}
                </div>

                <div style="margin-top:5px">
                    <strong>GEOGLOWS peak:</strong>
                    ${fmt(p.geoglows_peak_flow)} m³/s
                </div>

                <div style="margin-top:5px">
                    <strong>Hours to peak:</strong>
                    ${fmt(p.geoglows_hours_to_peak, 1)}
                </div>

            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                ML intelligence
            </div>

            <div class="ml-box">

                <div class="ml-header">

                    <div class="ml-name">
                        Historical flood-event model
                    </div>

                    <div class="ml-tag">
                        Parallel signal
                    </div>

                </div>


                ${
                    mlAvailable
                    ?
                    `
                        <div
                            style="
                                margin-top:8px;
                                font-size:18px;
                                font-weight:800;
                                color:#176b73;
                            "
                        >
                            ${(Number(mlProbability) * 100).toFixed(1)}%
                        </div>

                        <div class="ml-description">
                            Learned flood-event likelihood.
                            This is an ML signal, not the
                            deterministic PRAVAH risk score.
                        </div>
                    `
                    :
                    `
                        <div class="ml-description">
                            ML likelihood is not attached to
                            the current map snapshot.
                            The RF model remains a parallel
                            intelligence layer.
                        </div>
                    `
                }


                <div style="margin-top:9px">

                    <div
                        style="
                            font-size:8px;
                            font-weight:800;
                            color:#68777d;
                            text-transform:uppercase;
                        "
                    >
                        SHAP feature influence
                    </div>

                    ${shapHtml}

                </div>

            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                Satellite evidence
            </div>

            <div class="reasoning-card">

                <strong>
                    VIIRS:
                </strong>

                ${
                    p.eo_available
                        ? "Available"
                        : "Not available"
                }

                <br>

                <strong>
                    Observation:
                </strong>

                ${escapeHtml(
                    p.eo_observation_date || "N/A"
                )}

                <br>

                <strong>
                    Flood pixels:
                </strong>

                ${escapeHtml(
                    p.eo_flood_pixels || "N/A"
                )}

                <br>

                <strong>
                    Flood ratio:
                </strong>

                ${fmt(p.eo_flood_ratio_pct)}%

            </div>

        </div>


        <div class="agent-section">

            <div class="agent-section-title">
                Forward outlook
            </div>

            <div class="reasoning-card">

                <strong>
                    ${escapeHtml(r.future)}
                </strong>

                <br><br>

                ${escapeHtml(r.futureText)}

            </div>

        </div>

    `;
}


/* ============================================================
   DISTRICT STYLE
   ============================================================ */

function districtStyle(feature) {

    const p =
        feature.properties || {};

    const risk =
        p.pravah_risk || "NO DATA";

    return {

        fillColor:
            riskColor(risk),

        color:
            "#46565c",

        weight:
            1,

        opacity:
            0.95,

        fillOpacity:
            0.48
    };
}


/* ============================================================
   DISTRICT LAYER
   ============================================================ */

const riskLayer =
    L.geoJSON(
        districtData,
        {
            style:
                districtStyle,

            onEachFeature:
                function(feature, layer) {

                    layer.on({

                        click:
                            function() {

                                selectDistrict(
                                    feature,
                                    layer
                                );

                            },

                        mouseover:
                            function(event) {

                                if (
                                    selectedLayer !==
                                    event.target
                                ) {

                                    event.target.setStyle({

                                        weight: 2,

                                        color:
                                            "#176b73",

                                        fillOpacity:
                                            0.62

                                    });

                                }

                            },

                        mouseout:
                            function(event) {

                                if (
                                    selectedLayer !==
                                    event.target
                                ) {

                                    riskLayer.resetStyle(
                                        event.target
                                    );

                                }

                            }

                    });

                }

        }
    );


riskLayer.addTo(map);


/* ============================================================
   SELECT DISTRICT
   ============================================================ */

function selectDistrict(
    feature,
    layer
) {

    if (
        selectedLayer &&
        selectedLayer !== layer
    ) {

        riskLayer.resetStyle(
            selectedLayer
        );

    }

    selectedLayer =
        layer;

    layer.setStyle({

        weight: 3,

        color: "#176b73",

        fillOpacity: 0.70

    });

    layer.bringToFront();

    renderIntelligence(
        feature.properties || {}
    );

    const center =
        layer.getBounds().getCenter();

    map.panTo(
        center,
        {
            animate: true,
            duration: 0.35
        }
    );

}


/* ============================================================
   PRESSURE LAYER
   ============================================================ */

const pressureLayer =
    L.layerGroup();


districtData.features.forEach(
    function(feature) {

        const p =
            feature.properties || {};

        const score =
            p.pressure_index;

        if (
            score === null ||
            score === undefined
        ) {
            return;
        }

        const border =
            L.geoJSON(
                feature,
                {
                    style: {

                        color:
                            pressureColor(score),

                        weight:
                            score >= 55
                                ? 2.8
                                : score >= 30
                                    ? 2
                                    : 1,

                        opacity:
                            0.70,

                        fillOpacity:
                            0
                    }
                }
            );

        pressureLayer.addLayer(
            border
        );

    }
);

pressureLayer.addTo(map);


/* ============================================================
   RIVER STATIONS
   ============================================================ */

const riverLayer =
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
            "#2d7880";

        const status =
            upper(station.status);

        const trend =
            upper(station.trend);

        if (
            status.includes("DANGER")
        ) {

            color =
                "#b83232";

        } else if (
            status.includes("WARNING")
        ) {

            color =
                "#d85b32";

        } else if (
            trend.includes("RISING")
        ) {

            color =
                "#ef9f1c";
        }


        const marker =
            L.circleMarker(
                [
                    Number(station.lat),
                    Number(station.lon)
                ],
                {
                    radius: 4,

                    color:
                        "#ffffff",

                    weight: 1,

                    fillColor:
                        color,

                    fillOpacity:
                        0.9
                }
            );


        marker.bindTooltip(
            escapeHtml(
                station.station ||
                "River station"
            ),
            {
                direction:
                    "top",

                opacity:
                    0.9
            }
        );


        marker.addTo(
            riverLayer
        );

    }
);


riverLayer.addTo(map);


/* ============================================================
   RAIN STATIONS
   ============================================================ */

const rainLayer =
    L.layerGroup();


rainStations.forEach(
    function(station) {

        if (
            station.lat === null ||
            station.lon === null
        ) {
            return;
        }

        const marker =
            L.circleMarker(
                [
                    Number(station.lat),
                    Number(station.lon)
                ],
                {
                    radius: 2.5,

                    color:
                        "#ffffff",

                    weight: 0.7,

                    fillColor:
                        "#3d7e86",

                    fillOpacity:
                        0.62
                }
            );


        marker.bindTooltip(
            escapeHtml(
                station.station ||
                station.name ||
                "Rain gauge"
            ),
            {
                direction:
                    "top",

                opacity:
                    0.85
            }
        );


        marker.addTo(
            rainLayer
        );

    }
);


rainLayer.addTo(map);


/* ============================================================
   FUTURE OUTLOOK
   ============================================================ */

const futureLayer =
    L.layerGroup();


districtData.features.forEach(
    function(feature) {

        const p =
            feature.properties || {};

        const future =
            upper(
                p.future_outlook
            );

        if (
            future === "UNKNOWN" ||
            future === "N/A"
        ) {
            return;
        }

        const layer =
            L.geoJSON(
                feature,
                {
                    style: {

                        fillColor:
                            future === "ELEVATED"
                                ? "#7b5e2a"
                                : "#58747a",

                        color:
                            "#ffffff",

                        weight:
                            0.7,

                        opacity:
                            0.55,

                        fillOpacity:
                            0.14
                    }
                }
            );

        futureLayer.addLayer(
            layer
        );

    }
);


/* ============================================================
   RIVER INFLUENCE
   ============================================================ */

const corridorLayer =
    L.layerGroup();


riverStations.forEach(
    function(station) {

        if (
            station.lat === null ||
            station.lon === null
        ) {
            return;
        }

        const status =
            upper(station.status);

        const trend =
            upper(station.trend);

        let color =
            "#2d7880";

        if (
            status.includes("DANGER")
        ) {

            color =
                "#b83232";

        } else if (
            status.includes("WARNING")
        ) {

            color =
                "#d85b32";

        } else if (
            trend.includes("RISING")
        ) {

            color =
                "#ef9f1c";
        }

        const corridor =
            L.circle(
                [
                    Number(station.lat),
                    Number(station.lon)
                ],
                {
                    radius:
                        1200,

                    color:
                        color,

                    weight:
                        1,

                    opacity:
                        0.28,

                    fillColor:
                        color,

                    fillOpacity:
                        0.045
                }
            );

        corridorLayer.addLayer(
            corridor
        );

    }
);


/* ============================================================
   TERRAIN DRAINAGE PLACEHOLDER
   ============================================================ */

const drainageLayer =
    L.layerGroup();

/*
   The terrain-derived drainage raster is not converted into
   vector geometry inside this HTML snapshot.

   This layer is intentionally kept as a clean extension point
   so the real P99.5 drainage geometry can be added without
   pretending that district boundaries are drainage.
*/


/* ============================================================
   LAYER CONTROLS
   ============================================================ */

document
    .getElementById("layerRisk")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                riskLayer.addTo(map);

            } else {

                map.removeLayer(
                    riskLayer
                );

            }

        }
    );


document
    .getElementById("layerPressure")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                pressureLayer.addTo(map);

            } else {

                map.removeLayer(
                    pressureLayer
                );

            }

        }
    );


document
    .getElementById("layerFuture")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                futureLayer.addTo(map);

            } else {

                map.removeLayer(
                    futureLayer
                );

            }

        }
    );


document
    .getElementById("layerRain")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                rainLayer.addTo(map);

            } else {

                map.removeLayer(
                    rainLayer
                );

            }

        }
    );


document
    .getElementById("layerRiver")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                riverLayer.addTo(map);

            } else {

                map.removeLayer(
                    riverLayer
                );

            }

        }
    );


document
    .getElementById("layerCorridor")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                corridorLayer.addTo(map);

            } else {

                map.removeLayer(
                    corridorLayer
                );

            }

        }
    );


document
    .getElementById("layerDrainage")
    .addEventListener(
        "change",
        function(event) {

            if (
                event.target.checked
            ) {

                drainageLayer.addTo(map);

            } else {

                map.removeLayer(
                    drainageLayer
                );

            }

        }
    );


/* ============================================================
   TOOLBAR
   ============================================================ */

document
    .getElementById("fitNepal")
    .addEventListener(
        "click",
        function() {

            const bounds =
                riskLayer.getBounds();

            if (
                bounds.isValid()
            ) {

                map.fitBounds(
                    bounds,
                    {
                        paddingTopLeft:
                            [225, 80],

                        paddingBottomRight:
                            [390, 30]
                    }
                );

            }

        }
    );


document
    .getElementById("clearSelection")
    .addEventListener(
        "click",
        function() {

            if (
                selectedLayer
            ) {

                riskLayer.resetStyle(
                    selectedLayer
                );

            }

            selectedLayer =
                null;

            selectedProperties =
                null;

            document
                .getElementById(
                    "districtTitle"
                )
                .textContent =
                    "Select a district";

            document
                .getElementById(
                    "districtRiskBadge"
                )
                .textContent =
                    "READY";

            document
                .getElementById(
                    "districtRiskBadge"
                )
                .style.background =
                    "#78909c";

            document
                .getElementById(
                    "districtSubtitle"
                )
                .textContent =
                    "Click any district polygon to inspect evidence and PRAVAH reasoning.";

            document
                .getElementById(
                    "selectedStatus"
                )
                .textContent =
                    "NO DISTRICT SELECTED";

            document
                .getElementById(
                    "intelligenceBody"
                )
                .innerHTML = `

                    <div class="agent-empty">

                        <div class="agent-orb">
                            AI
                        </div>

                        <h3>
                            PRAVAH is ready
                        </h3>

                        <p>
                            Select a district. The agent will
                            combine evidence sources and explain
                            the current risk state.
                        </p>

                    </div>
                `;

        }
    );


/* ============================================================
   AGENT CHAT
   ============================================================ */

function addChatMessage(
    text,
    type
) {

    const container =
        document.getElementById(
            "chatMessages"
        );

    const message =
        document.createElement(
            "div"
        );

    message.className =
        `chat-message ${type === "user" ? "chat-user" : "chat-agent"}`;

    message.textContent =
        text;

    container.appendChild(
        message
    );

    container.scrollTop =
        container.scrollHeight;
}


function answerAgent(
    question
) {

    if (
        !selectedProperties
    ) {

        return "Select a district first. PRAVAH needs a spatial context before it can reason about the evidence.";

    }

    const p =
        selectedProperties;

    const r =
        buildReasoning(p);

    const q =
        question.toLowerCase();


    if (
        q.includes("why") &&
        (
            q.includes("risk") ||
            q.includes("watch") ||
            q.includes("warning") ||
            q.includes("critical")
        )
    ) {

        let response =
            `${r.district} is currently ${r.risk} with a risk score of ${fmt(r.score,1)}. ` +
            `The dominant evidence signal is ${r.dominant}. `;

        if (
            r.drivers.length
        ) {

            response +=
                `PRAVAH recorded: ${r.drivers.slice(0,3).join("; ")}. `;

        }

        response +=
            `Rainfall evidence is ${r.rainfall}, runoff evidence is ${r.runoff}, and river evidence is ${r.river}.`;

        return response;

    }


    if (
        q.includes("evidence") ||
        q.includes("support")
    ) {

        return (
            `PRAVAH is combining rainfall, SCS-CN runoff, ` +
            `river observations, forecast context and satellite ` +
            `evidence. For ${r.district}, the current evidence ` +
            `states are rainfall=${r.rainfall}, runoff=${r.runoff}, ` +
            `river=${r.river}, with cross-source agreement=${r.agreement}.`
        );

    }


    if (
        q.includes("next") ||
        q.includes("future") ||
        q.includes("happen")
    ) {

        return (
            `The forward outlook for ${r.district} is ` +
            `${r.future}. ${r.futureText} ` +
            `PRAVAH should continue monitoring the evidence rather ` +
            `than treating the current state as permanent.`
        );

    }


    if (
        q.includes("rain")
    ) {

        return (
            `${r.district} has BIPAD 1h rainfall of ` +
            `${fmt(p.rain_1h_mm)} mm, NASA 6h rainfall of ` +
            `${fmt(p.rain_6h_mm)} mm and NASA 24h rainfall of ` +
            `${fmt(p.rain_24h_mm)} mm. ` +
            `The rainfall evidence state is ${r.rainfall}.`
        );

    }


    if (
        q.includes("river")
    ) {

        return (
            `River evidence for ${r.district} is ` +
            `${r.river}. There are ` +
            `${p.river_rising_stations || 0} rising stations, ` +
            `${p.river_warning_stations || 0} warning stations and ` +
            `${p.river_danger_stations || 0} danger stations.`
        );

    }


    return (
        `For ${r.district}, PRAVAH currently reports ` +
        `${r.risk} risk with a score of ${fmt(r.score,1)}. ` +
        `You can ask me why this risk exists, what evidence ` +
        `supports it, what happens next, or ask specifically ` +
        `about rainfall or river conditions.`
    );
}


function sendAgentQuestion(
    question
) {

    const clean =
        String(question || "")
            .trim();

    if (!clean) {
        return;
    }

    addChatMessage(
        clean,
        "user"
    );

    const response =
        answerAgent(
            clean
        );

    setTimeout(
        function() {

            addChatMessage(
                response,
                "agent"
            );

        },
        180
    );

}


document
    .getElementById("chatSend")
    .addEventListener(
        "click",
        function() {

            const input =
                document.getElementById(
                    "chatInput"
                );

            sendAgentQuestion(
                input.value
            );

            input.value =
                "";

        }
    );


document
    .getElementById("chatInput")
    .addEventListener(
        "keydown",
        function(event) {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                document
                    .getElementById(
                        "chatSend"
                    )
                    .click();

            }

        }
    );


document
    .querySelectorAll(
        ".chat-suggestion"
    )
    .forEach(
        function(button) {

            button.addEventListener(
                "click",
                function() {

                    sendAgentQuestion(
                        button.dataset.question
                    );

                }
            );

        }
    );


/* ============================================================
   INITIAL MAP EXTENT
   ============================================================ */

const initialBounds =
    riskLayer.getBounds();

if (
    initialBounds.isValid()
) {

    map.fitBounds(
        initialBounds,
        {
            paddingTopLeft:
                [225, 80],

            paddingBottomRight:
                [390, 30]
        }
    );

}


/* ============================================================
   INITIAL AGENT MESSAGE
   ============================================================ */

addChatMessage(
    "PRAVAH intelligence is ready. Select a district to begin evidence-grounded reasoning.",
    "agent"
);


/* ============================================================
   IMPORTANT:
   No Geoman.
   No polygon drawing.
   No editing controls.
   No district popups.
   ============================================================ */

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