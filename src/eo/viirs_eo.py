import h5py
import geopandas as gpd
import numpy as np
import json
import re

from datetime import datetime, timezone

from rasterio.features import rasterize
from rasterio.transform import from_origin

from src.config import (
    GEOJSON_PATH,
    VIIRS_DIR,
    EO_FEATURES_FILE
)


GEOJSON = str(GEOJSON_PATH)

PRODUCT = "VCDWD_L3_NRT"

MIN_FLOOD_PIXELS = 5


print("=" * 85)
print("PRAVAH - VIIRS EO FEATURE GENERATION")
print("=" * 85)


# ============================================================
# 1. FIND VIIRS OBSERVATION FILES
# ============================================================

ALL_FILES = sorted(
    VIIRS_DIR.glob(
        f"{PRODUCT}*.h5"
    )
)


if not ALL_FILES:

    raise FileNotFoundError(
        f"No VIIRS H5 files found in: {VIIRS_DIR}"
    )


# ============================================================
# 2. EXTRACT OBSERVATION DATE
# ============================================================

def observation_date_from_filename(filename):

    match = re.search(
        r"\.A(\d{4})(\d{3})\.",
        filename
    )

    if not match:
        return None

    year = int(match.group(1))
    doy = int(match.group(2))

    try:

        date = (
            datetime(
                year,
                1,
                1
            )
            + __import__("datetime").timedelta(
                days=doy - 1
            )
        ).date()

        return date

    except ValueError:

        return None


# ============================================================
# 3. GROUP FILES BY OBSERVATION DATE
# ============================================================

files_by_date = {}


for path in ALL_FILES:

    obs_date = observation_date_from_filename(
        path.name
    )

    if obs_date is None:

        print(
            "WARNING: Could not determine "
            f"observation date: {path.name}"
        )

        continue

    files_by_date.setdefault(
        obs_date,
        []
    ).append(path)


if not files_by_date:

    raise FileNotFoundError(
        "No VIIRS files with valid observation dates found."
    )


# ============================================================
# 4. SELECT NEWEST OBSERVATION
# ============================================================

LATEST_DATE = max(
    files_by_date.keys()
)


LATEST_FILES = files_by_date[
    LATEST_DATE
]


# Only Nepal-covering tiles:
# h26v05 = 80-90E, 30-40N
# h26v06 = 80-90E, 20-30N

FILES = [
    f
    for f in LATEST_FILES
    if ".h26v05." in f.name
    or ".h26v06." in f.name
]


if not FILES:

    raise FileNotFoundError(
        "Newest VIIRS observation does not contain "
        "Nepal-covering h26v05/h26v06 tiles."
    )


print()
print("=" * 85)
print("LATEST VIIRS OBSERVATION")
print("=" * 85)

print(
    f"Observation date: {LATEST_DATE}"
)

print(
    f"Files selected: {len(FILES)}"
)

for f in FILES:

    print(
        f"  {f.name}"
    )


# ============================================================
# 5. LOAD DISTRICTS
# ============================================================

districts = gpd.read_file(
    GEOJSON
).to_crs(
    "EPSG:4326"
)

print()
print(
    "Districts loaded:",
    len(districts)
)


# ============================================================
# 6. STORAGE
# ============================================================

district_flood = {
    name: 0
    for name in districts["adm2_name"]
}

district_valid = {
    name: 0
    for name in districts["adm2_name"]
}


# ============================================================
# 7. PROCESS VIIRS TILES
# ============================================================

BASE = (
    "HDFEOS/GRIDS/"
    "Flood_Composite/Data Fields"
)


for filename in FILES:

    print()
    print(
        "Processing:",
        filename.name
    )

    with h5py.File(
        filename,
        "r"
    ) as f:

        flood = f[
            f"{BASE}/Flood_1Day_250m"
        ][:]

        valid = f[
            f"{BASE}/ValidCounts_1Day_250m"
        ][:]

        lat = f[
            f"{BASE}/lat"
        ][:]

        lon = f[
            f"{BASE}/lon"
        ][:]


    # --------------------------------------------------------
    # Nepal bounding box
    # --------------------------------------------------------

    lat_idx = np.where(
        (lat >= 26.0)
        &
        (lat <= 31.2)
    )[0]

    lon_idx = np.where(
        (lon >= 80.0)
        &
        (lon <= 89.0)
    )[0]


    flood = flood[
        np.ix_(
            lat_idx,
            lon_idx
        )
    ]

    valid = valid[
        np.ix_(
            lat_idx,
            lon_idx
        )
    ]

    lat = lat[
        lat_idx
    ]

    lon = lon[
        lon_idx
    ]


    # --------------------------------------------------------
    # Safety check
    # --------------------------------------------------------

    if len(lat) < 2 or len(lon) < 2:

        print(
            "WARNING: insufficient spatial "
            "resolution after Nepal clipping."
        )

        continue


    # --------------------------------------------------------
    # Pixel resolution
    # --------------------------------------------------------

    pixel_y = abs(
        lat[1] - lat[0]
    )

    pixel_x = abs(
        lon[1] - lon[0]
    )


    # Rasterio uses north -> south

    flood = np.flipud(
        flood
    )

    valid = np.flipud(
        valid
    )

    lat = lat[::-1]


    transform = from_origin(
        lon.min() - pixel_x / 2,
        lat.max() + pixel_y / 2,
        pixel_x,
        pixel_y
    )


    # --------------------------------------------------------
    # Rasterize districts
    # --------------------------------------------------------

    shapes = [
        (
            geometry,
            idx + 1
        )

        for idx, geometry
        in enumerate(
            districts.geometry
        )
    ]


    district_raster = rasterize(
        shapes,
        out_shape=flood.shape,
        transform=transform,
        fill=0,
        dtype="int16"
    )


    # --------------------------------------------------------
    # Masks
    # --------------------------------------------------------

    valid_mask = (
        valid > 0
    )


    flood_mask = (
        (flood == 3)
        &
        valid_mask
    )


    # --------------------------------------------------------
    # District statistics
    # --------------------------------------------------------

    for idx, name in enumerate(
        districts["adm2_name"]
    ):

        district_id = idx + 1

        mask = (
            district_raster
            == district_id
        )


        district_flood[name] += (
            np.count_nonzero(
                flood_mask
                &
                mask
            )
        )


        district_valid[name] += (
            np.count_nonzero(
                valid_mask
                &
                mask
            )
        )


# ============================================================
# 8. CREATE FLOOD RATIOS
# ============================================================

eo_districts = {}

ratios = []


for idx, name in enumerate(
    districts["adm2_name"]
):

    flood_count = (
        district_flood[name]
    )

    valid_count = (
        district_valid[name]
    )


    if valid_count > 0:

        flood_ratio = (
            flood_count
            /
            valid_count
        )

    else:

        flood_ratio = 0.0


    ratios.append(
        flood_ratio
    )


# ============================================================
# 9. RELATIVE SCORE
# ============================================================

meaningful_ratios = [

    ratios[i]

    for i in range(
        len(ratios)
    )

    if district_flood[
        list(
            district_flood.keys()
        )[i]
    ] >= MIN_FLOOD_PIXELS
]


if meaningful_ratios:

    max_ratio = max(
        meaningful_ratios
    )

else:

    max_ratio = 0.0


# ============================================================
# 10. BUILD DISTRICT FEATURES
# ============================================================

for idx, name in enumerate(
    districts["adm2_name"]
):

    flood_count = (
        district_flood[name]
    )

    valid_count = (
        district_valid[name]
    )


    if valid_count > 0:

        flood_ratio = (
            flood_count
            /
            valid_count
        )

    else:

        flood_ratio = 0.0


    # --------------------------------------------------------
    # Relative EO score
    # --------------------------------------------------------

    if (
        max_ratio > 0
        and
        flood_count >= MIN_FLOOD_PIXELS
    ):

        eo_score = (
            flood_ratio
            /
            max_ratio
        ) * 100

    else:

        eo_score = 0.0


    # --------------------------------------------------------
    # Evidence strength
    # --------------------------------------------------------

    if (
        flood_count
        <
        MIN_FLOOD_PIXELS
    ):

        strength = "NONE"

    elif eo_score >= 50:

        strength = "STRONG"

    elif eo_score >= 20:

        strength = "MODERATE"

    else:

        strength = "WEAK"


    eo_districts[name] = {

        "district_id":
            int(idx + 1),

        "district":
            name,

        "eo": {

            "flood_pixels":
                int(flood_count),

            "valid_pixels":
                int(valid_count),

            "flood_ratio":
                round(
                    flood_ratio,
                    6
                ),

            "flood_ratio_pct":
                round(
                    flood_ratio * 100,
                    3
                ),

            "eo_score":
                round(
                    eo_score,
                    2
                ),

            "evidence_strength":
                strength

        },

        "source_information": {

            "product":
                "VIIRS/JPSS1+JPSS2 Daily L3 Global Flood Composite NRT",

            "product_short_name":
                PRODUCT,

            "observation_period":
                str(LATEST_DATE),

            "resolution":
                "250m",

            "flood_flag":
                3,

            "flood_flag_meaning":
                "flood"

        },

        "data_quality": {

            "valid_observations":
                int(valid_count),

            "meaningful_flood_signal":
                bool(
                    flood_count
                    >=
                    MIN_FLOOD_PIXELS
                )

        }

    }


# ============================================================
# 11. BUILD OUTPUT
# ============================================================

output = {

    "project":
        "PRAVAH",

    "pipeline_version":
        "viirs_eo_v2",

    "generated_at_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "source":
        "NASA VIIRS NRT Global Flood Composite",

    "product":
        PRODUCT,

    "observation_date":
        str(LATEST_DATE),

    "resolution":
        "250m",

    "district_count":
        len(eo_districts),

    "minimum_flood_pixels":
        MIN_FLOOD_PIXELS,

    "semantics":
        "EO flood evidence only; not a standalone risk classification",

    "processed_files":
        [
            f.name
            for f in FILES
        ],

    "districts":
        eo_districts

}


# ============================================================
# 12. SAVE OUTPUT
# ============================================================

EO_FEATURES_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


with open(
    EO_FEATURES_FILE,
    "w"
) as f:

    json.dump(
        output,
        f,
        indent=2
    )


# ============================================================
# 13. SUMMARY
# ============================================================

strong = sum(
    1
    for d in eo_districts.values()
    if d["eo"]["evidence_strength"]
    == "STRONG"
)

moderate = sum(
    1
    for d in eo_districts.values()
    if d["eo"]["evidence_strength"]
    == "MODERATE"
)

weak = sum(
    1
    for d in eo_districts.values()
    if d["eo"]["evidence_strength"]
    == "WEAK"
)

none = sum(
    1
    for d in eo_districts.values()
    if d["eo"]["evidence_strength"]
    == "NONE"
)


print()
print("=" * 85)
print("VIIRS EO COMPLETE")
print("=" * 85)

print(
    f"Observation date : {LATEST_DATE}"
)

print(
    f"Files processed   : {len(FILES)}"
)

print(
    f"Districts         : {len(eo_districts)}"
)

print(
    f"STRONG            : {strong}"
)

print(
    f"MODERATE          : {moderate}"
)

print(
    f"WEAK              : {weak}"
)

print(
    f"NONE              : {none}"
)

print()
print(
    "Output:",
    EO_FEATURES_FILE
)