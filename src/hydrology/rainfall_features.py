import json
from pathlib import Path
from datetime import datetime, timezone
from src.config import LIVE_FUSED_FILE, DISTRICT_CN_FILE, RAINFALL_FILE

# ============================================================
# PRAVAH - RAINFALL FEATURE ENGINE
# ============================================================


INPUT_FILE = LIVE_FUSED_FILE
CN_FILE = DISTRICT_CN_FILE
OUTPUT_FILE = RAINFALL_FILE

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value):
    """Convert a value to float, otherwise return None."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_scs_cn_runoff(rainfall_mm, cn):
    """
    SCS Curve Number runoff calculation.

    P = rainfall in mm
    CN = Curve Number
    S = potential maximum retention
    Ia = initial abstraction

    S = (25400 / CN) - 254

    Ia = 0.2S

    If P <= Ia:
        Q = 0

    Otherwise:

        Q = (P - Ia)^2 / (P + 0.8S)
    """

    rainfall_mm = safe_float(rainfall_mm)
    cn = safe_float(cn)

    if rainfall_mm is None:
        return None

    if cn is None:
        return None

    if rainfall_mm <= 0:
        return 0.0

    if cn <= 0 or cn >= 100:
        return None

    S = (25400 / cn) - 254

    initial_abstraction = 0.2 * S

    if rainfall_mm <= initial_abstraction:
        return 0.0

    runoff = (
        (rainfall_mm - initial_abstraction) ** 2
        / (rainfall_mm + 0.8 * S)
    )

    return round(runoff, 3)


def calculate_rainfall_intensity(rainfall_6h):
    """
    Average rainfall intensity over 6 hours.
    """

    rainfall_6h = safe_float(rainfall_6h)

    if rainfall_6h is None:
        return None

    return round(rainfall_6h / 6.0, 3)


def calculate_antecedent_indicator(rainfall_3d, rainfall_5d):
    """
    Prototype antecedent rainfall indicator.

    3-day rainfall = 60%
    5-day rainfall = 40%

    This is NOT a formal AMC classification.
    """

    r3 = safe_float(rainfall_3d)
    r5 = safe_float(rainfall_5d)

    if r3 is None and r5 is None:
        return None

    if r3 is None:
        return round(r5, 3)

    if r5 is None:
        return round(r3, 3)

    indicator = (r3 * 0.60) + (r5 * 0.40)

    return round(indicator, 3)


def classify_rainfall_intensity(rainfall_6h):
    """
    Prototype classification.

    These thresholds are NOT official Nepal warning thresholds.
    """

    rainfall_6h = safe_float(rainfall_6h)

    if rainfall_6h is None:
        return "NO_DATA"

    if rainfall_6h < 10:
        return "LOW"

    if rainfall_6h < 25:
        return "MODERATE"

    if rainfall_6h < 50:
        return "HIGH"

    return "VERY_HIGH"


def calculate_rainfall_persistence(
    rainfall_6h,
    rainfall_12h,
    rainfall_24h
):
    """
    Prototype rainfall persistence indicator.
    """

    r6 = safe_float(rainfall_6h)
    r12 = safe_float(rainfall_12h)
    r24 = safe_float(rainfall_24h)

    if r6 is None or r12 is None or r24 is None:
        return None

    if r12 <= 0 or r24 <= 0:
        return None

    ratio_12 = r6 / r12
    ratio_24 = r12 / r24

    persistence = (ratio_12 + ratio_24) / 2

    return round(persistence, 3)


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


def load_cn_data():
    """
    Load district-specific Curve Number data.

    Uses cn_average from district_cn.json.
    """

    if not CN_FILE.exists():

        print("\nERROR: CN file not found:")
        print(CN_FILE)

        return {}

    try:

        with open(
            CN_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            cn_data = json.load(f)

    except json.JSONDecodeError as e:

        print("\nERROR: Invalid CN JSON:")
        print(e)

        return {}

    print(
        f"District CN records loaded: {len(cn_data)}"
    )

    return cn_data


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - RAINFALL FEATURE ENGINE")
    print("=" * 80)

    # ========================================================
    # LOAD FUSED DATA
    # ========================================================

    if not INPUT_FILE.exists():

        print("\nERROR: Input file not found:")
        print(INPUT_FILE)

        return

    print("\nLoading rainfall data:")
    print(INPUT_FILE)

    try:

        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            fused_data = json.load(f)

    except json.JSONDecodeError as e:

        print("\nERROR: Invalid fused JSON:")
        print(e)

        return

    # ========================================================
    # LOAD CN DATA
    # ========================================================

    print("\nLoading district Curve Numbers:")
    print(CN_FILE)

    cn_data = load_cn_data()

    if not cn_data:

        print("\nERROR: No CN data loaded.")
        return

    # ========================================================
    # GET DISTRICTS
    # ========================================================

    districts_raw = fused_data.get("districts")

    if districts_raw is None:

        print("\nERROR: 'districts' field not found.")

        return

    print(
        "\nDistrict data type:",
        type(districts_raw).__name__
    )

    districts = get_district_records(
        districts_raw
    )

    print(
        "Districts received:",
        len(districts)
    )

    # ========================================================
    # OUTPUT STRUCTURE
    # ========================================================

    output = {

        "project": "PRAVAH",

        "pipeline_version": "rainfall_features_v3",

        "generated_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),

        "source_file": str(INPUT_FILE),

        "curve_number_source": str(CN_FILE),

        "analysis_window_hours": (
            fused_data.get(
                "analysis_window_hours"
            )
        ),

        "district_count": len(districts),

        # ----------------------------------------------------
        # Semantics
        # ----------------------------------------------------

        "feature_semantics": {

            "bipad_1h": (
                "Maximum available 1-hour rainfall "
                "observation from BIPAD ground stations "
                "within the district."
            ),

            "nasa_6h": (
                "NASA IMERG district-level spatial "
                "average rainfall accumulated over 6 hours."
            ),

            "nasa_12h": (
                "NASA IMERG district-level spatial "
                "average rainfall accumulated over 12 hours."
            ),

            "nasa_24h": (
                "NASA IMERG district-level spatial "
                "average rainfall accumulated over 24 hours."
            ),

            "nasa_3day": (
                "NASA IMERG district-level rainfall "
                "accumulated over 3 days."
            ),

            "nasa_5day": (
                "NASA IMERG district-level rainfall "
                "accumulated over 5 days."
            ),

            "nasa_7day": (
                "NASA IMERG district-level rainfall "
                "accumulated over 7 days when sufficient "
                "continuous coverage exists."
            ),

            "antecedent_rainfall_indicator": (
                "Prototype indicator using recent "
                "3-day and 5-day rainfall."
            ),

            "rainfall_intensity": (
                "Average rainfall intensity based on "
                "the 6-hour rainfall window."
            ),

            "rainfall_persistence": (
                "Prototype indicator describing rainfall "
                "distribution across 6h, 12h and 24h windows."
            ),

            "scs_cn_runoff": (
                "Direct runoff estimate using the "
                "district-specific SCS Curve Number."
            ),

            "curve_number": (
                "District-specific average Curve Number "
                "loaded from district_cn.json."
            )
        },

        # ----------------------------------------------------
        # SCS-CN
        # ----------------------------------------------------

        "scs_cn": {

            "method": "SCS-CN",

            "source_file": str(CN_FILE),

            "cn_field": "cn_average",

            "formula": (
                "Q=(P-0.2S)^2/(P+0.8S)"
            ),

            "retention_formula": (
                "S=(25400/CN)-254"
            ),

            "initial_abstraction": "Ia=0.2S",

            "note": (
                "District-specific average Curve Numbers "
                "are used. CN values are derived from the "
                "provided district CN dataset."
            )
        },

        "districts": []
    }

    # ========================================================
    # COUNTERS
    # ========================================================

    processed = 0

    missing_rainfall = 0

    missing_cn = 0

    nasa_6h_available = 0

    nasa_24h_available = 0

    runoff_available = 0

    # ========================================================
    # PROCESS DISTRICTS
    # ========================================================

    for district in districts:

        district_id = district.get(
            "district_id"
        )

        district_name = district.get(
            "district"
        )

        # ----------------------------------------------------
        # RAINFALL
        # ----------------------------------------------------

        rainfall = district.get(
            "rainfall",
            {}
        )

        if not isinstance(rainfall, dict):
            rainfall = {}

        # ----------------------------------------------------
        # BIPAD
        # ----------------------------------------------------

        bipad_1h = safe_float(
            rainfall.get(
                "bipad_1h_max"
            )
        )

        bipad_station_count = rainfall.get(
            "bipad_station_count",
            0
        )

        bipad_latest_observed_at = rainfall.get(
            "bipad_latest_observed_at"
        )

        # ----------------------------------------------------
        # NASA
        # ----------------------------------------------------

        nasa_30min = safe_float(
            rainfall.get(
                "nasa_30min_mm"
            )
        )

        nasa_1h = safe_float(
            rainfall.get(
                "nasa_1h_mm"
            )
        )

        nasa_3h = safe_float(
            rainfall.get(
                "nasa_3h_mm"
            )
        )

        nasa_6h = safe_float(
            rainfall.get(
                "nasa_6h_mm"
            )
        )

        nasa_12h = safe_float(
            rainfall.get(
                "nasa_12h_mm"
            )
        )

        nasa_24h = safe_float(
            rainfall.get(
                "nasa_24h_mm"
            )
        )

        nasa_3day = safe_float(
            rainfall.get(
                "nasa_3day_mm"
            )
        )

        nasa_5day = safe_float(
            rainfall.get(
                "nasa_5day_mm"
            )
        )

        nasa_7day = safe_float(
            rainfall.get(
                "nasa_7day_mm"
            )
        )

        nasa_timesteps = rainfall.get(
            "nasa_timesteps"
        )

        nasa_coverage = rainfall.get(
            "nasa_available_coverage_hours"
        )

        nasa_gap_count = rainfall.get(
            "nasa_gap_count"
        )

        nasa_source = rainfall.get(
            "nasa_source"
        )

        # ====================================================
        # DISTRICT CN
        # ====================================================

        cn_record = cn_data.get(
            district_name
        )

        if cn_record is None:

            missing_cn += 1

            cn_average = None

        else:

            cn_average = safe_float(
                cn_record.get(
                    "cn_average"
                )
            )

        # ====================================================
        # DERIVED FEATURES
        # ====================================================

        antecedent_indicator = (
            calculate_antecedent_indicator(
                nasa_3day,
                nasa_5day
            )
        )

        rainfall_intensity = (
            calculate_rainfall_intensity(
                nasa_6h
            )
        )

        intensity_class = (
            classify_rainfall_intensity(
                nasa_6h
            )
        )

        rainfall_persistence = (
            calculate_rainfall_persistence(
                nasa_6h,
                nasa_12h,
                nasa_24h
            )
        )

        # ====================================================
        # SCS-CN RUNOFF
        # ====================================================

        runoff_6h = (
            calculate_scs_cn_runoff(
                nasa_6h,
                cn_average
            )
        )

        # ====================================================
        # DATA QUALITY
        # ====================================================

        expected_windows = [
            nasa_6h,
            nasa_12h,
            nasa_24h,
            nasa_3day,
            nasa_5day
        ]

        available_windows = sum(
            value is not None
            for value in expected_windows
        )

        if available_windows == 0:
            missing_rainfall += 1

        if nasa_6h is not None:
            nasa_6h_available += 1

        if nasa_24h is not None:
            nasa_24h_available += 1

        if runoff_6h is not None:
            runoff_available += 1

        # ====================================================
        # OUTPUT RECORD
        # ====================================================

        district_output = {

            "district_id": district_id,

            "district": district_name,

            # ------------------------------------------------
            # Rainfall
            # ------------------------------------------------

            "rainfall": {

                "bipad_1h_mm": bipad_1h,

                "nasa_30min_mm": nasa_30min,

                "nasa_1h_mm": nasa_1h,

                "nasa_3h_mm": nasa_3h,

                "nasa_6h_mm": nasa_6h,

                "nasa_12h_mm": nasa_12h,

                "nasa_24h_mm": nasa_24h,

                "nasa_3day_mm": nasa_3day,

                "nasa_5day_mm": nasa_5day,

                "nasa_7day_mm": nasa_7day
            },

            # ------------------------------------------------
            # Hydrological features
            # ------------------------------------------------

            "hydrological_features": {

                "antecedent_rainfall_indicator": (
                    antecedent_indicator
                ),

                "rainfall_intensity_6h_mm_per_hour": (
                    rainfall_intensity
                ),

                "rainfall_intensity_class": (
                    intensity_class
                ),

                "rainfall_persistence": (
                    rainfall_persistence
                ),

                "scs_cn_runoff_6h_mm": (
                    runoff_6h
                )
            },

            # ------------------------------------------------
            # District-specific CN
            # ------------------------------------------------

            "scs_cn": {

                "curve_number": cn_average,

                "curve_number_source": (
                    "district_cn.json"
                ),

                "curve_number_field": (
                    "cn_average"
                ),

                "rainfall_input_mm": nasa_6h,

                "runoff_mm": runoff_6h
            },

            # ------------------------------------------------
            # Source information
            # ------------------------------------------------

            "source_information": {

                "bipad": {

                    "station_count": (
                        bipad_station_count
                    ),

                    "latest_observed_at": (
                        bipad_latest_observed_at
                    )
                },

                "nasa": {

                    "source": nasa_source,

                    "timesteps": nasa_timesteps,

                    "available_coverage_hours": (
                        nasa_coverage
                    ),

                    "gap_count": (
                        nasa_gap_count
                    )
                }
            },

            # ------------------------------------------------
            # Data quality
            # ------------------------------------------------

            "data_quality": {

                "available_rainfall_windows": (
                    available_windows
                ),

                "expected_rainfall_windows": 5,

                "rainfall_data_available": (
                    available_windows > 0
                ),

                "nasa_6h_available": (
                    nasa_6h is not None
                ),

                "nasa_24h_available": (
                    nasa_24h is not None
                ),

                "nasa_7day_available": (
                    nasa_7day is not None
                ),

                "curve_number_available": (
                    cn_average is not None
                ),

                "runoff_available": (
                    runoff_6h is not None
                )
            }
        }

        output["districts"].append(
            district_output
        )

        processed += 1

    # ========================================================
    # SAVE
    # ========================================================

    try:

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

    except OSError as e:

        print("\nERROR: Could not write output:")
        print(e)

        return

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n")
    print("=" * 80)
    print("RAINFALL FEATURE ENGINE COMPLETE")
    print("=" * 80)

    print(
        f"\nDistricts processed       : {processed}"
    )

    print(
        f"Missing rainfall          : {missing_rainfall}"
    )

    print(
        f"Missing Curve Number      : {missing_cn}"
    )

    print(
        f"NASA 6h available         : "
        f"{nasa_6h_available}/{processed}"
    )

    print(
        f"NASA 24h available        : "
        f"{nasa_24h_available}/{processed}"
    )

    print(
        f"SCS-CN runoff available   : "
        f"{runoff_available}/{processed}"
    )

    print(
        "\nCurve Number source       : "
        "district_cn.json"
    )

    print(
        "Curve Number field        : "
        "cn_average"
    )

    print("\nGenerated features:")

    print("  ✓ BIPAD 1h rainfall")

    print("  ✓ NASA 30min rainfall")

    print("  ✓ NASA 1h rainfall")

    print("  ✓ NASA 3h rainfall")

    print("  ✓ NASA 6h rainfall")

    print("  ✓ NASA 12h rainfall")

    print("  ✓ NASA 24h rainfall")

    print("  ✓ NASA 3-day rainfall")

    print("  ✓ NASA 5-day rainfall")

    print("  ✓ NASA 7-day rainfall")

    print("  ✓ Antecedent rainfall indicator")

    print("  ✓ Rainfall intensity")

    print("  ✓ Rainfall persistence")

    print("  ✓ District-specific SCS-CN runoff")

    print("\nOutput:")
    print(
        f"  {OUTPUT_FILE}"
    )

    print("\nNext layer:")
    print("  BIPAD River Feature Engine")

    print("=" * 80)


if __name__ == "__main__":
    main()
