import json
from pathlib import Path

from src.ml.random_forest_inference import get_ml_evidence as run_ml_evidence


PROJECT_ROOT = Path(__file__).resolve().parents[2]


FILES = {
    "risk": PROJECT_ROOT / "outputs/risk/prava_risk_data.json",
    "risk_features": PROJECT_ROOT / "outputs/risk/prava_risk_features.json",
    "rainfall": PROJECT_ROOT / "data/processed/rainfall/prava_rainfall_features.json",
    "river": PROJECT_ROOT / "data/processed/river/prava_river_features.json",
    "hydrology": PROJECT_ROOT / "data/processed/fusion/prava_hydrology_features.json",
    "evidence": PROJECT_ROOT / "data/processed/fusion/prava_evidence_features.json",
    "eo": PROJECT_ROOT / "data/processed/eo/prava_eo_features.json",
    "events": PROJECT_ROOT / "outputs/events/prava_flood_events.json",
}


def load_json(name):
    path = FILES[name]

    if not path.exists():
        raise FileNotFoundError(f"PRAVAH data file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_district(data, district):
    districts = data.get("districts", {})

    if isinstance(districts, dict):
        for _, item in districts.items():
            if str(item.get("district", "")).strip().lower() == district.strip().lower():
                return item

    elif isinstance(districts, list):
        for item in districts:
            if str(item.get("district", "")).strip().lower() == district.strip().lower():
                return item

    return None


def get_current_risk(district: str):
    """
    Return current PRAVAH risk information.

    If district is provided, return that district.
    Otherwise return a summary of all districts.
    """
    data = load_json("risk_features")

    if district:
        result = find_district(data, district)

        if result is None:
            return {
                "success": False,
                "error": f"District not found: {district}",
            }

        return {
            "success": True,
            "district": result,
        }

    return {
        "success": True,
        "generated_at_utc": data.get("generated_at_utc"),
        "risk_levels": data.get("risk_levels"),
        "future_outlook": data.get("future_outlook"),
        "freshness": data.get("freshness"),
        "district_count": len(data.get("districts", {})),
    }


def get_rainfall(district: str):
    """Return rainfall and SCS-CN runoff information for a district."""
    data = load_json("rainfall")
    result = find_district(data, district)

    if result is None:
        return {
            "success": False,
            "error": f"District not found: {district}",
        }

    return {
        "success": True,
        "district": result.get("district"),
        "district_id": result.get("district_id"),
        "rainfall": result.get("rainfall"),
        "hydrological_features": result.get("hydrological_features"),
        "scs_cn": result.get("scs_cn"),
        "source_information": result.get("source_information"),
        "data_quality": result.get("data_quality"),
    }


def get_river_status(district: str):
    """Return BIPAD/DHM river observations for a district."""
    data = load_json("river")
    result = find_district(data, district)

    if result is None:
        return {
            "success": False,
            "error": f"District not found: {district}",
        }

    return {
        "success": True,
        "district": result.get("district"),
        "district_id": result.get("district_id"),
        "river": result.get("river"),
        "data_quality": result.get("data_quality"),
    }


def get_hydrology(district: str):
    """Return combined rainfall, river, forecast and GEOGLOWS hydrology."""
    data = load_json("hydrology")
    result = find_district(data, district)

    if result is None:
        return {
            "success": False,
            "error": f"District not found: {district}",
        }

    return {
        "success": True,
        "district": result.get("district"),
        "district_id": result.get("district_id"),
        "rainfall": result.get("rainfall"),
        "river": result.get("river"),
        "forecast": result.get("forecast"),
        "geoglows": result.get("geoglows"),
        "hydrological_fusion": result.get("hydrological_fusion"),
        "data_quality": result.get("data_quality"),
    }


def get_eo_evidence(district: str):
    """Return VIIRS Earth-observation flood evidence."""
    data = load_json("eo")
    result = find_district(data, district)

    if result is None:
        return {
            "success": False,
            "error": f"District not found: {district}",
        }

    return {
        "success": True,
        "district": result.get("district"),
        "district_id": result.get("district_id"),
        "eo": result.get("eo"),
        "source_information": result.get("source_information"),
        "data_quality": result.get("data_quality"),
    }


def get_event_status(district: str | None = None):
    """
    Return flood-event detector information.

    If district is provided, return that district's event status.
    Otherwise return the overall event summary and candidate lists.
    """
    data = load_json("events")

    if district:
        result = find_district(data, district)

        if result is None:
            return {
                "success": False,
                "error": f"District not found: {district}",
            }

        return {
            "success": True,
            "district": result,
        }

    return {
        "success": True,
        "generated_at_utc": data.get("generated_at_utc"),
        "statistics": data.get("statistics"),
        "simulation_candidates": data.get("simulation_candidates"),
        "scenario_candidates": data.get("scenario_candidates"),
        "watch_candidates": data.get("watch_candidates"),
        "monitor_candidates": data.get("monitor_candidates"),
    }



def get_ml_evidence(district: str):
    """
    Return Random Forest flood-event classification and SHAP evidence
    for the latest PRAVAH rainfall features.

    This is a parallel ML evidence layer and does not modify the
    deterministic PRAVAH risk state.
    """
    return run_ml_evidence(district)
