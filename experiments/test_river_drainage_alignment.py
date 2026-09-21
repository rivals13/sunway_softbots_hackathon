import numpy as np
import requests
import rasterio
from scipy.spatial import cKDTree
from pyproj import Transformer


# ============================================================
# CONFIG
# ============================================================

BIPAD_URL = (
    "https://bipadportal.gov.np/api/v1/river-stations/"
)

P99_TIF = (
    "data/boundaries/dem/derived/"
    "nepal_drainage_p99.tif"
)

P995_TIF = (
    "data/boundaries/dem/derived/"
    "nepal_drainage_p995.tif"
)

THRESHOLDS = [250, 500, 1000, 2000]

# Nepal geographic bounds used ONLY to detect
# obviously reversed [lat, lon] coordinates.
LON_MIN = 80.0
LON_MAX = 89.0
LAT_MIN = 26.0
LAT_MAX = 31.0


# ============================================================
# HEADER
# ============================================================

print("=" * 95)
print(
    "PRAVAH — BIPAD/DHM RIVER STATION "
    "↔ DEM DRAINAGE ALIGNMENT"
)
print("=" * 95)


# ============================================================
# FETCH LATEST STATIONS
# ============================================================

print("\nFetching latest BIPAD/DHM river stations...")

params = {
    "latest": "true",
    "limit": 5000,
}

response = requests.get(
    BIPAD_URL,
    params=params,
    timeout=60,
)

response.raise_for_status()

data = response.json()
records = data.get("results", [])

print(f"Records returned: {len(records)}")

if records:
    example = records[0]
    print("\nExample record:")
    print(f"  title : {example.get('title')}")
    print(f"  id    : {example.get('id')}")
    print(f"  stationSeriesId: {example.get('stationSeriesId')}")
    print(f"  point : {example.get('point')}")


# ============================================================
# EXTRACT + VALIDATE COORDINATES
# ============================================================

stations = []

missing = 0
invalid = 0
swapped = []

seen_series = set()

for record in records:

    series_id = record.get("stationSeriesId")

    # Deduplicate
    if series_id in seen_series:
        continue

    seen_series.add(series_id)

    point = record.get("point")

    if not point:
        missing += 1
        continue

    coords = point.get("coordinates")

    if not coords or len(coords) < 2:
        invalid += 1
        continue

    try:
        x = float(coords[0])
        y = float(coords[1])
    except (TypeError, ValueError):
        invalid += 1
        continue

    # --------------------------------------------------------
    # Normal GeoJSON:
    # [longitude, latitude]
    # --------------------------------------------------------

    if (
        LON_MIN <= x <= LON_MAX
        and LAT_MIN <= y <= LAT_MAX
    ):
        lon = x
        lat = y

    # --------------------------------------------------------
    # Swapped:
    # [latitude, longitude]
    # --------------------------------------------------------

    elif (
        LAT_MIN <= x <= LAT_MAX
        and LON_MIN <= y <= LON_MAX
    ):
        lon = y
        lat = x

        swapped.append({
            "title": record.get("title", "Unknown"),
            "raw": [x, y],
            "corrected": [lon, lat],
        })

    else:
        invalid += 1
        continue

    stations.append({
        "title": record.get("title", "Unknown"),
        "id": record.get("id"),
        "station_series_id": series_id,
        "lon": lon,
        "lat": lat,
    })


# ============================================================
# COORDINATE QUALITY REPORT
# ============================================================

print("\n" + "=" * 95)
print("COORDINATE QUALITY CHECK")
print("=" * 95)

print(f"Total records       : {len(records)}")
print(f"Normal [lon, lat]   : {len(stations) - len(swapped)}")
print(f"Swapped [lat, lon]  : {len(swapped)}")
print(f"Other/invalid       : {invalid}")
print(f"Missing coordinates : {missing}")

if swapped:
    print("\nCoordinate correction(s):")

    for item in swapped:
        print(
            f"  {item['title']}\n"
            f"    raw       = {item['raw']}\n"
            f"    corrected = {item['corrected']}"
        )

print(f"\nValid unique stations: {len(stations)}")


# ============================================================
# ALIGNMENT FUNCTION
# ============================================================

def test_alignment(tif_path, label):

    print("\n" + "=" * 95)
    print(f"{label} ALIGNMENT")
    print("=" * 95)

    print("\nLoading drainage raster:")
    print(tif_path)

    with rasterio.open(tif_path) as src:

        drainage = src.read(1)
        transform = src.transform
        crs = src.crs

        print(f"CRS: {crs}")
        print(
            f"Raster: {src.width} x {src.height}"
        )

        valid = drainage > 0

        rows, cols = np.where(valid)

        print(
            f"Drainage pixels: {len(rows):,}"
        )

        # ----------------------------------------------------
        # Convert drainage pixel locations to map coordinates
        # ----------------------------------------------------

        xs, ys = rasterio.transform.xy(
            transform,
            rows,
            cols,
            offset="center",
        )

        drainage_points = np.column_stack(
            [xs, ys]
        )

        print("Building spatial index...")

        tree = cKDTree(drainage_points)

        print("Spatial index ready.")

        # ----------------------------------------------------
        # Transform station coordinates
        # WGS84 -> raster CRS
        # ----------------------------------------------------

        transformer = Transformer.from_crs(
            "EPSG:4326",
            crs,
            always_xy=True,
        )

        results = []

        for station in stations:

            x, y = transformer.transform(
                station["lon"],
                station["lat"],
            )

            # Check whether station lies within raster
            # bounds before querying.
            if not (
                src.bounds.left <= x <= src.bounds.right
                and
                src.bounds.bottom <= y <= src.bounds.top
            ):
                results.append({
                    **station,
                    "distance_m": np.nan,
                })
                continue

            distance, index = tree.query(
                [x, y],
                k=1,
            )

            results.append({
                **station,
                "distance_m": float(distance),
            })

    # --------------------------------------------------------
    # Remove stations outside raster
    # --------------------------------------------------------

    valid_results = [
        r for r in results
        if np.isfinite(r["distance_m"])
    ]

    distances = np.array([
        r["distance_m"]
        for r in valid_results
    ])

    print("\n" + "-" * 95)
    print(f"{label} ALIGNMENT RESULTS")
    print("-" * 95)

    print(
        f"Stations tested : {len(valid_results)}"
    )

    print(
        f"Mean distance   : {np.mean(distances):,.1f} m"
    )

    print(
        f"Median distance : {np.median(distances):,.1f} m"
    )

    print(
        f"Minimum         : {np.min(distances):,.1f} m"
    )

    print(
        f"Maximum         : {np.max(distances):,.1f} m"
    )

    # --------------------------------------------------------
    # Coverage
    # --------------------------------------------------------

    print("\nAlignment coverage:")

    coverage = {}

    for threshold in THRESHOLDS:

        count = int(
            np.sum(distances <= threshold)
        )

        percent = (
            count / len(distances) * 100
            if len(distances)
            else 0
        )

        coverage[threshold] = percent

        print(
            f"  Within {threshold:4d} m : "
            f"{count:3d}/{len(distances)} "
            f"({percent:6.2f}%)"
        )

    # --------------------------------------------------------
    # Closest
    # --------------------------------------------------------

    print("\nClosest stations:")

    closest = sorted(
        valid_results,
        key=lambda r: r["distance_m"]
    )[:10]

    for r in closest:

        print(
            f"  {r['title']:<50}"
            f"{r['distance_m']:>10.1f} m"
        )

    # --------------------------------------------------------
    # Farthest
    # --------------------------------------------------------

    print("\nFarthest stations:")

    farthest = sorted(
        valid_results,
        key=lambda r: r["distance_m"],
        reverse=True,
    )[:10]

    for r in farthest:

        print(
            f"  {r['title']:<50}"
            f"{r['distance_m']:>10.1f} m"
        )

    return {
        "label": label,
        "count": len(valid_results),
        "coverage": coverage,
        "distances": distances,
        "results": valid_results,
    }


# ============================================================
# RUN P99
# ============================================================

p99 = test_alignment(
    P99_TIF,
    "P99",
)


# ============================================================
# RUN P99.5
# ============================================================

p995 = test_alignment(
    P995_TIF,
    "P99.5",
)


# ============================================================
# DIRECT COMPARISON
# ============================================================

print("\n" + "=" * 95)
print("P99 vs P99.5 — DIRECT COMPARISON")
print("=" * 95)

print(
    "\nThreshold                  P99          P99.5"
)

print("-" * 45)

for threshold in THRESHOLDS:

    a = p99["coverage"][threshold]
    b = p995["coverage"][threshold]

    print(
        f"{threshold:4d} m"
        f"{a:18.2f}%"
        f"{b:15.2f}%"
    )

print("\nMedian distance:")

print(
    f"  P99   : "
    f"{np.median(p99['distances']):,.1f} m"
)

print(
    f"  P99.5 : "
    f"{np.median(p995['distances']):,.1f} m"
)

print("\nMean distance:")

print(
    f"  P99   : "
    f"{np.mean(p99['distances']):,.1f} m"
)

print(
    f"  P99.5 : "
    f"{np.mean(p995['distances']):,.1f} m"
)


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 95)
print("ALIGNMENT TEST COMPLETE")
print("=" * 95)
