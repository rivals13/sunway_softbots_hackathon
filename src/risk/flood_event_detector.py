
import json
from datetime import datetime, timezone
from src.config import (
    EVIDENCE_FILE as CONFIG_EVIDENCE_FILE,
    HYDROLOGY_FILE as CONFIG_HYDROLOGY_FILE,
    FLOOD_EVENTS_FILE,
)

# ============================================================
# PRAVAH FLOOD EVENT DETECTOR V2
# ============================================================
#
# Purpose:
#   Convert PRAVAH's fused hydrological/evidence features into
#   operational states:
#
#       MONITOR
#       WATCH
#       SCENARIO
#       SIMULATE
#
# Important semantics:
#
#   OBSERVATION:
#       BIPAD/DHM rainfall and river observations
#
#   FORECAST:
#       Weather + forecast runoff + GeoGLOWS
#
#   EO:
#       VIIRS is lagged observed flood evidence.
#       It supports/confirm observations but does NOT independently
#       trigger current simulation.
#
#   SIMULATE:
#       Means current evidence is strong enough to justify running
#       a hydraulic inundation simulation.
#
#   SCENARIO:
#       Conditions are strong enough to prepare/run a scenario,
#       but we are NOT claiming the district is currently flooded.
#
# ============================================================


EVIDENCE_FILE = CONFIG_EVIDENCE_FILE
HYDROLOGY_FILE = CONFIG_HYDROLOGY_FILE
OUTPUT_FILE = FLOOD_EVENTS_FILE

# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value):
    return bool(value)


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def pct(value):
    return round(safe_float(value) * 100.0, 1)


# ============================================================
# LOAD DATA
# ============================================================

with open(EVIDENCE_FILE, "r", encoding="utf-8") as f:
    evidence_data = json.load(f)

with open(HYDROLOGY_FILE, "r", encoding="utf-8") as f:
    hydrology_data = json.load(f)


evidence_districts = evidence_data.get("districts", [])
hydrology_districts = hydrology_data.get("districts", [])


# ============================================================
# INDEX HYDROLOGY BY DISTRICT ID
# ============================================================

hydro_by_id = {}

for d in hydrology_districts:
    district_id = d.get("district_id")

    if district_id is not None:
        hydro_by_id[int(district_id)] = d


# ============================================================
# RESULT CONTAINERS
# ============================================================

results = []

statistics = {
    "district_count": len(evidence_districts),
    "simulate": 0,
    "scenario": 0,
    "watch": 0,
    "monitor": 0,
    "critical": 0,
    "high": 0,
    "moderate": 0,
    "low": 0,
}


# ============================================================
# PROCESS DISTRICTS
# ============================================================

for ev in evidence_districts:

    district_id = int(ev.get("district_id"))
    district_name = ev.get("district", "Unknown")

    hydro = hydro_by_id.get(district_id, {})

    evidence = ev.get("evidence", {})
    current = evidence.get("current", {})
    future = evidence.get("future", {})

    summary = ev.get("evidence_summary", {})
    eo = ev.get("eo_observation", {})
    hydro_context = ev.get("hydrology_context", {})

    rainfall = hydro.get("rainfall", {})
    river = hydro.get("river", {})
    forecast = hydro.get("forecast", {})
    geoglows = hydro.get("geoglows", {})


    # ========================================================
    # NUMERICAL VALUES
    # ========================================================

    rain_1h = safe_float(
        rainfall.get("bipad_1h_mm")
    )

    rain_6h = safe_float(
        rainfall.get("rain_6h_mm")
    )

    rain_12h = safe_float(
        rainfall.get("rain_12h_mm")
    )

    rain_24h = safe_float(
        rainfall.get("rain_24h_mm")
    )

    rain_3day = safe_float(
        rainfall.get("rain_3day_mm")
    )

    rain_5day = safe_float(
        rainfall.get("rain_5day_mm")
    )

    rainfall_intensity = safe_float(
        rainfall.get("rainfall_intensity_mm_per_hour")
    )

    runoff_6h = safe_float(
        rainfall.get("scs_cn_runoff_6h_mm")
    )

    hydro_signal = safe_float(
        hydro_context.get(
            "hydrological_signal",
            hydro.get("hydrological_fusion", {}).get(
                "hydrological_signal", 0
            )
        )
    )

    warning_utilization = safe_float(
        river.get("max_warning_utilization")
    )

    danger_utilization = safe_float(
        river.get("max_danger_utilization")
    )

    warning_crossed = safe_bool(
        river.get("warning_crossed")
    )

    danger_crossed = safe_bool(
        river.get("danger_crossed")
    )

    warning_station_count = int(
        river.get("warning_station_count", 0) or 0
    )

    danger_station_count = int(
        river.get("danger_station_count", 0) or 0
    )

    rising_station_count = int(
        river.get("rising_station_count", 0) or 0
    )

    river_status = str(
        river.get("river_status", "UNKNOWN")
    ).upper()

    near_warning = safe_bool(
        river.get("near_warning")
    )

    near_danger = safe_bool(
        river.get("near_danger")
    )


    # Forecast

    forecast_rain_6h = safe_float(
        forecast.get("rain_6h_mm")
    )

    forecast_rain_12h = safe_float(
        forecast.get("rain_12h_mm")
    )

    forecast_rain_24h = safe_float(
        forecast.get("rain_24h_mm")
    )

    forecast_rain_48h = safe_float(
        forecast.get("rain_48h_mm")
    )

    forecast_runoff_6h = safe_float(
        forecast.get("runoff_6h_mm")
    )

    forecast_runoff_12h = safe_float(
        forecast.get("runoff_12h_mm")
    )

    forecast_runoff_24h = safe_float(
        forecast.get("runoff_24h_mm")
    )

    forecast_runoff_48h = safe_float(
        forecast.get("runoff_48h_mm")
    )


    # GeoGLOWS

    geoglows_current = safe_float(
        geoglows.get("current_flow_m3s")
    )

    geoglows_peak = safe_float(
        geoglows.get("forecast_peak_flow_m3s")
    )

    geoglows_rise = safe_float(
        geoglows.get("forecast_rise_m3s")
    )

    geoglows_hours_to_peak = geoglows.get(
        "hours_to_peak"
    )


    # EO

    eo_available = safe_bool(
        eo.get("available")
    )

    eo_flood_pixels = int(
        eo.get("flood_pixels", 0) or 0
    )

    eo_ratio = safe_float(
        eo.get("flood_ratio_pct")
    )

    eo_score = safe_float(
        eo.get("eo_score")
    )

    eo_temporal_role = eo.get(
        "temporal_role",
        "UNKNOWN"
    )


    # ========================================================
    # SIGNAL COLLECTION
    # ========================================================

    current_signals = []
    future_signals = []
    supporting_warnings = []


    # ========================================================
    # 1. RIVER SIGNAL
    # ========================================================

    # Actual threshold crossing is the strongest signal.

    if danger_crossed or danger_station_count > 0:

        current_signals.append(
            "RIVER_DANGER_THRESHOLD"
        )

    elif warning_crossed or warning_station_count > 0:

        current_signals.append(
            "RIVER_WARNING_THRESHOLD"
        )

    elif warning_utilization >= 0.95:

        current_signals.append(
            "RIVER_VERY_NEAR_WARNING"
        )

    elif warning_utilization >= 0.85:

        current_signals.append(
            "RIVER_NEAR_WARNING"
        )


    # Supporting river information

    if warning_utilization >= 0.75:

        supporting_warnings.append(
            "RIVER_ELEVATED"
        )

    if rising_station_count > 0:

        supporting_warnings.append(
            "RIVER_RISING"
        )


    # ========================================================
    # 2. CURRENT RAINFALL SIGNAL
    # ========================================================

    # These are prototype operational thresholds.
    #
    # They are deliberately conservative and should eventually
    # be calibrated using historical Nepal rainfall/flood events.

    if rainfall_intensity >= 10:

        current_signals.append(
            "VERY_HIGH_CURRENT_RAINFALL"
        )

    elif rainfall_intensity >= 5:

        current_signals.append(
            "HIGH_CURRENT_RAINFALL"
        )

    elif rainfall_intensity >= 3:

        supporting_warnings.append(
            "MODERATE_CURRENT_RAINFALL"
        )


    # ========================================================
    # 3. RUNOFF SIGNAL
    # ========================================================

    if runoff_6h >= 10:

        current_signals.append(
            "HIGH_CURRENT_RUNOFF"
        )

    elif runoff_6h > 0:

        supporting_warnings.append(
            "CURRENT_RUNOFF_PRESENT"
        )


    # ========================================================
    # 4. HYDROLOGICAL RESPONSE
    # ========================================================

    if hydro_signal >= 0.70:

        current_signals.append(
            "STRONG_HYDROLOGICAL_RESPONSE"
        )

    elif hydro_signal >= 0.55:

        current_signals.append(
            "ELEVATED_HYDROLOGICAL_RESPONSE"
        )

    elif hydro_signal >= 0.40:

        supporting_warnings.append(
            "MODERATE_HYDROLOGICAL_RESPONSE"
        )


    # ========================================================
    # 5. FORECAST SIGNAL
    # ========================================================

    if forecast_rain_24h >= 50:

        future_signals.append(
            "HIGH_FORECAST_RAINFALL_24H"
        )

    elif forecast_rain_24h >= 25:

        future_signals.append(
            "SIGNIFICANT_FORECAST_RAINFALL_24H"
        )

    elif forecast_rain_24h >= 15:

        supporting_warnings.append(
            "ELEVATED_24H_FORECAST_RAIN"
        )


    if forecast_rain_48h >= 75:

        future_signals.append(
            "HIGH_FORECAST_RAINFALL_48H"
        )

    elif forecast_rain_48h >= 50:

        future_signals.append(
            "SIGNIFICANT_FORECAST_RAINFALL_48H"
        )


    # Forecast runoff

    if forecast_runoff_48h >= 10:

        future_signals.append(
            "SIGNIFICANT_FORECAST_RUNOFF"
        )

    elif forecast_runoff_48h > 0:

        supporting_warnings.append(
            "FORECAST_RUNOFF_PRESENT"
        )


    # ========================================================
    # 6. GEOGLOWS FORECAST
    # ========================================================

    if geoglows_rise > 0:

        future_signals.append(
            "GEOGLOWS_FLOW_RISING"
        )


    if geoglows_peak > geoglows_current and geoglows_current > 0:

        supporting_warnings.append(
            "GEOGLOWS_FORECAST_PEAK_ABOVE_CURRENT"
        )


    # ========================================================
    # 7. LAGGED EO SUPPORT
    # ========================================================

    if eo_available and eo_flood_pixels > 0:

        supporting_warnings.append(
            "LAGGED_VIIRS_FLOOD_EVIDENCE"
        )


    # ========================================================
    # CURRENT EVIDENCE SCORE
    # ========================================================
    #
    # This is NOT a probability of flooding.
    #
    # It is a transparent operational evidence score used to
    # decide whether a hydraulic simulation should be considered.
    #
    # Maximum approximate score = 100.
    #
    # River:
    #   35 points
    #
    # Hydrology:
    #   25 points
    #
    # Rainfall:
    #   20 points
    #
    # Runoff:
    #   10 points
    #
    # EO:
    #   10 points supporting only
    #
    # ========================================================

    evidence_score = 0.0


    # River contribution

    if danger_crossed:

        evidence_score += 35

    elif warning_crossed:

        evidence_score += 30

    else:

        evidence_score += 35 * clamp(
            warning_utilization
        )


    # Hydrology contribution

    evidence_score += 25 * clamp(
        hydro_signal
    )


    # Rainfall contribution

    rainfall_score = 0.0

    if rainfall_intensity >= 10:
        rainfall_score = 1.0

    elif rainfall_intensity >= 5:
        rainfall_score = 0.75

    elif rainfall_intensity >= 3:
        rainfall_score = 0.50

    elif rainfall_intensity >= 1:
        rainfall_score = 0.25

    evidence_score += 20 * rainfall_score


    # Runoff contribution

    runoff_score = 0.0

    if runoff_6h >= 10:
        runoff_score = 1.0

    elif runoff_6h > 5:
        runoff_score = 0.75

    elif runoff_6h > 0:
        runoff_score = 0.30

    evidence_score += 10 * runoff_score


    # EO contribution
    #
    # EO is deliberately capped at 10 points and cannot
    # independently produce SIMULATE.

    eo_support_score = 0.0

    if eo_available:

        if eo_ratio >= 5:
            eo_support_score = 1.0

        elif eo_ratio >= 2:
            eo_support_score = 0.70

        elif eo_ratio >= 1:
            eo_support_score = 0.40

        elif eo_ratio > 0:
            eo_support_score = 0.20

    evidence_score += 10 * eo_support_score


    evidence_score = round(
        evidence_score,
        2
    )


    # ========================================================
    # FUTURE PRESSURE SCORE
    # ========================================================

    future_score = 0.0


    # Forecast rainfall

    if forecast_rain_24h >= 50:
        future_score += 30

    elif forecast_rain_24h >= 25:
        future_score += 20

    elif forecast_rain_24h >= 15:
        future_score += 10


    if forecast_rain_48h >= 75:
        future_score += 20

    elif forecast_rain_48h >= 50:
        future_score += 15

    elif forecast_rain_48h >= 25:
        future_score += 8


    # Forecast runoff

    if forecast_runoff_48h >= 10:
        future_score += 25

    elif forecast_runoff_48h >= 5:
        future_score += 15

    elif forecast_runoff_48h > 0:
        future_score += 5


    # GeoGLOWS

    if geoglows_rise > 0:
        future_score += 15


    future_score = round(
        min(future_score, 100),
        2
    )


    # ========================================================
    # CONVERGENCE LOGIC
    # ========================================================

    current_count = len(current_signals)
    future_count = len(future_signals)

    strong_river = (
        warning_crossed
        or danger_crossed
        or warning_utilization >= 0.95
    )

    elevated_river = (
        warning_utilization >= 0.85
    )

    strong_hydro = (
        hydro_signal >= 0.55
    )

    meaningful_rain = (
        rainfall_intensity >= 3
    )

    meaningful_runoff = (
        runoff_6h > 0
    )

    significant_forecast = (
        forecast_rain_24h >= 25
        or forecast_rain_48h >= 50
        or forecast_runoff_48h >= 5
    )

    geoglows_rising = (
        geoglows_rise > 0
    )

    eo_support = (
        eo_available
        and eo_ratio > 0
    )


    # ========================================================
    # DECISION
    # ========================================================
    #
    # IMPORTANT:
    #
    # SIMULATE requires strong current evidence.
    #
    # SCENARIO means current conditions are concerning enough
    # to prepare/consider a hydraulic simulation.
    #
    # Forecast alone never creates SIMULATE.
    #
    # ========================================================

    decision = "MONITOR"
    severity = "LOW"


    # --------------------------------------------------------
    # CRITICAL
    # --------------------------------------------------------

    if danger_crossed:

        decision = "SIMULATE"
        severity = "CRITICAL"


    # --------------------------------------------------------
    # HIGH CURRENT RIVER CONDITION
    # --------------------------------------------------------

    elif warning_crossed:

        decision = "SIMULATE"
        severity = "HIGH"


    # --------------------------------------------------------
    # VERY STRONG CONVERGENCE
    # --------------------------------------------------------

    elif (
        strong_river
        and (
            strong_hydro
            or meaningful_rain
            or meaningful_runoff
        )
    ):

        decision = "SIMULATE"
        severity = "HIGH"


    # --------------------------------------------------------
    # STRONG SCENARIO CANDIDATE
    # --------------------------------------------------------

    elif (
        strong_river
        and (
            significant_forecast
            or geoglows_rising
        )
    ):

        decision = "SCENARIO"
        severity = "HIGH"


    elif (
        elevated_river
        and strong_hydro
        and (
            significant_forecast
            or geoglows_rising
            or meaningful_rain
        )
    ):

        decision = "SCENARIO"
        severity = "HIGH"


    # --------------------------------------------------------
    # MODERATE SCENARIO
    # --------------------------------------------------------

    elif (
        evidence_score >= 60
        and future_score >= 20
    ):

        decision = "SCENARIO"
        severity = "MODERATE"


    # --------------------------------------------------------
    # WATCH
    # --------------------------------------------------------

    elif (
        evidence_score >= 45
        or future_score >= 20
        or current_count > 0
        or future_count > 0
    ):

        decision = "WATCH"
        severity = "MODERATE"


    # --------------------------------------------------------
    # MONITOR
    # --------------------------------------------------------

    else:

        decision = "MONITOR"
        severity = "LOW"


    # ========================================================
    # SPECIAL RULE:
    # FORECAST-ONLY DISTRICTS CANNOT BECOME SIMULATE
    # ========================================================

    if (
        decision == "SIMULATE"
        and current_count == 0
        and not warning_crossed
        and not danger_crossed
    ):

        decision = "SCENARIO"
        severity = "HIGH"


    # ========================================================
    # EXPLANATION
    # ========================================================

    explanation_parts = []


    if danger_crossed:

        explanation_parts.append(
            "River danger threshold has been crossed."
        )

    elif warning_crossed:

        explanation_parts.append(
            "River warning threshold has been crossed."
        )

    elif warning_utilization >= 0.95:

        explanation_parts.append(
            f"River level is very close to warning threshold "
            f"({pct(warning_utilization)}%)."
        )

    elif warning_utilization >= 0.85:

        explanation_parts.append(
            f"River level is elevated at "
            f"{pct(warning_utilization)}% of warning level."
        )


    if hydro_signal >= 0.55:

        explanation_parts.append(
            f"Hydrological response is elevated "
            f"(signal {hydro_signal:.3f})."
        )


    if rainfall_intensity >= 3:

        explanation_parts.append(
            f"Current rainfall intensity is "
            f"{rainfall_intensity:.2f} mm/h."
        )


    if runoff_6h > 0:

        explanation_parts.append(
            f"Current SCS runoff is "
            f"{runoff_6h:.2f} mm over 6h."
        )


    if forecast_rain_24h >= 25:

        explanation_parts.append(
            f"Forecast rainfall reaches "
            f"{forecast_rain_24h:.1f} mm in 24h."
        )

    elif forecast_rain_24h >= 15:

        explanation_parts.append(
            f"Forecast rainfall is elevated at "
            f"{forecast_rain_24h:.1f} mm in 24h."
        )


    if forecast_rain_48h >= 25:

        explanation_parts.append(
            f"48h forecast rainfall is "
            f"{forecast_rain_48h:.1f} mm."
        )


    if forecast_runoff_48h > 0:

        explanation_parts.append(
            f"Forecast runoff reaches "
            f"{forecast_runoff_48h:.2f} mm over 48h."
        )


    if geoglows_rise > 0:

        explanation_parts.append(
            f"GeoGLOWS forecast indicates rising flow "
            f"(+{geoglows_rise:.1f} m³/s)."
        )


    if eo_support:

        explanation_parts.append(
            f"VIIRS provides lagged observed flood evidence "
            f"({eo_flood_pixels} flood pixels)."
        )


    if not explanation_parts:

        explanation_parts.append(
            "No significant current or forecast evidence detected."
        )


    explanation = " ".join(
        explanation_parts
    )


    # ========================================================
    # BUILD RESULT
    # ========================================================

    result = {

        "district_id": district_id,

        "district": district_name,

        "decision": decision,

        "severity": severity,

        "current_signal_count": current_count,

        "future_signal_count": future_count,

        "current_signals": current_signals,

        "future_signals": future_signals,

        "supporting_warnings": supporting_warnings,

        "scores": {

            "current_evidence_score": evidence_score,

            "future_pressure_score": future_score,

            "score_semantics":
                "Operational evidence indicators, NOT flood probability."
        },

        "current_state": {

            "rainfall_category":
                current.get("rainfall"),

            "runoff_category":
                current.get("runoff"),

            "river_category":
                current.get("river"),

            "antecedent_rainfall":
                current.get("antecedent_rainfall"),

            "hydrological_signal":
                round(hydro_signal, 3),

            "hydrological_state":
                hydro_context.get(
                    "hydrological_state"
                )
        },

        "river": {

            "warning_utilization_pct":
                round(warning_utilization * 100, 1),

            "danger_utilization_pct":
                round(danger_utilization * 100, 1),

            "warning_crossed":
                warning_crossed,

            "danger_crossed":
                danger_crossed,

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
                near_danger
        },

        "rainfall": {

            "rain_1h_mm":
                round(rain_1h, 3),

            "rain_6h_mm":
                round(rain_6h, 3),

            "rain_12h_mm":
                round(rain_12h, 3),

            "rain_24h_mm":
                round(rain_24h, 3),

            "rain_3day_mm":
                round(rain_3day, 3),

            "rain_5day_mm":
                round(rain_5day, 3),

            "intensity_mm_per_hour":
                round(rainfall_intensity, 3),

            "scs_runoff_6h_mm":
                round(runoff_6h, 3)
        },

        "forecast": {

            "rain_6h_mm":
                round(forecast_rain_6h, 3),

            "rain_12h_mm":
                round(forecast_rain_12h, 3),

            "rain_24h_mm":
                round(forecast_rain_24h, 3),

            "rain_48h_mm":
                round(forecast_rain_48h, 3),

            "runoff_6h_mm":
                round(forecast_runoff_6h, 3),

            "runoff_12h_mm":
                round(forecast_runoff_12h, 3),

            "runoff_24h_mm":
                round(forecast_runoff_24h, 3),

            "runoff_48h_mm":
                round(forecast_runoff_48h, 3)
        },

        "geoglows": {

            "current_flow_m3s":
                round(geoglows_current, 3),

            "forecast_peak_flow_m3s":
                round(geoglows_peak, 3),

            "forecast_rise_m3s":
                round(geoglows_rise, 3),

            "hours_to_peak":
                geoglows_hours_to_peak
        },

        "eo_support": {

            "available":
                eo_available,

            "flood_pixels":
                eo_flood_pixels,

            "flood_ratio_pct":
                round(eo_ratio, 3),

            "eo_score":
                round(eo_score, 3),

            "temporal_role":
                eo_temporal_role,

            "can_trigger_simulation":
                False
        },

        "explanation":
            explanation
    }


    results.append(result)

    statistics[
        decision.lower()
    ] += 1

    statistics[
        severity.lower()
    ] += 1


# ============================================================
# SORT
# ============================================================

priority = {
    "SIMULATE": 4,
    "SCENARIO": 3,
    "WATCH": 2,
    "MONITOR": 1
}

results.sort(
    key=lambda x: (
        priority.get(x["decision"], 0),
        x["scores"]["current_evidence_score"],
        x["scores"]["future_pressure_score"]
    ),
    reverse=True
)


# ============================================================
# OUTPUT
# ============================================================

output = {

    "project":
        "PRAVAH",

    "pipeline_version":
        "flood_event_detector_v2",

    "generated_at_utc":
        datetime.now(timezone.utc).isoformat(),

    "semantics": {

        "SIMULATE":
            "Current evidence is strong enough to justify hydraulic inundation simulation.",

        "SCENARIO":
            "Conditions are sufficiently concerning to prepare/run a hydraulic scenario, but current flooding is not asserted.",

        "WATCH":
            "Meaningful current or future evidence exists but simulation trigger is not yet satisfied.",

        "MONITOR":
            "No significant evidence convergence detected.",

        "EO":
            "VIIRS is lagged observed flood evidence and cannot independently trigger current simulation.",

        "scores":
            "Evidence scores are operational indicators, not probabilities of flooding."
    },

    "statistics":
        statistics,

    "simulation_candidates": [
        x for x in results
        if x["decision"] == "SIMULATE"
    ],

    "scenario_candidates": [
        x for x in results
        if x["decision"] == "SCENARIO"
    ],

    "watch_candidates": [
        x for x in results
        if x["decision"] == "WATCH"
    ],

    "monitor_candidates": [
        x for x in results
        if x["decision"] == "MONITOR"
    ],

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


# ============================================================
# CONSOLE OUTPUT
# ============================================================

print("=" * 100)
print("PRAVAH FLOOD EVENT DETECTOR V2")
print("=" * 100)

print()

print(
    f"Districts : {statistics['district_count']}"
)

print(
    f"SIMULATE : {statistics['simulate']}"
)

print(
    f"SCENARIO : {statistics['scenario']}"
)

print(
    f"WATCH    : {statistics['watch']}"
)

print(
    f"MONITOR  : {statistics['monitor']}"
)


# ============================================================
# SIMULATION CANDIDATES
# ============================================================

print()
print("=" * 100)
print("SIMULATION CANDIDATES")
print("=" * 100)

simulation_candidates = [
    x for x in results
    if x["decision"] == "SIMULATE"
]

if not simulation_candidates:

    print("No districts currently require hydraulic simulation.")

else:

    for d in simulation_candidates:

        print(
            f"{d['district']:<22}"
            f"{d['severity']:<10}"
            f"score={d['scores']['current_evidence_score']:<6}"
            f"current={d['current_signal_count']} "
            f"future={d['future_signal_count']}"
        )

        print(
            f"  {d['explanation']}"
        )


# ============================================================
# SCENARIO CANDIDATES
# ============================================================

print()
print("=" * 100)
print("SCENARIO CANDIDATES")
print("=" * 100)

scenario_candidates = [
    x for x in results
    if x["decision"] == "SCENARIO"
]

if not scenario_candidates:

    print("No strong scenario candidates.")

else:

    for d in scenario_candidates[:20]:

        print(
            f"{d['district']:<22}"
            f"{d['severity']:<10}"
            f"current_score={d['scores']['current_evidence_score']:<6}"
            f"future_score={d['scores']['future_pressure_score']:<6}"
        )

        print(
            f"  River={d['river']['warning_utilization_pct']}% "
            f"Hydro={d['current_state']['hydrological_signal']} "
            f"Rain={d['rainfall']['intensity_mm_per_hour']} mm/h"
        )


# ============================================================
# TOP WATCH
# ============================================================

print()
print("=" * 100)
print("TOP WATCH DISTRICTS")
print("=" * 100)

watch_candidates = [
    x for x in results
    if x["decision"] == "WATCH"
]

for d in watch_candidates[:15]:

    print(
        f"{d['district']:<22}"
        f"score={d['scores']['current_evidence_score']:<6}"
        f"future={d['scores']['future_pressure_score']:<6}"
        f"river={d['river']['warning_utilization_pct']}%"
    )


print()
print("=" * 100)

print(
    f"Output: {OUTPUT_FILE}"
)

print("=" * 100)
