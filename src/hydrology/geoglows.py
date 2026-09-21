import json
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config import GEOGLOWS_FILE, LIVE_FUSED_FILE
import pandas as pd
import requests


# ============================================================================
# CONFIGURATION
# ============================================================================

BIPAD_URL = "https://bipadportal.gov.np/api/v1/river-trimed/"
GEOGLOWS_URL = "https://geoglows.ecmwf.int/api"

OUTPUT_FILE = GEOGLOWS_FILE

LOOKBACK_HOURS = 24

BIPAD_PAGE_LIMIT = 5000
MAX_BIPAD_PAGES = 3

REQUEST_TIMEOUT = 30

# Conservative parallelism.
# GeoGLOWS rate-limits aggressive concurrent requests.
GEOGLOWS_WORKERS = 2

# Retry transient GeoGLOWS errors.
MAX_RETRIES = 4

# Initial retry delay.
RETRY_BASE_DELAY = 1.5

# Small spacing between successful requests from each worker.
REQUEST_DELAY = 0.15

# Cache file for coordinate -> GeoGLOWS river ID.
RIVER_ID_CACHE_FILE = (
    OUTPUT_FILE.parent / "geoglows_river_id_cache.json"
)


# ============================================================================
# BIPAD
# ============================================================================

def fetch_bipad_river_records():

    """
    Load the fresh BIPAD river snapshot produced by the
    PRAVAH fusion stage.

    This avoids making a second paginated BIPAD request.
    """

    print("=" * 80)
    print("PRAVAH - BIPAD × GEOGLOWS")
    print("=" * 80)

    if not LIVE_FUSED_FILE.exists():
        raise RuntimeError(
            f"Fresh fused snapshot not found: {LIVE_FUSED_FILE}"
        )

    with open(LIVE_FUSED_FILE, "r") as f:
        fused = json.load(f)

    generated_at = fused.get(
        "generated_at_utc"
    )

    districts = fused.get(
        "districts",
        {}
    )

    if not isinstance(districts, dict):
        raise RuntimeError(
            "Invalid fused snapshot: districts must be a dictionary."
        )

    records = []

    for district in districts.values():

        river = district.get(
            "river",
            {}
        )

        stations = river.get(
            "stations",
            []
        )

        if not isinstance(stations, list):
            continue

        for station in stations:

            point = station.get(
                "point"
            )

            if not isinstance(point, dict):
                continue

            coordinates = point.get(
                "coordinates"
            )

            if (
                not isinstance(coordinates, list)
                or len(coordinates) < 2
            ):
                continue

            records.append(
                {
                    "stationSeriesId":
                        station.get(
                            "station_series_id"
                        ),

                    "title":
                        station.get(
                            "station"
                        ),

                    "waterLevelOn":
                        station.get(
                            "observed_at"
                        ),

                    "point":
                        point,

                    "water_level_m":
                        station.get(
                            "water_level_m"
                        ),

                    "warning_level_m":
                        station.get(
                            "warning_level_m"
                        ),

                    "danger_level_m":
                        station.get(
                            "danger_level_m"
                        ),

                    "trend":
                        station.get(
                            "trend"
                        ),

                    "freshness":
                        station.get(
                            "freshness"
                        ),

                    "source":
                        station.get(
                            "source"
                        ),
                }
            )

    if not records:
        raise RuntimeError(
            "No river stations with coordinates "
            "found in the fused snapshot."
        )

    end_dt = datetime.now(
        timezone.utc
    )

    try:
        start_dt = datetime.fromisoformat(
            generated_at.replace(
                "Z",
                "+00:00"
            )
        )
    except Exception:
        start_dt = end_dt - timedelta(
            hours=LOOKBACK_HOURS
        )

    print(
        "\nUsing fresh fused BIPAD river snapshot."
    )

    print(
        "Fusion snapshot:",
        generated_at
    )

    print(
        "River stations available:",
        len(records)
    )

    print(
        "BIPAD API pagination skipped."
    )

    return records, start_dt, end_dt


# ============================================================================
# STATION DEDUPLICATION
# ============================================================================

def get_station_id(record):

    station_id = (
        record.get("stationSeriesId")
        or record.get("station")
        or record.get("id")
    )

    if station_id is None:
        return None

    return str(station_id)


def get_coordinates(record):

    point = record.get("point")

    if not isinstance(point, dict):
        return None, None

    coordinates = point.get("coordinates")

    if not isinstance(coordinates, list):
        return None, None

    if len(coordinates) < 2:
        return None, None

    try:

        lon = float(coordinates[0])
        lat = float(coordinates[1])

        return lat, lon

    except (TypeError, ValueError):

        return None, None


def get_latest_stations(records):

    stations = {}

    for record in records:

        station_id = get_station_id(record)

        if station_id is None:
            continue

        observed = (
            record.get("waterLevelOn")
            or record.get("observed_at")
            or ""
        )

        current = stations.get(station_id)

        if current is None:

            stations[station_id] = record

        else:

            old_time = (
                current.get("waterLevelOn")
                or current.get("observed_at")
                or ""
            )

            if observed > old_time:
                stations[station_id] = record

    return list(stations.values())


# ============================================================================
# GEOGLOWS RETRY HELPER
# ============================================================================

def geoglows_get(
    url,
    params=None,
    allow_csv=False,
):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent":
                        "PRAVAH/1.0 disaster-monitor"
                },
            )

            # ------------------------------------------------------------
            # Success
            # ------------------------------------------------------------

            if response.status_code == 200:

                return response

            # ------------------------------------------------------------
            # Retryable errors
            # ------------------------------------------------------------

            if response.status_code in (
                429,
                500,
                502,
                503,
                504,
            ):

                last_error = (
                    f"HTTP {response.status_code}"
                )

                if attempt < MAX_RETRIES:

                    # GEOGLOWS rate-limits large station batches with HTTP 429.
                    # Use a gentler backoff for rate limiting than for normal
                    # transient server errors.
                    if response.status_code == 429:
                        delay = 5.0 * (2 ** (attempt - 1))
                    else:
                        delay = (
                            RETRY_BASE_DELAY
                            * (2 ** (attempt - 1))
                        )

                    if response.status_code == 429:
                        print(
                            "    GEOGLOWS rate limit (429); "
                            f"backing off {delay:.0f}s"
                        )

                    time.sleep(delay)

                    continue

                break

            # ------------------------------------------------------------
            # Non-retryable error
            # ------------------------------------------------------------

            response.raise_for_status()

        except requests.RequestException as exc:

            last_error = str(exc)

            if attempt < MAX_RETRIES:

                delay = (
                    RETRY_BASE_DELAY
                    * (2 ** (attempt - 1))
                )

                print(
                    f"    Network error; "
                    f"retry {attempt}/{MAX_RETRIES - 1} "
                    f"in {delay:.1f}s"
                )

                time.sleep(delay)

                continue

            break

    raise RuntimeError(
        f"GeoGLOWS request failed after "
        f"{MAX_RETRIES} attempts: {last_error}"
    )


# ============================================================================
# RIVER ID CACHE
# ============================================================================

def load_river_id_cache():

    if not RIVER_ID_CACHE_FILE.exists():

        return {}

    try:

        with open(
            RIVER_ID_CACHE_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        if isinstance(data, dict):

            return data

    except Exception as exc:

        print(
            "Warning: could not load river ID cache:",
            exc
        )

    return {}


def save_river_id_cache(cache):

    with open(
        RIVER_ID_CACHE_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            cache,
            f,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================================
# GEOGLOWS
# ============================================================================

def make_coordinate_key(lat, lon):

    return (
        f"{lat:.6f},"
        f"{lon:.6f}"
    )


def get_river_id(
    lat,
    lon,
    river_id_cache,
):

    cache_key = make_coordinate_key(
        lat,
        lon
    )

    # ------------------------------------------------------------
    # Use cached river ID when available
    # ------------------------------------------------------------

    if cache_key in river_id_cache:

        return river_id_cache[cache_key]

    url = f"{GEOGLOWS_URL}/v2/getriverid"

    params = {
        "lat": lat,
        "lon": lon,
    }

    response = geoglows_get(
        url,
        params=params,
    )

    data = response.json()

    river_id = data.get("river_id")

    if river_id is not None:

        river_id_cache[cache_key] = river_id

    return river_id


def get_forecast(river_id):

    url = (
        f"{GEOGLOWS_URL}/v2/forecast/"
        f"{river_id}"
    )

    response = geoglows_get(
        url
    )

    df = pd.read_csv(
        StringIO(response.text)
    )

    if df.empty:

        return None

    df["datetime"] = pd.to_datetime(
        df["datetime"]
    )

    return df


# ============================================================================
# FORECAST FEATURES
# ============================================================================

def calculate_forecast_features(df):

    if df is None or df.empty:

        return None

    current_flow = float(
        df.iloc[0]["flow_median"]
    )

    peak_index = (
        df["flow_median"].idxmax()
    )

    peak_row = df.loc[
        peak_index
    ]

    peak_flow = float(
        peak_row["flow_median"]
    )

    peak_time = (
        peak_row["datetime"]
    )

    forecast_rise = (
        peak_flow -
        current_flow
    )

    hours_to_peak = (
        peak_time -
        df.iloc[0]["datetime"]
    ).total_seconds() / 3600.0

    return {

        "current_flow_m3s":
            round(
                current_flow,
                3
            ),

        "forecast_peak_flow_m3s":
            round(
                peak_flow,
                3
            ),

        "forecast_rise_m3s":
            round(
                forecast_rise,
                3
            ),

        "hours_to_peak":
            round(
                hours_to_peak,
                2
            ),

        "peak_time":
            peak_time.isoformat(),

        "forecast_upper_peak_m3s":
            round(
                float(
                    df.loc[
                        peak_index,
                        "flow_uncertainty_upper"
                    ]
                ),
                3,
            ),

        "forecast_lower_peak_m3s":
            round(
                float(
                    df.loc[
                        peak_index,
                        "flow_uncertainty_lower"
                    ]
                ),
                3,
            ),

        "forecast_records":
            len(df),

    }


# ============================================================================
# SINGLE STATION PROCESSOR
# ============================================================================

def process_station(
    station,
    river_id_cache,
):

    station_name = (
        station.get("title")
        or station.get("station_name")
        or "Unknown station"
    )

    station_id = get_station_id(
        station
    )

    lat, lon = get_coordinates(
        station
    )

    if lat is None or lon is None:

        return {
            "success": False,
            "station": station,
            "station_name": station_name,
            "error": "No coordinates",
        }

    try:

        # ------------------------------------------------------------
        # Find GEOGLOWS river
        # ------------------------------------------------------------

        river_id = get_river_id(
            lat,
            lon,
            river_id_cache,
        )

        if river_id is None:

            return {
                "success": False,
                "station": station,
                "station_name": station_name,
                "error":
                    "GEOGLOWS river ID not found",
            }

        # Small delay after network request.
        time.sleep(
            REQUEST_DELAY
        )

        # ------------------------------------------------------------
        # Forecast
        # ------------------------------------------------------------

        df = get_forecast(
            river_id
        )

        if df is None:

            return {
                "success": False,
                "station": station,
                "station_name": station_name,
                "error": "No forecast",
            }

        # ------------------------------------------------------------
        # Features
        # ------------------------------------------------------------

        features = (
            calculate_forecast_features(
                df
            )
        )

        result = {

            "station_id":
                station_id,

            "station_name":
                station_name,

            "basin":
                station.get(
                    "basin"
                ),

            "district_id":
                station.get(
                    "district"
                ),

            "province_id":
                station.get(
                    "province"
                ),

            "latitude":
                lat,

            "longitude":
                lon,

            "water_level_m":
                station.get(
                    "waterLevel"
                ),

            "warning_level_m":
                station.get(
                    "warningLevel"
                ),

            "danger_level_m":
                station.get(
                    "dangerLevel"
                ),

            "trend":
                (
                    station.get("steady")
                    or station.get("trend")
                    or "UNKNOWN"
                ),

            "official_status":
                station.get(
                    "status"
                ),

            "observed_at":
                station.get(
                    "waterLevelOn"
                ),

            "geoglows_river_id":
                river_id,

            "geoglows":
                features,

        }

        return {

            "success": True,

            "station":
                station,

            "station_name":
                station_name,

            "result":
                result,

        }

    except Exception as exc:

        return {

            "success": False,

            "station":
                station,

            "station_name":
                station_name,

            "error":
                str(exc),

        }


# ============================================================================
# MAIN
# ============================================================================

def main():

    records, start_dt, end_dt = (
        fetch_bipad_river_records()
    )

    stations = get_latest_stations(
        records
    )

    print(
        "\nUnique river stations:",
        len(stations)
    )

    print(
        "\nStarting GEOGLOWS matching..."
    )

    print(
        f"Parallel workers: "
        f"{GEOGLOWS_WORKERS}"
    )

    print(
        f"Retry attempts: "
        f"{MAX_RETRIES}"
    )

    # ------------------------------------------------------------
    # Load river ID cache
    # ------------------------------------------------------------

    river_id_cache = (
        load_river_id_cache()
    )

    print(
        "Cached river IDs:",
        len(river_id_cache)
    )

    results = []

    matched = 0
    failed = 0

    total = len(stations)

    completed = 0

    indexed_results = {}

    # ------------------------------------------------------------
    # Parallel station processing
    # ------------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=GEOGLOWS_WORKERS
    ) as executor:

        future_to_index = {

            executor.submit(
                process_station,
                station,
                river_id_cache,
            ): index

            for index, station
            in enumerate(
                stations
            )

        }

        for future in as_completed(
            future_to_index
        ):

            index = (
                future_to_index[
                    future
                ]
            )

            completed += 1

            try:

                result = (
                    future.result()
                )

            except Exception as exc:

                result = {

                    "success": False,

                    "station":
                        stations[index],

                    "station_name":
                        "Unknown station",

                    "error":
                        str(exc),

                }

            indexed_results[
                index
            ] = result

            station_name = (
                result.get(
                    "station_name",
                    "Unknown station"
                )
            )

            if result.get(
                "success"
            ):

                matched += 1

                features = (
                    result[
                        "result"
                    ][
                        "geoglows"
                    ]
                )

                print(

                    f"[{completed}/{total}] "
                    f"✓ {station_name} | "
                    f"current="
                    f"{features['current_flow_m3s']} | "
                    f"peak="
                    f"{features['forecast_peak_flow_m3s']} | "
                    f"rise="
                    f"{features['forecast_rise_m3s']} | "
                    f"peak_in="
                    f"{features['hours_to_peak']}h"

                )

            else:

                failed += 1

                print(

                    f"[{completed}/{total}] "
                    f"✗ {station_name} | "
                    f"{result.get('error', 'Unknown error')}"

                )

    # ------------------------------------------------------------
    # Save updated river ID cache
    # ------------------------------------------------------------

    save_river_id_cache(
        river_id_cache
    )

    print(
        "\nRiver ID cache saved:",
        len(river_id_cache)
    )

    # ------------------------------------------------------------
    # Restore original station order
    # ------------------------------------------------------------

    for index in range(
        total
    ):

        result = (
            indexed_results.get(
                index
            )
        )

        if (
            result
            and result.get("success")
        ):

            results.append(
                result["result"]
            )

    # ------------------------------------------------------------
    # Output
    # ------------------------------------------------------------

    output = {

        "project":
            "PRAVAH",

        "pipeline_version":
            "geoglows_v3_resilient",

        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "analysis_window": {

            "start_utc":
                start_dt.isoformat(),

            "end_utc":
                end_dt.isoformat(),

            "hours":
                LOOKBACK_HOURS,

        },

        "semantics": {

            "bipad":
                "Observed river water level.",

            "geoglows":
                "Forecast river discharge / streamflow.",

            "warning":
                "BIPAD warning and danger thresholds "
                "apply to observed water level only.",

            "important":
                "GEOGLOWS discharge must not be "
                "directly compared with BIPAD "
                "water-level thresholds.",

        },

        "statistics": {

            "bipad_records":
                len(records),

            "unique_stations":
                len(stations),

            "geoglows_matched":
                matched,

            "geoglows_failed":
                failed,

            "parallel_workers":
                GEOGLOWS_WORKERS,

            "retry_attempts":
                MAX_RETRIES,

            "cached_river_ids":
                len(river_id_cache),

        },

        "stations":
            results,

    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(
        "\n" + "=" * 80
    )

    print(
        "GEOGLOWS INTEGRATION COMPLETE"
    )

    print(
        "=" * 80
    )

    print(
        "BIPAD records:",
        len(records)
    )

    print(
        "Unique stations:",
        len(stations)
    )

    print(
        "GEOGLOWS matched:",
        matched
    )

    print(
        "GEOGLOWS failed:",
        failed
    )

    print(
        "Parallel workers:",
        GEOGLOWS_WORKERS
    )

    print(
        "Cached river IDs:",
        len(river_id_cache)
    )

    print(
        "Output:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()