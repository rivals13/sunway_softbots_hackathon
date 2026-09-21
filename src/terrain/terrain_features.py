import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape, mapping
from shapely.ops import transform
from pyproj import Transformer


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GEOJSON_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "npl_boundaries_extracted"
    / "npl_admin2.geojson"
)

DEM_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "dem"
    / "derived"
    / "nepal_dem_metric.tif"
)

SLOPE_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "dem"
    / "derived"
    / "nepal_slope.tif"
)

P99_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "dem"
    / "derived"
    / "nepal_drainage_p99.tif"
)

P995_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "dem"
    / "derived"
    / "nepal_drainage_p995.tif"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "terrain"
    / "prava_terrain_features.json"
)


# ============================================================
# HELPERS
# ============================================================

def safe_mean(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return None

    return float(np.mean(values))


def safe_min(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return None

    return float(np.min(values))


def safe_max(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return None

    return float(np.max(values))


# ============================================================
# LOAD + REPROJECT DISTRICTS
# ============================================================

def load_districts(target_crs):

    print("Loading Nepal district boundaries...")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    # The source GeoJSON explicitly declares OGC:CRS84.
    # CRS84 uses longitude, latitude axis order.
    source_crs = "OGC:CRS84"

    transformer = Transformer.from_crs(
        source_crs,
        target_crs,
        always_xy=True,
    )

    districts = []

    for index, feature in enumerate(
        geojson.get("features", []),
        start=1,
    ):

        properties = feature.get("properties", {})
        geometry = feature.get("geometry")

        if not geometry:
            continue

        name = (
            properties.get("adm2_name")
            or properties.get("NAME_2")
            or properties.get("name")
            or f"District {index}"
        )

        # Preserve the original administrative p-code.
        district_pcode = properties.get("adm2_pcode")

        # PRAVAH currently uses sequential 1..77 district IDs.
        district_id = index

        geom = shape(geometry)

        # Reproject district geometry from CRS84
        # into the DEM's projected metric CRS.
        geom_projected = transform(
            transformer.transform,
            geom,
        )

        districts.append(
            {
                "district_id": district_id,
                "district_pcode": district_pcode,
                "district": str(name),
                "geometry": geom_projected,
            }
        )

    print(f"Districts loaded: {len(districts)}")
    print(f"Boundary CRS      : {source_crs}")
    print(f"Raster CRS         : {target_crs}")

    return districts


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - TERRAIN FEATURE EXTRACTION")
    print("=" * 80)

    # --------------------------------------------------------
    # Check required files
    # --------------------------------------------------------

    required = [
        DEM_PATH,
        P99_PATH,
        P995_PATH,
    ]

    for path in required:

        if not path.exists():

            raise FileNotFoundError(
                f"Missing required file: {path}"
            )

    # Slope is currently optional.
    slope_available = SLOPE_PATH.exists()

    if not slope_available:

        print()
        print("WARNING: slope raster not found.")
        print("Slope statistics will be skipped.")
        print()

    # --------------------------------------------------------
    # Open reference DEM
    # --------------------------------------------------------

    with rasterio.open(DEM_PATH) as dem_src:

        target_crs = dem_src.crs

        # Load and reproject district geometries
        # into the DEM CRS.
        districts = load_districts(target_crs)

        # ----------------------------------------------------
        # Open aligned rasters
        # ----------------------------------------------------

        with rasterio.open(P99_PATH) as p99_src, \
             rasterio.open(P995_PATH) as p995_src:

            slope_src = (
                rasterio.open(SLOPE_PATH)
                if slope_available
                else None
            )

            try:

                # =================================================
                # RASTER ALIGNMENT CHECK
                # =================================================

                print()
                print("Checking raster alignment...")

                reference = (
                    dem_src.crs,
                    dem_src.width,
                    dem_src.height,
                    dem_src.transform,
                    dem_src.bounds,
                )

                rasters_to_check = [
                    ("P99", p99_src),
                    ("P99.5", p995_src),
                ]

                if slope_src is not None:

                    rasters_to_check.append(
                        ("Slope", slope_src)
                    )

                for name, src in rasters_to_check:

                    current = (
                        src.crs,
                        src.width,
                        src.height,
                        src.transform,
                        src.bounds,
                    )

                    if current != reference:

                        raise RuntimeError(
                            f"{name} raster is not aligned "
                            f"with DEM"
                        )

                print("Raster alignment: PASS")

                # =================================================
                # PROCESS DISTRICTS
                # =================================================

                results = []
                errors = []

                print()
                print("Processing districts...")
                print()

                for i, district in enumerate(
                    districts,
                    start=1,
                ):

                    geometry = district["geometry"]

                    feature = {

                        "district_id":
                            district["district_id"],

                        "district_pcode":
                            district["district_pcode"],

                        "district":
                            district["district"],

                        "terrain": {},
                    }

                    try:

                        # =================================================
                        # ELEVATION
                        # =================================================

                        dem_data, _ = mask(
                            dem_src,
                            [mapping(geometry)],
                            crop=True,
                            filled=False,
                        )

                        dem_values = (
                            dem_data[0].compressed()
                        )

                        feature["terrain"][
                            "elevation_mean_m"
                        ] = safe_mean(
                            dem_values
                        )

                        feature["terrain"][
                            "elevation_min_m"
                        ] = safe_min(
                            dem_values
                        )

                        feature["terrain"][
                            "elevation_max_m"
                        ] = safe_max(
                            dem_values
                        )

                        # =================================================
                        # SLOPE
                        # =================================================

                        if slope_src is not None:

                            slope_data, _ = mask(
                                slope_src,
                                [mapping(geometry)],
                                crop=True,
                                filled=False,
                            )

                            slope_values = (
                                slope_data[0].compressed()
                            )

                            feature["terrain"][
                                "slope_mean_deg"
                            ] = safe_mean(
                                slope_values
                            )

                        else:

                            feature["terrain"][
                                "slope_mean_deg"
                            ] = None

                        # =================================================
                        # P99 DRAINAGE AREA
                        # =================================================
                        #
                        # IMPORTANT:
                        #
                        # P99 raster is a binary mask:
                        #
                        #     0 = background
                        #     1 = high-flow-accumulation area
                        #
                        # The raster itself has NoData=0, but for this
                        # district-level percentage calculation we MUST
                        # retain the zero cells because they represent
                        # non-drainage/background area.
                        #
                        # Therefore we use:
                        #
                        #     filled=True
                        #     nodata=0
                        #
                        # and calculate:
                        #
                        #     number of cells == 1
                        #     ------------------ × 100
                        #     all cells in district window
                        #
                        # =================================================

                        p99_data, _ = mask(
                            p99_src,
                            [mapping(geometry)],
                            crop=True,
                            filled=True,
                            nodata=0,
                        )

                        p99_values = (
                            p99_data[0].ravel()
                        )

                        if p99_values.size > 0:

                            p99_pixels = int(
                                np.count_nonzero(
                                    p99_values == 1
                                )
                            )

                            total_pixels = int(
                                p99_values.size
                            )

                            feature["terrain"][
                                "drainage_area_pct_p99"
                            ] = (
                                p99_pixels
                                / total_pixels
                                * 100.0
                            )

                        else:

                            feature["terrain"][
                                "drainage_area_pct_p99"
                            ] = None

                        # =================================================
                        # P99.5 DRAINAGE AREA
                        # =================================================

                        p995_data, _ = mask(
                            p995_src,
                            [mapping(geometry)],
                            crop=True,
                            filled=True,
                            nodata=0,
                        )

                        p995_values = (
                            p995_data[0].ravel()
                        )

                        if p995_values.size > 0:

                            p995_pixels = int(
                                np.count_nonzero(
                                    p995_values == 1
                                )
                            )

                            total_pixels = int(
                                p995_values.size
                            )

                            feature["terrain"][
                                "drainage_area_pct_p995"
                            ] = (
                                p995_pixels
                                / total_pixels
                                * 100.0
                            )

                        else:

                            feature["terrain"][
                                "drainage_area_pct_p995"
                            ] = None

                        # =================================================
                        # STORE RESULT
                        # =================================================

                        results.append(feature)

                        print(
                            f"[{i:02d}/{len(districts)}] "
                            f"{district['district']:<20} "
                            f"elev="
                            f"{feature['terrain']['elevation_mean_m']:.1f}m "
                            f"p99="
                            f"{feature['terrain']['drainage_area_pct_p99']:.4f}% "
                            f"p995="
                            f"{feature['terrain']['drainage_area_pct_p995']:.4f}%"
                        )

                    except Exception as exc:

                        errors.append(
                            {
                                "district":
                                    district["district"],

                                "error":
                                    str(exc),
                            }
                        )

                        print(
                            f"[{i:02d}/{len(districts)}] "
                            f"{district['district']:<20} "
                            f"ERROR: {exc}"
                        )

                # =================================================
                # OUTPUT
                # =================================================

                output = {

                    "project":
                        "PRAVAH",

                    "pipeline_version":
                        "terrain_features_v1",

                    "description": (
                        "District-level terrain context "
                        "derived from SRTM DEM, slope, "
                        "and D8 flow accumulation "
                        "drainage masks."
                    ),

                    "methodology": {

                        "boundary_crs":
                            "OGC:CRS84",

                        "working_crs":
                            str(target_crs),

                        "dem":
                            "SRTM-derived 30 m metric DEM",

                        "flow_direction":
                            "WhiteboxTools D8 Pointer",

                        "flow_accumulation":
                            "WhiteboxTools D8 Flow "
                            "Accumulation in upstream cells",

                        "p99":
                            "Flow accumulation >= P99 threshold",

                        "p995":
                            "Flow accumulation >= P99.5 threshold",
                    },

                    "district_count":
                        len(results),

                    "districts":
                        results,

                    "errors":
                        errors,
                }

                OUTPUT_PATH.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with open(
                    OUTPUT_PATH,
                    "w",
                    encoding="utf-8",
                ) as f:

                    json.dump(
                        output,
                        f,
                        indent=2,
                    )

                # =================================================
                # SUMMARY
                # =================================================

                valid_elevation = sum(
                    1
                    for d in results
                    if d["terrain"].get(
                        "elevation_mean_m"
                    ) is not None
                )

                valid_slope = sum(
                    1
                    for d in results
                    if d["terrain"].get(
                        "slope_mean_deg"
                    ) is not None
                )

                valid_p99 = sum(
                    1
                    for d in results
                    if d["terrain"].get(
                        "drainage_area_pct_p99"
                    ) is not None
                )

                valid_p995 = sum(
                    1
                    for d in results
                    if d["terrain"].get(
                        "drainage_area_pct_p995"
                    ) is not None
                )

                print()
                print("=" * 80)
                print("TERRAIN FEATURE SUMMARY")
                print("=" * 80)

                print(
                    f"Districts processed : "
                    f"{len(results)}/{len(districts)}"
                )

                print(
                    f"Elevation available : "
                    f"{valid_elevation}/{len(results)}"
                )

                print(
                    f"Slope available     : "
                    f"{valid_slope}/{len(results)}"
                )

                print(
                    f"P99 available       : "
                    f"{valid_p99}/{len(results)}"
                )

                print(
                    f"P99.5 available     : "
                    f"{valid_p995}/{len(results)}"
                )

                print(
                    f"Errors              : "
                    f"{len(errors)}"
                )

                print()
                print("Output:")
                print(OUTPUT_PATH)

            finally:

                if slope_src is not None:
                    slope_src.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()