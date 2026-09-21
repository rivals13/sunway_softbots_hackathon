#!/usr/bin/env python3
"""
PRAVAH - LIVE BIPAD + NASA IMERG DATA FUSION

Purpose
-------
Fetch and align:

1. BIPAD rainfall observations
   - Ground-station observations
   - Used as LOCAL rainfall evidence
   - Preserved separately from NASA rainfall

2. BIPAD river observations
   - Ground-station water-level observations
   - Used as river evidence for later risk analysis

3. NASA IMERG Early Run rainfall
   - 30-minute satellite rainfall
   - Aggregated spatially by Nepal district
   - Used as the primary district-level rainfall input
     for the later SCS-CN runoff model

IMPORTANT
---------
BIPAD rainfall and NASA rainfall are NOT mathematically combined
using max(BIPAD, NASA).

They represent different:

    - spatial measurements
    - temporal windows
    - observation methods

Therefore PRAVAH keeps them as separate evidence streams.

Current downstream architecture:

    BIPAD rainfall ───────────────┐
                                  │
    NASA rainfall → SCS-CN → Runoff
                                  │
    BIPAD river ──────────────────┤
                                  │
    ICIMOD forecast ──────────────┤
                                  ↓
                             Risk Engine

Current runoff input recommendation:

    P = NASA district-level 6-hour rainfall

BIPAD rainfall is preserved for local observation evidence
and later risk fusion.

Requirements
------------
pip install requests numpy shapely rasterio

NASA credentials
----------------
export NASA_USER="your_nasa_username"
export NASA_PASS="your_nasa_password"

Run
---
python fusion_aligned.py
"""

import os
import re
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import numpy as np
import requests

from shapely.geometry import shape, Point

import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds


# ============================================================
# CONFIGURATION
# ============================================================

RAIN_API_URL = (
    "https://bipadportal.gov.np/api/v1/rain-trimed/"
)

RIVER_API_URL = (
    "https://bipadportal.gov.np/api/v1/river-trimed/"
)

DISTRICT_API_URL = (
    "https://bipadportal.gov.np/api/v1/district/"
)

GEOJSON_FILE = (
    "./npl_boundaries_extracted/npl_admin2.geojson"
)

# NASA rolling analysis window.
#
# IMPORTANT:
# This controls the historical NASA data searched/processed.
#
# It does NOT guarantee that a complete 24-hour NASA record
# exists. If fewer than 48 continuous 30-minute observations
# are available, NASA 24h will correctly remain null.
WINDOW_HOURS = 24


# NASA IMERG Early Run directory.
NASA_BASE_TEMPLATE = (
    "https://jsimpsonhttps.pps.eosdis.nasa.gov/"
    "imerg/gis/early/{year:04d}/{month:02d}/"
)

NASA_USER = os.getenv("NASA_USER", "")
NASA_PASS = os.getenv("NASA_PASS", "")


# NASA V07C GIS files currently use scaled rainfall values.
NASA_FILL_VALUE = 29999
NASA_SCALE_FACTOR = 10.0


# ------------------------------------------------------------
# Freshness thresholds
# ------------------------------------------------------------

# NASA Early Run naturally has several hours of latency.
# 6 hours is therefore used as an operational freshness
# threshold for the satellite source.
NASA_FRESHNESS_THRESHOLD_MIN = 360


# BIPAD is expected to be much closer to real-time.
# This threshold is intentionally strict.
BIPAD_FRESHNESS_THRESHOLD_MIN = 120


# Output
OUTPUT_JSON = "prava_live_fused_data.json"


# ============================================================
# HELPERS
# ============================================================

def utc_now():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def normalize_name(name):
    """
    Normalize district names so GeoJSON and BIPAD names
    can be matched reliably.
    """

    if not name:
        return ""

    value = str(name).strip().lower()

    value = (
        value.replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace(".", "")
    )

    aliases = {
        "chitawan": "chitwan",
        "terhathum": "terathum",
        "tehrathum": "terathum",

        "sindhupalchowk": "sindhupalchok",

        "dhanusha": "dhanusa",

        "tanahun": "tanahu",

        "kavre": "kavrepalanchok",
        "kavrepalanchowk": "kavrepalanchok",

        "kapilvastu": "kapilbastu",

        "rukumeast": "rukumeast",
        "rukumwest": "rukumwest",

        "nawalparasieast": "nawalparasieast",
        "nawalparasiwest": "nawalparasiwest",

        "ktm": "kathmandu",
    }

    return aliases.get(value, value)


def safe_float(value):
    """Convert value to finite float or None."""

    try:

        if value is None:
            return None

        number = float(value)

        if not np.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):

        return None


def parse_dt(value):
    """Parse ISO timestamp and normalize to UTC."""

    if not value:
        return None

    try:

        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:

        return None


def nepali_iso(dt):
    """Convert UTC datetime to Nepal time."""

    return dt.astimezone(
        timezone(
            timedelta(
                hours=5,
                minutes=45
            )
        )
    ).isoformat()


def age_minutes(observed_at, now):
    """Calculate observation age in minutes."""

    if observed_at is None:
        return None

    return round(
        (
            now - observed_at
        ).total_seconds() / 60.0,
        1
    )


def freshness_status(
    age_minutes_value,
    threshold_minutes
):
    """
    Classify source freshness.

    FRESH:
        Observation is within configured threshold.

    STALE:
        Observation exists but is older than threshold.

    NO_DATA:
        No observation timestamp exists.
    """

    if age_minutes_value is None:
        return "NO_DATA"

    if age_minutes_value <= threshold_minutes:
        return "FRESH"

    return "STALE"


# ============================================================
# START
# ============================================================

print("=" * 115)
print("PRAVAH - LIVE BIPAD + NASA DATA FUSION")
print("=" * 115)

print()
print("Architecture:")
print("  NASA rainfall   -> district rainfall -> future SCS-CN runoff")
print("  BIPAD rainfall  -> local ground observation evidence")
print("  BIPAD river     -> river observation evidence")
print("  Later ICIMOD    -> forecast/validation evidence")
print("  Risk Engine     -> final evidence fusion")
print()
print("IMPORTANT:")
print("  BIPAD rainfall and NASA rainfall are NOT combined using max().")
print("  They are preserved as separate measurements.")
print("=" * 115)


# ============================================================
# [1] LOAD GEOJSON
# ============================================================

print("\n[1] Loading GeoJSON districts...")

with open(
    GEOJSON_FILE,
    "r",
    encoding="utf-8"
) as f:

    geojson = json.load(f)


geojson_districts = []

for feature in geojson.get(
    "features",
    []
):

    props = feature.get(
        "properties",
        {}
    )

    geometry = feature.get(
        "geometry"
    )

    if not geometry:
        continue

    district_name = (
        props.get("adm2_name")
        or props.get("name")
        or props.get("district")
    )

    pcode = props.get(
        "adm2_pcode"
    )

    geojson_districts.append({

        "name": district_name,

        "normalized": normalize_name(
            district_name
        ),

        "pcode": pcode,

        "geometry": geometry,

        "shape": shape(
            geometry
        ),

    })


print(
    f"GeoJSON districts loaded: "
    f"{len(geojson_districts)}"
)


# ============================================================
# [2] BIPAD DISTRICTS
# ============================================================

print("\n[2] Fetching BIPAD district list...")

session = requests.Session()

session.headers.update({
    "User-Agent": "PRAVAH/1.0"
})


response = session.get(
    DISTRICT_API_URL,
    timeout=30
)

response.raise_for_status()

district_payload = response.json()

bipad_records = district_payload.get(
    "results",
    district_payload
)

if isinstance(
    bipad_records,
    dict
):

    bipad_records = bipad_records.get(
        "results",
        []
    )


print(
    f"BIPAD district records: "
    f"{len(bipad_records)}"
)


bipad_by_name = {}

for record in bipad_records:

    name = (
        record.get("title")
        or record.get("name")
        or record.get("district")
    )

    district_id = (
        record.get("id")
        or record.get("district")
    )

    if (
        name is not None
        and district_id is not None
    ):

        bipad_by_name[
            normalize_name(name)
        ] = {

            "id": district_id,

            "name": name,

        }


# ============================================================
# [3] GEOJSON -> BIPAD MAPPING
# ============================================================

print(
    "\n[3] Mapping GeoJSON districts to BIPAD IDs..."
)

geojson_to_bipad = {}

mapping_failures = []

for district in geojson_districts:

    key = district["normalized"]

    match = bipad_by_name.get(
        key
    )

    if match:

        geojson_to_bipad[
            match["id"]
        ] = district

        district["bipad_id"] = (
            match["id"]
        )

    else:

        mapping_failures.append(
            district["name"]
        )


print(
    f"Successfully mapped: "
    f"{len(geojson_to_bipad)} / "
    f"{len(geojson_districts)}"
)


if mapping_failures:

    print("Mapping failures:")

    for name in mapping_failures:

        print(
            "  -",
            name
        )

else:

    print(
        "SUCCESS: Every GeoJSON district "
        "has a BIPAD ID."
    )


# ============================================================
# DETERMINE CURRENT ROLLING WINDOW
# ============================================================

now_utc = utc_now()

window_start_utc = (
    now_utc
    - timedelta(
        hours=WINDOW_HOURS
    )
)


print("\n" + "=" * 115)
print("LIVE TEMPORAL WINDOW")
print("=" * 115)

print(
    f"Current UTC:       "
    f"{now_utc.isoformat()}"
)

print(
    f"Current NPT:       "
    f"{nepali_iso(now_utc)}"
)

print()

print(
    f"Rolling search start UTC: "
    f"{window_start_utc.isoformat()}"
)

print(
    f"Rolling search start NPT: "
    f"{nepali_iso(window_start_utc)}"
)

print()

print(
    "NASA files will be discovered from the latest "
    "directories actually available."
)


# ============================================================
# [4] BIPAD RAINFALL
# ============================================================

print(
    "\n[4] Fetching latest BIPAD rainfall..."
)


rain_params = {

    "measured_on__gt":
        nepali_iso(
            window_start_utc
        ),

    "measured_on__lt":
        nepali_iso(
            now_utc
        ),

    "trim_type":
        "daily",

    "trim_by":
        "avg",

    "limit":
        1000,

}


rain_response = session.get(
    RAIN_API_URL,
    params=rain_params,
    timeout=30
)

rain_response.raise_for_status()

rain_payload = rain_response.json()

rain_records = rain_payload.get(
    "results",
    rain_payload
)

if isinstance(
    rain_records,
    dict
):

    rain_records = rain_records.get(
        "results",
        []
    )


print(
    f"Rainfall records received: "
    f"{len(rain_records)}"
)


rain_by_district = defaultdict(list)

latest_bipad_rain_time = None

invalid_rain = 0

unmapped_rain = 0


for record in rain_records:

    averages = (
        record.get("averages")
        or []
    )

    rain_1h = None

    for item in averages:

        if item.get("interval") == 1:

            rain_1h = safe_float(

                item.get("value")
                if item.get("value") is not None
                else item.get("average")

            )

            break


    if (
        rain_1h is None
        or rain_1h < 0
    ):

        invalid_rain += 1

        continue


    district_id = (

        record.get("district")
        or record.get("districtId")
        or record.get("district_id")

    )


    if isinstance(
        district_id,
        dict
    ):

        district_id = district_id.get(
            "id"
        )


    # --------------------------------------------------------
    # Fallback: point-in-polygon
    # --------------------------------------------------------

    if district_id is None:

        point = record.get(
            "point"
        )

        coordinates = (
            point.get("coordinates")
            if isinstance(
                point,
                dict
            )
            else None
        )

        if (
            coordinates
            and len(coordinates) >= 2
        ):

            lon, lat = coordinates[:2]

            station_point = Point(
                lon,
                lat
            )

            for district in geojson_districts:

                if district["shape"].contains(
                    station_point
                ):

                    district_id = (
                        district.get(
                            "bipad_id"
                        )
                    )

                    break


    if district_id is None:

        unmapped_rain += 1

        continue


    measured_on = parse_dt(

        record.get("measuredOn")
        or record.get("measured_on")

    )


    if measured_on is not None:

        if (
            latest_bipad_rain_time is None
            or measured_on >
            latest_bipad_rain_time
        ):

            latest_bipad_rain_time = (
                measured_on
            )


    rain_by_district[
        district_id
    ].append({

        "rain_1h":
            rain_1h,

        "measured_on":
            (
                measured_on.isoformat()
                if measured_on
                else (
                    record.get("measuredOn")
                    or record.get("measured_on")
                )
            ),

        "station":
            (
                record.get("title")
                or record.get("station")
                or "Unknown"
            ),

    })


print(
    f"Usable 1-hour rainfall: "
    f"{sum(len(v) for v in rain_by_district.values())}"
)

print(
    f"Invalid rainfall records: "
    f"{invalid_rain}"
)

print(
    f"Unmapped rainfall: "
    f"{unmapped_rain}"
)

print(
    f"Rainfall districts: "
    f"{len(rain_by_district)}"
)


# ============================================================
# [5] BIPAD RIVER
# ============================================================

print(
    "\n[5] Fetching latest BIPAD river data..."
)


river_params = {

    "water_level_on__gt":
        nepali_iso(
            window_start_utc
        ),

    "water_level_on__lt":
        nepali_iso(
            now_utc
        ),

    "limit":
        1000,

}


river_response = session.get(
    RIVER_API_URL,
    params=river_params,
    timeout=30
)

river_response.raise_for_status()

river_payload = river_response.json()

river_records = river_payload.get(
    "results",
    river_payload
)

if isinstance(
    river_records,
    dict
):

    river_records = river_records.get(
        "results",
        []
    )


print(
    f"River records received: "
    f"{len(river_records)}"
)


# Keep newest valid observation for each station.
latest_station = {}

latest_bipad_river_time = None


for record in river_records:

    station_id = (

        record.get("station")
        or record.get("stationId")
        or record.get("station_id")

    )


    observed_at = parse_dt(

        record.get("waterLevelOn")
        or record.get("water_level_on")

    )


    water = safe_float(

        record.get("waterLevel")
        if record.get("waterLevel") is not None
        else record.get("water_level")

    )


    warning = safe_float(

        record.get("warning")
        if record.get("warning") is not None
        else record.get("warningLevel")

    )


    danger = safe_float(

        record.get("danger")
        if record.get("danger") is not None
        else record.get("dangerLevel")

    )


    if (
        station_id is None
        or observed_at is None
        or water is None
    ):

        continue


    if abs(water) > 1000:

        continue


    if (
        warning is None
        or danger is None
    ):

        continue


    if danger < warning:

        continue


    previous = latest_station.get(
        station_id
    )


    if (
        previous is None
        or observed_at >
        previous["observed_at"]
    ):

        latest_station[
            station_id
        ] = {

            "record":
                record,

            "observed_at":
                observed_at,

            "water":
                water,

            "warning":
                warning,

            "danger":
                danger,

        }


river_by_district = defaultdict(list)


for item in latest_station.values():

    record = item["record"]


    district_id = (

        record.get("district")
        or record.get("districtId")
        or record.get("district_id")

    )


    if isinstance(
        district_id,
        dict
    ):

        district_id = district_id.get(
            "id"
        )


    if district_id is None:
        continue


    water = item["water"]

    warning = item["warning"]

    danger = item["danger"]


    if water >= danger:

        status = "RIVER DANGER"

    elif water >= warning:

        status = "RIVER WARNING"

    else:

        status = "RIVER NORMAL"


    if (
        latest_bipad_river_time is None
        or item["observed_at"] >
        latest_bipad_river_time
    ):

        latest_bipad_river_time = (
            item["observed_at"]
        )


    river_by_district[
        district_id
    ].append({

        "station":
            (
                record.get("title")
                or record.get("station")
                or "Unknown"
            ),

        "water":
            water,

        "warning":
            warning,

        "danger":
            danger,

        "status":
            status,

        "observed_at":
            item[
                "observed_at"
            ].isoformat(),

        "trend":
            record.get("steady"),

        "source":
            record.get("dataSource"),

    })


print(
    f"Unique river stations: "
    f"{len(latest_station)}"
)

print(
    f"River districts: "
    f"{len(river_by_district)}"
)


# ============================================================
# NASA CREDENTIAL CHECK
# ============================================================

if (
    not NASA_USER
    or not NASA_PASS
):

    raise SystemExit(

        "\nERROR: NASA_USER and NASA_PASS "
        "environment variables are required.\n\n"

        "Example:\n"

        '  export NASA_USER="your_nasa_username"\n'

        '  export NASA_PASS="your_nasa_password"\n'

    )


# ============================================================
# [6] NASA DIRECTORY DISCOVERY
# ============================================================

print(
    "\n[6] Discovering latest NASA "
    "IMERG Early Run files..."
)


# Check current month and previous month.
months_to_check = []


cursor = datetime(
    now_utc.year,
    now_utc.month,
    1,
    tzinfo=timezone.utc
)


for _ in range(2):

    months_to_check.append(
        (
            cursor.year,
            cursor.month
        )
    )


    previous_month = (
        cursor.month - 1
    )

    previous_year = cursor.year


    if previous_month == 0:

        previous_month = 12

        previous_year -= 1


    cursor = datetime(
        previous_year,
        previous_month,
        1,
        tzinfo=timezone.utc
    )


all_nasa_files = []


for year, month in months_to_check:

    nasa_base_url = (
        NASA_BASE_TEMPLATE.format(
            year=year,
            month=month
        )
    )


    try:

        response = session.get(
            nasa_base_url,
            auth=(
                NASA_USER,
                NASA_PASS
            ),
            timeout=30
        )

        response.raise_for_status()


        links = re.findall(

            r'href=["\']([^"\']+\.tif)["\']',

            response.text,

            re.IGNORECASE,

        )


        month_files = [

            name

            for name in links

            if ".30min.tif" in name

        ]


        print(
            f"  {year}-{month:02d}: "
            f"{len(month_files)} "
            f"30-minute files"
        )


        for filename in month_files:

            all_nasa_files.append(
                (
                    nasa_base_url,
                    filename
                )
            )


    except Exception as exc:

        print(
            f"  Could not read NASA directory "
            f"{year}-{month:02d}: {exc}"
        )


print(
    f"Total NASA 30-minute files discovered: "
    f"{len(all_nasa_files)}"
)


# ============================================================
# NASA TIMESTAMP PARSING
# ============================================================

def parse_nasa_filename(filename):
    """
    Parse IMERG filename.

    Example:

    3B-HHR-E.MS.MRG.3IMERG.
    20260913-S103000-E105959.0630.V07C.30min.tif
    """

    pattern = (

        r"3IMERG\."

        r"(\d{8})"

        r"-S(\d{6})"

        r"-E(\d{6})"

    )


    match = re.search(
        pattern,
        filename
    )


    if not match:

        return None, None


    date_text = match.group(1)

    start_text = match.group(2)

    end_text = match.group(3)


    start = datetime.strptime(

        date_text + start_text,

        "%Y%m%d%H%M%S",

    ).replace(
        tzinfo=timezone.utc
    )


    end = datetime.strptime(

        date_text + end_text,

        "%Y%m%d%H%M%S",

    ).replace(
        tzinfo=timezone.utc
    )


    return start, end


parsed_nasa_files = []


for base_url, filename in all_nasa_files:

    start, end = parse_nasa_filename(
        filename
    )


    if start is None:
        continue


    # A NASA file is usable only when:
    #
    # 1. it begins inside the rolling search window
    # 2. it has already ended
    #
    # This prevents using a future/incomplete observation.

    if (
        start >= window_start_utc
        and end <= now_utc
    ):

        parsed_nasa_files.append({

            "url":
                base_url + filename,

            "filename":
                filename,

            "start":
                start,

            "end":
                end,

        })


parsed_nasa_files.sort(
    key=lambda x: x["start"]
)


print(
    f"NASA files inside rolling window: "
    f"{len(parsed_nasa_files)}"
)


if not parsed_nasa_files:

    raise SystemExit(

        "ERROR: No NASA IMERG 30-minute "
        "files were available inside "
        "the rolling window."

    )


latest_nasa_end = (
    parsed_nasa_files[-1]["end"]
)


print()
print("LATEST NASA FILE:")

print(
    f"  {parsed_nasa_files[-1]['filename']}"
)

print(
    f"  Start UTC: "
    f"{parsed_nasa_files[-1]['start'].isoformat()}"
)

print(
    f"  End UTC:   "
    f"{latest_nasa_end.isoformat()}"
)

print(
    f"  End NPT:   "
    f"{nepali_iso(latest_nasa_end)}"
)


# ============================================================
# NASA ANALYSIS WINDOW
# ============================================================

# NASA may lag behind wall-clock time.
#
# Therefore the NASA analysis window ends at the newest
# NASA observation that actually exists.
#
# BIPAD observations are NOT assumed to cover this exact
# window. Their freshness is reported separately.

common_end_utc = latest_nasa_end

common_start_utc = (
    common_end_utc
    - timedelta(
        hours=WINDOW_HOURS
    )
)


selected_nasa_files = [

    item

    for item in parsed_nasa_files

    if (
        item["start"] >= common_start_utc
        and item["end"] <= common_end_utc
    )

]


print("\n" + "=" * 115)
print("NASA ANALYSIS WINDOW")
print("=" * 115)

print(
    f"NASA window start UTC: "
    f"{common_start_utc.isoformat()}"
)

print(
    f"NASA window end UTC:   "
    f"{common_end_utc.isoformat()}"
)

print(
    f"NASA window start NPT: "
    f"{nepali_iso(common_start_utc)}"
)

print(
    f"NASA window end NPT:   "
    f"{nepali_iso(common_end_utc)}"
)

print(
    f"NASA files selected:   "
    f"{len(selected_nasa_files)}"
)

print()

print(
    "NOTE: BIPAD observations are preserved separately "
    "and are not assumed to cover the full NASA window."
)


# ============================================================
# SOURCE FRESHNESS / LATENCY
# ============================================================

nasa_age_minutes = age_minutes(
    latest_nasa_end,
    now_utc
)


bipad_rain_age_minutes = age_minutes(
    latest_bipad_rain_time,
    now_utc
)


bipad_river_age_minutes = age_minutes(
    latest_bipad_river_time,
    now_utc
)


nasa_status = freshness_status(
    nasa_age_minutes,
    NASA_FRESHNESS_THRESHOLD_MIN
)


bipad_rain_status = freshness_status(
    bipad_rain_age_minutes,
    BIPAD_FRESHNESS_THRESHOLD_MIN
)


bipad_river_status = freshness_status(
    bipad_river_age_minutes,
    BIPAD_FRESHNESS_THRESHOLD_MIN
)


print("\nSOURCE FRESHNESS")
print("-" * 115)

print(
    f"NASA latest observation UTC:       "
    f"{latest_nasa_end.isoformat()}"
)

print(
    f"NASA latest observation NPT:       "
    f"{nepali_iso(latest_nasa_end)}"
)

print(
    f"NASA data age:                     "
    f"{nasa_age_minutes} minutes"
)

print(
    f"NASA freshness status:             "
    f"{nasa_status}"
)

print()

print(
    f"BIPAD latest rainfall UTC:         "
    f"{
        latest_bipad_rain_time.isoformat()
        if latest_bipad_rain_time
        else 'N/A'
    }"
)

print(
    f"BIPAD rainfall data age:           "
    f"{bipad_rain_age_minutes}"
    f" minutes"
)

print(
    f"BIPAD rainfall status:             "
    f"{bipad_rain_status}"
)

print()

print(
    f"BIPAD latest river UTC:            "
    f"{
        latest_bipad_river_time.isoformat()
        if latest_bipad_river_time
        else 'N/A'
    }"
)

print(
    f"BIPAD river data age:              "
    f"{bipad_river_age_minutes}"
    f" minutes"
)

print(
    f"BIPAD river status:                "
    f"{bipad_river_status}"
)

print()

print(
    "NOTE:"
)

print(
    "  NASA IMERG Early Run is latest-available "
    "satellite rainfall and may have multi-hour latency."
)

print(
    "  BIPAD rainfall is local ground-station evidence."
)

print(
    "  BIPAD river data is local river-station evidence."
)

print(
    "  Freshness is reported explicitly rather than "
    "silently treating all sources as current."
)


# ============================================================
# [7] NASA DISTRICT AGGREGATION PREPARATION
# ============================================================

print(
    "\n[7] Preparing NASA district aggregation..."
)


first_file = selected_nasa_files[0]


with session.get(

    first_file["url"],

    auth=(
        NASA_USER,
        NASA_PASS
    ),

    timeout=120,

    stream=True,

) as response:

    response.raise_for_status()


    temp_path = (
        "/tmp/prava_first_nasa.tif"
    )


    with open(
        temp_path,
        "wb"
    ) as out:

        for chunk in response.iter_content(
            chunk_size=1024 * 1024
        ):

            if chunk:
                out.write(chunk)


with rasterio.open(
    temp_path
) as src:

    nasa_crs = src.crs

    width = src.width

    height = src.height


    district_shapes = [

        (
            district["shape"],
            int(district["bipad_id"])
        )

        for district in geojson_districts

        if district.get(
            "bipad_id"
        ) is not None

    ]


    # Nepal bounds from district polygons.

    minx = min(
        d["shape"].bounds[0]
        for d in geojson_districts
    )

    miny = min(
        d["shape"].bounds[1]
        for d in geojson_districts
    )

    maxx = max(
        d["shape"].bounds[2]
        for d in geojson_districts
    )

    maxy = max(
        d["shape"].bounds[3]
        for d in geojson_districts
    )


    if str(nasa_crs) != "EPSG:4326":

        print(
            f"NASA CRS is {nasa_crs}; "
            f"unexpected CRS."
        )

        raise RuntimeError(

            f"Unexpected NASA CRS {nasa_crs}. "

            "Expected EPSG:4326 for "
            "this PRAVAH pipeline."

        )


    window = from_bounds(

        minx,
        miny,
        maxx,
        maxy,

        transform=src.transform,

    ).round_offsets().round_lengths()


    district_mask = rasterize(

        district_shapes,

        out_shape=(

            int(window.height),

            int(window.width)

        ),

        transform=src.window_transform(
            window
        ),

        fill=0,

        dtype="int32",

    )


    print(
        f"NASA full raster: "
        f"{width} x {height}"
    )

    print(
        f"NASA Nepal window: "
        f"{int(window.width)} x "
        f"{int(window.height)}"
    )

    print(
        f"Districts rasterized: "
        f"{len(district_shapes)}"
    )


# ============================================================
# [8] NASA DOWNLOAD + AGGREGATION
# ============================================================

nasa_series = defaultdict(list)

nasa_files_processed = 0

nasa_files_failed = 0

nasa_valid_pixel_values = 0

nasa_positive_pixels = 0


print(
    "\n[8] Processing NASA rainfall..."
)


for index, item in enumerate(

    selected_nasa_files,

    start=1

):

    print(

        f"\n[NASA {index}/"
        f"{len(selected_nasa_files)}] "
        f"{item['filename']}"

    )


    local_path = (
        f"/tmp/prava_nasa_{index}.tif"
    )


    try:

        # ----------------------------------------------------
        # Download
        # ----------------------------------------------------

        with session.get(

            item["url"],

            auth=(
                NASA_USER,
                NASA_PASS
            ),

            timeout=120,

            stream=True,

        ) as response:

            response.raise_for_status()


            with open(
                local_path,
                "wb"
            ) as out:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        out.write(chunk)


        # ----------------------------------------------------
        # Read raster
        # ----------------------------------------------------

        with rasterio.open(
            local_path
        ) as src:

            data = src.read(
                1,
                window=window
            )


            values = data.astype(
                np.float64
            )


            # NASA fill-value check.

            valid = (

                np.isfinite(values)

                & (
                    values
                    != NASA_FILL_VALUE
                )

                & (
                    values >= 0
                )

            )


            # Convert scaled values to mm.

            values = (
                values
                / NASA_SCALE_FACTOR
            )


            valid &= np.isfinite(
                values
            )

            valid &= (
                values >= 0
            )


            nasa_valid_pixel_values += int(
                valid.sum()
            )


            nasa_positive_pixels += int(

                (
                    (values > 0)
                    & valid
                ).sum()

            )


            valid_values = values[
                valid
            ]


            valid_districts = (
                district_mask[
                    valid
                ]
            )


            if len(valid_values) == 0:
                continue


            # ------------------------------------------------
            # Aggregate by district
            # ------------------------------------------------

            sums = np.bincount(

                valid_districts,

                weights=valid_values,

            )


            counts = np.bincount(
                valid_districts
            )


            timestamp = item["start"]


            for district_id in range(
                len(sums)
            ):

                if (
                    counts[district_id]
                    <= 0
                ):

                    continue


                district_mean = (

                    sums[district_id]
                    /
                    counts[district_id]

                )


                nasa_series[
                    district_id
                ].append({

                    "timestamp":
                        timestamp,

                    "rain_30min_mm":
                        float(
                            district_mean
                        ),

                })


        nasa_files_processed += 1


        print(
            f"  Valid pixels: "
            f"{int(valid.sum())}"
        )


    except Exception as exc:

        nasa_files_failed += 1

        print(
            f"  FAILED: {exc}"
        )


    finally:

        if os.path.exists(
            local_path
        ):

            os.remove(
                local_path
            )


# ============================================================
# NASA ROLLING ACCUMULATIONS
# ============================================================

def contiguous_accumulation(
    records,
    steps
):
    """
    Calculate accumulation from the latest N contiguous
    30-minute NASA observations.

    Example:

        2 steps  = 1 hour
        6 steps  = 3 hours
        12 steps = 6 hours
        48 steps = 24 hours

    If there are not enough continuous records,
    return None.

    This is intentional.

    None means:

        "Insufficient historical NASA observations"

    rather than:

        "zero rainfall"
    """

    if len(records) < steps:
        return None


    records = sorted(
        records,
        key=lambda x:
            x["timestamp"]
    )


    window_records = records[
        -steps:
    ]


    for i in range(
        1,
        len(window_records)
    ):

        previous = (
            window_records[
                i - 1
            ]["timestamp"]
        )

        current = (
            window_records[
                i
            ]["timestamp"]
        )


        if (
            current - previous
            != timedelta(
                minutes=30
            )
        ):

            return None


    return float(

        sum(

            item[
                "rain_30min_mm"
            ]

            for item
            in window_records

        )

    )


def latest_value(records):

    if not records:
        return None


    records = sorted(

        records,

        key=lambda x:
            x["timestamp"]

    )


    return records[
        -1
    ]["rain_30min_mm"]


# ============================================================
# BUILD FINAL 77-DISTRICT DATASET
# ============================================================

print(
    "\n" + "=" * 125
)

print(
    "PRAVAH - LIVE 77-DISTRICT FUSED DATA"
)

print(
    "=" * 125
)


district_data = {}


for district in geojson_districts:

    district_id = district.get(
        "bipad_id"
    )


    if district_id is None:
        continue


    rain_records = (
        rain_by_district.get(
            district_id,
            []
        )
    )


    river_records_for_district = (
        river_by_district.get(
            district_id,
            []
        )
    )


    nasa_records = (
        nasa_series.get(
            district_id,
            []
        )
    )


    # --------------------------------------------------------
    # BIPAD rainfall
    # --------------------------------------------------------

    # IMPORTANT:
    #
    # This is a LOCAL ground-station measurement.
    #
    # It is NOT combined with NASA 6h rainfall.
    #
    # "max" here is only across BIPAD stations within
    # the same district for the 1-hour observation.
    #
    # It does NOT mean:
    #
    # max(BIPAD 1h, NASA 6h)

    bipad_1h = (

        max(
            item["rain_1h"]
            for item in rain_records
        )

        if rain_records

        else None

    )


    # --------------------------------------------------------
    # NASA rainfall
    # --------------------------------------------------------

    # NASA is a DISTRICT-LEVEL spatial average.

    nasa_30m = latest_value(
        nasa_records
    )


    nasa_1h = contiguous_accumulation(
        nasa_records,
        2
    )


    nasa_3h = contiguous_accumulation(
        nasa_records,
        6
    )


    nasa_6h = contiguous_accumulation(
        nasa_records,
        12
    )


    nasa_24h = contiguous_accumulation(
        nasa_records,
        48
    )


    # --------------------------------------------------------
    # River status
    # --------------------------------------------------------

    if river_records_for_district:

        river_statuses = [

            item["status"]

            for item
            in river_records_for_district

        ]


        if (
            "RIVER DANGER"
            in river_statuses
        ):

            river_status = (
                "RIVER DANGER"
            )


        elif (
            "RIVER WARNING"
            in river_statuses
        ):

            river_status = (
                "RIVER WARNING"
            )


        else:

            river_status = (
                "RIVER NORMAL"
            )


    else:

        river_status = (
            "NO VALID RIVER DATA"
        )


    # --------------------------------------------------------
    # District object
    # --------------------------------------------------------

    district_data[
        district_id
    ] = {

        "district_id":
            district_id,

        "district":
            district["name"],


        # ====================================================
        # RAINFALL
        # ====================================================

        "rainfall": {

            # ------------------------------------------------
            # BIPAD
            # ------------------------------------------------
            #
            # Local ground-station evidence.
            #
            # This is deliberately NOT combined mathematically
            # with NASA rainfall.
            #
            "bipad_1h_max":
                bipad_1h,

            "bipad_station_count":
                len(rain_records),


            # ------------------------------------------------
            # NASA
            # ------------------------------------------------
            #
            # District-level spatial average.
            #
            "nasa_30min_mm":
                nasa_30m,

            "nasa_1h_mm":
                nasa_1h,

            "nasa_3h_mm":
                nasa_3h,

            "nasa_6h_mm":
                nasa_6h,

            "nasa_24h_mm":
                nasa_24h,

            "nasa_timesteps":
                len(nasa_records),

            "nasa_source":
                "NASA IMERG Early",


            # ------------------------------------------------
            # Measurement semantics
            # ------------------------------------------------

            "measurement_semantics": {

                "bipad":
                    (
                        "Local ground-station "
                        "observation. "
                        "1-hour maximum across "
                        "available stations "
                        "within the district."
                    ),

                "nasa":
                    (
                        "District-level spatial "
                        "average derived from "
                        "NASA IMERG Early Run "
                        "30-minute rainfall."
                    ),

                "fusion_rule":
                    (
                        "BIPAD and NASA rainfall "
                        "are retained separately. "
                        "They are not combined using "
                        "max() because they differ "
                        "in spatial and temporal "
                        "measurement."
                    ),

                "runoff_input":
                    (
                        "NASA 6-hour district "
                        "rainfall is the recommended "
                        "rainfall input for the "
                        "initial SCS-CN runoff engine."
                    ),

                "bipad_role":
                    (
                        "Local observation evidence "
                        "for later PRAVAH risk fusion."
                    ),

            },

        },


        # ====================================================
        # RIVER
        # ====================================================

        "river": {

            "status":
                river_status,

            "station_count":
                len(
                    river_records_for_district
                ),

            "stations":
                river_records_for_district,

        },


        # ====================================================
        # SOURCE EVIDENCE / FRESHNESS
        # ====================================================

        "source_status": {

            "nasa": {

                "age_minutes":
                    nasa_age_minutes,

                "status":
                    nasa_status,

                "latest_observation_utc":
                    latest_nasa_end.isoformat(),

            },

            "bipad_rainfall": {

                "age_minutes":
                    bipad_rain_age_minutes,

                "status":
                    bipad_rain_status,

                "latest_observation_utc":
                    (
                        latest_bipad_rain_time.isoformat()
                        if latest_bipad_rain_time
                        else None
                    ),

            },

            "bipad_river": {

                "age_minutes":
                    bipad_river_age_minutes,

                "status":
                    bipad_river_status,

                "latest_observation_utc":
                    (
                        latest_bipad_river_time.isoformat()
                        if latest_bipad_river_time
                        else None
                    ),

            },

        },


        # ====================================================
        # TIME
        # ====================================================

        "time": {

            "current_utc":
                now_utc.isoformat(),

            "common_start_utc":
                common_start_utc.isoformat(),

            "common_end_utc":
                common_end_utc.isoformat(),

            "common_start_npt":
                nepali_iso(
                    common_start_utc
                ),

            "common_end_npt":
                nepali_iso(
                    common_end_utc
                ),

        },

    }


# ============================================================
# DISPLAY
# ============================================================

print(

    f"{'ID':<6}"

    f"{'DISTRICT':<25}"

    f"{'BIPAD 1H':>12}"

    f"{'NASA 30M':>12}"

    f"{'NASA 6H':>12}"

    f"{'NASA 24H':>12}"

    f"{'RIVER':>22}"

)


print(
    "-" * 125
)


def fmt(value):

    return (

        f"{value:.2f}"

        if value is not None

        else "-"

    )


for district_id in sorted(
    district_data
):

    result = district_data[
        district_id
    ]


    print(

        f"{district_id:<6}"

        f"{result['district']:<25}"

        f"{fmt(result['rainfall']['bipad_1h_max']):>12}"

        f"{fmt(result['rainfall']['nasa_30min_mm']):>12}"

        f"{fmt(result['rainfall']['nasa_6h_mm']):>12}"

        f"{fmt(result['rainfall']['nasa_24h_mm']):>12}"

        f"{result['river']['status']:>22}"

    )


# ============================================================
# NASA DISTRICT VALIDATION
# ============================================================

expected_bipad_ids = {

    int(
        d["bipad_id"]
    )

    for d in geojson_districts

    if d.get(
        "bipad_id"
    ) is not None

}


nasa_expected_ids = (

    expected_bipad_ids

    .intersection(
        nasa_series.keys()
    )

)


nasa_extra_ids = (

    set(
        nasa_series.keys()
    )

    - expected_bipad_ids

)


# ============================================================
# NASA HISTORY AVAILABILITY
# ============================================================

districts_with_24h = 0

districts_without_24h = 0

districts_with_6h = 0


for result in district_data.values():

    rainfall = result[
        "rainfall"
    ]


    if rainfall[
        "nasa_24h_mm"
    ] is not None:

        districts_with_24h += 1

    else:

        districts_without_24h += 1


    if rainfall[
        "nasa_6h_mm"
    ] is not None:

        districts_with_6h += 1


print("\nNASA HISTORY AVAILABILITY")
print("-" * 115)

print(
    f"Districts with NASA 6h rainfall:  "
    f"{districts_with_6h}"
)

print(
    f"Districts with NASA 24h rainfall: "
    f"{districts_with_24h}"
)

print(
    f"Districts without NASA 24h:        "
    f"{districts_without_24h}"
)

if districts_without_24h > 0:

    print()

    print(
        "NOTE: NASA 24h rainfall is unavailable "
        "where fewer than 48 continuous 30-minute "
        "observations exist."
    )

    print(
        "This is treated as data insufficiency, "
        "not as zero rainfall."
    )

    print(
        "The current runoff engine can therefore "
        "continue using NASA 6h rainfall."
    )


# ============================================================
# SAVE JSON FOR NEXT PRAVAH LAYERS
# ============================================================

output = {

    "project":
        "PRAVAH",


    "pipeline_version":
        "fusion_aligned_v2",


    "generated_at_utc":
        now_utc.isoformat(),


    "generated_at_npt":
        nepali_iso(
            now_utc
        ),


    "analysis_window_hours":
        WINDOW_HOURS,


    # --------------------------------------------------------
    # NASA analysis window
    # --------------------------------------------------------

    "common_window": {

        "start_utc":
            common_start_utc.isoformat(),

        "end_utc":
            common_end_utc.isoformat(),

        "start_npt":
            nepali_iso(
                common_start_utc
            ),

        "end_npt":
            nepali_iso(
                common_end_utc
            ),

        "note":
            (
                "This is the NASA analysis window "
                "ending at the latest available NASA "
                "observation. BIPAD observations are "
                "retained separately and may have "
                "different observation ages."
            ),

    },


    # --------------------------------------------------------
    # Sources
    # --------------------------------------------------------

    "sources": {

        "bipad_rain":
            RAIN_API_URL,

        "bipad_river":
            RIVER_API_URL,

        "nasa":
            "NASA IMERG Early Run",

        "geojson":
            GEOJSON_FILE,

    },


    # --------------------------------------------------------
    # Source freshness
    # --------------------------------------------------------

    "freshness": {

        "generated_at_utc":
            now_utc.isoformat(),

        "generated_at_npt":
            nepali_iso(
                now_utc
            ),


        "nasa_latest_observation_utc":
            latest_nasa_end.isoformat(),

        "nasa_latest_observation_npt":
            nepali_iso(
                latest_nasa_end
            ),

        "nasa_age_minutes":
            nasa_age_minutes,

        "nasa_status":
            nasa_status,


        "bipad_latest_rainfall_utc":
            (
                latest_bipad_rain_time.isoformat()
                if latest_bipad_rain_time
                else None
            ),

        "bipad_rainfall_age_minutes":
            bipad_rain_age_minutes,

        "bipad_rainfall_status":
            bipad_rain_status,


        "bipad_latest_river_utc":
            (
                latest_bipad_river_time.isoformat()
                if latest_bipad_river_time
                else None
            ),

        "bipad_river_age_minutes":
            bipad_river_age_minutes,

        "bipad_river_status":
            bipad_river_status,


        "thresholds_minutes": {

            "nasa":
                NASA_FRESHNESS_THRESHOLD_MIN,

            "bipad":
                BIPAD_FRESHNESS_THRESHOLD_MIN,

        },


        "note":
            (
                "NASA IMERG Early Run is "
                "latest-available satellite "
                "rainfall and may have multi-hour "
                "processing latency. BIPAD rainfall "
                "and river timestamps represent "
                "the latest observations returned "
                "by the APIs. Source freshness is "
                "reported explicitly."
            ),

    },


    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    "statistics": {

        "geojson_districts":
            len(
                geojson_districts
            ),

        "bipad_districts":
            len(
                bipad_records
            ),

        "mapped_districts":
            len(
                geojson_to_bipad
            ),

        "bipad_rain_districts":
            len(
                rain_by_district
            ),

        "bipad_river_districts":
            len(
                river_by_district
            ),

        "nasa_files_selected":
            len(
                selected_nasa_files
            ),

        "nasa_files_processed":
            nasa_files_processed,

        "nasa_files_failed":
            nasa_files_failed,

        "nasa_valid_pixel_values":
            nasa_valid_pixel_values,

        "nasa_positive_pixels":
            nasa_positive_pixels,

        "nasa_expected_districts":
            len(
                nasa_expected_ids
            ),

        "nasa_extra_raster_ids":
            sorted(
                nasa_extra_ids
            ),

        "districts_with_nasa_6h":
            districts_with_6h,

        "districts_with_nasa_24h":
            districts_with_24h,

        "districts_without_nasa_24h":
            districts_without_24h,

    },


    # --------------------------------------------------------
    # District data
    # --------------------------------------------------------

    "districts":
        district_data,

}


with open(
    OUTPUT_JSON,
    "w",
    encoding="utf-8"
) as f:

    json.dump(

        output,

        f,

        indent=2,

        ensure_ascii=False

    )


# ============================================================
# FINAL STATUS
# ============================================================

river_signal_count = sum(

    1

    for result
    in district_data.values()

    if result["river"]["status"]

    in {

        "RIVER WARNING",
        "RIVER DANGER"

    }

)


print(
    "\n" + "=" * 115
)

print(
    "LIVE PRAVAH VALIDATION"
)

print(
    "=" * 115
)


print(
    f"GeoJSON districts:              "
    f"{len(geojson_districts)}"
)

print(
    f"BIPAD districts:                "
    f"{len(bipad_records)}"
)

print(
    f"GeoJSON -> BIPAD mappings:      "
    f"{len(geojson_to_bipad)}"
)

print(
    f"BIPAD rainfall districts:       "
    f"{len(rain_by_district)}"
)

print(
    f"BIPAD river districts:          "
    f"{len(river_by_district)}"
)

print(
    f"NASA files selected:             "
    f"{len(selected_nasa_files)}"
)

print(
    f"NASA files processed:            "
    f"{nasa_files_processed}"
)

print(
    f"NASA files failed:               "
    f"{nasa_files_failed}"
)

print(
    f"NASA districts populated:        "
    f"{len(nasa_expected_ids)} / "
    f"{len(expected_bipad_ids)}"
)


if nasa_extra_ids:

    print(
        f"NASA extra raster IDs ignored:  "
        f"{sorted(nasa_extra_ids)}"
    )


print(
    f"Final fused districts:           "
    f"{len(district_data)}"
)

print(
    f"River warning/danger districts:  "
    f"{river_signal_count}"
)


print()

print(
    f"NASA freshness:                  "
    f"{nasa_status}"
)

print(
    f"BIPAD rainfall freshness:        "
    f"{bipad_rain_status}"
)

print(
    f"BIPAD river freshness:           "
    f"{bipad_river_status}"
)


print()

print(
    f"NASA 6h districts available:     "
    f"{districts_with_6h}"
)

print(
    f"NASA 24h districts available:    "
    f"{districts_with_24h}"
)


print()

print(
    f"Saved: {OUTPUT_JSON}"
)


# ============================================================
# FINAL SUCCESS CHECK
# ============================================================

success = (

    len(geojson_districts) == 77

    and len(geojson_to_bipad) == 77

    and len(district_data) == 77

    and len(nasa_expected_ids) == 77

    and nasa_files_processed > 0

    and nasa_files_failed == 0

)


if success:

    print("\nSUCCESS!")

    print(
        "PRAVAH fusion layer completed successfully."
    )

    print()

    print(
        "Rainfall architecture:"
    )

    print(
        "  NASA 6h -> primary district rainfall "
        "input for SCS-CN runoff."
    )

    print(
        "  BIPAD 1h -> local ground-station evidence."
    )

    print(
        "  BIPAD river -> river observation evidence."
    )

    print(
        "  No BIPAD/NASA max() fusion is performed."
    )

    print()

    print(
        "The output is ready for the next layer:"
    )

    print(
        "  prava_live_fused_data.json"
    )

    print(
        "       -> runoff_engine.py"
    )

else:

    print("\nCHECK REQUIRED:")

    print(
        "One or more sources did not "
        "produce the expected result."
    )


print(
    "=" * 115
)