import requests
import json
from collections import defaultdict
from shapely.geometry import shape, Point


# ============================================================
# CONFIG
# ============================================================

RAIN_API_URL = "https://bipadportal.gov.np/api/v1/rain-trimed/"
RIVER_API_URL = "https://bipadportal.gov.np/api/v1/river-trimed/"
DISTRICT_API_URL = "https://bipadportal.gov.np/api/v1/district/"

GEOJSON_FILE = "./npl_boundaries_extracted/npl_admin2.geojson"

START_DATE = "2026-09-10T00:00:00+05:45"
END_DATE   = "2026-09-12T00:00:00+05:45"


# ============================================================
# HELPER: NORMALIZE DISTRICT NAME
# ============================================================

def normalize_name(name):

    if not name:
        return ""

    name = str(name).strip().lower()

    # Remove spaces, hyphens and punctuation
    name = (
        name
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace(".", "")
    )

    # Known spelling differences
    aliases = {

        "chitawan": "chitwan",

        "terhathum": "terathum",

        "sindhupalchowk": "sindhupalchok",

        "kapilbastu": "kapilbast u".replace(" ", ""),

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

print("=" * 100)
print("BIPAD DISTRICT-ID STANDARDIZATION + RAIN + RIVER MERGE")
print("=" * 100)


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

district_data = response.json()

bipad_districts = {}

for item in district_data.get("results", []):

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
        "normalized": normalize_name(title)
    }


print(
    f"BIPAD district records: "
    f"{len(bipad_districts)}"
)


# ============================================================
# 3. CREATE NAME → BIPAD ID LOOKUP
# ============================================================

bipad_name_to_id = {}

for district_id, district in bipad_districts.items():

    normalized = district["normalized"]

    if normalized:
        bipad_name_to_id[normalized] = district_id


# ============================================================
# 4. STANDARDIZE GEOJSON → BIPAD ID
# ============================================================

print("\n[3] Standardizing GeoJSON districts to BIPAD IDs...")

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

    print("SUCCESS: Every GeoJSON district has a BIPAD ID.")


# ============================================================
# 5. CHECK FOR DUPLICATE BIPAD IDs
# ============================================================

bipad_id_usage = defaultdict(list)

for geo_name, bipad_id in geojson_to_bipad.items():

    bipad_id_usage[bipad_id].append(geo_name)


duplicate_ids = {
    bipad_id: names
    for bipad_id, names in bipad_id_usage.items()
    if len(names) > 1
}


print()

if duplicate_ids:

    print("WARNING: Multiple GeoJSON districts map to one BIPAD ID:")

    for bipad_id, names in duplicate_ids.items():

        print(
            f"  BIPAD ID {bipad_id}: "
            f"{names}"
        )

else:

    print(
        "SUCCESS: No duplicate GeoJSON → BIPAD ID mappings."
    )


# ============================================================
# 6. POINT → STANDARDIZED BIPAD DISTRICT ID
# ============================================================

def find_bipad_district(lon, lat):

    point = Point(lon, lat)

    for district in geojson_districts:

        if district["geometry"].contains(point):

            geo_name = district["name"]

            bipad_id = geojson_to_bipad.get(
                geo_name
            )

            return bipad_id

    return None


# ============================================================
# 7. FETCH RAINFALL
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
# 8. PROCESS RAINFALL → BIPAD DISTRICT ID
# ============================================================

rain_by_district = defaultdict(list)

usable_rain = 0
unmapped_rain = 0

for record in rain_records:

    # ----------------------------------------
    # Find interval = 1
    # ----------------------------------------

    rain_1h = None

    for average in record.get("averages", []):

        if average.get("interval") == 1:

            rain_1h = average.get("value")
            break

    if rain_1h is None:
        continue


    # ----------------------------------------
    # Coordinates
    # ----------------------------------------

    point_data = record.get("point")

    if not point_data:
        continue

    coordinates = point_data.get("coordinates")

    if not coordinates or len(coordinates) < 2:
        continue

    lon = coordinates[0]
    lat = coordinates[1]


    # ----------------------------------------
    # Map to BIPAD district ID
    # ----------------------------------------

    bipad_id = find_bipad_district(
        lon,
        lat
    )

    if bipad_id is None:

        unmapped_rain += 1
        continue


    usable_rain += 1

    rain_by_district[bipad_id].append({

        "value":
            float(rain_1h),

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
            lon
    })


print(
    f"Usable 1-hour rainfall: "
    f"{usable_rain}"
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
# 9. FETCH CURRENT RIVER DATA
# ============================================================

print("\n[5] Fetching time-filtered BIPAD river data...")

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
# 10. KEEP LATEST RIVER RECORD PER STATION
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
# 11. PROCESS RIVER → BIPAD DISTRICT ID
# ============================================================

river_by_district = defaultdict(list)

anomalous_river = 0
suspicious_threshold = 0
valid_river = 0

for record in latest_river.values():

    water = record.get(
        "waterLevel"
    )

    warning = record.get(
        "warningLevel"
    )

    danger = record.get(
        "dangerLevel"
    )

    district_id = record.get(
        "district"
    )

    if (
        water is None
        or district_id is None
    ):
        continue


    water = float(water)

    if warning is not None:
        warning = float(warning)

    if danger is not None:
        danger = float(danger)


    # ----------------------------------------
    # Anomaly check
    # ----------------------------------------

    if abs(water) > 1000:

        anomalous_river += 1
        continue


    # ----------------------------------------
    # Threshold check
    # ----------------------------------------

    if (
        warning is not None
        and danger is not None
        and danger < warning
    ):

        suspicious_threshold += 1
        continue


    district_id = int(district_id)


    # ----------------------------------------
    # Confirm district exists
    # ----------------------------------------

    if district_id not in bipad_districts:
        continue


    # ----------------------------------------
    # Status
    # ----------------------------------------

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
    f"Anomalous river observations skipped: "
    f"{anomalous_river}"
)

print(
    f"Suspicious threshold observations skipped: "
    f"{suspicious_threshold}"
)


# ============================================================
# 12. MERGE RAIN + RIVER BY BIPAD DISTRICT ID
# ============================================================

print("\n[6] Merging rainfall + river by BIPAD district ID...")

merged = {}

for district_id, district_info in bipad_districts.items():

    name = district_info["name"]


    # ----------------------------------------
    # Rain
    # ----------------------------------------

    rain_values = [
        x["value"]
        for x in rain_by_district.get(
            district_id,
            []
        )
    ]

    if rain_values:

        rain_max = max(rain_values)

        rain_avg = (
            sum(rain_values)
            / len(rain_values)
        )

        rain_station_count = len(
            rain_values
        )

    else:

        rain_max = None
        rain_avg = None
        rain_station_count = 0


    # ----------------------------------------
    # River
    # ----------------------------------------

    rivers = river_by_district.get(
        district_id,
        []
    )


    river_status = "NO VALID RIVER DATA"
    river_trigger = None


    if rivers:

        danger_records = [
            r for r in rivers
            if r["status"] == "RIVER DANGER"
        ]

        warning_records = [
            r for r in rivers
            if r["status"] == "RIVER WARNING"
        ]


        if danger_records:

            river_status = "RIVER DANGER"

            river_trigger = max(
                danger_records,
                key=lambda r: r["water"]
            )


        elif warning_records:

            river_status = "RIVER WARNING"

            river_trigger = max(
                warning_records,
                key=lambda r: r["water"]
            )


        else:

            river_status = "RIVER NORMAL"


    # ----------------------------------------
    # Save merged record
    # ----------------------------------------

    merged[district_id] = {

        "district_id":
            district_id,

        "district":
            name,

        "rain_max_1h":
            rain_max,

        "rain_avg_1h":
            rain_avg,

        "rain_station_count":
            rain_station_count,

        "river_status":
            river_status,

        "river_trigger":
            river_trigger
    }


# ============================================================
# 13. PRINT FINAL 77-DISTRICT TABLE
# ============================================================

print()
print("=" * 110)
print("FINAL 77-DISTRICT BIPAD MERGED DATA")
print("=" * 110)

print(
    f"{'ID':<6}"
    f"{'DISTRICT':<23}"
    f"{'RAIN MAX':>12}"
    f"{'RAIN AVG':>12}"
    f"{'RAIN STN':>10}"
    f"{'RIVER STATUS':>25}"
)

print("-" * 110)


for district_id in sorted(merged):

    result = merged[district_id]

    rain_max = result["rain_max_1h"]
    rain_avg = result["rain_avg_1h"]

    rain_max_text = (
        f"{rain_max:.2f}"
        if rain_max is not None
        else "-"
    )

    rain_avg_text = (
        f"{rain_avg:.2f}"
        if rain_avg is not None
        else "-"
    )

    print(
        f"{district_id:<6}"
        f"{result['district']:<23}"
        f"{rain_max_text:>12}"
        f"{rain_avg_text:>12}"
        f"{result['rain_station_count']:>10}"
        f"{result['river_status']:>25}"
    )


# ============================================================
# 14. SHOW RIVER SIGNALS
# ============================================================

print()
print("=" * 110)
print("DISTRICTS WITH CURRENT RIVER WARNING / DANGER")
print("=" * 110)

river_signal_count = 0

for district_id in sorted(merged):

    result = merged[district_id]

    if result["river_status"] not in [
        "RIVER WARNING",
        "RIVER DANGER"
    ]:
        continue

    river_signal_count += 1

    trigger = result["river_trigger"]

    print()
    print(
        f"District: "
        f"{result['district']}"
        f" (BIPAD ID {district_id})"
    )

    print(
        f"Status: "
        f"{result['river_status']}"
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
        "\nNo current river warning/danger "
        "signals after QC."
    )


# ============================================================
# 15. FINAL VALIDATION
# ============================================================

print()
print("=" * 110)
print("FINAL VALIDATION")
print("=" * 110)

print(
    f"GeoJSON districts:             "
    f"{len(geojson_districts)}"
)

print(
    f"BIPAD districts:               "
    f"{len(bipad_districts)}"
)

print(
    f"GeoJSON → BIPAD mappings:       "
    f"{len(geojson_to_bipad)}"
)

print(
    f"Mapping failures:               "
    f"{len(mapping_failures)}"
)

print(
    f"Rainfall districts:             "
    f"{len(rain_by_district)}"
)

print(
    f"River districts with valid data:"
    f" {len(river_by_district)}"
)

print(
    f"Final merged districts:         "
    f"{len(merged)}"
)

print(
    f"River warning/danger districts: "
    f"{river_signal_count}"
)


print()

if (
    len(geojson_districts) == 77
    and len(bipad_districts) == 77
    and len(mapping_failures) == 0
    and len(merged) == 77
):

    print(
        "SUCCESS: Rainfall and river data "
        "are standardized to the same 77 BIPAD district IDs."
    )

else:

    print(
        "CHECK REQUIRED: District standardization "
        "is not yet complete."
    )


print()
print("=" * 110)
print("END")
print("=" * 110)