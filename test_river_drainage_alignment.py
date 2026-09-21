from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.warp import transform
from scipy.spatial import cKDTree


# =============================================================================
# CONFIG
# =============================================================================

BIPAD_URL = "https://bipadportal.gov.np/api/v1/river-stations/"

P99_PATH = Path(
    "data/boundaries/dem/derived/nepal_drainage_p99.tif"
)

P995_PATH = Path(
    "data/boundaries/dem/derived/nepal_drainage_p995.tif"
)

# Approximate Nepal extent.
# Used ONLY to detect obviously reversed coordinates.
LON_MIN, LON_MAX = 79.5, 88.5
LAT_MIN, LAT_MAX = 26.0, 30.5


# =============================================================================
# BIPAD STATIONS
# =============================================================================

def fetch_stations():
    print("Fetching latest BIPAD/DHM river stations...")

    response = requests.get(
        BIPAD_URL,
        params={
            "latest": "true",
            "limit": 5000,
        },
        timeout=30,
    )

    response.raise_for_status()

    results = response.json().get("results", [])

    print(f"Records returned: {len(results)}")

    if results:
        example = results[0]

        print("\nExample record:")
        print("  title :", example.get("title"))
        print("  id    :", example.get("id"))
        print("  stationSeriesId:", example.get("stationSeriesId"))
        print("  point :", example.get("point"))

    return results


def extract_stations(records):
    stations = []

    missing = 0
    invalid = 0
    corrected = 0

    seen_series = set()

    for record in records:

        title = record.get("title", "")
        series_id = record.get("stationSeriesId")

        # Deduplicate by station series.
        if series_id in seen_series:
            continue

        point = record.get("point")

        if not point or not point.get("coordinates"):
            missing += 1
            continue

        coordinates = point["coordinates"]

        if len(coordinates) < 2:
            invalid += 1
            continue

        a, b = coordinates[:2]

        try:
            a = float(a)
            b = float(b)
        except (TypeError, ValueError):
            invalid += 1
            continue

        # ---------------------------------------------------------------------
        # Normal GeoJSON:
        #   [longitude, latitude]
        #
        # Detect the one obvious reversed case:
        #   [latitude, longitude]
        # ---------------------------------------------------------------------

        normal = (
            LON_MIN <= a <= LON_MAX
            and
            LAT_MIN <= b <= LAT_MAX
        )

        swapped = (
            LAT_MIN <= a <= LAT_MAX
            and
            LON_MIN <= b <= LON_MAX
        )

        if normal:
            lon = a
            lat = b

        elif swapped:
            # BIPAD coordinate-order correction.
            lon = b
            lat = a

            corrected += 1

            print("\nCoordinate correction:")
            print(f"  Station : {title}")
            print(f"  Raw     : [{a}, {b}]")
            print(f"  Correct : [{lon}, {lat}]")

        else:
            invalid += 1
            continue

        seen_series.add(series_id)

        stations.append(
            {
                "title": title,
                "id": record.get("id"),
                "stationSeriesId": series_id,
                "lon": lon,
                "lat": lat,
            }
        )

    print("\nStation extraction:")
    print(f"  Valid unique stations : {len(stations)}")
    print(f"  Missing coordinates   : {missing}")
    print(f"  Invalid coordinates   : {invalid}")
    print(f"  Coordinate corrections: {corrected}")

    return stations


# =============================================================================
# LOAD DRAINAGE PIXELS
# =============================================================================

def load_drainage_pixels(path):
    print("\n" + "-" * 95)
    print("Loading drainage raster:")
    print(path)
    print("-" * 95)

    with rasterio.open(path) as src:

        data = src.read(1)

        valid = data > 0

        rows, cols = np.where(valid)

        # Convert raster pixel centers into projected coordinates.
        xs, ys = rasterio.transform.xy(
            src.transform,
            rows,
            cols,
            offset="center",
        )

        points = np.column_stack(
            [
                np.asarray(xs),
                np.asarray(ys),
            ]
        )

        print("CRS:", src.crs)
        print("Raster:", src.width, "x", src.height)
        print("Drainage pixels:", len(points))
        print("Bounds:", src.bounds)

        return {
            "points": points,
            "crs": src.crs,
            "bounds": src.bounds,
        }


# =============================================================================
# ALIGN STATIONS
# =============================================================================

def align_stations(stations, drainage):
    src_crs = drainage["crs"]
    bounds = drainage["bounds"]
    drainage_points = drainage["points"]

    print("Building spatial index...")
    tree = cKDTree(drainage_points)
    print("Spatial index ready.")

    lons = [s["lon"] for s in stations]
    lats = [s["lat"] for s in stations]

    xs, ys = transform(
        "EPSG:4326",
        src_crs,
        lons,
        lats,
    )

    results = []

    outside = 0

    for station, x, y in zip(stations, xs, ys):

        inside = (
            bounds.left <= x <= bounds.right
            and
            bounds.bottom <= y <= bounds.top
        )

        if not inside:
            outside += 1

            results.append(
                {
                    **station,
                    "x": x,
                    "y": y,
                    "inside_raster": False,
                    "distance_m": None,
                }
            )

            continue

        distance, index = tree.query([x, y], k=1)

        results.append(
            {
                **station,
                "x": x,
                "y": y,
                "inside_raster": True,
                "distance_m": float(distance),
            }
        )

    print(f"Stations outside raster: {outside}")

    return results


# =============================================================================
# STATISTICS
# =============================================================================

def print_results(name, results):

    valid = [
        r
        for r in results
        if r["inside_raster"]
        and r["distance_m"] is not None
    ]

    distances = np.array(
        [r["distance_m"] for r in valid],
        dtype=float,
    )

    print("\n" + "=" * 95)
    print(f"{name} ALIGNMENT RESULTS")
    print("=" * 95)

    print(f"Stations tested : {len(valid)}")

    if len(distances) == 0:
        print("No valid stations.")
        return {
            "name": name,
            "count": 0,
        }

    print(f"Mean distance   : {distances.mean():,.1f} m")
    print(f"Median distance : {np.median(distances):,.1f} m")
    print(f"Minimum         : {distances.min():,.1f} m")
    print(f"Maximum         : {distances.max():,.1f} m")

    print("\nAlignment coverage:")

    thresholds = [250, 500, 1000, 2000]

    coverage = {}

    for threshold in thresholds:

        count = int(np.sum(distances <= threshold))
        percentage = count / len(distances) * 100

        coverage[threshold] = percentage

        print(
            f"  Within {threshold:4d} m : "
            f"{count:3d}/{len(distances)} "
            f"({percentage:6.2f}%)"
        )

    # -------------------------------------------------------------------------
    # Closest
    # -------------------------------------------------------------------------

    print("\nClosest stations:")

    closest = sorted(
        valid,
        key=lambda x: x["distance_m"],
    )[:10]

    for r in closest:
        print(
            f"  {r['title']:<48} "
            f"{r['distance_m']:8.1f} m"
        )

    # -------------------------------------------------------------------------
    # Farthest
    # -------------------------------------------------------------------------

    print("\nFarthest stations:")

    farthest = sorted(
        valid,
        key=lambda x: x["distance_m"],
        reverse=True,
    )[:10]

    for r in farthest:
        print(
            f"  {r['title']:<48} "
            f"{r['distance_m']:8.1f} m"
        )

    return {
        "name": name,
        "count": len(valid),
        "mean": float(distances.mean()),
        "median": float(np.median(distances)),
        "min": float(distances.min()),
        "max": float(distances.max()),
        "coverage": coverage,
    }


# =============================================================================
# MAIN
# =============================================================================

def main():

    print("=" * 95)
    print("PRAVAH — BIPAD/DHM RIVER STATION ↔ DEM DRAINAGE ALIGNMENT")
    print("=" * 95)

    # -------------------------------------------------------------------------
    # 1. BIPAD
    # -------------------------------------------------------------------------

    records = fetch_stations()

    stations = extract_stations(records)

    # -------------------------------------------------------------------------
    # 2. P99
    # -------------------------------------------------------------------------

    print("\n" + "=" * 95)
    print("P99 ALIGNMENT")
    print("=" * 95)

    p99 = load_drainage_pixels(P99_PATH)

    p99_results = align_stations(
        stations,
        p99,
    )

    p99_stats = print_results(
        "P99",
        p99_results,
    )

    # -------------------------------------------------------------------------
    # 3. P99.5
    # -------------------------------------------------------------------------

    print("\n" + "=" * 95)
    print("P99.5 ALIGNMENT")
    print("=" * 95)

    p995 = load_drainage_pixels(P995_PATH)

    p995_results = align_stations(
        stations,
        p995,
    )

    p995_stats = print_results(
        "P99.5",
        p995_results,
    )

    # -------------------------------------------------------------------------
    # 4. Direct comparison
    # -------------------------------------------------------------------------

    print("\n" + "=" * 95)
    print("P99 vs P99.5 — DIRECT COMPARISON")
    print("=" * 95)

    print(
        "\n"
        f"{'Threshold':<20}"
        f"{'P99':>12}"
        f"{'P99.5':>12}"
    )

    print("-" * 45)

    for threshold in [250, 500, 1000, 2000]:

        p99_value = p99_stats["coverage"].get(threshold, 0)
        p995_value = p995_stats["coverage"].get(threshold, 0)

        print(
            f"{str(threshold) + ' m':<20}"
            f"{p99_value:>11.2f}%"
            f"{p995_value:>11.2f}%"
        )

    print("\nMedian distance:")

    print(
        f"  P99   : {p99_stats.get('median', float('nan')):,.1f} m"
    )

    print(
        f"  P99.5 : {p995_stats.get('median', float('nan')):,.1f} m"
    )

    print("\nMean distance:")

    print(
        f"  P99   : {p99_stats.get('mean', float('nan')):,.1f} m"
    )

    print(
        f"  P99.5 : {p995_stats.get('mean', float('nan')):,.1f} m"
    )

    print("\n" + "=" * 95)
    print("ALIGNMENT TEST COMPLETE")
    print("=" * 95)

    print(
        "\nThis experiment evaluates spatial alignment between "
        "BIPAD/DHM river-monitoring stations and DEM-derived "
        "drainage pixels."
    )

    print(
        "It does NOT evaluate flood prediction accuracy "
        "or risk-engine performance."
    )


if __name__ == "__main__":
    main()