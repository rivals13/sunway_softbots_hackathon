import json
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from src.config import (
    GEOJSON_PATH,
    DISTRICT_CN_FILE,
    BOUNDARIES_DIR,
)

# =========================================================
# PRAVAH - GCN250 DISTRICT CURVE NUMBER EXTRACTION
# =========================================================

GEOJSON = str(GEOJSON_PATH)


RASTERS = {
    "cn_dry": str(BOUNDARIES_DIR / "nepal_gcn250_arcI.tif"),
    "cn_average": str(BOUNDARIES_DIR / "nepal_gcn250_arcII.tif"),
    "cn_wet": str(BOUNDARIES_DIR / "nepal_gcn250_arcIII.tif"),
}

OUTPUT = str(DISTRICT_CN_FILE)




print("=" * 75)
print("PRAVAH - GCN250 DISTRICT CURVE NUMBER EXTRACTION")
print("=" * 75)

# ---------------------------------------------------------
# LOAD DISTRICTS
# ---------------------------------------------------------

print("\nLoading Nepal districts...")

gdf = gpd.read_file(GEOJSON)

print(f"Districts loaded: {len(gdf)}")


# ---------------------------------------------------------
# PREPARE RESULTS
# ---------------------------------------------------------

results = {}

for _, row in gdf.iterrows():

    district_name = row.get("adm2_name")

    if not district_name:
        district_name = f"district_{_}"

    results[district_name] = {}


# ---------------------------------------------------------
# PROCESS EACH ARC
# ---------------------------------------------------------

for condition, raster_path in RASTERS.items():

    print("\n" + "-" * 75)
    print(f"Processing: {condition}")
    print("-" * 75)

    with rasterio.open(raster_path) as src:

        print(f"Raster CRS: {src.crs}")
        print(f"Raster size: {src.width} x {src.height}")
        print(f"Resolution: {src.res}")

        # Reproject districts if necessary
        if gdf.crs != src.crs:
            working_gdf = gdf.to_crs(src.crs)
        else:
            working_gdf = gdf

        for index, row in working_gdf.iterrows():

            district_name = row.get("adm2_name")

            if not district_name:
                district_name = f"district_{index}"

            try:

                geometry = [row.geometry]

                data, transform = mask(
                    src,
                    geometry,
                    crop=True,
                    filled=True,
                    nodata=0
                )

                values = data[0]

                # Valid CN values
                valid = values[
                    (values > 0) &
                    (values <= 100)
                ]

                if len(valid) == 0:

                    results[district_name][condition] = None

                    print(
                        f"{district_name:25s} "
                        f"{condition:12s} → NO DATA"
                    )

                    continue

                cn_mean = float(np.mean(valid))

                results[district_name][condition] = round(
                    cn_mean, 2
                )

            except Exception as e:

                print(
                    f"{district_name:25s} "
                    f"{condition:12s} → ERROR: {e}"
                )

                results[district_name][condition] = None


# ---------------------------------------------------------
# SAVE
# ---------------------------------------------------------

with open(OUTPUT, "w") as f:
    json.dump(results, f, indent=2)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("FINAL CN DATASET")
print("=" * 75)

print(f"Districts: {len(results)}")

complete = 0

for district, values in results.items():

    if all(
        values.get(k) is not None
        for k in ["cn_dry", "cn_average", "cn_wet"]
    ):
        complete += 1

print(f"Complete districts: {complete}")
print(f"Incomplete districts: {len(results) - complete}")

print("\nExample districts:")

for district in list(results.keys())[:5]:

    print(
        f"{district:20s} "
        f"Dry={results[district]['cn_dry']:6.2f}  "
        f"Avg={results[district]['cn_average']:6.2f}  "
        f"Wet={results[district]['cn_wet']:6.2f}"
    )

print("\nSaved:")
print(OUTPUT)

print("\nSUCCESS!")
