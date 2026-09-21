
#!/usr/bin/env python3
"""
PRAVAH - BIPAD Real-Time Monitoring Layer
------------------------------------------

Purpose
-------
Fetch current BIPAD rainfall and river observations and turn them into a
clean, district-aligned monitoring dataset.

This is intentionally separate from the SCS-CN runoff engine.

Roles:
    BIPAD rain  -> local rainfall observations
    BIPAD river -> observed river level / trend / official thresholds
    NASA        -> handled by fusion_aligned.py
    SCS-CN      -> handled by run_off.py

Output:
    prava_bipad_realtime.json

The river logic deliberately keeps stations even when warning/danger
thresholds are unavailable. Missing thresholds are represented as null.
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from src.config import GEOJSON_PATH, BIPAD_FILE

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "https://bipadportal.gov.np/api/v1"

RAIN_URL = f"{BASE_URL}/rain-trimed/"
RIVER_URL = f"{BASE_URL}/river-trimed/"
DISTRICT_URL = f"{BASE_URL}/district/"





OUTPUT_PATH = BIPAD_FILE


# Pull a recent observation window. We still keep only the latest observation
# for each physical station in the final monitoring view.
LOOKBACK_HOURS = 24

REQUEST_TIMEOUT = 30

# BIPAD/DHM rainfall intervals commonly exposed by the realtime endpoint.
RAIN_INTERVALS = [1, 3, 6, 12, 24]


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(dt):
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def parse_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    # Handle trailing Z.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def clean_float(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def normalize_name(value):
    if value is None:
        return ""

    text = str(value).strip().lower()

    # Common naming variations encountered between BIPAD and GeoJSON.
    aliases = {
        "terhathum": "tehrathum",
        "terathum": "tehrathum",
        "tehrathum": "tehrathum",
        "sindhupalchowk": "sindhupalchok",
        "dhanusha": "dhanusa",
        "tanahun": "tanahu",
        "kapilvastu": "kapilbastu",
        "kavre": "kavrepalanchok",
        "kavrepalanchowk": "kavrepalanchok",
        "chitawan": "chitwan",
        "ktm": "kathmandu",
        "nawalparasieast": "nawalparasi east",
        "nawalparasi east": "nawalparasi east",
        "nawalparasiwest": "nawalparasi west",
        "nawalparasi west": "nawalparasi west",
        "rukumeast": "rukum east",
        "rukum east": "rukum east",
        "rukumwest": "rukum west",
        "rukum west": "rukum west",
    }

    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    compact = text.replace(" ", "")

    return aliases.get(text, aliases.get(compact, text))


def get_json(response):
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict) and "results" in payload:
        return payload["results"]

    return payload


def fetch_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "PRAVAH/1.0 real-time-monitor"},
    )
    return get_json(response)


def request_window():
    end = utc_now()
    start = end.timestamp() - LOOKBACK_HOURS * 3600
    start_dt = datetime.fromtimestamp(start, tz=timezone.utc)

    return start_dt, end


def api_time(dt):
    # BIPAD accepts ISO timestamps. Use +00:00 explicitly.
    return dt.astimezone(timezone.utc).isoformat()


# ============================================================================
# GEOJSON / DISTRICT MAPPING
# ============================================================================

def load_geojson():
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(
            f"GeoJSON not found: {GEOJSON_PATH}\n"
            "Run this script from the PRAVAH project root."
        )

    with GEOJSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    districts = []

    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry")

        if not geometry:
            continue

        try:
            district_shape = shape(geometry)
        except Exception:
            continue

        districts.append({
            "name": properties.get("adm2_name"),
            "pcode": properties.get("adm2_pcode"),
            "name_key": normalize_name(properties.get("adm2_name")),
            "shape": district_shape,
        })

    return districts


def build_bipad_districts():
    records = fetch_json(DISTRICT_URL)

    if not isinstance(records, list):
        raise RuntimeError("Unexpected BIPAD district response format.")

    by_id = {}
    by_name = {}

    for record in records:
        district_id = record.get("id")
        title = (
            record.get("title_en")
            or record.get("title")
            or record.get("name")
        )

        if district_id is not None:
            try:
                by_id[int(district_id)] = record
            except (TypeError, ValueError):
                pass

        if title:
            by_name[normalize_name(title)] = record

    return by_id, by_name


def district_from_record(record, bipad_by_id, bipad_by_name, geojson):
    """
    Return:
        {
            "id": int or None,
            "name": str or None,
            "method": "district_id" | "district_name" | "coordinates" | None
        }
    """

    raw_district = (
        record.get("district")
        or record.get("districtId")
        or record.get("district_id")
    )

    # Direct numeric ID.
    if isinstance(raw_district, dict):
        raw_district = (
            raw_district.get("id")
            or raw_district.get("district_id")
            or raw_district.get("value")
        )

    if raw_district is not None:
        try:
            district_id = int(raw_district)
            district = bipad_by_id.get(district_id)

            if district:
                return {
                    "id": district_id,
                    "name": (
                        district.get("title_en")
                        or district.get("title")
                    ),
                    "method": "district_id",
                }
        except (TypeError, ValueError):
            pass

        # Sometimes a district name is returned instead.
        name_key = normalize_name(raw_district)
        district = bipad_by_name.get(name_key)

        if district:
            return {
                "id": district.get("id"),
                "name": (
                    district.get("title_en")
                    or district.get("title")
                ),
                "method": "district_name",
            }

    # Coordinate fallback.
    point_data = record.get("point")

    if isinstance(point_data, dict):
        coordinates = point_data.get("coordinates")
    else:
        coordinates = None

    if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
        lon = clean_float(coordinates[0])
        lat = clean_float(coordinates[1])

        if lon is not None and lat is not None:
            point = Point(lon, lat)

            for district in geojson:
                try:
                    # covers() also includes boundary points.
                    if district["shape"].covers(point):
                        district_record = bipad_by_name.get(
                            district["name_key"]
                        )

                        if district_record:
                            return {
                                "id": district_record.get("id"),
                                "name": (
                                    district_record.get("title_en")
                                    or district_record.get("title")
                                    or district["name"]
                                ),
                                "method": "coordinates",
                            }
                except Exception:
                    continue

    return {
        "id": None,
        "name": None,
        "method": None,
    }


# ============================================================================
# RAINFALL
# ============================================================================

def extract_rain_intervals(record):
    """
    Try to read the rainfall intervals exposed by BIPAD.

    Expected concept:
        interval 1  -> 1-hour rainfall
        interval 3  -> 3-hour rainfall
        interval 6  -> 6-hour rainfall
        interval 12 -> 12-hour rainfall
        interval 24 -> 24-hour rainfall

    BIPAD payload structures can change, so several common shapes are
    supported.
    """

    result = {str(interval): None for interval in RAIN_INTERVALS}

    # Some payloads expose a list called "averages".
    averages = record.get("averages")

    if isinstance(averages, list):
        for item in averages:
            if not isinstance(item, dict):
                continue

            interval = (
                item.get("interval")
                or item.get("hours")
                or item.get("duration")
            )

            try:
                interval = int(float(interval))
            except (TypeError, ValueError):
                continue

            if interval not in RAIN_INTERVALS:
                continue

            value = (
                item.get("average")
                if item.get("average") is not None
                else item.get("value")
            )

            if value is None:
                value = item.get("rainfall")

            result[str(interval)] = clean_float(value)

    # Also support direct fields if the endpoint exposes them.
    direct_candidates = {
        1: ["rain_1h", "rain1h", "1h", "one_hour"],
        3: ["rain_3h", "rain3h", "3h", "three_hour"],
        6: ["rain_6h", "rain6h", "6h", "six_hour"],
        12: ["rain_12h", "rain12h", "12h", "twelve_hour"],
        24: ["rain_24h", "rain24h", "24h", "twenty_four_hour"],
    }

    for interval, keys in direct_candidates.items():
        if result[str(interval)] is not None:
            continue

        for key in keys:
            if key in record:
                value = clean_float(record.get(key))
                if value is not None:
                    result[str(interval)] = value
                    break

    return result


def rain_station_id(record):
    return (
        record.get("station")
        or record.get("stationId")
        or record.get("station_id")
        or record.get("id")
    )


def rain_observed_at(record):
    return (
        record.get("measured_on")
        or record.get("measuredOn")
        or record.get("observed_at")
        or record.get("observedAt")
        or record.get("timestamp")
    )


def fetch_rainfall(start_dt, end_dt):
    params = {
        "measured_on__gt": api_time(start_dt),
        "measured_on__lt": api_time(end_dt),
        "limit": 5000,
    }

    records = fetch_json(RAIN_URL, params=params)

    if not isinstance(records, list):
        raise RuntimeError("Unexpected BIPAD rainfall response format.")

    latest_by_station = {}
    invalid = 0
    mapped_by_id = 0
    mapped_by_name = 0
    mapped_by_coordinates = 0
    unmapped = 0

    return {
        "records": records,
        "latest_by_station": latest_by_station,
        "invalid": invalid,
        "mapped_by_id": mapped_by_id,
        "mapped_by_name": mapped_by_name,
        "mapped_by_coordinates": mapped_by_coordinates,
        "unmapped": unmapped,
    }


def process_rainfall(raw, bipad_by_id, bipad_by_name, geojson):
    latest = raw["latest_by_station"]

    for record in raw["records"]:
        station_id = rain_station_id(record)
        observed = parse_datetime(rain_observed_at(record))
        intervals = extract_rain_intervals(record)

        if station_id is None or observed is None:
            raw["invalid"] += 1
            continue

        if not any(v is not None for v in intervals.values()):
            raw["invalid"] += 1
            continue

        district = district_from_record(
            record, bipad_by_id, bipad_by_name, geojson
        )

        if district["method"] == "district_id":
            raw["mapped_by_id"] += 1
        elif district["method"] == "district_name":
            raw["mapped_by_name"] += 1
        elif district["method"] == "coordinates":
            raw["mapped_by_coordinates"] += 1
        else:
            raw["unmapped"] += 1

        key = str(station_id)

        candidate = {
            "station_id": station_id,
            "station_name": (
                record.get("station_name")
                or record.get("stationName")
                or record.get("title")
                or record.get("name")
            ),
            "district_id": district["id"],
            "district": district["name"],
            "mapping_method": district["method"],
            "observed_at": iso_utc(observed),
            "rainfall_mm": intervals,
            "point": record.get("point"),
            "source": "BIPAD / DHM",
        }

        previous = latest.get(key)

        if previous is None:
            latest[key] = candidate
        else:
            previous_dt = parse_datetime(previous["observed_at"])
            if previous_dt is None or observed > previous_dt:
                latest[key] = candidate

    return latest


# ============================================================================
# RIVER
# ============================================================================

def river_station_id(record):
    return (
        record.get("station")
        or record.get("stationId")
        or record.get("station_id")
        or record.get("stationSeriesId")
        or record.get("id")
    )


def river_observed_at(record):
    return (
        record.get("waterLevelOn")
        or record.get("water_level_on")
        or record.get("observed_at")
        or record.get("observedAt")
        or record.get("timestamp")
    )


def classify_threshold_state(water, warning, danger):
    if water is None:
        return "NO WATER OBSERVATION"

    if danger is not None and water >= danger:
        return "DANGER"

    if warning is not None and water >= warning:
        return "WARNING"

    if warning is not None:
        return "BELOW WARNING"

    return "NO THRESHOLD CONFIGURED"


def threshold_percent(current, threshold):
    if current is None or threshold is None:
        return None

    if threshold <= 0:
        return None

    return (current / threshold) * 100.0


def fetch_river(start_dt, end_dt):
    params = {
        "waterLevelOn__gt": api_time(start_dt),
        "waterLevelOn__lt": api_time(end_dt),
        "limit": 5000,
    }

    records = fetch_json(RIVER_URL, params=params)

    if not isinstance(records, list):
        raise RuntimeError("Unexpected BIPAD river response format.")

    return records


def process_river(records, bipad_by_id, bipad_by_name, geojson):
    latest = {}

    stats = {
        "records_received": len(records),
        "valid_water_observations": 0,
        "invalid_records": 0,
        "mapped_by_id": 0,
        "mapped_by_name": 0,
        "mapped_by_coordinates": 0,
        "unmapped": 0,
        "stations_with_warning": 0,
        "stations_with_danger": 0,
    }

    for record in records:
        station_id = river_station_id(record)
        observed = parse_datetime(river_observed_at(record))
        water = clean_float(
            record.get("waterLevel")
            if record.get("waterLevel") is not None
            else record.get("water_level")
        )

        if station_id is None or observed is None or water is None:
            stats["invalid_records"] += 1
            continue

        # Reject obviously corrupt physical values, but do NOT require
        # warning/danger thresholds to be present.
        if abs(water) > 1000:
            stats["invalid_records"] += 1
            continue

        warning = clean_float(
            record.get("warningLevel")
            if record.get("warningLevel") is not None
            else record.get("warning_level")
        )

        danger = clean_float(
            record.get("dangerLevel")
            if record.get("dangerLevel") is not None
            else record.get("danger_level")
        )

        if warning is not None and danger is not None and danger < warning:
            stats["invalid_records"] += 1
            continue

        district = district_from_record(
            record, bipad_by_id, bipad_by_name, geojson
        )

        if district["method"] == "district_id":
            stats["mapped_by_id"] += 1
        elif district["method"] == "district_name":
            stats["mapped_by_name"] += 1
        elif district["method"] == "coordinates":
            stats["mapped_by_coordinates"] += 1
        else:
            stats["unmapped"] += 1

        stats["valid_water_observations"] += 1

        if warning is not None:
            stats["stations_with_warning"] += 1

        if danger is not None:
            stats["stations_with_danger"] += 1

        key = str(station_id)

        candidate = {
            "station_id": station_id,
            "station_name": (
                record.get("title")
                or record.get("station_name")
                or record.get("stationName")
                or record.get("name")
            ),
            "basin": record.get("basin"),
            "district_id": district["id"],
            "district": district["name"],
            "mapping_method": district["method"],
            "province_id": record.get("province"),
            "water_level_m": water,
            "warning_level_m": warning,
            "danger_level_m": danger,
            "warning_utilization_pct": (
                round(threshold_percent(water, warning), 2)
                if threshold_percent(water, warning) is not None
                else None
            ),
            "danger_utilization_pct": (
                round(threshold_percent(water, danger), 2)
                if threshold_percent(water, danger) is not None
                else None
            ),
            "trend": (
                record.get("steady")
                or record.get("trend")
                or "UNKNOWN"
            ),
            "official_status": record.get("status"),
            "observed_at": iso_utc(observed),
            "point": record.get("point"),
            "source": "BIPAD / DHM",
        }

        candidate["threshold_state"] = classify_threshold_state(
            water, warning, danger
        )

        previous = latest.get(key)

        if previous is None:
            latest[key] = candidate
        else:
            previous_dt = parse_datetime(previous["observed_at"])
            if previous_dt is None or observed > previous_dt:
                latest[key] = candidate

    return latest, stats


# ============================================================================
# DISTRICT AGGREGATION
# ============================================================================

def empty_district(name, district_id):
    return {
        "district_id": district_id,
        "district": name,
        "rainfall": {
            "station_count": 0,
            "latest_station_count": 0,
            "max_1h_mm": None,
            "max_3h_mm": None,
            "max_6h_mm": None,
            "max_12h_mm": None,
            "max_24h_mm": None,
            "latest_observation": None,
        },
        "river": {
            "station_count": 0,
            "warning_threshold_stations": 0,
            "danger_threshold_stations": 0,
            "warning_stations": 0,
            "danger_stations": 0,
            "rising_stations": 0,
            "falling_stations": 0,
            "steady_stations": 0,
            "latest_observation": None,
            "max_warning_utilization_pct": None,
            "max_danger_utilization_pct": None,
        },
        "monitoring": {
            "state": "NO DATA",
            "reasons": [],
        },
        "rain_stations": [],
        "river_stations": [],
    }


def aggregate_districts(
    bipad_by_id,
    rain_stations,
    river_stations,
):
    districts = {}

    for district_id, record in bipad_by_id.items():
        name = record.get("title_en") or record.get("title") or str(district_id)
        districts[str(district_id)] = empty_district(name, district_id)

    for station in rain_stations.values():
        district_id = station.get("district_id")
        if district_id is None:
            continue

        key = str(district_id)
        if key not in districts:
            districts[key] = empty_district(
                station.get("district") or f"District {district_id}",
                district_id,
            )

        district = districts[key]
        district["rain_stations"].append(station)

        rainfall = station["rainfall_mm"]

        for interval in RAIN_INTERVALS:
            value = rainfall.get(str(interval))
            if value is None:
                continue

            field = f"max_{interval}h_mm"
            current = district["rainfall"][field]

            if current is None or value > current:
                district["rainfall"][field] = value

        district["rainfall"]["station_count"] += 1

        observed = parse_datetime(station.get("observed_at"))
        if observed:
            current_latest = parse_datetime(
                district["rainfall"]["latest_observation"]
            )

            if current_latest is None or observed > current_latest:
                district["rainfall"]["latest_observation"] = station["observed_at"]

    for station in river_stations.values():
        district_id = station.get("district_id")
        if district_id is None:
            continue

        key = str(district_id)
        if key not in districts:
            districts[key] = empty_district(
                station.get("district") or f"District {district_id}",
                district_id,
            )

        district = districts[key]
        district["river_stations"].append(station)

        district["river"]["station_count"] += 1

        if station.get("warning_level_m") is not None:
            district["river"]["warning_threshold_stations"] += 1

        if station.get("danger_level_m") is not None:
            district["river"]["danger_threshold_stations"] += 1

        state = station.get("threshold_state")
        if state == "WARNING":
            district["river"]["warning_stations"] += 1
        elif state == "DANGER":
            district["river"]["danger_stations"] += 1

        trend = str(station.get("trend") or "").upper()

        if "RISING" in trend:
            district["river"]["rising_stations"] += 1
        elif "FALLING" in trend:
            district["river"]["falling_stations"] += 1
        elif "STEADY" in trend:
            district["river"]["steady_stations"] += 1

        warning_pct = station.get("warning_utilization_pct")
        danger_pct = station.get("danger_utilization_pct")

        if warning_pct is not None:
            current = district["river"]["max_warning_utilization_pct"]
            if current is None or warning_pct > current:
                district["river"]["max_warning_utilization_pct"] = warning_pct

        if danger_pct is not None:
            current = district["river"]["max_danger_utilization_pct"]
            if current is None or danger_pct > current:
                district["river"]["max_danger_utilization_pct"] = danger_pct

        observed = parse_datetime(station.get("observed_at"))
        if observed:
            current_latest = parse_datetime(
                district["river"]["latest_observation"]
            )

            if current_latest is None or observed > current_latest:
                district["river"]["latest_observation"] = station["observed_at"]

    # Round values for clean JSON.
    for district in districts.values():
        for field in [
            "max_1h_mm",
            "max_3h_mm",
            "max_6h_mm",
            "max_12h_mm",
            "max_24h_mm",
        ]:
            value = district["rainfall"][field]
            if value is not None:
                district["rainfall"][field] = round(value, 2)

        if district["river"]["max_warning_utilization_pct"] is not None:
            district["river"]["max_warning_utilization_pct"] = round(
                district["river"]["max_warning_utilization_pct"], 2
            )

        if district["river"]["max_danger_utilization_pct"] is not None:
            district["river"]["max_danger_utilization_pct"] = round(
                district["river"]["max_danger_utilization_pct"], 2
            )

    return districts


# ============================================================================
# MONITORING STATE
# ============================================================================

def derive_monitoring_state(district):
    river = district["river"]
    rain = district["rainfall"]

    reasons = []

    if river["danger_stations"] > 0:
        reasons.append("River station at or above danger threshold")
        state = "DANGER"
    elif river["warning_stations"] > 0:
        reasons.append("River station at or above warning threshold")
        state = "WARNING"
    elif river["rising_stations"] > 0:
        reasons.append("River station(s) rising")
        state = "RIVER RISING"
    elif river["station_count"] > 0:
        reasons.append("River monitoring observations available")
        state = "MONITORING"
    elif rain["station_count"] > 0:
        reasons.append("Rainfall monitoring observations available")
        state = "MONITORING"
    else:
        state = "NO DATA"

    return state, reasons


def apply_monitoring_state(districts):
    for district in districts.values():
        state, reasons = derive_monitoring_state(district)

        district["monitoring"]["state"] = state
        district["monitoring"]["reasons"] = reasons


# ============================================================================
# FRESHNESS
# ============================================================================

def age_minutes(observed_at, now):
    dt = parse_datetime(observed_at)
    if dt is None:
        return None

    return max(0.0, (now - dt).total_seconds() / 60.0)


def freshness_label(minutes):
    if minutes is None:
        return "NO DATA"
    if minutes <= 30:
        return "FRESH"
    if minutes <= 120:
        return "RECENT"
    if minutes <= 360:
        return "STALE"
    return "VERY STALE"


def add_freshness(districts, generated_at):
    now = parse_datetime(generated_at)

    for district in districts.values():
        rain_age = age_minutes(
            district["rainfall"]["latest_observation"], now
        )
        river_age = age_minutes(
            district["river"]["latest_observation"], now
        )

        district["rainfall"]["age_minutes"] = (
            round(rain_age, 1) if rain_age is not None else None
        )
        district["rainfall"]["freshness"] = freshness_label(rain_age)

        district["river"]["age_minutes"] = (
            round(river_age, 1) if river_age is not None else None
        )
        district["river"]["freshness"] = freshness_label(river_age)


# ============================================================================
# TOP MONITORING LIST
# ============================================================================

STATE_PRIORITY = {
    "DANGER": 5,
    "WARNING": 4,
    "RIVER RISING": 3,
    "HEAVY RAIN": 2,
    "PERSISTENT RAIN": 2,
    "MONITORING": 1,
    "NO DATA": 0,
}


def build_top_monitoring(districts):
    rows = []

    for district in districts.values():
        state = district["monitoring"]["state"]

        rows.append({
            "district_id": district["district_id"],
            "district": district["district"],
            "state": state,
            "priority": STATE_PRIORITY.get(state, 0),
            "reasons": district["monitoring"]["reasons"],
            "rain_1h_mm": district["rainfall"]["max_1h_mm"],
            "rain_24h_mm": district["rainfall"]["max_24h_mm"],
            "river_stations": district["river"]["station_count"],
            "rising_stations": district["river"]["rising_stations"],
            "warning_stations": district["river"]["warning_stations"],
            "danger_stations": district["river"]["danger_stations"],
            "max_warning_utilization_pct": district["river"][
                "max_warning_utilization_pct"
            ],
        })

    rows.sort(
        key=lambda x: (
            x["priority"],
            x["danger_stations"],
            x["warning_stations"],
            x["rising_stations"],
            x["max_warning_utilization_pct"] or -1,
            x["rain_1h_mm"] or -1,
        ),
        reverse=True,
    )

    return rows[:10]


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("PRAVAH BIPAD REAL-TIME MONITOR")
    print("=" * 80)

    start_dt, end_dt = request_window()

    print(f"\nMonitoring window:")
    print(f"  Start UTC: {start_dt.isoformat()}")
    print(f"  End UTC:   {end_dt.isoformat()}")

    print("\nLoading GeoJSON districts...")
    geojson = load_geojson()
    print(f"GeoJSON districts loaded: {len(geojson)}")

    print("\nFetching BIPAD districts...")
    bipad_by_id, bipad_by_name = build_bipad_districts()
    print(f"BIPAD districts loaded: {len(bipad_by_id)}")

    # ------------------------------------------------------------------------
    # RAIN
    # ------------------------------------------------------------------------
    print("\nFetching BIPAD rainfall...")
    rain_raw = fetch_rainfall(start_dt, end_dt)
    process_rainfall(
        rain_raw,
        bipad_by_id,
        bipad_by_name,
        geojson,
    )

    rain_stations = rain_raw["latest_by_station"]

    print(f"Rain records received: {len(rain_raw['records'])}")
    print(f"Latest unique rain stations: {len(rain_stations)}")
    print(f"Rain invalid records: {rain_raw['invalid']}")
    print(f"Rain mapped by district ID: {rain_raw['mapped_by_id']}")
    print(f"Rain mapped by district name: {rain_raw['mapped_by_name']}")
    print(f"Rain mapped by coordinates: {rain_raw['mapped_by_coordinates']}")
    print(f"Rain unmapped: {rain_raw['unmapped']}")

    # ------------------------------------------------------------------------
    # RIVER
    # ------------------------------------------------------------------------
    print("\nFetching BIPAD river...")
    river_records = fetch_river(start_dt, end_dt)

    river_stations, river_stats = process_river(
        river_records,
        bipad_by_id,
        bipad_by_name,
        geojson,
    )

    print(f"River records received: {river_stats['records_received']}")
    print(f"Valid river observations: {river_stats['valid_water_observations']}")
    print(f"Unique river stations: {len(river_stations)}")
    print(f"River invalid records: {river_stats['invalid_records']}")
    print(f"River mapped by district ID: {river_stats['mapped_by_id']}")
    print(f"River mapped by district name: {river_stats['mapped_by_name']}")
    print(f"River mapped by coordinates: {river_stats['mapped_by_coordinates']}")
    print(f"River unmapped: {river_stats['unmapped']}")
    print(
        "Stations with warning threshold:",
        river_stats["stations_with_warning"],
    )
    print(
        "Stations with danger threshold:",
        river_stats["stations_with_danger"],
    )

    # ------------------------------------------------------------------------
    # DISTRICTS
    # ------------------------------------------------------------------------
    districts = aggregate_districts(
        bipad_by_id,
        rain_stations,
        river_stations,
    )

    apply_monitoring_state(districts)

    generated_at = iso_utc(utc_now())
    add_freshness(districts, generated_at)

    top_monitoring = build_top_monitoring(districts)

    # ------------------------------------------------------------------------
    # NATIONAL SUMMARY
    # ------------------------------------------------------------------------
    summary = {
        "districts": len(districts),
        "rain_stations": len(rain_stations),
        "river_stations": len(river_stations),
        "river_warning_stations": river_stats["stations_with_warning"],
        "river_danger_stations": river_stats["stations_with_danger"],
        "river_danger_state_districts": sum(
            1
            for d in districts.values()
            if d["monitoring"]["state"] == "DANGER"
        ),
        "river_warning_state_districts": sum(
            1
            for d in districts.values()
            if d["monitoring"]["state"] == "WARNING"
        ),
        "river_rising_districts": sum(
            1
            for d in districts.values()
            if d["river"]["rising_stations"] > 0
        ),
        "rain_monitoring_districts": sum(
            1
            for d in districts.values()
            if d["rainfall"]["station_count"] > 0
        ),
    }

    output = {
        "project": "PRAVAH",
        "pipeline_version": "bipad_realtime_v1",
        "generated_at_utc": generated_at,
        "analysis_window": {
            "start_utc": start_dt.isoformat(),
            "end_utc": end_dt.isoformat(),
            "hours": LOOKBACK_HOURS,
        },
        "sources": {
            "rainfall": RAIN_URL,
            "river": RIVER_URL,
            "district": DISTRICT_URL,
            "geojson": str(GEOJSON_PATH),
        },
        "semantics": {
            "rainfall": (
                "Local BIPAD/DHM station observations. Rainfall intervals "
                "are retained separately."
            ),
            "river": (
                "Local BIPAD/DHM river observations including water level, "
                "trend, official warning/danger thresholds, and official status."
            ),
            "thresholds": (
                "Warning and danger thresholds are optional station metadata. "
                "Missing thresholds are retained as null and never fabricated."
            ),
            "monitoring_state": (
                "Operational observation state only. It is not the final "
                "PRAVAH flood-risk classification."
            ),
            "risk": (
                "Final district risk will be produced later by the PRAVAH "
                "evidence-fusion engine using BIPAD, NASA, runoff and "
                "future forecast/flood-extent evidence."
            ),
        },
        "statistics": {
            "rain": {
                "records_received": len(rain_raw["records"]),
                "unique_stations": len(rain_stations),
                "invalid_records": rain_raw["invalid"],
                "mapped_by_district_id": rain_raw["mapped_by_id"],
                "mapped_by_district_name": rain_raw["mapped_by_name"],
                "mapped_by_coordinates": rain_raw["mapped_by_coordinates"],
                "unmapped": rain_raw["unmapped"],
            },
            "river": river_stats,
            "summary": summary,
        },
        "top_monitoring_areas": top_monitoring,
        "districts": districts,
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------------
    # PRINT SUMMARY
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PRAVAH REAL-TIME MONITORING SUMMARY")
    print("=" * 80)

    print(f"Districts:                    {summary['districts']}")
    print(f"Rain stations:                {summary['rain_stations']}")
    print(f"River stations:               {summary['river_stations']}")
    print(f"River warning thresholds:     {summary['river_warning_stations']}")
    print(f"River danger thresholds:      {summary['river_danger_stations']}")
    print(f"River warning districts:      {summary['river_warning_state_districts']}")
    print(f"River danger districts:       {summary['river_danger_state_districts']}")
    print(f"River rising districts:       {summary['river_rising_districts']}")
    print(f"Rain-monitoring districts:    {summary['rain_monitoring_districts']}")

    print("\n" + "=" * 80)
    print("TOP MONITORING AREAS")
    print("=" * 80)

    for index, item in enumerate(top_monitoring, start=1):
        if item["state"] == "NO DATA":
            continue

        print(
            f"{index:2d}. {item['district']:<22} "
            f"{item['state']:<16} "
            f"rain1h={item['rain_1h_mm'] if item['rain_1h_mm'] is not None else 'N/A'} "
            f"rising={item['rising_stations']} "
            f"warning={item['warning_stations']} "
            f"danger={item['danger_stations']}"
        )

    print("\n" + "=" * 80)
    print("PRAVAH BIPAD REAL-TIME MONITOR COMPLETE")
    print("=" * 80)
    print(f"Saved: {OUTPUT_PATH}")
    print("\nNext layer:")
    print("  prava_bipad_realtime.json")
    print("          +")
    print("  prava_runoff_data.json")
    print("          +")
    print("  NASA fused rainfall")
    print("          ↓")
    print("  PRAVAH evidence-fusion risk engine")


if __name__ == "__main__":
    main()
