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

    components = []

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

    evidence = risk_record.get(
        "evidence",
        evidence_record.get(
            "evidence",
            {}
        )
    )

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

    river_local = river_record.get(
        "river",
        {}
    )

    if not isinstance(
        river_local,
        dict
    ):

        river_local = {}

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
# HTML CONTENT
# ============================================================

# Note the exact string matching 'html_content = r"""' required by update_pravah_agent_ui.py
html_content = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>PRAVAH Hazard Map V4</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body { margin: 0; padding: 0; font-family: sans-serif; }
        #map { width: 100vw; height: 100vh; }
    </style>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map').setView([28.3949, 84.1240], 7);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

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

if (typeof districtShadowLayer !== 'undefined') districtShadowLayer.bringToBack();
if (typeof riskLayer !== 'undefined') riskLayer.bringToFront();
if (typeof pressureGlowLayer !== 'undefined') pressureGlowLayer.bringToFront();
if (typeof riverCorridorLayer !== 'undefined') riverCorridorLayer.bringToFront();
if (typeof riverStationLayer !== 'undefined') riverStationLayer.bringToFront();

if (typeof rainLayer !== 'undefined' && rainLayer) {
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