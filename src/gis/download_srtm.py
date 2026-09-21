from pathlib import Path
import math
import subprocess
import requests
import geopandas as gpd


# ============================================================
# PRAVAH - Nepal SRTM DEM Downloader
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BOUNDARY_FILE = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "npl_boundaries_extracted"
    / "npl_admin0.geojson"
)

DEM_DIR = PROJECT_ROOT / "data" / "boundaries" / "dem"
TILES_DIR = DEM_DIR / "tiles"

SRTM_BASE = (
    "https://data.lpdaac.earthdatacloud.nasa.gov/"
    "lp-prod-protected/SRTMGL1.003"
)

OUTPUT_VRT = DEM_DIR / "nepal_srtm.vrt"
OUTPUT_DEM = DEM_DIR / "nepal_srtm.tif"


# ============================================================
# Helpers
# ============================================================

def tile_name(lat, lon):
    """
    Convert integer tile coordinates to SRTM naming convention.

    Example:
        lat=28, lon=84
        -> N28E084
    """

    lat_prefix = "N" if lat >= 0 else "S"
    lon_prefix = "E" if lon >= 0 else "W"

    return (
        f"{lat_prefix}{abs(lat):02d}"
        f"{lon_prefix}{abs(lon):03d}"
    )


def tile_url(name):
    """
    Build current NASA Earthdata Cloud SRTMGL1 URL.
    """

    return (
        f"{SRTM_BASE}/"
        f"{name}.SRTMGL1.hgt/"
        f"{name}.SRTMGL1.hgt.zip"
    )


def get_required_tiles(boundary):
    """
    Determine 1-degree SRTM tiles intersecting the Nepal boundary.
    """

    minx, miny, maxx, maxy = boundary.total_bounds

    # Include the tile containing the maximum coordinate.
    min_lon = math.floor(minx)
    max_lon = math.floor(maxx)
    min_lat = math.floor(miny)
    max_lat = math.floor(maxy)

    tiles = []

    for lat in range(min_lat, max_lat + 1):
        for lon in range(min_lon, max_lon + 1):

            name = tile_name(lat, lon)

            # 1-degree tile polygon
            tile_polygon = gpd.GeoSeries.from_wkt(
                [
                    (
                        f"POLYGON(("
                        f"{lon} {lat}, "
                        f"{lon + 1} {lat}, "
                        f"{lon + 1} {lat + 1}, "
                        f"{lon} {lat + 1}, "
                        f"{lon} {lat}"
                        f"))"
                    )
                ],
                crs="EPSG:4326",
            ).iloc[0]

            if boundary.intersects(tile_polygon).any():
                tiles.append(name)

    return sorted(tiles)


def download_tile(name):
    """
    Download one SRTM tile using Earthdata .netrc authentication.

    Authentication is intentionally delegated to curl so that
    your existing ~/.netrc and ~/.urs_cookies are used.
    """

    zip_path = TILES_DIR / f"{name}.SRTMGL1.hgt.zip"
    hgt_path = TILES_DIR / f"{name}.hgt"

    if hgt_path.exists():
        print(f"  EXISTS: {name}.hgt")
        return True

    url = tile_url(name)

    print(f"\n  Downloading: {name}")
    print(f"  URL: {url}")

    cmd = [
        "curl",
        "-n",
        "-b",
        str(Path.home() / ".urs_cookies"),
        "-c",
        str(Path.home() / ".urs_cookies"),
        "-L",
        "-f",
        "--retry",
        "3",
        "--retry-delay",
        "2",
        "-o",
        str(zip_path),
        url,
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"  FAILED DOWNLOAD: {name}")
        return False

    print(f"  Downloaded: {zip_path}")

    # Extract only the HGT file.
    result = subprocess.run(
        [
            "unzip",
            "-o",
            str(zip_path),
            "-d",
            str(TILES_DIR),
        ]
    )

    if result.returncode != 0:
        print(f"  FAILED EXTRACTION: {name}")
        return False

    # NASA archive extracts as N28E084.hgt, etc.
    extracted = TILES_DIR / f"{name}.hgt"

    if not extracted.exists():
        print(f"  ERROR: expected {extracted} was not created")
        return False

    print(f"  Extracted: {extracted}")

    return True


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - NEPAL SRTM DEM DOWNLOADER")
    print("=" * 80)

    DEM_DIR.mkdir(parents=True, exist_ok=True)
    TILES_DIR.mkdir(parents=True, exist_ok=True)

    print("\nLoading Nepal boundary:")
    print(f"  {BOUNDARY_FILE}")

    if not BOUNDARY_FILE.exists():
        raise FileNotFoundError(
            f"Nepal boundary not found:\n{BOUNDARY_FILE}"
        )

    gdf = gpd.read_file(BOUNDARY_FILE)

    if gdf.empty:
        raise RuntimeError("Nepal boundary is empty.")

    # Ensure geographic coordinates.
    if gdf.crs is None:
        raise RuntimeError("Nepal boundary has no CRS.")

    boundary = gdf.to_crs("EPSG:4326")

    print(f"  Features: {len(boundary)}")
    print(f"  CRS: {boundary.crs}")

    minx, miny, maxx, maxy = boundary.total_bounds

    print("\nNepal boundary extent:")
    print(f"  Longitude: {minx:.6f} -> {maxx:.6f}")
    print(f"  Latitude : {miny:.6f} -> {maxy:.6f}")

    print("\nFinding required SRTM tiles...")

    tiles = get_required_tiles(boundary)

    print(f"\nRequired SRTM tiles: {len(tiles)}")

    for name in tiles:
        print(f"  {name}")

    print("\n" + "=" * 80)
    print("DOWNLOADING / EXTRACTING")
    print("=" * 80)

    success = []
    failed = []

    for index, name in enumerate(tiles, start=1):

        print(
            f"\n[{index}/{len(tiles)}] {name}"
        )

        if download_tile(name):
            success.append(name)
        else:
            failed.append(name)

    print("\n" + "=" * 80)
    print("DOWNLOAD SUMMARY")
    print("=" * 80)

    print(f"Required : {len(tiles)}")
    print(f"Success  : {len(success)}")
    print(f"Failed   : {len(failed)}")

    if failed:
        print("\nFailed tiles:")
        for name in failed:
            print(f"  {name}")

        raise RuntimeError(
            "Some SRTM tiles failed. Fix them before creating the DEM."
        )

    # --------------------------------------------------------
    # Build VRT
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print("BUILDING SRTM VIRTUAL MOSAIC")
    print("=" * 80)

    hgt_files = [
        str(TILES_DIR / f"{name}.hgt")
        for name in success
    ]

    vrt_cmd = [
        "gdalbuildvrt",
        "-overwrite",
        str(OUTPUT_VRT),
        *hgt_files,
    ]

    result = subprocess.run(vrt_cmd)

    if result.returncode != 0:
        raise RuntimeError("gdalbuildvrt failed.")

    print(f"\nVRT created:")
    print(f"  {OUTPUT_VRT}")

    # --------------------------------------------------------
    # Clip to Nepal
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print("CLIPPING DEM TO NEPAL")
    print("=" * 80)

    clip_cmd = [
        "gdalwarp",
        "-overwrite",
        "-cutline",
        str(BOUNDARY_FILE),
        "-crop_to_cutline",
        "-dstnodata",
        "-32768",
        "-of",
        "GTiff",
        "-co",
        "TILED=YES",
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "BIGTIFF=IF_SAFER",
        str(OUTPUT_VRT),
        str(OUTPUT_DEM),
    ]

    result = subprocess.run(clip_cmd)

    if result.returncode != 0:
        raise RuntimeError("gdalwarp clipping failed.")

    print(f"\nFinal Nepal DEM:")
    print(f"  {OUTPUT_DEM}")

    print("\n" + "=" * 80)
    print("PRAVAH SRTM DEM COMPLETE")
    print("=" * 80)

    print(f"""
Output:
  {OUTPUT_DEM}

Tiles:
  {len(success)}

Next:
  Verify DEM with gdalinfo
""")


if __name__ == "__main__":
    main()
