import requests
import datetime
import re
import os
import rasterio
import numpy as np


# ============================================================
# CONFIG
# ============================================================

NASA_USER = "sansar.chhetri@study.lbef.edu.np"
NASA_PASS = "sansar.chhetri@study.lbef.edu.np"

OUTPUT_FILE = "latest_imerg_30min.tif"


# ============================================================
# NASA DIRECTORY
# ============================================================

now_utc = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=4)

yyyy = now_utc.strftime("%Y")
mm = now_utc.strftime("%m")

NASA_URL = (
    f"https://jsimpsonhttps.pps.eosdis.nasa.gov/"
    f"imerg/gis/early/{yyyy}/{mm}/"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 90)
print("PRAVAH - NASA IMERG EARLY RUN DOWNLOAD TEST")
print("=" * 90)

print(f"NASA directory:")
print(NASA_URL)
print()


# ============================================================
# 1. GET DIRECTORY
# ============================================================

print("[1] Accessing NASA directory...")

response = requests.get(
    NASA_URL,
    auth=(NASA_USER, NASA_PASS),
    timeout=30
)

response.raise_for_status()

print(f"[✓] HTTP Status: {response.status_code}")


# ============================================================
# 2. FIND 30-MINUTE TIFF FILES
# ============================================================

print("\n[2] Finding 30-minute IMERG TIFF files...")

tif_files = re.findall(
    r'href=["\']([^"\']+\.tif)["\']',
    response.text,
    re.IGNORECASE
)

# Only keep 30-minute products
tif_files = [
    f for f in tif_files
    if ".30min.tif" in f
]

print(f"[✓] 30-minute TIFF files found: {len(tif_files)}")


if not tif_files:

    print("[!] No 30-minute TIFF files found.")
    exit()


# ============================================================
# 3. GET LATEST FILE
# ============================================================

latest_file = tif_files[-1]

print()
print("[3] Latest IMERG file:")
print(latest_file)


download_url = NASA_URL + latest_file

print()
print("Download URL:")
print(download_url)


# ============================================================
# 4. DOWNLOAD
# ============================================================

print()
print("[4] Downloading latest IMERG GeoTIFF...")

file_response = requests.get(
    download_url,
    auth=(NASA_USER, NASA_PASS),
    stream=True,
    timeout=60
)

file_response.raise_for_status()

with open(OUTPUT_FILE, "wb") as f:

    for chunk in file_response.iter_content(
        chunk_size=1024 * 1024
    ):

        if chunk:
            f.write(chunk)


file_size = os.path.getsize(OUTPUT_FILE)

print("[✓] Download complete")

print(
    f"[✓] Local file: {OUTPUT_FILE}"
)

print(
    f"[✓] File size: {file_size / (1024 * 1024):.2f} MB"
)


# ============================================================
# 5. OPEN GEOTIFF
# ============================================================

print()
print("[5] Inspecting GeoTIFF...")

with rasterio.open(OUTPUT_FILE) as src:

    print()
    print("GeoTIFF metadata")
    print("-" * 70)

    print(f"Driver:       {src.driver}")
    print(f"Width:        {src.width}")
    print(f"Height:       {src.height}")
    print(f"Bands:        {src.count}")
    print(f"Data type:    {src.dtypes[0]}")
    print(f"CRS:          {src.crs}")
    print(f"Transform:    {src.transform}")

    print()
    print("Geographic bounds")
    print("-" * 70)

    print(f"Left:         {src.bounds.left}")
    print(f"Right:        {src.bounds.right}")
    print(f"Bottom:       {src.bounds.bottom}")
    print(f"Top:          {src.bounds.top}")


    # ========================================================
    # 6. READ RASTER VALUES
    # ========================================================

    data = src.read(1)

    print()
    print("Raw raster values")
    print("-" * 70)

    print(f"Total pixels: {data.size}")

    print(f"Raw minimum:  {data.min()}")
    print(f"Raw maximum:  {data.max()}")
    print(f"Raw mean:     {data.mean():.2f}")


    # ========================================================
    # 7. FILTER INVALID VALUES
    # ========================================================

    nodata = src.nodata

    print()
    print(f"NoData value: {nodata}")

    valid = data.astype(float)

    if nodata is not None:
        valid[valid == nodata] = np.nan

    valid[valid < 0] = np.nan

    valid_pixels = valid[~np.isnan(valid)]


    if valid_pixels.size > 0:

        print()
        print("Valid precipitation values")
        print("-" * 70)

        print(
            f"Valid pixels: "
            f"{valid_pixels.size}"
        )

        print(
            f"Raw minimum: "
            f"{valid_pixels.min():.2f}"
        )

        print(
            f"Raw maximum: "
            f"{valid_pixels.max():.2f}"
        )

        print(
            f"Raw mean: "
            f"{valid_pixels.mean():.2f}"
        )


        # NASA Early Run GIS values are scaled ×10
        precipitation_mm = valid_pixels / 10.0

        print()
        print("Converted precipitation")
        print("-" * 70)

        print(
            f"Minimum: "
            f"{precipitation_mm.min():.2f} mm"
        )

        print(
            f"Maximum: "
            f"{precipitation_mm.max():.2f} mm"
        )

        print(
            f"Mean: "
            f"{precipitation_mm.mean():.2f} mm"
        )


# ============================================================
# FINISHED
# ============================================================

print()
print("=" * 90)
print("NASA IMERG DOWNLOAD + GEOTIFF TEST COMPLETE")
print("=" * 90)