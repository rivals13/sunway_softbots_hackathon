import json
from pathlib import Path
from datetime import datetime, timezone
from src.config import EVIDENCE_FILE, RISK_FILE

# ============================================================
# PRAVAH - FLOOD SIGNAL ENGINE V4
# ============================================================

INPUT_FILE = EVIDENCE_FILE
OUTPUT_FILE = RISK_FILE

ENGINE_VERSION = "flood_signal_engine_v4"

# VIIRS is lagged observational evidence.
# It can strengthen the flood signal but cannot independently
# trigger WARNING or CRITICAL.
EO_MAX_CONTRIBUTION = 15.0

# Forecast evidence represents future conditions.
# It strengthens the flood signal but does not directly
# override observed river warning/danger thresholds.
FUTURE_MAX_CONTRIBUTION = 20.0

# ============================================================
# LOAD
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# HYDROLOGY EXTRACTION
# ============================================================

def extract_hydrology(record):
    """
    Evidence Fusion V4 may provide hydrology information
    in different places depending on the upstream pipeline.

    Prefer the top-level hydrology object, but also safely
    look for hydrological information inside evidence.
    """

    # Evidence Fusion V4 stores hydrology under
    # "hydrology_context".
    # Keep older fallbacks for compatibility.
    hydrology = record.get("hydrology_context", {})

    if not isinstance(hydrology, dict):
        hydrology = {}

    if not hydrology:
        hydrology = record.get("hydrology", {})

    if not isinstance(hydrology, dict):
        hydrology = {}

    evidence = record.get("evidence", {})

    if not isinstance(evidence, dict):
        evidence = {}

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    signal = hydrology.get("hydrological_signal", hydrology.get("signal"))

    if signal is None:
        signal = evidence.get("hydrology_signal", 0)

    try:
        signal = float(signal)
    except (TypeError, ValueError):
        signal = 0.0

    signal = max(0.0, min(signal, 1.0))

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    state = hydrology.get(
        "hydrological_state",
        hydrology.get("state", "UNKNOWN")
    )

    if state is None:
        state = "UNKNOWN"

    # --------------------------------------------------------
    # Signal strength
    # --------------------------------------------------------

    signal_strength = hydrology.get(
        "signal_strength",
        "UNKNOWN"
    )

    if signal_strength is None:
        signal_strength = "UNKNOWN"

    return {
        "state": state,
        "signal": signal,
        "signal_strength": signal_strength
    }


# ============================================================
# FUTURE EVIDENCE EXTRACTION
# ============================================================

def extract_future_evidence(record):
    """
    Extract future evidence from Evidence Fusion V4.

    Future evidence consists of:
      - forecast rainfall
      - forecast runoff
      - GEOGLOWS river outlook
      - combined future outlook

    These are interpreted signals, not raw measurements.
    """

    evidence = record.get(
        "evidence",
        {}
    )

    if not isinstance(evidence, dict):
        evidence = {}

    future = evidence.get(
        "future",
        {}
    )

    if not isinstance(future, dict):
        future = {}

    data_quality = record.get(
        "data_quality",
        {}
    )

    if not isinstance(data_quality, dict):
        data_quality = {}

    forecast_available = bool(
        data_quality.get(
            "forecast_available",
            False
        )
    )

    geoglows_available = bool(
        data_quality.get(
            "geoglows_available",
            False
        )
    )

    return {

        "forecast_available":
            forecast_available,

        "geoglows_available":
            geoglows_available,

        "forecast_rainfall":
            future.get(
                "forecast_rainfall",
                "NO_DATA"
            ),

        "forecast_runoff":
            future.get(
                "forecast_runoff",
                "NO_DATA"
            ),

        "geoglows":
            future.get(
                "geoglows",
                "NO_DATA"
            ),

        "outlook":
            future.get(
                "outlook",
                "UNKNOWN"
            )
    }



# ============================================================
# FUTURE SIGNAL
# ============================================================

def calculate_future_signal(future):
    """
    Convert Evidence Fusion future categories into a bounded
    future flood signal.

    Maximum contribution: 20 points.

    Future evidence strengthens the Flood Signal but does not
    independently override observed river warning/danger
    thresholds.
    """

    if not isinstance(future, dict):
        return {
            "signal": 0.0,
            "score": 0.0,
            "rainfall_score": 0.0,
            "runoff_score": 0.0,
            "geoglows_score": 0.0
        }

    # --------------------------------------------------------
    # Forecast rainfall
    # --------------------------------------------------------

    rainfall_scores = {
        "LOW": 0.0,
        "MODERATE": 2.0,
        "HIGH": 4.0,
        "VERY_HIGH": 6.0,
        "NO_DATA": 0.0
    }

    rainfall_score = rainfall_scores.get(
        str(
            future.get(
                "forecast_rainfall",
                "NO_DATA"
            )
        ).upper(),
        0.0
    )

    # --------------------------------------------------------
    # Forecast runoff
    # --------------------------------------------------------

    runoff_scores = {
        "VERY_LOW": 0.0,
        "LOW": 1.0,
        "MODERATE": 3.0,
        "HIGH": 5.0,
        "NO_DATA": 0.0
    }

    runoff_score = runoff_scores.get(
        str(
            future.get(
                "forecast_runoff",
                "NO_DATA"
            )
        ).upper(),
        0.0
    )

    # --------------------------------------------------------
    # GEOGLOWS
    # --------------------------------------------------------

    geoglows_scores = {
        "NORMAL": 0.0,
        "RISING": 4.0,
        "HIGH": 5.0,
        "VERY_HIGH": 6.0,
        "NO_DATA": 0.0
    }

    geoglows_score = geoglows_scores.get(
        str(
            future.get(
                "geoglows",
                "NO_DATA"
            )
        ).upper(),
        0.0
    )

    # --------------------------------------------------------
    # Combined future score
    # --------------------------------------------------------

    score = min(
        rainfall_score
        + runoff_score
        + geoglows_score,
        FUTURE_MAX_CONTRIBUTION
    )

    signal = round(
        score / FUTURE_MAX_CONTRIBUTION,
        2
    )

    return {

        "signal":
            signal,

        "score":
            round(score, 2),

        "rainfall_score":
            rainfall_score,

        "runoff_score":
            runoff_score,

        "geoglows_score":
            geoglows_score
    }


# ============================================================
# DOMINANT SIGNAL
# ============================================================

def determine_dominant_signal(
    rainfall,
    runoff,
    river,
    antecedent,
    eo_flood
):
    """
    Determine which current evidence source is contributing
    most strongly to the risk.

    Priority is given to actual current hydrological
    conditions, followed by lagged EO corroboration.
    """

    # River threshold conditions are strongest.
    if river == "DANGER":
        return "RIVER"

    if river == "WARNING":
        return "RIVER"

    if river == "NEAR_DANGER":
        return "RIVER"

    if river == "NEAR_WARNING":
        return "RIVER"

    # Current rainfall.
    if rainfall == "VERY_HIGH":
        return "RAINFALL"

    if rainfall == "HIGH":
        return "RAINFALL"

    # Current runoff.
    if runoff == "HIGH":
        return "RUNOFF"

    if runoff == "MODERATE":
        return "RUNOFF"

    # Antecedent wetness.
    if antecedent == "HIGH":
        return "ANTECEDENT_RAINFALL"

    if antecedent == "MODERATE":
        return "ANTECEDENT_RAINFALL"

    # EO is corroborating evidence, not the primary current
    # signal.
    if eo_flood in ("STRONG", "MODERATE", "WEAK"):
        return "VIIRS_EO"

    return "NONE"


# ============================================================
# EVIDENCE AGREEMENT
# ============================================================

def determine_agreement(
    rainfall,
    runoff,
    river,
    antecedent,
    eo_flood
):
    """
    Describe how current hydrological evidence agrees.

    EO is treated separately as corroborating evidence.
    """

    current_values = [
        rainfall,
        runoff,
        river,
        antecedent
    ]

    available = [
        x for x in current_values
        if x != "NO_DATA"
    ]

    if not available:
        return "UNKNOWN"

    # --------------------------------------------------------
    # Elevated river but low rain/runoff
    # --------------------------------------------------------

    if river in (
        "DANGER",
        "WARNING",
        "NEAR_DANGER",
        "NEAR_WARNING"
    ):

        if rainfall in (
            "LOW",
            "NO_DATA"
        ) and runoff in (
            "VERY_LOW",
            "LOW",
            "NO_DATA"
        ):

            if eo_flood in (
                "STRONG",
                "MODERATE"
            ):
                return "PARTIAL_WITH_EO_CORROBORATION"

            return "PARTIAL"

    # --------------------------------------------------------
    # Strong rainfall/runoff agreement
    # --------------------------------------------------------

    elevated_rain = rainfall in (
        "HIGH",
        "VERY_HIGH"
    )

    elevated_runoff = runoff in (
        "MODERATE",
        "HIGH"
    )

    if elevated_rain and elevated_runoff:
        return "HIGH"

    # --------------------------------------------------------
    # Strong river + rainfall agreement
    # --------------------------------------------------------

    elevated_river = river in (
        "DANGER",
        "WARNING",
        "NEAR_DANGER",
        "NEAR_WARNING"
    )

    if elevated_river and elevated_rain:
        return "HIGH"

    # --------------------------------------------------------
    # EO corroboration
    # --------------------------------------------------------

    if eo_flood in (
        "STRONG",
        "MODERATE"
    ):

        if elevated_rain or elevated_runoff or elevated_river:
            return "PARTIAL_WITH_EO_CORROBORATION"

    # --------------------------------------------------------
    # Mostly normal/low signals
    # --------------------------------------------------------

    if (
        rainfall in ("LOW", "NO_DATA")
        and runoff in ("VERY_LOW", "LOW", "NO_DATA")
        and river in ("NORMAL", "NO_DATA")
    ):
        return "HIGH"

    return "PARTIAL"


# ============================================================
# RISK SCORE
# ============================================================

def calculate_risk_score(
    rainfall,
    runoff,
    river,
    antecedent,
    hydrology_signal,
    eo_observation,
    future_score=0.0
):

    # --------------------------------------------------------
    # River
    # --------------------------------------------------------

    river_scores = {
        "NORMAL": 0,
        "NEAR_WARNING": 20,
        "NEAR_DANGER": 40,
        "WARNING": 65,
        "DANGER": 90,
        "NO_DATA": 0
    }

    river_score = river_scores.get(
        river,
        0
    )

    # --------------------------------------------------------
    # Rainfall
    # --------------------------------------------------------

    rainfall_scores = {
        "LOW": 0,
        "MODERATE": 10,
        "HIGH": 20,
        "VERY_HIGH": 30,
        "NO_DATA": 0
    }

    rainfall_score = rainfall_scores.get(
        rainfall,
        0
    )

    # --------------------------------------------------------
    # Runoff
    # --------------------------------------------------------

    runoff_scores = {
        "VERY_LOW": 0,
        "LOW": 5,
        "MODERATE": 12,
        "HIGH": 20,
        "NO_DATA": 0
    }

    runoff_score = runoff_scores.get(
        runoff,
        0
    )

    # --------------------------------------------------------
    # Antecedent rainfall
    # --------------------------------------------------------

    antecedent_scores = {
        "VERY_LOW": 0,
        "LOW": 5,
        "MODERATE": 10,
        "HIGH": 15,
        "NO_DATA": 0
    }

    antecedent_score = antecedent_scores.get(
        antecedent,
        0
    )

    # --------------------------------------------------------
    # Hydrology signal
    # --------------------------------------------------------

    hydro_score = min(
        hydrology_signal * 20,
        20
    )

    # --------------------------------------------------------
    # VIIRS EO
    # --------------------------------------------------------

    eo_score = 0.0

    if (
        isinstance(eo_observation, dict)
        and eo_observation.get("available")
    ):

        try:
            raw_eo_score = float(
                eo_observation.get(
                    "eo_score",
                    0
                )
            )
        except (TypeError, ValueError):
            raw_eo_score = 0.0

        eo_score = (
            raw_eo_score / 100.0
        ) * EO_MAX_CONTRIBUTION

        eo_score = min(
            eo_score,
            EO_MAX_CONTRIBUTION
        )

        # --------------------------------------------------------
    # Future evidence
    # --------------------------------------------------------

    future_score = max(
        0.0,
        min(
            float(future_score),
            FUTURE_MAX_CONTRIBUTION
        )
    )

    total = (
        river_score
        + rainfall_score
        + runoff_score
        + antecedent_score
        + hydro_score
        + future_score
        + eo_score
    )

    return round(
        min(total, 100),
        2
    )


# ============================================================
# RISK LEVEL
# ============================================================

def determine_risk_level(score, river):

    # Direct river thresholds have priority.
    if river == "DANGER":
        return "CRITICAL"

    if river == "WARNING":
        return "WARNING"

    if river in (
        "NEAR_DANGER",
        "NEAR_WARNING"
    ):
        return "WATCH"

    # Score thresholds.
    if score >= 70:

        if river == "NO_DATA":
            return "WARNING"

        return "CRITICAL"

    if score >= 45:
        return "WARNING"

    if score >= 20:
        return "WATCH"

    return "LOW"


# ============================================================
# SEVERITY
# ============================================================

def determine_severity(level):

    return {
        "LOW": "NORMAL",
        "WATCH": "ELEVATED",
        "WARNING": "HIGH",
        "CRITICAL": "SEVERE"
    }.get(
        level,
        "NORMAL"
    )


# ============================================================
# DRIVERS
# ============================================================

def identify_drivers(
    rainfall,
    runoff,
    river,
    antecedent,
    eo_flood,
    hydrology_signal
):

    drivers = []

    # River.
    if river == "DANGER":
        drivers.append(
            "River level has crossed the danger threshold"
        )

    elif river == "WARNING":
        drivers.append(
            "River level has crossed the warning threshold"
        )

    elif river == "NEAR_DANGER":
        drivers.append(
            "River level is approaching the danger threshold"
        )

    elif river == "NEAR_WARNING":
        drivers.append(
            "River level is approaching the warning threshold"
        )

    # Rainfall.
    if rainfall == "VERY_HIGH":
        drivers.append(
            "Very high rainfall intensity detected"
        )

    elif rainfall == "HIGH":
        drivers.append(
            "High rainfall intensity detected"
        )

    elif rainfall == "MODERATE":
        drivers.append(
            "Moderate rainfall detected"
        )

    # Runoff.
    if runoff == "HIGH":
        drivers.append(
            "High estimated surface runoff"
        )

    elif runoff == "MODERATE":
        drivers.append(
            "Moderate estimated surface runoff"
        )

    # Antecedent.
    if antecedent == "HIGH":
        drivers.append(
            "High antecedent rainfall indicates wet catchment conditions"
        )

    elif antecedent == "MODERATE":
        drivers.append(
            "Moderate antecedent rainfall indicates increasing catchment wetness"
        )

    # Hydrology.
    if hydrology_signal >= 0.7:
        drivers.append(
            "Strong hydrological signal"
        )

    elif hydrology_signal >= 0.4:
        drivers.append(
            "Moderate hydrological signal"
        )

    # VIIRS.
    if eo_flood == "STRONG":
        drivers.append(
            "VIIRS observed strong flood evidence in the latest satellite observation"
        )

    elif eo_flood == "MODERATE":
        drivers.append(
            "VIIRS observed moderate flood evidence in the latest satellite observation"
        )

    elif eo_flood == "WEAK":
        drivers.append(
            "VIIRS observed weak flood evidence in the latest satellite observation"
        )

    if not drivers:
        drivers.append(
            "No strong current flood driver detected"
        )

    return drivers


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    rainfall,
    runoff,
    river,
    antecedent,
    eo_observation
):

    values = [
        rainfall,
        runoff,
        river,
        antecedent
    ]

    available = sum(
        1 for value in values
        if value != "NO_DATA"
    )

    data_score = available / 4.0

    # EO is useful corroboration but not treated as current
    # hydrological sensor data.
    confidence_score = data_score * 0.7

    # If all core current evidence exists, confidence is high.
    if available == 4:
        confidence_score = 0.70

    # EO corroboration can raise confidence slightly.
    if (
        eo_observation
        and eo_observation.get("available")
    ):
        confidence_score += 0.0

    confidence_score = round(
        min(confidence_score, 1.0),
        2
    )

    if confidence_score >= 0.70:
        level = "HIGH"

    elif confidence_score >= 0.40:
        level = "MODERATE"

    else:
        level = "LOW"

    return {
        "level": level,
        "score": confidence_score
    }


# ============================================================
# PROCESS DISTRICT
# ============================================================

def process_district(record):

    district_id = record.get(
        "district_id"
    )

    district = record.get(
        "district",
        "UNKNOWN"
    )

    evidence = record.get(
        "evidence",
        {}
    )

    if not isinstance(evidence, dict):
        evidence = {}

    current = evidence.get(
        "current",
        {}
    )

    if not isinstance(current, dict):
        current = {}

    # --------------------------------------------------------
    # Current evidence
    # --------------------------------------------------------

    rainfall = current.get(
        "rainfall",
        "NO_DATA"
    )

    runoff = current.get(
        "runoff",
        "NO_DATA"
    )

    river = current.get(
        "river",
        "NO_DATA"
    )

    antecedent = current.get(
        "antecedent_rainfall",
        "NO_DATA"
    )

    eo_flood = current.get(
        "eo_flood",
        "NO_DATA"
    )

    # --------------------------------------------------------
    # EO observation
    # --------------------------------------------------------

    eo_observation = record.get(
        "eo_observation",
        {}
    )

    if not isinstance(
        eo_observation,
        dict
    ):
        eo_observation = {}

    # --------------------------------------------------------
    # Hydrology
    # --------------------------------------------------------

    hydrology = extract_hydrology(
        record
    )

    # --------------------------------------------------------
    # Future evidence
    # --------------------------------------------------------

    future = extract_future_evidence(record)
    future_signal = calculate_future_signal(future)

    # --------------------------------------------------------
    # Derived interpretation
    # --------------------------------------------------------

    dominant_signal = determine_dominant_signal(
        rainfall,
        runoff,
        river,
        antecedent,
        eo_flood
    )

    agreement = determine_agreement(
        rainfall,
        runoff,
        river,
        antecedent,
        eo_flood
    )

    # --------------------------------------------------------
    # Risk score
    # --------------------------------------------------------

    score = calculate_risk_score(
    rainfall,
    runoff,
    river,
    antecedent,
    hydrology["signal"],
    eo_observation,
    future_signal["score"]
)
    level = determine_risk_level(
        score,
        river
    )

    severity = determine_severity(
        level
    )

    # --------------------------------------------------------
    # Drivers
    # --------------------------------------------------------

    drivers = identify_drivers(
        rainfall,
        runoff,
        river,
        antecedent,
        eo_flood,
        hydrology["signal"]
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = calculate_confidence(
        rainfall,
        runoff,
        river,
        antecedent,
        eo_observation
    )

    # --------------------------------------------------------
    # EO contribution
    # --------------------------------------------------------

    eo_contribution = 0.0

    if eo_observation.get(
        "available",
        False
    ):

        try:
            raw_eo_score = float(
                eo_observation.get(
                    "eo_score",
                    0
                )
            )

            eo_contribution = round(
                min(
                    (raw_eo_score / 100.0)
                    * EO_MAX_CONTRIBUTION,
                    EO_MAX_CONTRIBUTION
                ),
                2
            )

        except (
            TypeError,
            ValueError
        ):
            eo_contribution = 0.0

    # --------------------------------------------------------
    # Data quality
    # --------------------------------------------------------

    data_quality = record.get(
        "data_quality",
        {}
    )

    if not isinstance(
        data_quality,
        dict
    ):
        data_quality = {}

    rainfall_available = bool(
        data_quality.get(
            "rainfall_available",
            rainfall != "NO_DATA"
        )
    )

    river_available = bool(
        data_quality.get(
            "river_available",
            river != "NO_DATA"
        )
    )

    forecast_available = bool(
        data_quality.get(
            "forecast_available",
            False
        )
    )

    geoglows_available = bool(
        data_quality.get(
            "geoglows_available",
            False
        )
    )

    eo_available = bool(
        eo_observation.get(
            "available",
            False
        )
    )

    if (
        rainfall_available
        and river_available
        and forecast_available
    ):
        overall_quality = "GOOD"

    elif rainfall_available or river_available:
        overall_quality = "PARTIAL"

    else:
        overall_quality = "POOR"

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    return {

        "district_id": district_id,

        "district": district,

        "risk": {
            "level": level,
            "score": score,
            "severity": severity
        },

        "drivers": drivers,

        "evidence": {

            "rainfall": rainfall,

            "runoff": runoff,

            "river": river,

            "antecedent_rainfall": antecedent,

            "eo_flood": eo_flood,

            "dominant_signal": dominant_signal,

            "agreement": agreement
        },

        "eo_observation": {

            "available": eo_available,

            "observation_date":
                eo_observation.get(
                    "observation_date"
                ),

            "source":
                eo_observation.get(
                    "source"
                ),

            "resolution":
                eo_observation.get(
                    "resolution"
                ),

            "flood_pixels":
                eo_observation.get(
                    "flood_pixels",
                    0
                ),

            "flood_ratio_pct":
                eo_observation.get(
                    "flood_ratio_pct",
                    0
                ),

            "eo_score":
                eo_observation.get(
                    "eo_score",
                    0
                ),

            "temporal_role":
                eo_observation.get(
                    "temporal_role",
                    "LAGGED_OBSERVATION"
                ),

            "risk_score_contribution":
                eo_contribution
        },

        "confidence": confidence,

        "hydrology": {

            "state":
                hydrology["state"],

            "signal":
                hydrology["signal"],

            "signal_strength":
                hydrology["signal_strength"]
        },

        "future_evidence": {

    "forecast_available":
        future["forecast_available"],

    "geoglows_available":
        future["geoglows_available"],

    "forecast_rainfall":
        future["forecast_rainfall"],

    "forecast_runoff":
        future["forecast_runoff"],

    "geoglows":
        future["geoglows"],

    "outlook":
        future["outlook"],

    "signal":
        future_signal["signal"],

    "score":
        future_signal["score"],

    "rainfall_score":
        future_signal["rainfall_score"],

    "runoff_score":
        future_signal["runoff_score"],

    "geoglows_score":
        future_signal["geoglows_score"]
},

        "data_quality": {

            "overall":
                overall_quality,

            "rainfall_available":
                rainfall_available,

            "river_available":
                river_available,

            "river_station_count":
                data_quality.get(
                    "river_station_count",
                    0
                ),

            "forecast_available":
                forecast_available,

            "geoglows_available":
                geoglows_available,

            "geoglows_station_count":
                data_quality.get(
                    "geoglows_station_count",
                    0
                ),

            "eo_available":
                eo_available
        }
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("PRAVAH - RISK ENGINE V4")
    print("=" * 80)

    data = load_json(
        INPUT_FILE
    )

    districts = data.get(
        "districts",
        []
    )

    print(
        f"Districts received : {len(districts)}"
    )

    results = []

    for record in districts:

        try:

            results.append(
                process_district(record)
            )

        except Exception as e:

            district = record.get(
                "district",
                "UNKNOWN"
            )

            print(
                f"ERROR processing {district}: {e}"
            )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    risk_counts = {
        "LOW": 0,
        "WATCH": 0,
        "WARNING": 0,
        "CRITICAL": 0
    }

    confidence_counts = {
        "HIGH": 0,
        "MODERATE": 0,
        "LOW": 0
    }

    eo_counts = {
        "STRONG": 0,
        "MODERATE": 0,
        "WEAK": 0,
        "NONE": 0
    }

    dominant_counts = {}

    agreement_counts = {}

    for result in results:

        # Risk.
        level = result["risk"]["level"]

        if level in risk_counts:
            risk_counts[level] += 1

        # Confidence.
        confidence = result[
            "confidence"
        ]["level"]

        if confidence in confidence_counts:
            confidence_counts[
                confidence
            ] += 1

        # EO.
        eo_level = result[
            "evidence"
        ].get(
            "eo_flood",
            "NO_DATA"
        )

        if eo_level in eo_counts:
            eo_counts[eo_level] += 1
        else:
            eo_counts["NONE"] += 1

        # Dominant signal.
        dominant = result[
            "evidence"
        ].get(
            "dominant_signal",
            "NONE"
        )

        dominant_counts[dominant] = (
            dominant_counts.get(
                dominant,
                0
            ) + 1
        )

        # Agreement.
        agreement = result[
            "evidence"
        ].get(
            "agreement",
            "UNKNOWN"
        )

        agreement_counts[agreement] = (
            agreement_counts.get(
                agreement,
                0
            ) + 1
        )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    output = {

        "metadata": {

            "pipeline_version":
                ENGINE_VERSION,

            "description":
                "PRAVAH flood risk engine using current hydrological evidence, future outlook and lagged VIIRS flood corroboration",

            "eo_policy":
                "VIIRS EO is lagged observational corroborating evidence and cannot independently trigger WARNING or CRITICAL",

            "eo_max_risk_contribution":
                EO_MAX_CONTRIBUTION,

            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "district_count":
                len(results)
        },

        "statistics": {

            "risk_levels":
                risk_counts,

            "confidence":
                confidence_counts,

            "eo_evidence":
                eo_counts,

            "dominant_signals":
                dominant_counts,

            "evidence_agreement":
                agreement_counts
        },

        "districts":
            results
    }

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
    # Terminal
    # --------------------------------------------------------

    print()

    print("Risk levels:")
    print(
        f"  LOW       : {risk_counts['LOW']}"
    )
    print(
        f"  WATCH     : {risk_counts['WATCH']}"
    )
    print(
        f"  WARNING   : {risk_counts['WARNING']}"
    )
    print(
        f"  CRITICAL  : {risk_counts['CRITICAL']}"
    )

    print()

    print("Confidence:")
    print(
        f"  HIGH      : {confidence_counts['HIGH']}"
    )
    print(
        f"  MODERATE  : {confidence_counts['MODERATE']}"
    )
    print(
        f"  LOW       : {confidence_counts['LOW']}"
    )

    print()

    print("VIIRS EO evidence:")
    print(
        f"  STRONG    : {eo_counts['STRONG']}"
    )
    print(
        f"  MODERATE  : {eo_counts['MODERATE']}"
    )
    print(
        f"  WEAK      : {eo_counts['WEAK']}"
    )
    print(
        f"  NONE      : {eo_counts['NONE']}"
    )

    print()

    print("Dominant signals:")

    for signal, count in sorted(
        dominant_counts.items(),
        key=lambda x: x[0]
    ):
        print(
            f"  {signal:<24}: {count}"
        )

    print()

    print("Evidence agreement:")

    for agreement, count in sorted(
        agreement_counts.items(),
        key=lambda x: x[0]
    ):
        print(
            f"  {agreement:<32}: {count}"
        )

    print()

    print(
        f"Output written to : {OUTPUT_FILE}"
    )

    print("=" * 80)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
