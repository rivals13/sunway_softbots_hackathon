from pathlib import Path

# ============================================================
# PRAVAH PROJECT PATHS
# ============================================================

# softbots/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Main directories
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Boundary/reference data
BOUNDARIES_DIR = DATA_DIR / "boundaries"
GEOJSON_PATH = BOUNDARIES_DIR / "npl_boundaries_extracted" / "npl_admin2.geojson"

# Raw data
RAW_DIR = DATA_DIR / "raw"
VIIRS_DIR = RAW_DIR / "viirs"

# Processed data
PROCESSED_DIR = DATA_DIR / "processed"
TERRAIN_FILE = DATA_DIR / "processed" / "terrain" / "prava_terrain_features.json"


# Processed data categories
BIPAD_DIR = PROCESSED_DIR / "bipad"
FUSED_DIR = PROCESSED_DIR / "fused"
RAINFALL_DIR = PROCESSED_DIR / "rainfall"
RIVER_DIR = PROCESSED_DIR / "river"
RUNOFF_DIR = PROCESSED_DIR / "runoff"
WEATHER_DIR = PROCESSED_DIR / "weather"
EO_DIR = PROCESSED_DIR / "eo"
FUSION_DIR = PROCESSED_DIR / "fusion"

# Risk/event/map outputs
RISK_DIR = OUTPUTS_DIR / "risk"
EVENTS_DIR = OUTPUTS_DIR / "events"
MAPS_DIR = OUTPUTS_DIR / "maps"

# Reference datasets
DISTRICT_CN_FILE = BOUNDARIES_DIR / "district_cn.json"
DISTRICT_CN_ARCII_FILE = BOUNDARIES_DIR / "district_cn_arcII.json"

# ============================================================
# PRAVAH PIPELINE FILES
# ============================================================

BIPAD_FILE = BIPAD_DIR / "prava_bipad_realtime.json"
LIVE_FUSED_FILE = FUSED_DIR / "prava_live_fused_data.json"

RAINFALL_FILE = RAINFALL_DIR / "prava_rainfall_features.json"
RIVER_FILE = RIVER_DIR / "prava_river_features.json"
GEOGLOWS_FILE = RIVER_DIR / "prava_geoglows_features.json"

RUNOFF_FILE = RUNOFF_DIR / "prava_runoff_data.json"
FORECAST_RUNOFF_FILE = RUNOFF_DIR / "prava_forecast_runoff.json"

WEATHER_FILE = WEATHER_DIR / "prava_weather_forecast.json"

EO_FEATURES_FILE = EO_DIR / "prava_eo_features.json"

HYDROLOGY_FILE = FUSION_DIR / "prava_hydrology_features.json"
EVIDENCE_FILE = FUSION_DIR / "prava_evidence_features.json"

RISK_FILE = RISK_DIR / "prava_risk_features.json"
OLD_RISK_FILE = RISK_DIR / "prava_risk_data.json"

FLOOD_EVENTS_FILE = EVENTS_DIR / "prava_flood_events.json"

HAZARD_MAP_FILE = MAPS_DIR / "prava_hazard_map.html"
OLD_HAZARD_MAP_FILE = MAPS_DIR / "pravah_hazard_map.html"
