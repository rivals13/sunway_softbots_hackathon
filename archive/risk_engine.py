import json
from datetime import datetime, timezone


# ============================================================
# PRAVAH RISK ENGINE V3
# ============================================================

LIVE_FILE = "prava_live_fused_data.json"
RUNOFF_FILE = "prava_runoff_data.json"
EVIDENCE_FILE = "prava_evidence_features.json"

OUTPUT_FILE = "prava_risk_data.json"


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


def risk_level(score):

    if score >= 75:
        return "CRITICAL"

    elif score >= 50:
        return "WARNING"

    elif score >= 25:
        return "WATCH"

    return "LOW"


# ============================================================
# START
# ============================================================

print("=" * 80)
print("PRAVAH RISK ENGINE V3")
print("=" * 80)


# ============================================================
# LOAD DATA
# ============================================================

with open(
    LIVE_FILE,
    "r",
    encoding="utf-8"
) as f:

    live_data = json.load(f)


with open(
    RUNOFF_FILE,
    "r",
    encoding="utf-8"
) as f:

    runoff_data = json.load(f)


with open(
    EVIDENCE_FILE,
    "r",
    encoding="utf-8"
) as f:

    evidence_data = json.load(f)


live_districts = live_data.get(
    "districts",
    {}
)

runoff_districts = runoff_data.get(
    "districts",
    {}
)

evidence_districts = evidence_data.get(
    "districts",
    []
)


print()
print(
    f"Live districts: "
    f"{len(live_districts)}"
)

print(
    f"Runoff districts: "
    f"{len(runoff_districts)}"
)

print(
    f"Evidence districts: "
    f"{len(evidence_districts)}"
)


# ============================================================
# RUNOFF LOOKUP
# ============================================================

runoff_lookup = {}


for district_id, district in runoff_districts.items():

    district_name = district.get(
        "district"
    )

    if district_name:

        runoff_lookup[
            normalize_name(district_name)
        ] = district


# ============================================================
# EVIDENCE LOOKUP
# ============================================================

evidence_lookup = {}


for district in evidence_districts:

    district_name = district.get(
        "district"
    )

    if district_name:

        evidence_lookup[
            normalize_name(district_name)
        ] = district


# ============================================================
# FRESHNESS
# ============================================================

freshness = live_data.get(
    "freshness",
    {}
)


nasa_freshness = freshness.get(
    "nasa",
    {}
)

bipad_rain_freshness = freshness.get(
    "bipad_rain",
    {}
)

bipad_river_freshness = freshness.get(
    "bipad_river",
    {}
)


nasa_available = (
    nasa_freshness.get("status")
    not in (
        None,
        "UNAVAILABLE",
        "MISSING"
    )
)


nasa_fresh = (
    nasa_freshness.get("status")
    == "FRESH"
)


bipad_rain_fresh = (
    bipad_rain_freshness.get("status")
    == "FRESH"
)


bipad_river_fresh = (
    bipad_river_freshness.get("status")
    == "FRESH"
)


# ============================================================
# RISK RESULTS
# ============================================================

risk_results = {}


count_low = 0
count_watch = 0
count_warning = 0
count_critical = 0

count_future_normal = 0
count_future_elevated = 0


# ============================================================
# PROCESS DISTRICTS
# ============================================================

for district_id, live_record in live_districts.items():

    district_name = live_record.get(
        "district"
    )

    score = 0

    evidence = []


    # ========================================================
    # RAINFALL
    # ========================================================

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


    # ========================================================
    # RUNOFF
    # ========================================================

    runoff_record = runoff_lookup.get(
        normalize_name(district_name)
    )


    runoff_depth = None

    runoff_class = None


    if runoff_record:

        scs_cn = runoff_record.get(
            "scs_cn",
            {}
        )

        runoff_depth = safe_float(
            scs_cn.get(
                "runoff_depth_Q_mm"
            )
        )

        runoff_class = scs_cn.get(
            "runoff_class"
        )


    # ========================================================
    # 1. RUNOFF EVIDENCE
    # ========================================================

    if runoff_class == "VERY HIGH RUNOFF":

        score += 40

        evidence.append({

            "type": "runoff",

            "value_mm": runoff_depth,

            "class": runoff_class,

            "points": 40

        })


    elif runoff_class == "HIGH RUNOFF":

        score += 30

        evidence.append({

            "type": "runoff",

            "value_mm": runoff_depth,

            "class": runoff_class,

            "points": 30

        })


    elif runoff_class == "MODERATE RUNOFF":

        score += 20

        evidence.append({

            "type": "runoff",

            "value_mm": runoff_depth,

            "class": runoff_class,

            "points": 20

        })


    elif runoff_class == "LOW RUNOFF":

        score += 10

        evidence.append({

            "type": "runoff",

            "value_mm": runoff_depth,

            "class": runoff_class,

            "points": 10

        })


    elif runoff_class == "NEGLIGIBLE RUNOFF":

        evidence.append({

            "type": "runoff",

            "value_mm": runoff_depth,

            "class": runoff_class,

            "points": 0

        })


    # ========================================================
    # 2. NASA 6-HOUR RAINFALL
    # ========================================================

    if nasa_6h is not None:

        if nasa_6h >= 50:

            score += 25

            evidence.append({

                "type": "nasa_6h_rainfall",

                "value_mm": nasa_6h,

                "points": 25

            })


        elif nasa_6h >= 25:

            score += 15

            evidence.append({

                "type": "nasa_6h_rainfall",

                "value_mm": nasa_6h,

                "points": 15

            })


        elif nasa_6h >= 10:

            score += 8

            evidence.append({

                "type": "nasa_6h_rainfall",

                "value_mm": nasa_6h,

                "points": 8

            })


    # ========================================================
    # 3. BIPAD 1-HOUR RAINFALL
    # ========================================================

    if bipad_1h is not None:

        if bipad_1h >= 50:

            score += 20

            evidence.append({

                "type": "bipad_1h_rainfall",

                "value_mm": bipad_1h,

                "points": 20

            })


        elif bipad_1h >= 25:

            score += 15

            evidence.append({

                "type": "bipad_1h_rainfall",

                "value_mm": bipad_1h,

                "points": 15

            })


        elif bipad_1h >= 10:

            score += 8

            evidence.append({

                "type": "bipad_1h_rainfall",

                "value_mm": bipad_1h,

                "points": 8

            })


    # ========================================================
    # 4. RIVER EVIDENCE
    # ========================================================

    river = live_record.get(
        "river",
        {}
    )


    river_stations = river.get(
        "stations",
        []
    )


    danger_count = 0

    warning_count = 0

    rising_count = 0


    for station in river_stations:

        status = str(
            station.get(
                "status",
                ""
            )
        ).upper()


        trend = str(
            station.get(
                "trend",
                ""
            )
        ).upper()


        # IMPORTANT:
        # Use exact status matching.
        # "BELOW WARNING LEVEL" must NOT
        # be counted as a warning.

        if status in (
            "ABOVE DANGER LEVEL",
            "DANGER"
        ):

            danger_count += 1


        elif status in (
            "ABOVE WARNING LEVEL",
            "WARNING"
        ):

            warning_count += 1


        if "RISING" in trend:

            rising_count += 1


    # --------------------------------------------------------
    # RIVER DANGER
    # --------------------------------------------------------

    if danger_count > 0:

        score += 40

        evidence.append({

            "type": "river_danger",

            "stations": danger_count,

            "points": 40

        })


    # --------------------------------------------------------
    # RIVER WARNING
    # --------------------------------------------------------

    elif warning_count > 0:

        score += 25

        evidence.append({

            "type": "river_warning",

            "stations": warning_count,

            "points": 25

        })


    # --------------------------------------------------------
    # RIVER RISING
    # --------------------------------------------------------

    if rising_count > 0:

        score += 10

        evidence.append({

            "type": "river_rising",

            "stations": rising_count,

            "points": 10

        })


    # ========================================================
    # CURRENT RISK LEVEL
    # ========================================================

    raw_score = score

    level = risk_level(score)


    # ========================================================
    # SAFETY CAP
    # ========================================================

    river_stale = not bipad_river_fresh


    runoff_zero = (
        runoff_depth is None
        or runoff_depth <= 0.1
    )


    nasa_low = (
        nasa_6h is None
        or nasa_6h < 25
    )


    if (
        level in (
            "WARNING",
            "CRITICAL"
        )

        and river_stale

        and runoff_zero

        and nasa_low
    ):

        level = "WATCH"

        evidence.append({

            "type": "safety_cap",

            "reason": (
                "River observations are stale "
                "while runoff and NASA rainfall "
                "remain low."
            ),

            "original_score": raw_score,

            "capped_level": "WATCH"

        })


    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence_score = 0


    if nasa_available:

        confidence_score += 2


    if nasa_fresh:

        confidence_score += 2


    if bipad_rain_fresh:

        confidence_score += 1


    if bipad_river_fresh:

        confidence_score += 2


    if confidence_score >= 6:

        confidence = "HIGH"

    elif confidence_score >= 3:

        confidence = "MEDIUM"

    else:

        confidence = "LOW"


    # ========================================================
    # FUTURE EVIDENCE
    # ========================================================

    evidence_record = evidence_lookup.get(
        normalize_name(district_name)
    )


    future_evidence = {}

    future_outlook = "UNKNOWN"

    future_available = False


    if evidence_record:

        evidence_block = evidence_record.get(
            "evidence",
            {}
        )

        future_evidence = evidence_block.get(
            "future",
            {}
        )


        future_outlook = future_evidence.get(
            "outlook",
            "UNKNOWN"
        )


        future_available = bool(
            evidence_record.get(
                "evidence_summary",
                {}
            ).get(
                "future_evidence_available",
                False
            )
        )


    # ========================================================
    # FUTURE COUNTS
    # ========================================================

    if future_outlook == "ELEVATED":

        count_future_elevated += 1

    elif future_outlook == "NORMAL":

        count_future_normal += 1


    # ========================================================
    # SAVE DISTRICT
    # ========================================================

    risk_results[str(district_id)] = {

        "district_id": int(
            district_id
        ),

        "district": district_name,

        "risk": {

            "score": score,

            "raw_score": raw_score,

            "level": level,

            "confidence": confidence,

            "confidence_score": (
                confidence_score
            )

        },

        "future": {

            "forecast_rainfall": (
                future_evidence.get(
                    "forecast_rainfall"
                )
            ),

            "forecast_runoff": (
                future_evidence.get(
                    "forecast_runoff"
                )
            ),

            "geoglows": (
                future_evidence.get(
                    "geoglows"
                )
            ),

            "outlook": future_outlook,

            "evidence_available": (
                future_available
            )

        },

        "rainfall": {

            "nasa_6h_mm": nasa_6h,

            "bipad_1h_mm": bipad_1h,

            "nasa_role": (
                "Primary rainfall input "
                "for SCS-CN runoff."
            ),

            "bipad_role": (
                "Local rainfall observation "
                "evidence."
            )

        },

        "runoff": {

            "runoff_depth_Q_mm": runoff_depth,

            "runoff_class": runoff_class,

            "source": (
                "prava_runoff_data.json"
            )

        },

        "river": {

            "danger_stations": (
                danger_count
            ),

            "warning_stations": (
                warning_count
            ),

            "rising_stations": (
                rising_count
            ),

            "source": (
                "BIPAD river observations"
            )

        },

        "evidence": evidence

    }


    # ========================================================
    # COUNTS
    # ========================================================

    if level == "LOW":

        count_low += 1

    elif level == "WATCH":

        count_watch += 1

    elif level == "WARNING":

        count_warning += 1

    elif level == "CRITICAL":

        count_critical += 1


# ============================================================
# FINAL OUTPUT
# ============================================================

output = {

    "project": "PRAVAH",

    "pipeline_version": (
        "risk_engine_v3"
    ),

    "generated_at_utc": (
        datetime.now(
            timezone.utc
        ).isoformat()
    ),

    "risk_levels": {

        "LOW": count_low,

        "WATCH": count_watch,

        "WARNING": count_warning,

        "CRITICAL": count_critical

    },

    "future_outlook": {

        "NORMAL": count_future_normal,

        "ELEVATED": count_future_elevated

    },

    "methodology": {

        "current_risk": (
            "Current risk preserves the "
            "validated Risk Engine V2 "
            "scoring and thresholds."
        ),

        "rainfall": (
            "NASA IMERG Early 6-hour "
            "district rainfall is the "
            "primary rainfall input "
            "for SCS-CN."
        ),

        "runoff": (
            "SCS-CN estimates direct "
            "runoff depth in mm."
        ),

        "bipad_rain": (
            "BIPAD 1-hour rainfall is "
            "retained as local observation "
            "evidence."
        ),

        "river": (
            "BIPAD river observations "
            "provide station-level "
            "evidence."
        ),

        "future": (
            "Forecast rainfall, forecast "
            "runoff and GEOGLOWS evidence "
            "are reported as a separate "
            "future outlook."
        ),

        "future_risk_policy": (
            "Future ELEVATED outlook does "
            "not automatically increase "
            "the current risk level."
        ),

        "geoglows_note": (
            "GEOGLOWS discharge is treated "
            "as future hydrological evidence "
            "and is not directly compared "
            "with BIPAD water-level thresholds."
        ),

        "unit_note": (
            "SCS-CN runoff depth in mm "
            "is not directly compared "
            "with river discharge "
            "thresholds in m3/s."
        )

    },

    "freshness": {

        "nasa": nasa_freshness,

        "bipad_rain": (
            bipad_rain_freshness
        ),

        "bipad_river": (
            bipad_river_freshness
        )

    },

    "districts": risk_results

}


# ============================================================
# SAVE
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
print("RISK SUMMARY")
print("=" * 80)

print(
    f"LOW:      {count_low}"
)

print(
    f"WATCH:    {count_watch}"
)

print(
    f"WARNING:  {count_warning}"
)

print(
    f"CRITICAL: {count_critical}"
)

print()
print("=" * 80)
print("FUTURE OUTLOOK")
print("=" * 80)

print(
    f"NORMAL:   {count_future_normal}"
)

print(
    f"ELEVATED: {count_future_elevated}"
)


print()
print("=" * 80)
print("DISTRICTS ABOVE LOW RISK")
print("=" * 80)


found = False


for district_id, result in risk_results.items():

    level = result["risk"]["level"]


    if level != "LOW":

        found = True

        print(

            f"{result['district_id']:>2} | "

            f"{result['district']:<20} | "

            f"Score="
            f"{result['risk']['score']:>3} | "

            f"{level:<8} | "

            f"Confidence="
            f"{result['risk']['confidence']} | "

            f"Future="
            f"{result['future']['outlook']}"

        )


if not found:

    print(
        "No districts currently "
        "above LOW risk."
    )


print()
print("=" * 80)
print("PRAVAH RISK ENGINE V3 COMPLETE")
print("=" * 80)

print(
    f"Saved: {OUTPUT_FILE}"
)   