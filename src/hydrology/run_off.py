import json
from datetime import datetime, timezone
from src.config import LIVE_FUSED_FILE, DISTRICT_CN_FILE, RUNOFF_FILE

# ============================================================
# PRAVAH SCS-CN RUNOFF ENGINE
# ============================================================

LIVE_FILE = LIVE_FUSED_FILE
CN_FILE = DISTRICT_CN_FILE
OUTPUT_FILE = RUNOFF_FILE


# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        value = float(value)

        if value != value:
            return None

        return value

    except (TypeError, ValueError):
        return None


def normalize_name(name):
    if not name:
        return ""

    name = str(name).strip().lower()

    aliases = {
        "tehrathum": "terhathum",
        "terathum": "terhathum",
        "terhathum": "terhathum",

        "sindhupalchowk": "sindhupalchok",

        "dhanusha": "dhanusa",

        "tanahun": "tanahu",

        "kapilvastu": "kapilbastu",

        "ktm": "kathmandu",

        "chitawan": "chitwan",

        "kavre": "kavrepalanchok",

        "nawalparasieast": "nawalparasi east",
        "nawalparasi east": "nawalparasi east",

        "nawalparasiwest": "nawalparasi west",
        "nawalparasi west": "nawalparasi west",

        "rukumeast": "rukum east",
        "rukum east": "rukum east",

        "rukumwest": "rukum west",
        "rukum west": "rukum west",
    }

    return aliases.get(name, name)


def classify_runoff(Q):
    """
    PRAVAH prototype runoff classification.

    These are operational prototype categories,
    NOT official flood-warning thresholds.
    """

    if Q < 0.1:
        return "NEGLIGIBLE RUNOFF"

    elif Q < 5:
        return "LOW RUNOFF"

    elif Q < 20:
        return "MODERATE RUNOFF"

    elif Q < 50:
        return "HIGH RUNOFF"

    else:
        return "VERY HIGH RUNOFF"


# ============================================================
# START
# ============================================================

print("=" * 80)
print("PRAVAH SCS-CN RUNOFF ENGINE")
print("=" * 80)


# ============================================================
# LOAD FILES
# ============================================================

with open(LIVE_FILE, "r", encoding="utf-8") as f:
    live_data = json.load(f)


with open(CN_FILE, "r", encoding="utf-8") as f:
    cn_data = json.load(f)


live_districts = live_data.get("districts", {})


print()
print(f"Live districts: {len(live_districts)}")
print(f"CN districts: {len(cn_data)}")


# ============================================================
# BUILD CN LOOKUP
# ============================================================

cn_lookup = {}


for district_name, values in cn_data.items():

    normalized = normalize_name(district_name)

    cn_average = safe_float(
        values.get("cn_average")
    )

    cn_lookup[normalized] = {
        "district_name": district_name,
        "cn_average": cn_average
    }


print(f"CN lookup entries: {len(cn_lookup)}")


# ============================================================
# RUNOFF CALCULATION
# ============================================================

runoff_results = {}


processed = 0
positive_runoff = 0
zero_runoff = 0
missing_rainfall = 0
missing_cn = 0
invalid_cn = 0


for district_id, live_record in live_districts.items():

    district_name = live_record.get(
        "district",
        f"District {district_id}"
    )


    # --------------------------------------------------------
    # GET RAINFALL
    # --------------------------------------------------------

    rainfall = live_record.get(
        "rainfall",
        {}
    )

    nasa_6h = safe_float(
        rainfall.get("nasa_6h_mm")
    )

    bipad_1h = safe_float(
        rainfall.get("bipad_1h_max")
    )


    if nasa_6h is None:

        missing_rainfall += 1

        continue


    # --------------------------------------------------------
    # GET CURVE NUMBER
    # --------------------------------------------------------

    normalized_name = normalize_name(
        district_name
    )

    cn_record = cn_lookup.get(
        normalized_name
    )


    if cn_record is None:

        missing_cn += 1

        continue


    CN = safe_float(
        cn_record.get("cn_average")
    )


    if CN is None or CN <= 0 or CN >= 100:

        invalid_cn += 1

        continue


    # --------------------------------------------------------
    # SCS-CN CALCULATION
    # --------------------------------------------------------

    P = nasa_6h


    # Potential maximum retention
    S = (25400 / CN) - 254


    # Initial abstraction
    Ia = 0.2 * S


    # Direct runoff
    if P <= Ia:

        Q = 0.0

    else:

        Q = (
            (P - Ia) ** 2
        ) / (
            P - Ia + S
        )


    # --------------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------------

    runoff_class = classify_runoff(Q)


    if Q > 0:

        positive_runoff += 1

    else:

        zero_runoff += 1


    processed += 1


    # --------------------------------------------------------
    # SAVE RESULT
    # --------------------------------------------------------

    runoff_results[str(district_id)] = {

        "district_id": int(district_id),

        "district": district_name,

        "rainfall": {

            "nasa_6h_mm": round(
                P,
                6
            ),

            "rainfall_source": (
                "NASA IMERG Early"
            ),

            "rainfall_role": (
                "district_spatial_rainfall_input"
            ),

            "bipad_1h_mm": (
                round(bipad_1h, 6)
                if bipad_1h is not None
                else None
            ),

            "bipad_role": (
                "local_observation_evidence"
            ),

            "note": (
                "BIPAD rainfall is preserved "
                "separately and is not used as "
                "the SCS-CN rainfall input."
            )

        },

        "curve_number": {

            "cn_average": round(
                CN,
                6
            ),

            "cn_source": (
                "district_cn.json"
            )

        },

        "scs_cn": {

            "potential_retention_S_mm": round(
                S,
                9
            ),

            "initial_abstraction_Ia_mm": round(
                Ia,
                9
            ),

            "runoff_depth_Q_mm": round(
                Q,
                9
            ),

            "runoff_class": runoff_class

        },

        "data_quality": {

            "rainfall_available": True,

            "curve_number_available": True,

            "runoff_available": True

        }

    }


# ============================================================
# OUTPUT
# ============================================================

output = {

    "project": "PRAVAH",

    "pipeline_version": "scs_cn_v2",

    "generated_at_utc": datetime.now(
        timezone.utc
    ).isoformat(),

    "input": {

        "rainfall_source": (
            "NASA IMERG Early"
        ),

        "rainfall_window": (
            "6-hour district rainfall"
        ),

        "curve_number_source": (
            "district_cn.json"
        ),

        "curve_number_type": (
            "CN average"
        )

    },

    "methodology": {

        "formula": (
            "S = 25400/CN - 254; "
            "Ia = 0.2S; "
            "Q = (P-Ia)^2/(P-Ia+S) "
            "when P > Ia, otherwise Q = 0."
        ),

        "runoff_unit": "mm",

        "rainfall_input": (
            "NASA 6-hour district rainfall "
            "is used as the SCS-CN rainfall input."
        ),

        "bipad_role": (
            "BIPAD rainfall is retained separately "
            "as local observation evidence."
        ),

        "classification_note": (
            "Runoff classes are PRAVAH prototype "
            "operational categories and are not "
            "official flood-warning thresholds."
        )

    },

    "statistics": {

        "live_districts": len(live_districts),

        "processed_districts": processed,

        "positive_runoff_districts": positive_runoff,

        "zero_runoff_districts": zero_runoff,

        "missing_rainfall": missing_rainfall,

        "missing_cn": missing_cn,

        "invalid_cn": invalid_cn

    },

    "districts": runoff_results

}


# ============================================================
# SAVE JSON
# ============================================================

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


# ============================================================
# PRINT SUMMARY
# ============================================================

print()
print("=" * 80)
print("RUNOFF SUMMARY")
print("=" * 80)

print(
    f"Processed districts: "
    f"{processed}"
)

print(
    f"Positive runoff districts: "
    f"{positive_runoff}"
)

print(
    f"Zero runoff districts: "
    f"{zero_runoff}"
)

print(
    f"Missing rainfall: "
    f"{missing_rainfall}"
)

print(
    f"Missing CN: "
    f"{missing_cn}"
)

print(
    f"Invalid CN: "
    f"{invalid_cn}"
)


# ============================================================
# POSITIVE RUNOFF DISTRICTS
# ============================================================

print()
print("=" * 80)
print("DISTRICTS WITH POSITIVE RUNOFF")
print("=" * 80)


found = False


for district_id, result in runoff_results.items():

    Q = result["scs_cn"]["runoff_depth_Q_mm"]

    if Q > 0:

        found = True

        district = result["district"]

        P = result["rainfall"]["nasa_6h_mm"]

        CN = result["curve_number"]["cn_average"]

        S = result["scs_cn"][
            "potential_retention_S_mm"
        ]

        Ia = result["scs_cn"][
            "initial_abstraction_Ia_mm"
        ]

        runoff_class = result["scs_cn"][
            "runoff_class"
        ]

        print(
            f"{district_id:>2} | "
            f"{district:<20} | "
            f"NASA6h={P} mm | "
            f"CN={CN} | "
            f"S={S} mm | "
            f"Ia={Ia} mm | "
            f"Q={Q} mm | "
            f"{runoff_class}"
        )


if not found:

    print(
        "No districts currently have "
        "positive direct runoff."
    )


print()
print("=" * 80)
print("PRAVAH SCS-CN RUNOFF ENGINE COMPLETE")
print("=" * 80)

print(
    f"Saved: {OUTPUT_FILE}"
)
