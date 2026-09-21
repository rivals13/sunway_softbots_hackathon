import json

from src.config import (
    HYDROLOGY_FILE as CONFIG_HYDROLOGY_FILE,
    EO_FEATURES_FILE,
    EVIDENCE_FILE,
    TERRAIN_FILE,
)


INPUT_FILE = CONFIG_HYDROLOGY_FILE
EO_FILE = EO_FEATURES_FILE
OUTPUT_FILE = EVIDENCE_FILE


# =========================================================
# LOAD DATA
# =========================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# LOAD TERRAIN FEATURES
# =========================================================

# =========================================================
# LOAD TERRAIN FEATURES
# =========================================================

def load_terrain_features():
    """
    Load read-only terrain context for all districts.

    Source terrain values are stored inside the nested
    `terrain` object in prava_terrain_features.json.

    Terrain is contextual information only.
    It does NOT contribute directly to the risk score
    in Evidence Fusion.
    """

    if not TERRAIN_FILE.exists():
        print(
            f"WARNING: Terrain file not found: {TERRAIN_FILE}"
        )
        return {}

    data = load_json(TERRAIN_FILE)

    terrain_lookup = {}

    for district in data.get("districts", []):

        district_id = district.get("district_id")

        if district_id is None:
            continue

        try:
            district_id = int(district_id)
        except (TypeError, ValueError):
            continue

        # -------------------------------------------------
        # IMPORTANT:
        # Terrain features are nested under:
        #
        # district["terrain"]
        # -------------------------------------------------
        terrain = district.get("terrain") or {}

        terrain_lookup[district_id] = {
            "elevation_mean_m":
                terrain.get("elevation_mean_m"),

            "elevation_min_m":
                terrain.get("elevation_min_m"),

            "elevation_max_m":
                terrain.get("elevation_max_m"),

            "slope_mean_deg":
                terrain.get("slope_mean_deg"),

            "drainage_area_pct_p99":
                terrain.get("drainage_area_pct_p99"),

            "drainage_area_pct_p995":
                terrain.get("drainage_area_pct_p995"),
        }

    return terrain_lookup

# =========================================================
# RAINFALL EVIDENCE
# =========================================================

def classify_rainfall(rainfall):

    rain_6h = rainfall.get("rain_6h_mm")
    rain_24h = rainfall.get("rain_24h_mm")

    if rain_6h is None or rain_24h is None:
        return "NO_DATA"

    if rain_6h >= 50 or rain_24h >= 150:
        return "VERY_HIGH"

    if rain_6h >= 25 or rain_24h >= 75:
        return "HIGH"

    if rain_6h >= 10 or rain_24h >= 30:
        return "MODERATE"

    return "LOW"


# =========================================================
# RUNOFF EVIDENCE
# =========================================================

def classify_runoff(rainfall):

    runoff = rainfall.get(
        "scs_cn_runoff_6h_mm"
    )

    if runoff is None:
        return "NO_DATA"

    if runoff >= 50:
        return "HIGH"

    if runoff >= 25:
        return "MODERATE"

    if runoff > 0:
        return "LOW"

    return "VERY_LOW"


# =========================================================
# ANTECEDENT RAINFALL
# =========================================================

def classify_antecedent(rainfall):

    antecedent = rainfall.get(
        "antecedent_rainfall_indicator"
    )

    if antecedent is None:
        return "NO_DATA"

    if antecedent >= 150:
        return "HIGH"

    if antecedent >= 75:
        return "MODERATE"

    if antecedent >= 25:
        return "LOW"

    return "VERY_LOW"


# =========================================================
# RIVER EVIDENCE
# =========================================================

def classify_river(
    river,
    data_quality
):

    river_available = data_quality.get(
        "river_available",
        False
    )

    station_count = river.get(
        "station_count",
        0
    )

    if (
        not river_available
        or station_count == 0
    ):
        return "NO_DATA"

    if river.get(
        "danger_crossed",
        False
    ):
        return "DANGER"

    if river.get(
        "warning_crossed",
        False
    ):
        return "WARNING"

    if river.get(
        "near_danger",
        False
    ):
        return "NEAR_DANGER"

    if river.get(
        "near_warning",
        False
    ):
        return "NEAR_WARNING"

    return "NORMAL"


# =========================================================
# FORECAST RAINFALL EVIDENCE
# =========================================================

def classify_forecast_rainfall(
    forecast
):

    rain_24h = forecast.get(
        "rain_24h_mm"
    )

    rain_48h = forecast.get(
        "rain_48h_mm"
    )

    if (
        rain_24h is None
        and rain_48h is None
    ):
        return "NO_DATA"

    values = [
        value
        for value in [
            rain_24h,
            rain_48h
        ]
        if value is not None
    ]

    max_rain = max(values)

    if max_rain >= 150:
        return "VERY_HIGH"

    if max_rain >= 75:
        return "HIGH"

    if max_rain >= 30:
        return "MODERATE"

    return "LOW"


# =========================================================
# FORECAST RUNOFF EVIDENCE
# =========================================================

def classify_forecast_runoff(
    forecast
):

    runoff_24h = forecast.get(
        "runoff_24h_mm"
    )

    runoff_48h = forecast.get(
        "runoff_48h_mm"
    )

    if (
        runoff_24h is None
        and runoff_48h is None
    ):
        return "NO_DATA"

    values = [
        value
        for value in [
            runoff_24h,
            runoff_48h
        ]
        if value is not None
    ]

    max_runoff = max(values)

    if max_runoff >= 50:
        return "HIGH"

    if max_runoff >= 25:
        return "MODERATE"

    if max_runoff > 0:
        return "LOW"

    return "VERY_LOW"


# =========================================================
# GEOGLOWS FORECAST EVIDENCE
# =========================================================

def classify_geoglows(
    geoglows
):

    station_count = geoglows.get(
        "station_count",
        0
    )

    forecast_rise = geoglows.get(
        "forecast_rise_m3s"
    )

    forecast_peak = geoglows.get(
        "forecast_peak_flow_m3s"
    )

    if station_count == 0:
        return "NO_DATA"

    if (
        forecast_rise is None
        and forecast_peak is None
    ):
        return "NO_DATA"

    if forecast_rise is not None:

        if forecast_rise > 0:
            return "RISING"

        if forecast_rise < 0:
            return "FALLING"

    return "STABLE"


# =========================================================
# VIIRS EO EVIDENCE
# =========================================================

def classify_eo(
    eo_record
):

    if not eo_record:
        return "NO_DATA"

    eo = eo_record.get(
        "eo",
        {}
    )

    flood_pixels = eo.get(
        "flood_pixels",
        0
    )

    strength = eo.get(
        "evidence_strength",
        "NONE"
    )

    if flood_pixels < 5:
        return "NONE"

    if strength == "STRONG":
        return "STRONG"

    if strength == "MODERATE":
        return "MODERATE"

    if strength == "WEAK":
        return "WEAK"

    return "NONE"


# =========================================================
# FUTURE OUTLOOK
# =========================================================

def determine_future_outlook(
    forecast_rainfall_evidence,
    forecast_runoff_evidence,
    geoglows_evidence
):

    future_elevated = False

    if forecast_rainfall_evidence in [
        "MODERATE",
        "HIGH",
        "VERY_HIGH"
    ]:
        future_elevated = True

    if forecast_runoff_evidence in [
        "MODERATE",
        "HIGH"
    ]:
        future_elevated = True

    if geoglows_evidence == "RISING":
        future_elevated = True

    if future_elevated:
        return "ELEVATED"

    return "NORMAL"


# =========================================================
# DOMINANT SIGNAL
# =========================================================

def determine_dominant_signal(
    rainfall_evidence,
    runoff_evidence,
    river_evidence,
    antecedent_evidence
):

    river_priority = {
        "DANGER": 5,
        "WARNING": 4,
        "NEAR_DANGER": 3,
        "NEAR_WARNING": 2,
        "NORMAL": 0,
        "NO_DATA": 0
    }

    rainfall_priority = {
        "VERY_HIGH": 4,
        "HIGH": 3,
        "MODERATE": 2,
        "LOW": 1,
        "NO_DATA": 0
    }

    runoff_priority = {
        "HIGH": 3,
        "MODERATE": 2,
        "LOW": 1,
        "VERY_LOW": 0,
        "NO_DATA": 0
    }

    antecedent_priority = {
        "HIGH": 3,
        "MODERATE": 2,
        "LOW": 1,
        "VERY_LOW": 0,
        "NO_DATA": 0
    }

    candidates = [
        (
            "RIVER",
            river_priority.get(
                river_evidence,
                0
            )
        ),
        (
            "RAINFALL",
            rainfall_priority.get(
                rainfall_evidence,
                0
            )
        ),
        (
            "RUNOFF",
            runoff_priority.get(
                runoff_evidence,
                0
            )
        ),
        (
            "ANTECEDENT_RAINFALL",
            antecedent_priority.get(
                antecedent_evidence,
                0
            )
        )
    ]

    candidates.sort(
        key=lambda x: x[1],
        reverse=True
    )

    if candidates[0][1] == 1:
        return "NONE"

    return candidates[0][0]


# =========================================================
# EVIDENCE AGREEMENT
# =========================================================

def determine_agreement(
    rainfall_evidence,
    runoff_evidence,
    river_evidence
):

    rainfall_elevated = (
        rainfall_evidence in [
            "MODERATE",
            "HIGH",
            "VERY_HIGH"
        ]
    )

    runoff_elevated = (
        runoff_evidence in [
            "MODERATE",
            "HIGH"
        ]
    )

    river_elevated = (
        river_evidence in [
            "NEAR_WARNING",
            "NEAR_DANGER",
            "WARNING",
            "DANGER"
        ]
    )

    available = []

    if rainfall_evidence != "NO_DATA":
        available.append(
            rainfall_elevated
        )

    if runoff_evidence != "NO_DATA":
        available.append(
            runoff_elevated
        )

    if river_evidence != "NO_DATA":
        available.append(
            river_elevated
        )

    if len(available) < 3:
        return "LIMITED_EVIDENCE"

    elevated_count = sum(
        available
    )

    if elevated_count == len(available):
        return "HIGH"

    if elevated_count == 0:
        return "HIGH"

    if elevated_count >= len(available) / 2:
        return "MODERATE"

    return "LOW"


# =========================================================
# DATA QUALITY
# =========================================================

def determine_data_quality(
    rainfall,
    river,
    data_quality
):

    rainfall_available = data_quality.get(
        "rainfall_available",
        False
    )

    river_available = data_quality.get(
        "river_available",
        False
    )

    station_count = data_quality.get(
        "river_station_count",
        0
    )

    if (
        rainfall_available
        and river_available
        and station_count > 0
    ):
        return "GOOD"

    if (
        rainfall_available
        or river_available
    ):
        return "MODERATE"

    return "POOR"


# =========================================================
# CONFIDENCE
# =========================================================

def determine_confidence(
    data_quality,
    agreement,
    river_evidence,
    rainfall_evidence
):

    score = 0.0

    if data_quality == "GOOD":
        score += 0.45

    elif data_quality == "MODERATE":
        score += 0.25

    else:
        score += 0.05

    if agreement == "HIGH":
        score += 0.30

    elif agreement == "MODERATE":
        score += 0.20

    elif agreement == "LOW":
        score += 0.10

    if river_evidence != "NO_DATA":
        score += 0.15

    if rainfall_evidence != "NO_DATA":
        score += 0.10

    score = min(
        score,
        1.0
    )

    if score >= 0.75:
        confidence = "HIGH"

    elif score >= 0.50:
        confidence = "MODERATE"

    else:
        confidence = "LOW"

    return (
        confidence,
        round(score, 3)
    )


# =========================================================
# PROCESS ONE DISTRICT
# =========================================================

def process_district(
    district,
    eo_record,
    terrain
):

    rainfall = district.get(
        "rainfall",
        {}
    )

    river = district.get(
        "river",
        {}
    )

    forecast = district.get(
        "forecast",
        {}
    )

    geoglows = district.get(
        "geoglows",
        {}
    )

    data_quality_input = district.get(
        "data_quality",
        {}
    )

    hydrology = district.get(
        "hydrological_fusion",
        {}
    )

    # =====================================================
    # CURRENT EVIDENCE
    # =====================================================

    rainfall_evidence = classify_rainfall(
        rainfall
    )

    runoff_evidence = classify_runoff(
        rainfall
    )

    antecedent_evidence = classify_antecedent(
        rainfall
    )

    river_evidence = classify_river(
        river,
        data_quality_input
    )

    # =====================================================
    # EO OBSERVED EVIDENCE
    # =====================================================

    eo_evidence = classify_eo(
        eo_record
    )

    # =====================================================
    # FUTURE EVIDENCE
    # =====================================================

    forecast_rainfall_evidence = (
        classify_forecast_rainfall(
            forecast
        )
    )

    forecast_runoff_evidence = (
        classify_forecast_runoff(
            forecast
        )
    )

    geoglows_evidence = classify_geoglows(
        geoglows
    )

    # =====================================================
    # FUTURE OUTLOOK
    # =====================================================

    future_outlook = determine_future_outlook(
        forecast_rainfall_evidence,
        forecast_runoff_evidence,
        geoglows_evidence
    )

    # =====================================================
    # OVERALL DATA QUALITY
    # =====================================================

    data_quality = determine_data_quality(
        rainfall,
        river,
        data_quality_input
    )

    # =====================================================
    # CURRENT DOMINANT SIGNAL
    # =====================================================

    dominant_signal = determine_dominant_signal(
        rainfall_evidence,
        runoff_evidence,
        river_evidence,
        antecedent_evidence
    )

    # =====================================================
    # CURRENT AGREEMENT
    # =====================================================

    agreement = determine_agreement(
        rainfall_evidence,
        runoff_evidence,
        river_evidence
    )

    # =====================================================
    # CONFIDENCE
    # =====================================================

    confidence, confidence_score = (
        determine_confidence(
            data_quality,
            agreement,
            river_evidence,
            rainfall_evidence
        )
    )

    # =====================================================
    # FUTURE EVIDENCE AVAILABILITY
    # =====================================================

    future_evidence_available = any([
        forecast_rainfall_evidence != "NO_DATA",
        forecast_runoff_evidence != "NO_DATA",
        geoglows_evidence != "NO_DATA"
    ])

    # =====================================================
    # EO AVAILABILITY
    # =====================================================

    eo_available = (
        eo_evidence != "NO_DATA"
        and eo_evidence != "NONE"
    )

    # =====================================================
    # TERRAIN AVAILABILITY
    # =====================================================

    terrain_available = bool(terrain)

    # =====================================================
    # FINAL OUTPUT
    # =====================================================

    return {

        "district_id":
            district.get(
                "district_id"
            ),

        "district":
            district.get(
                "district"
            ),

        # -------------------------------------------------
        # EVIDENCE
        # -------------------------------------------------

        "evidence": {

            "current": {

                "rainfall":
                    rainfall_evidence,

                "runoff":
                    runoff_evidence,

                "river":
                    river_evidence,

                "antecedent_rainfall":
                    antecedent_evidence,

                "eo_flood":
                    eo_evidence
            },

            "future": {

                "forecast_rainfall":
                    forecast_rainfall_evidence,

                "forecast_runoff":
                    forecast_runoff_evidence,

                "geoglows":
                    geoglows_evidence,

                "outlook":
                    future_outlook
            }
        },

        # -------------------------------------------------
        # EVIDENCE SUMMARY
        # -------------------------------------------------

        "evidence_summary": {

            "dominant_signal":
                dominant_signal,

            "agreement":
                agreement,

            "confidence":
                confidence,

            "confidence_score":
                confidence_score,

            "future_outlook":
                future_outlook,

            "future_evidence_available":
                future_evidence_available,

            "eo_flood_evidence":
                eo_available
        },

        # -------------------------------------------------
        # TERRAIN CONTEXT
        #
        # IMPORTANT:
        # This is descriptive/contextual only.
        # It is NOT added to the risk score here.
        # -------------------------------------------------

        "terrain_context": {

            "available":
                terrain_available,

            "elevation_mean_m":
                terrain.get(
                    "elevation_mean_m"
                ),

            "elevation_min_m":
                terrain.get(
                    "elevation_min_m"
                ),

            "elevation_max_m":
                terrain.get(
                    "elevation_max_m"
                ),

            "slope_mean_deg":
                terrain.get(
                    "slope_mean_deg"
                ),

            "drainage_area_pct_p99":
                terrain.get(
                    "drainage_area_pct_p99"
                ),

            "drainage_area_pct_p995":
                terrain.get(
                    "drainage_area_pct_p995"
                )
        },

        # -------------------------------------------------
        # EO METADATA
        # -------------------------------------------------

        "eo_observation": {

            "available":
                eo_available,

            "observation_date":
                eo_record.get(
                    "source_information",
                    {}
                ).get(
                    "observation_period"
                ) if eo_record else None,

            "source":
                eo_record.get(
                    "source_information",
                    {}
                ).get(
                    "product"
                ) if eo_record else None,

            "resolution":
                eo_record.get(
                    "source_information",
                    {}
                ).get(
                    "resolution"
                ) if eo_record else None,

            "flood_pixels":
                eo_record.get(
                    "eo",
                    {}
                ).get(
                    "flood_pixels",
                    0
                ) if eo_record else 0,

            "flood_ratio_pct":
                eo_record.get(
                    "eo",
                    {}
                ).get(
                    "flood_ratio_pct",
                    0
                ) if eo_record else 0,

            "eo_score":
                eo_record.get(
                    "eo",
                    {}
                ).get(
                    "eo_score",
                    0
                ) if eo_record else 0,

            "temporal_role":
                "LAGGED_OBSERVATION"
        },

        # -------------------------------------------------
        # HYDROLOGY CONTEXT
        # -------------------------------------------------

        "hydrology_context": {

            "hydrological_state":
                hydrology.get(
                    "hydrological_state"
                ),

            "hydrological_signal":
                hydrology.get(
                    "hydrological_signal"
                ),

            "signal_strength":
                hydrology.get(
                    "signal_strength"
                )
        },

        # -------------------------------------------------
        # DATA QUALITY
        # -------------------------------------------------

        "data_quality": {

            "overall":
                data_quality,

            "rainfall_available":
                data_quality_input.get(
                    "rainfall_available",
                    False
                ),

            "river_available":
                data_quality_input.get(
                    "river_available",
                    False
                ),

            "river_station_count":
                data_quality_input.get(
                    "river_station_count",
                    0
                ),

            "forecast_available":
                data_quality_input.get(
                    "forecast_available",
                    False
                ),

            "geoglows_available":
                data_quality_input.get(
                    "geoglows_available",
                    False
                ),

            "geoglows_station_count":
                data_quality_input.get(
                    "geoglows_station_count",
                    0
                ),

            "eo_available":
                eo_available,

            "terrain_available":
                terrain_available
        }
    }


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 80)
    print("PRAVAH - EVIDENCE FUSION ENGINE V4")
    print("=" * 80)

    # =====================================================
    # LOAD HYDROLOGY DATA
    # =====================================================

    data = load_json(
        INPUT_FILE
    )

    districts = data.get(
        "districts",
        []
    )

    # =====================================================
    # LOAD EO DATA
    # =====================================================

    eo_data = load_json(
        EO_FILE
    )

    eo_districts = eo_data.get(
        "districts",
        {}
    )

    # =====================================================
    # LOAD TERRAIN DATA
    # =====================================================

    terrain_lookup = load_terrain_features()

    print(
        f"Hydrology districts : "
        f"{len(districts)}"
    )

    print(
        f"VIIRS EO districts   : "
        f"{len(eo_districts)}"
    )

    print(
        f"Terrain districts    : "
        f"{len(terrain_lookup)}"
    )

    # =====================================================
    # PROCESS DISTRICTS
    # =====================================================

    results = []

    eo_matches = 0
    eo_missing = 0

    terrain_matches = 0
    terrain_missing = 0

    for district in districts:

        district_name = district.get(
            "district"
        )

        district_id = district.get(
            "district_id"
        )

        # -------------------------------------------------
        # EO MATCH
        #
        # IMPORTANT:
        # Match EO by district NAME.
        # Do NOT rely on district_id because VIIRS IDs
        # were generated independently.
        # -------------------------------------------------

        eo_record = eo_districts.get(
            district_name
        )

        if eo_record:
            eo_matches += 1

        else:
            eo_missing += 1

        # -------------------------------------------------
        # TERRAIN MATCH
        #
        # Terrain uses the same PRAVAH district_id
        # generated from the Nepal district boundary file.
        # -------------------------------------------------

        try:
            terrain_id = int(
                district_id
            )
        except (
            TypeError,
            ValueError
        ):
            terrain_id = None

        terrain = (
            terrain_lookup.get(
                terrain_id,
                {}
            )
            if terrain_id is not None
            else {}
        )

        if terrain:
            terrain_matches += 1

        else:
            terrain_missing += 1

        # -------------------------------------------------
        # PROCESS
        # -------------------------------------------------

        results.append(
            process_district(
                district,
                eo_record,
                terrain
            )
        )

    # =====================================================
    # OUTPUT
    # =====================================================

    output = {

        "project":
            "PRAVAH",

        "pipeline_version":
            "evidence_fusion_v4",

        "description":
            "Evidence fusion combining current "
            "rainfall, runoff and river observations "
            "with forecast rainfall, forecast runoff, "
            "GeoGLOWS, lagged VIIRS flood evidence, "
            "and read-only terrain context.",

        "eo_semantics":
            "VIIRS is treated as lagged observed flood "
            "evidence and does not independently "
            "determine current flood risk.",

        "terrain_semantics":
            "Terrain features are contextual spatial "
            "information describing elevation, slope "
            "and drainage concentration. They are not "
            "directly converted into risk points in "
            "Evidence Fusion.",

        "eo_source":
            eo_data.get(
                "source"
            ),

        "eo_product":
            eo_data.get(
                "product"
            ),

        "eo_observation_date":
            eo_data.get(
                "observation_date"
            ),

        "district_count":
            len(results),

        "eo_district_matches":
            eo_matches,

        "eo_district_missing":
            eo_missing,

        "terrain_district_matches":
            terrain_matches,

        "terrain_district_missing":
            terrain_missing,

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
            indent=2
        )

    # =====================================================
    # SUMMARY
    # =====================================================

    eo_evidence_count = sum(
        1
        for district in results
        if district["data_quality"]["eo_available"]
    )

    strong_eo_count = sum(
        1
        for district in results
        if (
            district["evidence"]["current"]["eo_flood"]
            == "STRONG"
        )
    )

    moderate_eo_count = sum(
        1
        for district in results
        if (
            district["evidence"]["current"]["eo_flood"]
            == "MODERATE"
        )
    )

    terrain_available_count = sum(
        1
        for district in results
        if district["terrain_context"]["available"]
    )

    # =====================================================
    # PRINT SUMMARY
    # =====================================================

    print()
    print("=" * 80)
    print("EVIDENCE FUSION V4 SUMMARY")
    print("=" * 80)

    print(
        f"Districts processed    : "
        f"{len(results)}"
    )

    print(
        f"EO district matches     : "
        f"{eo_matches}"
    )

    print(
        f"EO evidence available  : "
        f"{eo_evidence_count}"
    )

    print(
        f"Strong EO evidence     : "
        f"{strong_eo_count}"
    )

    print(
        f"Moderate EO evidence   : "
        f"{moderate_eo_count}"
    )

    print(
        f"Terrain matches        : "
        f"{terrain_matches}"
    )

    print(
        f"Terrain missing        : "
        f"{terrain_missing}"
    )

    print(
        f"Terrain available      : "
        f"{terrain_available_count}"
    )

    print(
        f"Output                 : "
        f"{OUTPUT_FILE}"
    )

    print("=" * 80)

    # =====================================================
    # TOP EO DISTRICTS
    # =====================================================

    print()
    print("Top EO evidence:")

    top_eo = sorted(
        [
            district
            for district in results
            if district["data_quality"]["eo_available"]
        ],
        key=lambda x:
            x["eo_observation"]["eo_score"],
        reverse=True
    )

    for district in top_eo[:10]:

        print(
            f"{district['district']:<22} "
            f"EO={district['evidence']['current']['eo_flood']:<9} "
            f"Flood={district['eo_observation']['flood_pixels']:>5} "
            f"Ratio={district['eo_observation']['flood_ratio_pct']:>6.2f}%"
        )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
