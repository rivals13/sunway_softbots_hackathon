import rasterio
import numpy as np

INPUT = "data/boundaries/dem/derived/nepal_dem_metric.tif"
OUTPUT = "data/boundaries/dem/derived/nepal_slope_python.tif"

print("=" * 80)
print("PRAVAH TERRAIN SLOPE")
print("=" * 80)

with rasterio.open(INPUT) as src:

    dem = src.read(1).astype(np.float32)

    nodata = src.nodata
    transform = src.transform

    print(f"DEM size       : {src.width} x {src.height}")
    print(f"DEM NoData     : {nodata}")
    print(f"Pixel X        : {transform.a} m")
    print(f"Pixel Y        : {abs(transform.e)} m")
    print(f"CRS            : {src.crs}")

    # ---------------------------------------------------------------
    # Valid DEM cells
    # ---------------------------------------------------------------
    valid = np.isfinite(dem)

    if nodata is not None:
        valid &= dem != nodata

    print(f"Valid DEM cells: {valid.sum():,}")

    # ---------------------------------------------------------------
    # Prevent NoData (-32768) from contaminating gradient calculation
    # ---------------------------------------------------------------
    work = dem.copy()

    fill_value = np.median(dem[valid])
    work[~valid] = fill_value

    # ---------------------------------------------------------------
    # Calculate gradients
    # ---------------------------------------------------------------
    dx = abs(transform.a)
    dy = abs(transform.e)

    dz_dy, dz_dx = np.gradient(work, dy, dx)

    # ---------------------------------------------------------------
    # Calculate slope in degrees
    # ---------------------------------------------------------------
    slope = np.degrees(
        np.arctan(
            np.sqrt(
                dz_dx ** 2 +
                dz_dy ** 2
            )
        )
    ).astype(np.float32)

    # ---------------------------------------------------------------
    # Restore NoData
    # ---------------------------------------------------------------
    slope_nodata = -9999.0

    slope[~valid] = slope_nodata

    # Remove impossible values
    bad = (
        ~np.isfinite(slope) |
        (slope < 0) |
        (slope > 90)
    )

    slope[bad] = slope_nodata

    # ---------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------
    good = slope != slope_nodata

    print()
    print("SLOPE STATISTICS")
    print("-" * 80)
    print(f"Valid cells     : {good.sum():,}")
    print(f"Minimum slope   : {slope[good].min():.3f} degrees")
    print(f"Maximum slope   : {slope[good].max():.3f} degrees")
    print(f"Mean slope      : {slope[good].mean():.3f} degrees")
    print(f"Median slope    : {np.median(slope[good]):.3f} degrees")

    # ---------------------------------------------------------------
    # Write GeoTIFF
    # ---------------------------------------------------------------
    profile = src.profile.copy()

    profile.update(
    dtype=rasterio.float32,
    count=1,
    nodata=slope_nodata,
    compress="lzw",
    tiled=False
)

    with rasterio.open(OUTPUT, "w", **profile) as dst:
        dst.write(slope, 1)

print()
print("=" * 80)
print(f"OUTPUT: {OUTPUT}")
print("=" * 80)