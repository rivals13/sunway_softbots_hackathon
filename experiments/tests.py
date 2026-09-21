import requests
import json
import re
import os
import numpy as np
import rasterio

from collections import defaultdict
from datetime import datetime, timezone

from shapely.geometry import shape, Point
from rasterio.mask import mask


# ============================================================
# CONFIG
# ============================================================

RAIN_API_URL = "https://bipadportal.gov.np/api/v1/rain-trimed/"
RIVER_API_URL = "https://bipadportal.gov.np/api/v1/river-trimed/"
DISTRICT_API_URL = "https://bipadportal.gov.np/api/v1/district/"

GEOJSON_FILE = "./npl_boundaries_extracted/npl_admin2.geojson"

# ------------------------------------------------------------
# BIPAD ANALYSIS WINDOW
# ------------------------------------------------------------

START_DATE = "2026-09-10T00:00:00+05:45"
END_DATE   = "2026-09-12T00:00:00+05:45"


# ------------------------------------------------------------
# NASA
# ------------------------------------------------------------

NASA_USER = "sansar.chhetri@study.lbef.edu.np"
NASA_PASS = "sansar.chhetri@study.lbef.edu.np"

NASA_BASE_URL = (
    "https://jsimpsonhttps.pps.eosdis.nasa.gov/"
    "imerg/gis/early/2026/09/"
)

NASA_FILL_VALUE = 29999
NASA_SCALE_FACTOR = 10.0

NASA_LOCAL_FILE = "latest_imerg_30min.tif"


# ============================================================
# HELPER: NORMALIZE DISTRICT NAME
# ============================================================

def normalize_name(name):

    if not name:
        return ""

    name = str(name).strip().lower()

    name = (
        name
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace(".", "")
    )

    aliases = {

        "chitawan": "chitwan",

        "terhathum": "terathum",

        "sindhupalchowk": "sindhupalchok",

        "kapilbastu": "kapilbastu",

        "dhanusha": "dhanusa",

        "tanahun": "tanahu",

        "nawalparasieast": "nawalparasieast",
        "nawalparasiwest": "nawalparasiwest",

        "rukumeast": "rukumeast",
        "rukumwest": "rukumwest",

        "kavre": "kavrepalanchok",
        "kavrepalanchowk": "kavrepalanchok",
    }

    return aliases.get(name, name)


# ============================================================
# HEADER
# ============================================================

print("=" * 115)
print("PRAVAH - BIPAD + NASA MULTI-SOURCE DISTRICT DATA FUSION")
print("=" * 115)


# ============================================================
# 1. LOAD GEOJSON
# ============================================================

print("\n[1] Loading GeoJSON districts...")

with open(GEOJSON_FILE, "r", encoding="utf-8") as f:
    geojson = json.load(f)

geojson_districts = []

for feature in geojson.get("features", []):

    props = feature.get("properties", {})
    geometry = feature.get("geometry")

    if not geometry:
        continue

    name = props.get("adm2_name")
    pcode = props.get("adm2_pcode")

    geojson_districts.append({
        "name": name,
        "pcode": pcode,
        "geometry": shape(geometry)
    })

print(
    f"GeoJSON districts loaded: "
    f"{len(geojson_districts)}"
)


# ============================================================
# 2. FETCH BIPAD DISTRICTS
# ============================================================

print("\n[2] Fetching BIPAD district list...")

response = requests.get(
    DISTRICT_API_URL,
    params={"limit": 1000},
    timeout=30
)

response.raise_for_status()

district_response = response.json()

bipad_districts = {}

for item in district_response.get("results", []):

    district_id = item.get("id")

    if district_id is None:
        continue

    district_id = int(district_id)

    title = (
        item.get("title_en")
        or item.get("title")
        or ""
    )

    bipad_districts[district_id] = {

        "id": district_id,

        "name": title,

        "normalized":
            normalize_name(title)
    }


print(
    f"BIPAD district records: "
    f"{len(bipad_districts)}"
)


# ============================================================
# 3. GEOJSON → BIPAD ID
# ============================================================

print("\n[3] Standardizing GeoJSON districts to BIPAD IDs...")

bipad_name_to_id = {}

for district_id, district in bipad_districts.items():

    normalized = district["normalized"]

    if normalized:

        bipad_name_to_id[normalized] = district_id


geojson_to_bipad = {}
mapping_failures = []

for district in geojson_districts:

    geo_name = district["name"]

    normalized = normalize_name(geo_name)

    bipad_id = bipad_name_to_id.get(normalized)

    if bipad_id is None:

        mapping_failures.append({
            "geojson_name": geo_name,
            "normalized": normalized
        })

        continue

    geojson_to_bipad[geo_name] = bipad_id


print(
    f"Successfully mapped: "
    f"{len(geojson_to_bipad)} / "
    f"{len(geojson_districts)}"
)


if mapping_failures:

    print("\nMAPPING FAILURES:")

    for item in mapping_failures:

        print(
            f"  {item['geojson_name']}"
            f" -> {item['normalized']}"
        )

else:

    print(
        "SUCCESS: Every GeoJSON district has a BIPAD ID."
    )


# ============================================================
# 4. POINT → BIPAD DISTRICT
# ============================================================

def find_bipad_district(lon, lat):

    point = Point(lon, lat)

    for district in geojson_districts:

        if district["geometry"].contains(point):

            geo_name = district["name"]

            return geojson_to_bipad.get(
                geo_name
            )

    return None


# ============================================================
# 5. FETCH BIPAD RAINFALL
# ============================================================

print("\n[4] Fetching BIPAD rainfall...")

rain_params = {

    "measured_on__gt":
        START_DATE,

    "measured_on__lt":
        END_DATE,

    "trim_type":
        "daily",

    "trim_by":
        "avg",

    "limit":
        1000
}

response = requests.get(
    RAIN_API_URL,
    params=rain_params,
    timeout=30
)

response.raise_for_status()

rain_data = response.json()

rain_records = rain_data.get(
    "results",
    []
)

print(
    f"Rainfall records received: "
    f"{len(rain_records)}"
)


# ============================================================
# 6. PROCESS BIPAD RAINFALL
# ============================================================

rain_by_district = defaultdict(list)

usable_rain = 0
unmapped_rain = 0
invalid_rain = 0

for record in rain_records:

    rain_1h = None

    for average in record.get("averages", []):

        if average.get("interval") == 1:

            rain_1h = average.get("value")

            break

    if rain_1h is None:

        invalid_rain += 1

        continue

    try:

        rain_1h = float(rain_1h)

    except (TypeError, ValueError):

        invalid_rain += 1

        continue


    point_data = record.get("point")

    if not point_data:

        invalid_rain += 1

        continue

    coordinates = point_data.get("coordinates")

    if not coordinates or len(coordinates) < 2:

        invalid_rain += 1

        continue

    lon = coordinates[0]
    lat = coordinates[1]


    bipad_id = find_bipad_district(
        lon,
        lat
    )

    if bipad_id is None:

        unmapped_rain += 1

        continue


    usable_rain += 1

    rain_by_district[bipad_id].append({

        "value": rain_1h,

        "station":
            record.get("station")
            or record.get("stationName")
            or "Unknown",

        "station_series_id":
            record.get("stationSeriesId"),

        "measured_on":
            record.get("measuredOn"),

        "lat":
            lat,

        "lon":
            lon,

        "source":
            "BIPAD"
    })


print(
    f"Usable 1-hour rainfall: "
    f"{usable_rain}"
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
    f"Rainfall district IDs: "
    f"{len(rain_by_district)}"
)


# ============================================================
# 7. FETCH BIPAD RIVER
# ============================================================

print("\n[5] Fetching BIPAD river data...")

river_params = {

    "water_level_on__gt":
        START_DATE,

    "water_level_on__lt":
        END_DATE,

    "limit":
        1000
}

response = requests.get(
    RIVER_API_URL,
    params=river_params,
    timeout=30
)

response.raise_for_status()

river_data = response.json()

river_records = river_data.get(
    "results",
    []
)

print(
    f"River records received: "
    f"{len(river_records)}"
)


# ============================================================
# 8. KEEP LATEST RIVER RECORD
# ============================================================

latest_river = {}

for record in river_records:

    station_series_id = record.get(
        "stationSeriesId"
    )

    station_id = record.get(
        "station"
    )

    station_key = (
        station_series_id
        if station_series_id is not None
        else station_id
    )

    if station_key is None:
        continue

    timestamp = record.get(
        "waterLevelOn"
    )

    if not timestamp:
        continue

    previous = latest_river.get(
        station_key
    )

    if (
        previous is None
        or timestamp > previous.get(
            "waterLevelOn",
            ""
        )
    ):

        latest_river[station_key] = record


print(
    f"Unique river stations: "
    f"{len(latest_river)}"
)


# ============================================================
# 9. PROCESS RIVER
# ============================================================

river_by_district = defaultdict(list)

anomalous_river = 0
suspicious_threshold = 0
invalid_river = 0
valid_river = 0

for record in latest_river.values():

    water = record.get("waterLevel")
    warning = record.get("warningLevel")
    danger = record.get("dangerLevel")
    district_id = record.get("district")

    if (
        water is None
        or district_id is None
    ):

        invalid_river += 1

        continue

    try:

        water = float(water)

        if warning is not None:
            warning = float(warning)

        if danger is not None:
            danger = float(danger)

        district_id = int(district_id)

    except (TypeError, ValueError):

        invalid_river += 1

        continue


    if abs(water) > 1000:

        anomalous_river += 1

        continue


    if (
        warning is not None
        and danger is not None
        and danger < warning
    ):

        suspicious_threshold += 1

        continue


    if district_id not in bipad_districts:

        invalid_river += 1

        continue


    status = "RIVER NORMAL"

    if (
        danger is not None
        and water >= danger
    ):

        status = "RIVER DANGER"

    elif (
        warning is not None
        and water >= warning
    ):

        status = "RIVER WARNING"


    valid_river += 1

    river_by_district[district_id].append({

        "station":
            record.get("title")
            or record.get("station")
            or "Unknown",

        "station_id":
            record.get("station"),

        "station_series_id":
            record.get("stationSeriesId"),

        "water":
            water,

        "warning":
            warning,

        "danger":
            danger,

        "status":
            status,

        "trend":
            record.get("steady"),

        "observed_at":
            record.get("waterLevelOn"),

        "source":
            record.get("dataSource")
    })


print(
    f"Valid river observations: "
    f"{valid_river}"
)

print(
    f"Invalid river observations: "
    f"{invalid_river}"
)

print(
    f"Anomalous river observations skipped: "
    f"{anomalous_river}"
)

print(
    f"Suspicious threshold observations skipped: "
    f"{suspicious_threshold}"
)


# ============================================================
# 10. NASA - FIND LATEST IMERG FILE
# ============================================================

print("\n[6] Finding latest NASA IMERG Early Run file...")

try:

    response = requests.get(
        NASA_BASE_URL,
        auth=(NASA_USER, NASA_PASS),
        timeout=30
    )

    response.raise_for_status()

except Exception as e:

    print("NASA directory request failed:")
    print(e)

    raise SystemExit(1)


tif_links = re.findall(
    r'href=["\']([^"\']+\.tif)["\']',
    response.text,
    re.IGNORECASE
)


# Keep only 30-minute IMERG files
tif_files = [
    filename
    for filename in tif_links
    if ".30min.tif" in filename
]


if not tif_files:

    print("ERROR: No NASA 30-minute TIFF files found.")

    raise SystemExit(1)


# Sort by filename timestamp
tif_files.sort()

latest_tif = tif_files[-1]

nasa_download_url = (
    NASA_BASE_URL
    + latest_tif
)


print(
    f"30-minute TIFF files found: "
    f"{len(tif_files)}"
)

print(
    f"Latest NASA file: "
    f"{latest_tif}"
)


# ============================================================
# 11. DOWNLOAD NASA FILE
# ============================================================

print("\n[7] Downloading NASA IMERG file...")

response = requests.get(
    nasa_download_url,
    auth=(NASA_USER, NASA_PASS),
    timeout=120,
    stream=True
)

response.raise_for_status()

with open(NASA_LOCAL_FILE, "wb") as f:

    for chunk in response.iter_content(
        chunk_size=1024 * 1024
    ):

        if chunk:

            f.write(chunk)


file_size_mb = (
    os.path.getsize(NASA_LOCAL_FILE)
    / (1024 * 1024)
)

print(
    f"NASA file downloaded: "
    f"{NASA_LOCAL_FILE}"
)

print(
    f"File size: "
    f"{file_size_mb:.2f} MB"
)


# ============================================================
# 12. NASA DISTRICT EXTRACTION
# ============================================================

print("\n[8] Extracting NASA rainfall by district...")

nasa_by_district = {}

with rasterio.open(NASA_LOCAL_FILE) as src:

    print(
        f"NASA raster: "
        f"{src.width} x {src.height}"
    )

    print(
        f"NASA resolution: "
        f"{src.res}"
    )

    print(
        f"NASA CRS: "
        f"{src.crs}"
    )

    # --------------------------------------------------------
    # Make sure GeoJSON CRS matches NASA
    # --------------------------------------------------------

    # Your GeoJSON is already EPSG:4326.
    # NASA raster is also EPSG:4326.

    for district in geojson_districts:

        district_name = district["name"]

        bipad_id = geojson_to_bipad.get(
            district_name
        )

        if bipad_id is None:
            continue


        try:

            clipped, _ = mask(
                src,
                [district["geometry"]],
                crop=True
            )

            raw = clipped[0]

            # --------------------------------------------
            # Remove NASA fill value
            # --------------------------------------------

            valid_raw = raw[
                raw != NASA_FILL_VALUE
            ]

            if len(valid_raw) == 0:

                nasa_by_district[bipad_id] = {

                    "avg_mm": None,

                    "max_mm": None,

                    "valid_pixels": 0,

                    "rain_pixels": 0,

                    "source": "NASA IMERG Early"
                }

                continue


            # --------------------------------------------
            # Convert raw → mm
            # --------------------------------------------

            rainfall_mm = (
                valid_raw.astype(float)
                / NASA_SCALE_FACTOR
            )


            # --------------------------------------------
            # IMPORTANT:
            # Average ALL valid pixels
            # --------------------------------------------

            avg_mm = float(
                rainfall_mm.mean()
            )

            max_mm = float(
                rainfall_mm.max()
            )

            rain_pixels = int(
                (rainfall_mm > 0).sum()
            )


            nasa_by_district[bipad_id] = {

                "avg_mm": avg_mm,

                "max_mm": max_mm,

                "valid_pixels":
                    int(len(valid_raw)),

                "rain_pixels":
                    rain_pixels,

                "source":
                    "NASA IMERG Early",

                "file":
                    latest_tif
            }


        except Exception as e:

            print(
                f"NASA extraction failed for "
                f"{district_name}: {e}"
            )

            nasa_by_district[bipad_id] = {

                "avg_mm": None,

                "max_mm": None,

                "valid_pixels": 0,

                "rain_pixels": 0,

                "source": "NASA IMERG Early"
            }


print(
    f"NASA districts processed: "
    f"{len(nasa_by_district)}"
)


# ============================================================
# 13. BUILD FUSED 77-DISTRICT DATASET
# ============================================================

print("\n[9] Building fused 77-district dataset...")

district_data = {}


for district_id, district_info in bipad_districts.items():

    district_name = district_info["name"]


    # ========================================================
    # BIPAD RAIN
    # ========================================================

    rain_stations = rain_by_district.get(
        district_id,
        []
    )

    rain_values = [

        station["value"]

        for station in rain_stations
    ]


    if rain_values:

        bipad_rain_max = max(
            rain_values
        )

        bipad_rain_avg = (
            sum(rain_values)
            / len(rain_values)
        )

    else:

        bipad_rain_max = None
        bipad_rain_avg = None


    # ========================================================
    # NASA RAIN
    # ========================================================

    nasa = nasa_by_district.get(
        district_id,
        {}
    )

    nasa_avg = nasa.get(
        "avg_mm"
    )

    nasa_max = nasa.get(
        "max_mm"
    )

    nasa_valid_pixels = nasa.get(
        "valid_pixels",
        0
    )

    nasa_rain_pixels = nasa.get(
        "rain_pixels",
        0
    )


    # ========================================================
    # RIVER
    # ========================================================

    river_stations = river_by_district.get(
        district_id,
        []
    )

    river_status = (
        "NO VALID RIVER DATA"
    )

    river_trigger = None


    if river_stations:

        danger_records = [

            r
            for r in river_stations

            if r["status"]
            == "RIVER DANGER"
        ]

        warning_records = [

            r
            for r in river_stations

            if r["status"]
            == "RIVER WARNING"
        ]


        if danger_records:

            river_status = (
                "RIVER DANGER"
            )

            river_trigger = max(
                danger_records,
                key=lambda r: r["water"]
            )


        elif warning_records:

            river_status = (
                "RIVER WARNING"
            )

            river_trigger = max(
                warning_records,
                key=lambda r: r["water"]
            )


        else:

            river_status = (
                "RIVER NORMAL"
            )


    # ========================================================
    # DISTRICT OBJECT
    # ========================================================

    district_data[district_id] = {

        "district_id":
            district_id,

        "district":
            district_name,

        "rainfall": {

            "bipad_1h_max":
                bipad_rain_max,

            "bipad_1h_avg":
                bipad_rain_avg,

            "bipad_station_count":
                len(rain_stations),

            "nasa_30min_avg":
                nasa_avg,

            "nasa_30min_max":
                nasa_max,

            "nasa_valid_pixels":
                nasa_valid_pixels,

            "nasa_rain_pixels":
                nasa_rain_pixels,

            "nasa_file":
                latest_tif
        },

        "river": {

            "status":
                river_status,

            "station_count":
                len(river_stations),

            "trigger":
                river_trigger,

            "stations":
                river_stations
        }
    }


# ============================================================
# 14. PRINT FUSED SUMMARY
# ============================================================

print()
print("=" * 125)
print("PRAVAH - BIPAD + NASA FUSED DISTRICT DATA")
print("=" * 125)

print(
    f"{'ID':<6}"
    f"{'DISTRICT':<23}"
    f"{'BIPAD 1H':>12}"
    f"{'NASA AVG':>12}"
    f"{'NASA MAX':>12}"
    f"{'RIVER':>22}"
)

print("-" * 125)


for district_id in sorted(district_data):

    result = district_data[district_id]

    bipad_max = (
        result["rainfall"]["bipad_1h_max"]
    )

    nasa_avg = (
        result["rainfall"]["nasa_30min_avg"]
    )

    nasa_max = (
        result["rainfall"]["nasa_30min_max"]
    )

    bipad_text = (
        f"{bipad_max:.2f}"
        if bipad_max is not None
        else "-"
    )

    nasa_avg_text = (
        f"{nasa_avg:.2f}"
        if nasa_avg is not None
        else "-"
    )

    nasa_max_text = (
        f"{nasa_max:.2f}"
        if nasa_max is not None
        else "-"
    )

    print(
        f"{district_id:<6}"
        f"{result['district']:<23}"
        f"{bipad_text:>12}"
        f"{nasa_avg_text:>12}"
        f"{nasa_max_text:>12}"
        f"{result['river']['status']:>22}"
    )


# ============================================================
# 15. TOP NASA DISTRICTS
# ============================================================

print()
print("=" * 100)
print("TOP 10 DISTRICTS BY NASA MAXIMUM")
print("=" * 100)

valid_nasa = [

    result

    for result in district_data.values()

    if result["rainfall"]["nasa_30min_max"]
    is not None
]


valid_nasa.sort(
    key=lambda x:
        x["rainfall"]["nasa_30min_max"],
    reverse=True
)


for i, result in enumerate(
    valid_nasa[:10],
    1
):

    print(

        f"{i:2}. "
        f"{result['district']:<23} "

        f"NASA AVG: "
        f"{result['rainfall']['nasa_30min_avg']:>6.2f} mm | "

        f"NASA MAX: "
        f"{result['rainfall']['nasa_30min_max']:>6.2f} mm"
    )


# ============================================================
# 16. RIVER SIGNALS
# ============================================================

print()
print("=" * 100)
print("DISTRICTS WITH RIVER WARNING / DANGER")
print("=" * 100)

river_signal_count = 0

for district_id in sorted(district_data):

    result = district_data[district_id]

    status = result["river"]["status"]

    if status not in [
        "RIVER WARNING",
        "RIVER DANGER"
    ]:

        continue

    river_signal_count += 1

    trigger = result["river"]["trigger"]

    print(
        f"\n{result['district']} "
        f"(BIPAD ID {district_id})"
    )

    print(
        f"Status: {status}"
    )

    if trigger:

        print(
            f"Station: "
            f"{trigger['station']}"
        )

        print(
            f"Water: "
            f"{trigger['water']:.3f}"
        )

        print(
            f"Warning: "
            f"{trigger['warning']}"
        )

        print(
            f"Danger: "
            f"{trigger['danger']}"
        )

        print(
            f"Trend: "
            f"{trigger['trend']}"
        )

        print(
            f"Observed: "
            f"{trigger['observed_at']}"
        )


if river_signal_count == 0:

    print(
        "No current river warning/danger "
        "signals after QC."
    )


# ============================================================
# 17. FINAL VALIDATION
# ============================================================

print()
print("=" * 115)
print("FINAL PRAVAH VALIDATION")
print("=" * 115)

print(
    f"GeoJSON districts:              "
    f"{len(geojson_districts)}"
)

print(
    f"BIPAD districts:                "
    f"{len(bipad_districts)}"
)

print(
    f"GeoJSON → BIPAD mappings:        "
    f"{len(geojson_to_bipad)}"
)

print(
    f"Mapping failures:                "
    f"{len(mapping_failures)}"
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
    f"NASA districts:                 "
    f"{len(nasa_by_district)}"
)

print(
    f"Final fused districts:          "
    f"{len(district_data)}"
)

print(
    f"River warning/danger districts: "
    f"{river_signal_count}"
)


# ============================================================
# 18. SUCCESS CHECK
# ============================================================

print()

if (

    len(geojson_districts) == 77

    and len(bipad_districts) == 77

    and len(geojson_to_bipad) == 77

    and len(mapping_failures) == 0

    and len(district_data) == 77

    and len(nasa_by_district) == 77

):

    print(
        "SUCCESS!"
    )

    print(
        "PRAVAH now has a complete 77-district "
        "BIPAD + NASA fused dataset."
    )

else:

    print(
        "CHECK REQUIRED:"
    )

    print(
        "One or more data sources did not "
        "produce a complete 77-district dataset."
    )


print()
print("=" * 115)
print("END OF PRAVAH DATA FUSION")
print("=" * 115)