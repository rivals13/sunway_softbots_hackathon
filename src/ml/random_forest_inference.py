import json
from pathlib import Path

import joblib
import pandas as pd
import shap


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = PROJECT_ROOT / "data/ml/model/prava_random_forest.joblib"
RAINFALL_PATH = (
    PROJECT_ROOT
    / "data/processed/rainfall/prava_rainfall_features.json"
)

FEATURE_MAP = {
    "rain_1h": "nasa_1h_mm",
    "rain_3h": "nasa_3h_mm",
    "rain_6h": "nasa_6h_mm",
    "rain_12h": "nasa_12h_mm",
    "rain_24h": "nasa_24h_mm",
}


def _load_rainfall():
    if not RAINFALL_PATH.exists():
        raise FileNotFoundError(
            f"Rainfall feature file not found: {RAINFALL_PATH}"
        )

    with open(RAINFALL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_district(data, district):
    target = district.strip().lower()

    for item in data.get("districts", []):
        if str(item.get("district", "")).strip().lower() == target:
            return item

    return None


def get_ml_evidence(district: str):
    """
    Run the existing PRAVAH Random Forest model and SHAP explanation
    against the latest district rainfall features.

    This is a parallel ML evidence layer. It does not modify the
    deterministic PRAVAH risk state.
    """

    if not district or not district.strip():
        return {
            "success": False,
            "error": "District is required.",
        }

    model = joblib.load(MODEL_PATH)
    rainfall_data = _load_rainfall()

    district_data = _find_district(rainfall_data, district)

    if district_data is None:
        return {
            "success": False,
            "error": f"District not found: {district}",
        }

    rainfall = district_data.get("rainfall", {})

    X = pd.DataFrame([{
        feature: rainfall.get(source_field)
        for feature, source_field in FEATURE_MAP.items()
    }])

    # The trained pipeline already contains the imputer.
    probability = model.predict_proba(X)[0]
    prediction = int(model.predict(X)[0])

    rf = model.named_steps["rf"]
    imputer = model.named_steps["imputer"]

    X_imputed = imputer.transform(X)

    explainer = shap.TreeExplainer(rf)
    shap_values = explainer.shap_values(X_imputed)

    if isinstance(shap_values, list):
        values = shap_values[1][0]
    else:
        if len(shap_values.shape) == 3:
            values = shap_values[0, :, 1]
        else:
            values = shap_values[0]

    shap_contributions = {
        feature: float(value)
        for feature, value in zip(X.columns, values)
    }

    return {
        "success": True,
        "district": district_data.get("district"),
        "district_id": district_data.get("district_id"),
        "model": {
            "type": "RandomForestClassifier",
            "prediction": prediction,
            "prediction_label": (
                "flood_event" if prediction == 1 else "non_flood_event"
            ),
            "flood_event_probability": float(probability[1]),
            "non_flood_event_probability": float(probability[0]),
        },
        "features": {
            feature: (
                None
                if pd.isna(value)
                else float(value)
            )
            for feature, value in X.iloc[0].items()
        },
        "shap": {
            "flood_event_class": shap_contributions,
        },
        "source": {
            "model": str(MODEL_PATH.relative_to(PROJECT_ROOT)),
            "rainfall": str(
                RAINFALL_PATH.relative_to(PROJECT_ROOT)
            ),
        },
    }
