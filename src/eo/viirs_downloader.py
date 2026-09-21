import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from src.config import VIIRS_DIR


BASE_URL = (
    "https://nrt3.modaps.eosdis.nasa.gov/"
    "archive/allData/5200/VCDWD_L3_NRT"
)

PRODUCT = "VCDWD_L3_NRT"

NEPAL_MIN_LON = 80.0
NEPAL_MAX_LON = 88.3
NEPAL_MIN_LAT = 26.3
NEPAL_MAX_LAT = 30.5

TOKEN = os.getenv("NASA_EARTHDATA_TOKEN")

if not TOKEN:
    print("ERROR: NASA_EARTHDATA_TOKEN is not set.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}


# ============================================================
# NASA DAY LISTING
# ============================================================

def get_day_listing(year, doy):

    url = f"{BASE_URL}/{year}/{doy}/"

    print(f"Checking: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

    if response.status_code != 200:
        print(f"HTTP {response.status_code}")
        return None

    return response.text


# ============================================================
# FIND H5 FILES
# ============================================================

def extract_h5_files(html):

    soup = BeautifulSoup(html, "html.parser")

    files = set()

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if href.endswith(".h5"):

            filename = href.split("/")[-1]

            if filename.startswith(PRODUCT):
                files.add(filename)

    return sorted(files)


# ============================================================
# TILE BOUNDS
# ============================================================

def tile_bounds(filename):

    match = re.search(
        r"\.h(\d{2})v(\d{2})\.",
        filename
    )

    if not match:
        return None

    h = int(match.group(1))
    v = int(match.group(2))

    min_lon = h * 10 - 180
    max_lon = min_lon + 10

    min_lat = 90 - (v + 1) * 10
    max_lat = min_lat + 10

    return (
        min_lon,
        max_lon,
        min_lat,
        max_lat
    )


# ============================================================
# CHECK WHETHER TILE COVERS NEPAL
# ============================================================

def intersects_nepal(filename):

    bounds = tile_bounds(filename)

    if bounds is None:
        return False

    min_lon, max_lon, min_lat, max_lat = bounds

    longitude_overlap = (
        max_lon > NEPAL_MIN_LON
        and min_lon < NEPAL_MAX_LON
    )

    latitude_overlap = (
        max_lat > NEPAL_MIN_LAT
        and min_lat < NEPAL_MAX_LAT
    )

    return (
        longitude_overlap
        and latitude_overlap
    )


# ============================================================
# FIND NEWEST AVAILABLE NEPAL OBSERVATION
# ============================================================

def find_latest_nepal_files(max_days_back=7):

    today = datetime.now(timezone.utc).date()

    for offset in range(max_days_back + 1):

        date = today - timedelta(days=offset)

        year = date.strftime("%Y")
        doy = date.strftime("%j")

        html = get_day_listing(year, doy)

        if not html:
            continue

        files = extract_h5_files(html)

        if not files:
            continue

        nepal_files = [
            filename
            for filename in files
            if intersects_nepal(filename)
        ]

        if nepal_files:

            return (
                date,
                year,
                doy,
                nepal_files
            )

    return None


# ============================================================
# DOWNLOAD FILE
# ============================================================

def download_file(filename, year, doy):

    VIIRS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = VIIRS_DIR / filename

    if output_path.exists():

        print(
            f"Already exists: {filename}"
        )

        return output_path

    url = (
        f"{BASE_URL}/"
        f"{year}/{doy}/"
        f"{filename}"
    )

    print(f"Downloading: {filename}")

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            stream=True,
            timeout=120
        )

    except requests.RequestException as e:

        print(
            f"FAILED: request error: {e}"
        )

        return None

    if response.status_code != 200:

        print(
            f"FAILED: HTTP {response.status_code}"
        )

        return None

    try:

        with open(
            output_path,
            "wb"
        ) as f:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if chunk:
                    f.write(chunk)

    except Exception as e:

        print(
            f"FAILED: could not save file: {e}"
        )

        if output_path.exists():
            output_path.unlink()

        return None

    if not output_path.exists():

        print(
            f"FAILED: file was not created: "
            f"{filename}"
        )

        return None

    print(
        f"Saved: {output_path}"
    )

    return output_path


# ============================================================
# EXTRACT OBSERVATION DATE FROM FILENAME
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

        return (
            datetime(
                year,
                1,
                1
            )
            + timedelta(days=doy - 1)
        ).date()

    except ValueError:

        return None


# ============================================================
# CLEAN OLD VIIRS OBSERVATIONS
# ============================================================

def cleanup_old_observations(latest_date):

    print()
    print("=" * 80)
    print("CLEANING OLD VIIRS OBSERVATIONS")
    print("=" * 80)

    all_files = sorted(
        VIIRS_DIR.glob(
            f"{PRODUCT}*.h5"
        )
    )

    removed = 0
    kept = 0

    for path in all_files:

        file_date = observation_date_from_filename(
            path.name
        )

        if file_date is None:

            print(
                f"Skipping unknown-date file: "
                f"{path.name}"
            )

            continue

        if file_date == latest_date:

            print(
                f"KEEP: {path.name}"
            )

            kept += 1

        elif file_date < latest_date:

            try:

                path.unlink()

                print(
                    f"REMOVE: {path.name}"
                )

                removed += 1

            except Exception as e:

                print(
                    f"FAILED TO REMOVE: "
                    f"{path.name} -> {e}"
                )

        else:

            # Future-dated files are never deleted.
            print(
                f"KEEP future-dated file: "
                f"{path.name}"
            )

            kept += 1

    print()
    print(
        f"Kept files   : {kept}"
    )

    print(
        f"Removed files: {removed}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - VIIRS NRT DOWNLOADER")
    print("=" * 80)

    result = find_latest_nepal_files()

    if not result:

        print()
        print(
            "No Nepal VIIRS files found."
        )

        sys.exit(1)

    (
        date,
        year,
        doy,
        files
    ) = result

    print()
    print("=" * 80)
    print("LATEST NEPAL VIIRS OBSERVATION")
    print("=" * 80)

    print(
        f"Date: {date}"
    )

    print(
        f"DOY : {doy}"
    )

    print()

    print("Selected tiles:")

    for filename in files:

        bounds = tile_bounds(filename)

        print(
            f"  {filename}"
        )

        print(
            f"    bounds: "
            f"lon {bounds[0]} to {bounds[1]}, "
            f"lat {bounds[2]} to {bounds[3]}"
        )

    print()
    print("=" * 80)
    print("DOWNLOADING")
    print("=" * 80)

    downloaded = []

    for filename in files:

        path = download_file(
            filename,
            year,
            doy
        )

        if path and path.exists():

            downloaded.append(path)

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    if len(downloaded) != len(files):

        print()
        print("=" * 80)
        print("DOWNLOAD INCOMPLETE")
        print("=" * 80)

        print(
            f"Expected files: {len(files)}"
        )

        print(
            f"Available files: {len(downloaded)}"
        )

        print(
            "OLD FILES WILL NOT BE DELETED."
        )

        sys.exit(1)

    # --------------------------------------------------------
    # CLEAN OLD OBSERVATIONS
    # --------------------------------------------------------

    cleanup_old_observations(date)

    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)

    print(
        f"Observation date: {date}"
    )

    print(
        f"Files available: {len(downloaded)}"
    )

    print(
        f"Directory: {VIIRS_DIR}"
    )


if __name__ == "__main__":
    main()