import json
from pathlib import Path
from datetime import datetime, timezone
from src.config import LIVE_FUSED_FILE, RIVER_FILE


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = LIVE_FUSED_FILE
OUTPUT_FILE = RIVER_FILE

# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_district_records(districts):
    """
    Supports both:
        districts = [...]
    and:
        districts = {
            "1": {...},
            "2": {...}
        }
    """

    if isinstance(districts, list):
        return districts

    if isinstance(districts, dict):
        records = []

        for key, value in districts.items():
            if not isinstance(value, dict):
                continue

            district = value.copy()

            if district.get("district_id") is None:
                district["district_id"] = key

            records.append(district)

        return records

    return []


def calculate_utilization(water_level, threshold):
    """
    Calculate:
        water level / warning or danger level
    """

    water_level = safe_float(water_level)
    threshold = safe_float(threshold)

    if water_level is None or threshold is None:
        return None

    if threshold <= 0:
        return None

    return round(water_level / threshold, 3)


def classify_utilization(utilization):
    """
    Prototype classification.

    These are NOT official DHM thresholds.
    They are feature-engineering categories.
    """

    if utilization is None:
        return "NO_DATA"

    if utilization >= 1.0:
        return "THRESHOLD_CROSSED"

    if utilization >= 0.90:
        return "NEAR_THRESHOLD"

    if utilization >= 0.70:
        return "ELEVATED"

    return "NORMAL"


def classify_river_status(
    max_warning_utilization,
    max_danger_utilization,
    warning_station_count,
    danger_station_count
):
    """
    District-level river status.
    """

    danger = safe_float(max_danger_utilization)
    warning = safe_float(max_warning_utilization)

    if danger is not None and danger >= 1.0:
        return "DANGER"

    if danger_station_count > 0:
        return "DANGER"

    if warning is not None and warning >= 1.0:
        return "WARNING"

    if warning_station_count > 0:
        return "WARNING"

    if danger is not None and danger >= 0.90:
        return "NEAR_DANGER"

    if warning is not None and warning >= 0.90:
        return "NEAR_WARNING"

    return "NORMAL"


def get_station_status(
    water_level,
    warning_level,
    danger_level
):
    """
    Determine station-level threshold status.
    """

    water_level = safe_float(water_level)
    warning_level = safe_float(warning_level)
    danger_level = safe_float(danger_level)

    if water_level is None:
        return "NO_DATA"

    if danger_level is not None and water_level >= danger_level:
        return "DANGER"

    if warning_level is not None and water_level >= warning_level:
        return "WARNING"

    if danger_level is not None:
        danger_utilization = water_level / danger_level

        if danger_utilization >= 0.90:
            return "NEAR_DANGER"

    if warning_level is not None:
        warning_utilization = water_level / warning_level

        if warning_utilization >= 0.90:
            return "NEAR_WARNING"

    return "BELOW_WARNING"


def get_river_section(district):
    """
    Extract the river section from the fused district record.
    """

    river = district.get("river")

    if not isinstance(river, dict):
        return {}

    return river


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - BIPAD RIVER FEATURE ENGINE")
    print("=" * 80)

    # --------------------------------------------------------
    # Load fused data
    # --------------------------------------------------------

    print()
    print("Loading river data:")
    print(INPUT_FILE)

    if not INPUT_FILE.exists():
        print()
        print("ERROR: Input file not found:")
        print(INPUT_FILE)
        return

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            fused_data = json.load(f)
    except json.JSONDecodeError as e:
        print()
        print("ERROR: Invalid JSON:")
        print(e)
        return

    districts = fused_data.get("districts", [])

    district_records = get_district_records(districts)

    print()
    print("District data type:", type(districts).__name__)
    print("Districts received:", len(district_records))

    # --------------------------------------------------------
    # Feature metadata
    # --------------------------------------------------------

    generated_at = datetime.now(timezone.utc).isoformat()

    output = {
        "project": "PRAVAH",
        "pipeline_version": "river_features_v1",
        "generated_at_utc": generated_at,
        "source_file": str(INPUT_FILE),
        "district_count": len(district_records),

        "feature_semantics": {
            "river_station_count":
                "Number of BIPAD river monitoring stations available within the district.",

            "max_water_level":
                "Maximum observed water level among available BIPAD river stations in the district.",

            "warning_utilization":
                "Water level divided by the station warning level.",

            "danger_utilization":
                "Water level divided by the station danger level.",

            "warning_station_count":
                "Number of river stations at or above their warning level.",

            "danger_station_count":
                "Number of river stations at or above their danger level.",

            "rising_station_count":
                "Number of river stations reporting a rising river trend.",

            "river_status":
                "Prototype district-level river status derived from warning and danger threshold utilization.",

            "near_warning":
                "True when the maximum warning utilization reaches at least 0.90 but remains below 1.00.",

            "near_danger":
                "True when the maximum danger utilization reaches at least 0.90 but remains below 1.00.",

            "threshold_crossed":
                "True when at least one river station reaches or exceeds its threshold.",

            "note":
                "Threshold categories are prototype analytical features and are not official DHM warning classifications."
        },

        "districts": []
    }

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    districts_processed = 0
    districts_missing_river = 0

    total_stations = 0
    districts_with_river = 0

    districts_with_warning = 0
    districts_with_danger = 0
    districts_with_rising = 0

    # --------------------------------------------------------
    # Process districts
    # --------------------------------------------------------

    for district in district_records:

        district_id = district.get("district_id")
        district_name = district.get("district", "Unknown")

        river = get_river_section(district)

        stations = river.get("stations", [])

        if not isinstance(stations, list):
            stations = []

        if len(stations) > 0:
            districts_with_river += 1
        else:
            districts_missing_river += 1

        station_features = []

        max_water_level = None
        max_warning_utilization = None
        max_danger_utilization = None

        warning_station_count = 0
        danger_station_count = 0
        rising_station_count = 0

        latest_observed_at = river.get("latest_observed_at")

        # ----------------------------------------------------
        # Process stations
        # ----------------------------------------------------

        for station in stations:

            if not isinstance(station, dict):
                continue

            station_name = station.get("station")

            water_level = safe_float(
                station.get("water_level_m")
            )

            warning_level = safe_float(
                station.get("warning_level_m")
            )

            danger_level = safe_float(
                station.get("danger_level_m")
            )

            warning_utilization = safe_float(
                station.get("warning_utilization")
            )

            danger_utilization = safe_float(
                station.get("danger_utilization")
            )

            # ------------------------------------------------
            # Recalculate utilization if missing
            # ------------------------------------------------

            if warning_utilization is None:
                warning_utilization = calculate_utilization(
                    water_level,
                    warning_level
                )

            if danger_utilization is None:
                danger_utilization = calculate_utilization(
                    water_level,
                    danger_level
                )

            # ------------------------------------------------
            # Water level maximum
            # ------------------------------------------------

            if water_level is not None:

                if (
                    max_water_level is None
                    or water_level > max_water_level
                ):
                    max_water_level = water_level

            # ------------------------------------------------
            # Warning utilization maximum
            # ------------------------------------------------

            if warning_utilization is not None:

                if (
                    max_warning_utilization is None
                    or warning_utilization > max_warning_utilization
                ):
                    max_warning_utilization = warning_utilization

            # ------------------------------------------------
            # Danger utilization maximum
            # ------------------------------------------------

            if danger_utilization is not None:

                if (
                    max_danger_utilization is None
                    or danger_utilization > max_danger_utilization
                ):
                    max_danger_utilization = danger_utilization

            # ------------------------------------------------
            # Station threshold status
            # ------------------------------------------------

            station_status = get_station_status(
                water_level,
                warning_level,
                danger_level
            )

            # ------------------------------------------------
            # Counts
            # ------------------------------------------------

            if station_status == "WARNING":
                warning_station_count += 1

            elif station_status == "DANGER":
                danger_station_count += 1

            trend = station.get("trend")

            if isinstance(trend, str):
                if trend.lower() == "rising":
                    rising_station_count += 1

            # ------------------------------------------------
            # Save station-level features
            # ------------------------------------------------

            station_features.append({
                "station": station_name,

                "station_series_id":
                    station.get("station_series_id"),

                "water_level_m":
                    water_level,

                "warning_level_m":
                    warning_level,

                "danger_level_m":
                    danger_level,

                "warning_utilization":
                    warning_utilization,

                "danger_utilization":
                    danger_utilization,

                "warning_utilization_class":
                    classify_utilization(
                        warning_utilization
                    ),

                "danger_utilization_class":
                    classify_utilization(
                        danger_utilization
                    ),

                "status":
                    station_status,

                "trend":
                    trend,

                "observed_at":
                    station.get("observed_at"),

                "source":
                    station.get("source")
            })

        # ----------------------------------------------------
        # District river status
        # ----------------------------------------------------

        river_status = classify_river_status(
            max_warning_utilization,
            max_danger_utilization,
            warning_station_count,
            danger_station_count
        )

        near_warning = (
            max_warning_utilization is not None
            and 0.90 <= max_warning_utilization < 1.0
        )

        near_danger = (
            max_danger_utilization is not None
            and 0.90 <= max_danger_utilization < 1.0
        )

        warning_crossed = (
            max_warning_utilization is not None
            and max_warning_utilization >= 1.0
        )

        danger_crossed = (
            max_danger_utilization is not None
            and max_danger_utilization >= 1.0
        )

        threshold_crossed = (
            warning_crossed
            or danger_crossed
        )

        # ----------------------------------------------------
        # District counters
        # ----------------------------------------------------

        if warning_station_count > 0:
            districts_with_warning += 1

        if danger_station_count > 0:
            districts_with_danger += 1

        if rising_station_count > 0:
            districts_with_rising += 1

        total_stations += len(station_features)
        districts_processed += 1

        # ----------------------------------------------------
        # District output
        # ----------------------------------------------------

        district_output = {
            "district_id": district_id,
            "district": district_name,

            "river": {

                "station_count":
                    len(station_features),

                "max_water_level_m":
                    max_water_level,

                "max_warning_utilization":
                    max_warning_utilization,

                "max_danger_utilization":
                    max_danger_utilization,

                "warning_station_count":
                    warning_station_count,

                "danger_station_count":
                    danger_station_count,

                "rising_station_count":
                    rising_station_count,

                "river_status":
                    river_status,

                "near_warning":
                    near_warning,

                "near_danger":
                    near_danger,

                "warning_crossed":
                    warning_crossed,

                "danger_crossed":
                    danger_crossed,

                "threshold_crossed":
                    threshold_crossed,

                "latest_observed_at":
                    latest_observed_at,

                "trend":
                    river.get("trend"),

                "stations":
                    station_features
            },

            "data_quality": {

                "river_data_available":
                    len(station_features) > 0,

                "station_count":
                    len(station_features),

                "warning_data_available":
                    max_warning_utilization is not None,

                "danger_data_available":
                    max_danger_utilization is not None,

                "latest_observation_available":
                    latest_observed_at is not None
            }
        }

        output["districts"].append(district_output)

    # --------------------------------------------------------
    # Save output
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("RIVER FEATURE ENGINE COMPLETE")
    print("=" * 80)

    print()
    print("Districts processed       :", districts_processed)
    print("Districts with river data :", districts_with_river)
    print("Missing river data        :", districts_missing_river)

    print()
    print("Total river stations      :", total_stations)
    print("Districts with warning    :", districts_with_warning)
    print("Districts with danger     :", districts_with_danger)
    print("Districts with rising     :", districts_with_rising)

    print()
    print("Generated features:")
    print("  ✓ River station count")
    print("  ✓ Maximum water level")
    print("  ✓ Warning utilization")
    print("  ✓ Danger utilization")
    print("  ✓ Warning station count")
    print("  ✓ Danger station count")
    print("  ✓ Rising station count")
    print("  ✓ Near-warning detection")
    print("  ✓ Near-danger detection")
    print("  ✓ Warning threshold detection")
    print("  ✓ Danger threshold detection")
    print("  ✓ District river status")
    print("  ✓ Station-level river features")

    print()
    print("Output:")
    print(" ", OUTPUT_FILE)

    print()
    print("Next layer:")
    print("  Hydrology Feature Fusion")
    print("=" * 80)


if __name__ == "__main__":
    main()
