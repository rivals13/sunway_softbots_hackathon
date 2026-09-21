from pathlib import Path
import json
import html
import re
from datetime import datetime


# ============================================================
# PRAVAH — AGENTIC DISASTER INTELLIGENCE MAP
# UI / PRESENTATION LAYER
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

GEOJSON_PATH = ROOT / "data/boundaries/npl_boundaries_extracted/npl_admin2.geojson"
RISK_PATH = ROOT / "outputs/risk/prava_risk_features.json"
RISK_DATA_PATH = ROOT / "outputs/risk/prava_risk_data.json"
FUSED_PATH = ROOT / "data/processed/fused/prava_live_fused_data.json"

OUT_DIR = ROOT / "outputs/maps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUT_DIR / "prava_hazard_map.html"


# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARNING: Could not load {path}: {e}")
        return {}


def norm(value):
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def safe(value, default="N/A"):
    if value is None or value == "":
        return default
    return value


def number(value, digits=1):
    try:
        return round(float(value), digits)
    except Exception:
        return None


def risk_color(level):
    level = str(level or "LOW").upper()

    return {
        "LOW": "#3fb950",
        "WATCH": "#f2b84b",
        "WARNING": "#f97316",
        "CRITICAL": "#ef4444",
        "NO DATA": "#64748b",
    }.get(level, "#64748b")


def risk_class(level):
    return str(level or "LOW").upper().replace(" ", "-")


# ============================================================
# LOAD DATA
# ============================================================

geojson = load_json(GEOJSON_PATH)
risk_features = load_json(RISK_PATH)
risk_data = load_json(RISK_DATA_PATH)
fused_data = load_json(FUSED_PATH)

features = geojson.get("features", [])

if not features:
    raise RuntimeError(f"No GeoJSON districts found: {GEOJSON_PATH}")


# ============================================================
# BUILD RISK LOOKUP
# ============================================================

risk_lookup = {}

# GeoJSON risk features
if isinstance(risk_features, dict):
    for feature in risk_features.get("features", []):
        props = feature.get("properties", {})
        name = (
            props.get("district")
            or props.get("district_name")
            or props.get("adm2_name")
            or props.get("name")
        )

        if name:
            risk_lookup[norm(name)] = props


# Main risk dataset
district_data = {}

if isinstance(risk_data, dict):
    districts = risk_data.get("districts", {})

    if isinstance(districts, dict):
        for key, value in districts.items():
            if isinstance(value, dict):
                name = (
                    value.get("district")
                    or value.get("district_name")
                    or key
                )
                district_data[norm(name)] = value


# Fused data lookup
fused_lookup = {}

if isinstance(fused_data, dict):
    fused_districts = fused_data.get("districts", {})

    if isinstance(fused_districts, dict):
        for key, value in fused_districts.items():
            if isinstance(value, dict):
                name = (
                    value.get("district")
                    or value.get("district_name")
                    or key
                )
                fused_lookup[norm(name)] = value


# ============================================================
# MERGE DISTRICTS
# ============================================================

merged_features = []

for feature in features:

    props = dict(feature.get("properties", {}))

    district_name = (
        props.get("adm2_name")
        or props.get("district")
        or props.get("name")
        or props.get("NAME_2")
        or "Unknown"
    )

    key = norm(district_name)

    risk_props = risk_lookup.get(key, {})
    district = district_data.get(key, {})
    fused = fused_lookup.get(key, {})

    risk_obj = district.get("risk", {})
    future_obj = district.get("future", {})
    rainfall_obj = district.get("rainfall", {})
    runoff_obj = district.get("runoff", {})
    river_obj = district.get("river", {})

    if not isinstance(risk_obj, dict):
        risk_obj = {}

    if not isinstance(future_obj, dict):
        future_obj = {}

    if not isinstance(rainfall_obj, dict):
        rainfall_obj = {}

    if not isinstance(runoff_obj, dict):
        runoff_obj = {}

    if not isinstance(river_obj, dict):
        river_obj = {}

    level = (
        risk_obj.get("level")
        or risk_props.get("pravah_risk")
        or risk_props.get("risk_level")
        or "LOW"
    )

    score = (
        risk_obj.get("score")
        if risk_obj.get("score") is not None
        else risk_props.get("pravah_score", 0)
    )

    confidence = (
        risk_obj.get("confidence")
        or risk_props.get("pravah_confidence")
        or "LOW"
    )

    future = (
        future_obj.get("outlook")
        or risk_props.get("future_outlook")
        or "NORMAL"
    )

    rainfall = (
        rainfall_obj
        if rainfall_obj
        else {}
    )

    runoff = runoff_obj if runoff_obj else {}
    river = river_obj if river_obj else {}

    # Attempt additional flattened properties
    def pick(*names):
        for source in (
            district,
            risk_props,
            fused,
            rainfall,
            runoff,
            river,
        ):
            if isinstance(source, dict):
                for n in names:
                    if source.get(n) is not None:
                        return source.get(n)
        return None

    record = {
        "district": district_name,
        "district_id": pick("district_id", "pravah_district_id"),
        "risk_level": str(level).upper(),
        "risk_score": number(score, 1) or 0,
        "confidence": confidence,
        "confidence_score": pick(
            "confidence_score",
            "pravah_confidence_score",
        ),

        "future_outlook": str(future).upper(),

        "nasa_1h": pick("nasa_1h_mm", "rain_1h_mm"),
        "nasa_6h": pick("nasa_6h_mm", "rain_6h_mm"),
        "nasa_12h": pick("nasa_12h_mm", "rain_12h_mm"),
        "nasa_24h": pick("nasa_24h_mm", "rain_24h_mm"),

        "bipad_1h": pick("bipad_1h_mm"),

        "runoff": pick(
            "runoff_depth_Q_mm",
            "scs_cn_runoff_6h_mm",
            "runoff_mm",
        ),

        "runoff_class": pick(
            "runoff_class",
        ),

        "river_status": pick(
            "river_status",
            "status",
        ),

        "river_warning": pick(
            "river_warning_stations",
            "warning_stations",
        ),

        "river_danger": pick(
            "river_danger_stations",
            "danger_stations",
        ),

        "river_rising": pick(
            "river_rising_stations",
            "rising_stations",
        ),

        "geoglows_current": pick(
            "geoglows_current_flow",
            "current_flow_m3s",
        ),

        "geoglows_peak": pick(
            "geoglows_peak_flow",
            "forecast_peak_flow_m3s",
        ),

        "geoglows_rise": pick(
            "geoglows_forecast_rise",
            "forecast_rise_m3s",
        ),

        "geoglows_hours": pick(
            "geoglows_hours_to_peak",
            "hours_to_peak",
        ),

        "eo_available": pick("eo_available"),
        "eo_date": pick(
            "eo_observation_date",
            "eo_date",
        ),

        "pressure": pick(
            "pressure_index",
        ),

        "drivers": pick(
            "pravah_drivers",
            "drivers",
        ),
    }

    props["pravah"] = record

    feature["properties"] = props

    merged_features.append(feature)


# ============================================================
# STATISTICS
# ============================================================

counts = {
    "LOW": 0,
    "WATCH": 0,
    "WARNING": 0,
    "CRITICAL": 0,
}

future_elevated = 0

for feature in merged_features:

    p = feature["properties"]["pravah"]

    level = p["risk_level"]

    if level in counts:
        counts[level] += 1

    if p["future_outlook"] == "ELEVATED":
        future_elevated += 1


geojson_out = {
    "type": "FeatureCollection",
    "features": merged_features,
}


generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

geojson_json = json.dumps(
    geojson_out,
    ensure_ascii=False,
    separators=(",", ":"),
)


# ============================================================
# HTML
# ============================================================

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>PRAVAH — Disaster Intelligence</title>

<link rel="stylesheet"
      href="../../src/mapping/vendor/leaflet/leaflet.css">

<style>

:root {
    --bg: #071018;
    --panel: #0c1720;
    --panel2: #101f2a;
    --border: #213542;

    --text: #edf4f7;
    --muted: #91a5b0;

    --teal: #2dd4bf;
    --green: #3fb950;
    --amber: #f2b84b;
    --orange: #f97316;
    --red: #ef4444;

    --font: Inter, ui-sans-serif, system-ui, -apple-system,
            BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;

    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
}

button,
input,
textarea {
    font-family: inherit;
}

#app {
    width: 100%;
    height: 100%;
    display: grid;

    grid-template-columns: 255px minmax(0, 1fr) 390px;

    grid-template-rows: 68px minmax(0, 1fr) 42px;
}


/* ============================================================
   HEADER
   ============================================================ */

header {
    grid-column: 1 / 4;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 22px;

    background: #08131b;
    border-bottom: 1px solid var(--border);

    z-index: 1000;
}

.brand {
    display: flex;
    align-items: center;
    gap: 13px;
}

.brand-mark {
    width: 38px;
    height: 38px;

    display: grid;
    place-items: center;

    border: 1px solid #2dd4bf66;
    border-radius: 10px;

    color: var(--teal);
    font-size: 19px;
    font-weight: 800;

    background: #0b262b;
}

.brand-name {
    font-size: 21px;
    font-weight: 800;
    letter-spacing: .04em;
}

.brand-sub {
    color: var(--muted);
    font-size: 12px;
    margin-top: 2px;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 20px;
}

.live {
    display: flex;
    align-items: center;
    gap: 8px;

    color: #b7c7ce;
    font-size: 13px;
}

.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);

    box-shadow: 0 0 0 4px #3fb95018;
}

.header-stat {
    color: var(--muted);
    font-size: 13px;
}

.header-stat strong {
    color: var(--text);
}


/* ============================================================
   LEFT SIDEBAR
   ============================================================ */

#sidebar {
    grid-column: 1;
    grid-row: 2;

    overflow-y: auto;

    background: #09151e;
    border-right: 1px solid var(--border);

    padding: 18px 15px;
}

.section-title {
    color: #d7e4e9;

    font-size: 12px;
    font-weight: 800;

    letter-spacing: .12em;
    text-transform: uppercase;

    margin: 7px 8px 10px;
}

.layer {
    width: 100%;

    display: flex;
    align-items: center;
    gap: 11px;

    padding: 12px 11px;
    margin-bottom: 5px;

    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;

    color: #aebfc7;

    cursor: pointer;
    text-align: left;

    font-size: 14px;

    transition: .15s ease;
}

.layer:hover {
    background: #10222c;
    color: white;
}

.layer.active {
    background: #103036;
    border-color: #2dd4bf44;
    color: white;
}

.layer-icon {
    width: 28px;
    height: 28px;

    display: grid;
    place-items: center;

    border-radius: 7px;

    background: #142630;

    font-size: 15px;
}

.layer.active .layer-icon {
    color: var(--teal);
    background: #164047;
}

.status-block {
    margin-top: 22px;

    border-top: 1px solid var(--border);

    padding-top: 17px;
}

.status-row {
    display: flex;
    justify-content: space-between;

    padding: 8px;

    font-size: 13px;
}

.status-row span:first-child {
    color: var(--muted);
}

.status-row strong {
    color: white;
}

.legend {
    margin-top: 18px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 10px;

    padding: 7px 8px;

    font-size: 13px;
    color: #aebfc7;
}

.legend-dot {
    width: 11px;
    height: 11px;
    border-radius: 50%;
}


/* ============================================================
   MAP
   ============================================================ */

#map {
    grid-column: 2;
    grid-row: 2;

    width: 100%;
    height: 100%;

    background:
        radial-gradient(circle at 50% 45%, #17313a 0%, #0a171f 60%);
}

.leaflet-container {
    font-family: var(--font);
    background: #09151d;
}

.leaflet-control-zoom {
    border: 1px solid var(--border) !important;
}

.leaflet-control-zoom a {
    background: #0b1821 !important;
    color: #d8e5e9 !important;
    border-bottom-color: var(--border) !important;
}

.district-label {
    background: transparent;
    border: none;

    color: #c9d8dd;

    font-size: 10px;
    font-weight: 600;

    text-shadow:
        0 1px 3px #000,
        0 0 4px #000;
}


/* ============================================================
   RISK MARKER
   ============================================================ */

.risk-marker {
    width: 20px;
    height: 20px;

    border-radius: 50%;

    border: 2px solid white;

    box-shadow:
        0 0 0 5px rgba(255,255,255,.07),
        0 3px 12px rgba(0,0,0,.5);
}

.risk-marker.watch {
    animation: watchPulse 2.2s infinite;
}

.risk-marker.warning {
    animation: warningPulse 1.5s infinite;
}

.risk-marker.critical {
    animation: criticalPulse 1.1s infinite;
}

@keyframes watchPulse {
    0%,100% {
        box-shadow:
            0 0 0 4px rgba(242,184,75,.12),
            0 3px 12px rgba(0,0,0,.5);
    }

    50% {
        box-shadow:
            0 0 0 10px rgba(242,184,75,.04),
            0 3px 14px rgba(0,0,0,.6);
    }
}

@keyframes warningPulse {
    0%,100% {
        box-shadow:
            0 0 0 4px rgba(249,115,22,.14),
            0 3px 14px rgba(0,0,0,.5);
    }

    50% {
        box-shadow:
            0 0 0 12px rgba(249,115,22,.04),
            0 3px 16px rgba(0,0,0,.6);
    }
}

@keyframes criticalPulse {
    0%,100% {
        box-shadow:
            0 0 0 5px rgba(239,68,68,.16),
            0 3px 15px rgba(0,0,0,.5);
    }

    50% {
        box-shadow:
            0 0 0 14px rgba(239,68,68,.04),
            0 3px 20px rgba(0,0,0,.65);
    }
}


/* ============================================================
   DISTINCT OBSERVATION SYMBOLS
   ============================================================ */

.obs-marker {
    width: 30px;
    height: 30px;

    display: grid;
    place-items: center;

    border-radius: 9px;

    background: #0b1821;
    border: 1px solid #5a7380;

    box-shadow: 0 3px 12px #0008;

    font-size: 15px;
}

.obs-marker.rain {
    border-color: #38bdf866;
    color: #38bdf8;
}

.obs-marker.river {
    border-color: #22d3ee66;
    color: #22d3ee;
}

.obs-marker.eo {
    border-color: #a78bfa66;
    color: #a78bfa;
}


/* ============================================================
   RIGHT INTELLIGENCE PANEL
   ============================================================ */

#intelligence {
    grid-column: 3;
    grid-row: 2;

    min-width: 0;

    display: flex;
    flex-direction: column;

    background: #0a151e;
    border-left: 1px solid var(--border);
}

.intel-head {
    padding: 18px 19px 14px;

    border-bottom: 1px solid var(--border);
}

.intel-kicker {
    color: var(--teal);

    font-size: 11px;
    font-weight: 800;

    letter-spacing: .12em;
    text-transform: uppercase;
}

.intel-title {
    font-size: 24px;
    font-weight: 800;

    margin-top: 6px;
}

.intel-body {
    flex: 1;

    overflow-y: auto;

    padding: 17px 18px;
}

.selected-district {
    padding: 15px;

    background: #101f29;

    border: 1px solid var(--border);
    border-radius: 11px;
}

.district-name {
    font-size: 23px;
    font-weight: 800;
}

.district-meta {
    color: var(--muted);
    font-size: 13px;
    margin-top: 4px;
}

.risk-badge {
    display: inline-flex;
    align-items: center;

    margin-top: 13px;

    padding: 6px 10px;

    border-radius: 6px;

    font-size: 12px;
    font-weight: 800;
    letter-spacing: .06em;
}

.metric-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;

    gap: 8px;

    margin-top: 10px;
}

.metric {
    padding: 11px;

    background: #0d1a23;

    border: 1px solid #1d303a;
    border-radius: 8px;
}

.metric-label {
    color: var(--muted);
    font-size: 11px;
}

.metric-value {
    margin-top: 5px;

    font-size: 19px;
    font-weight: 750;
}

.card {
    margin-top: 13px;

    padding: 14px;

    background: #0e1b24;

    border: 1px solid #1e313c;
    border-radius: 10px;
}

.card-title {
    color: #dce8ec;

    font-size: 13px;
    font-weight: 800;

    letter-spacing: .05em;
    text-transform: uppercase;

    margin-bottom: 11px;
}

.reasoning {
    color: #c5d2d8;

    font-size: 14px;
    line-height: 1.65;
}

.reasoning strong {
    color: white;
}

.evidence-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;

    padding: 9px 0;

    border-bottom: 1px solid #1c2b34;

    font-size: 13px;
}

.evidence-row:last-child {
    border-bottom: none;
}

.evidence-name {
    color: #91a5b0;
}

.evidence-value {
    color: #e6eff2;
    font-weight: 650;
    text-align: right;
}

.outlook {
    display: flex;
    align-items: center;
    gap: 9px;

    font-size: 14px;
    font-weight: 700;
}

.outlook-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
}

.ml-note {
    color: #9fb0b8;
    font-size: 12px;
    line-height: 1.55;
}

.shap-row {
    margin-top: 10px;
}

.shap-top {
    display: flex;
    justify-content: space-between;

    color: #c8d6db;

    font-size: 12px;
}

.shap-bar {
    height: 5px;

    margin-top: 5px;

    border-radius: 3px;

    background: #172831;
    overflow: hidden;
}

.shap-fill {
    height: 100%;

    background: var(--teal);
}


/* ============================================================
   AGENT
   ============================================================ */

.agent {
    border-top: 1px solid var(--border);

    padding: 13px 15px 15px;

    background: #08131b;
}

.agent-label {
    color: var(--teal);

    font-size: 11px;
    font-weight: 800;

    letter-spacing: .1em;
    text-transform: uppercase;

    margin-bottom: 8px;
}

.agent-input {
    width: 100%;

    resize: none;

    min-height: 45px;
    max-height: 100px;

    padding: 11px 12px;

    background: #0e1d26;

    color: white;

    border: 1px solid #29404b;
    border-radius: 8px;

    outline: none;

    font-size: 13px;
}

.agent-input:focus {
    border-color: #2dd4bf88;
}

.agent-actions {
    display: flex;
    gap: 6px;

    margin-top: 7px;
}

.quick {
    flex: 1;

    padding: 8px 5px;

    background: #10222b;

    border: 1px solid #253a44;

    border-radius: 7px;

    color: #b8c9cf;

    cursor: pointer;

    font-size: 11px;
}

.quick:hover {
    color: white;
    border-color: #2dd4bf66;
}

.agent-response {
    max-height: 150px;

    overflow-y: auto;

    margin-top: 8px;

    padding: 10px;

    background: #0d1b24;

    border-left: 2px solid var(--teal);

    color: #cbd9de;

    font-size: 13px;
    line-height: 1.55;

    border-radius: 4px;
}


/* ============================================================
   FOOTER
   ============================================================ */

footer {
    grid-column: 1 / 4;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 15px;

    background: #071118;
    border-top: 1px solid var(--border);

    color: #718691;

    font-size: 11px;
}

.footer-left {
    display: flex;
    gap: 18px;
}

.footer-left strong {
    color: #b6c7cd;
}


/* ============================================================
   SEARCH
   ============================================================ */

.search {
    position: absolute;

    top: 82px;
    left: 275px;

    z-index: 900;

    width: 245px;

    background: #0b1821;

    border: 1px solid #29404b;
    border-radius: 8px;

    box-shadow: 0 8px 30px #0008;
}

.search input {
    width: 100%;

    border: none;
    outline: none;

    background: transparent;

    color: white;

    padding: 10px 12px;

    font-size: 13px;
}


/* ============================================================
   RESPONSIVE
   ============================================================ */

@media (max-width: 1150px) {

    #app {
        grid-template-columns: 210px minmax(0, 1fr) 340px;
    }

    #intelligence {
        font-size: 13px;
    }
}

@media (max-width: 900px) {

    #app {
        grid-template-columns: 1fr;
        grid-template-rows: 62px minmax(0, 1fr);
    }

    header {
        grid-column: 1;
    }

    #sidebar {
        display: none;
    }

    #map {
        grid-column: 1;
        grid-row: 2;
    }

    #intelligence {
        position: absolute;
        right: 0;
        top: 62px;
        bottom: 0;

        width: 360px;

        z-index: 1500;
    }

    footer {
        display: none;
    }

    .search {
        left: 15px;
        top: 76px;
    }
}

</style>
</head>

<body>

<div id="app">

<header>

    <div class="brand">

        <div class="brand-mark">P</div>

        <div>
            <div class="brand-name">PRAVAH</div>
            <div class="brand-sub">
                Agentic Disaster Intelligence
            </div>
        </div>

    </div>

    <div class="header-right">

        <div class="live">
            <span class="live-dot"></span>
            LIVE SNAPSHOT
        </div>

        <div class="header-stat">
            <strong id="districtCount">77</strong>
            districts monitored
        </div>

        <div class="header-stat">
            Generated <strong>__GENERATED__</strong>
        </div>

    </div>

</header>


<aside id="sidebar">

    <div class="section-title">Evidence layers</div>

    <button class="layer active" data-layer="risk">
        <span class="layer-icon">◉</span>
        <span>Current Risk</span>
    </button>

    <button class="layer" data-layer="future">
        <span class="layer-icon">◌</span>
        <span>Future Outlook</span>
    </button>

    <button class="layer" data-layer="rain">
        <span class="layer-icon">♢</span>
        <span>Rainfall</span>
    </button>

    <button class="layer" data-layer="river">
        <span class="layer-icon">≈</span>
        <span>River Stations</span>
    </button>

    <button class="layer" data-layer="drainage">
        <span class="layer-icon">⌁</span>
        <span>Terrain Drainage</span>
    </button>

    <button class="layer" data-layer="eo">
        <span class="layer-icon">◇</span>
        <span>EO Observations</span>
    </button>


    <div class="status-block">

        <div class="section-title">System status</div>

        <div class="status-row">
            <span>Districts</span>
            <strong>77 / 77</strong>
        </div>

        <div class="status-row">
            <span>Current Watch</span>
            <strong id="watchCount">__WATCH__</strong>
        </div>

        <div class="status-row">
            <span>Warning</span>
            <strong id="warningCount">__WARNING__</strong>
        </div>

        <div class="status-row">
            <span>Critical</span>
            <strong id="criticalCount">__CRITICAL__</strong>
        </div>

        <div class="status-row">
            <span>Future Elevated</span>
            <strong>__ELEVATED__</strong>
        </div>

    </div>


    <div class="legend">

        <div class="section-title">Risk state</div>

        <div class="legend-item">
            <span class="legend-dot" style="background:#3fb950"></span>
            Normal / Low
        </div>

        <div class="legend-item">
            <span class="legend-dot" style="background:#f2b84b"></span>
            Watch
        </div>

        <div class="legend-item">
            <span class="legend-dot" style="background:#f97316"></span>
            Warning
        </div>

        <div class="legend-item">
            <span class="legend-dot" style="background:#ef4444"></span>
            Critical
        </div>

    </div>

</aside>


<div id="map"></div>


<div class="search">
    <input id="searchInput"
           placeholder="Search district...">
</div>


<section id="intelligence">

    <div class="intel-head">

        <div class="intel-kicker">
            PRAVAH Intelligence
        </div>

        <div class="intel-title">
            Evidence → Reasoning → Action
        </div>

    </div>


    <div class="intel-body">

        <div id="districtCard" class="selected-district">

            <div class="district-name">
                Select a district
            </div>

            <div class="district-meta">
                Click a district on the map to inspect PRAVAH evidence.
            </div>

        </div>


        <div id="reasoningCard" class="card">

            <div class="card-title">
                PRAVAH assessment
            </div>

            <div class="reasoning">
                PRAVAH will combine the available rainfall,
                runoff, river, forecast and EO evidence for the
                selected district.
            </div>

        </div>


        <div id="evidenceCard" class="card">

            <div class="card-title">
                Evidence
            </div>

            <div class="evidence-row">
                <span class="evidence-name">NASA rainfall</span>
                <span class="evidence-value">—</span>
            </div>

            <div class="evidence-row">
                <span class="evidence-name">BIPAD rainfall</span>
                <span class="evidence-value">—</span>
            </div>

            <div class="evidence-row">
                <span class="evidence-name">SCS-CN runoff</span>
                <span class="evidence-value">—</span>
            </div>

            <div class="evidence-row">
                <span class="evidence-name">River response</span>
                <span class="evidence-value">—</span>
            </div>

            <div class="evidence-row">
                <span class="evidence-name">GEOGLOWS</span>
                <span class="evidence-value">—</span>
            </div>

            <div class="evidence-row">
                <span class="evidence-name">EO observation</span>
                <span class="evidence-value">—</span>
            </div>

        </div>


        <div id="futureCard" class="card">

            <div class="card-title">
                Future outlook
            </div>

            <div class="outlook">
                <span class="outlook-dot"
                      style="background:#64748b"></span>

                <span>Awaiting district selection</span>
            </div>

        </div>


        <div id="mlCard" class="card">

            <div class="card-title">
                ML intelligence
            </div>

            <div class="ml-note">
                PRAVAH can use the historical Random Forest
                intelligence layer and SHAP explanations here.
                District-specific predictions are shown only
                when precomputed model evidence is available.
            </div>

            <div id="shapContainer"></div>

        </div>

    </div>


    <div class="agent">

        <div class="agent-label">
            Ask PRAVAH
        </div>

        <textarea id="agentInput"
                  class="agent-input"
                  placeholder="Ask about this district..."></textarea>

        <div class="agent-actions">

            <button class="quick" data-question="why">
                Why this district?
            </button>

            <button class="quick" data-question="drivers">
                What is driving risk?
            </button>

            <button class="quick" data-question="next">
                What happens next?
            </button>

        </div>

        <div id="agentResponse"
             class="agent-response"
             style="display:none">
        </div>

    </div>

</section>


<footer>

    <div class="footer-left">
        <span>
            <strong>PRAVAH</strong>
            evidence-grounded disaster intelligence
        </span>

        <span>
            Spatial alignment • SCS-CN • Risk states
        </span>
    </div>

    <span>
        __GENERATED__
    </span>

</footer>

</div>


<script src="../../src/mapping/vendor/leaflet/leaflet.js"></script>

<script>

const DISTRICTS = __GEOJSON__;

const map = L.map("map", {
    zoomControl: true,
    preferCanvas: true,
    attributionControl: false
}).setView([28.3949, 84.1240], 7);


/* ============================================================
   LAYERS
   ============================================================ */

const layers = {
    district: L.layerGroup().addTo(map),
    rain: L.layerGroup(),
    river: L.layerGroup(),
    drainage: L.layerGroup(),
    eo: L.layerGroup(),
    future: L.layerGroup()
};


let selectedFeature = null;
let selectedLayer = null;
let activeMode = "risk";


/* ============================================================
   MAP STYLE
   ============================================================ */

function districtStyle(feature) {

    const p = feature.properties.pravah;

    let color = "#3fb950";

    if (activeMode === "future") {

        color =
            p.future_outlook === "ELEVATED"
                ? "#f2b84b"
                : "#31525a";

    } else {

        color = {
            LOW: "#3fb950",
            WATCH: "#f2b84b",
            WARNING: "#f97316",
            CRITICAL: "#ef4444"
        }[p.risk_level] || "#64748b";

    }

    return {
        color: color,
        weight: selectedFeature === feature ? 3 : 1,
        opacity: selectedFeature === feature ? 1 : .72,

        fillColor: color,
        fillOpacity:
            selectedFeature === feature
                ? .48
                : activeMode === "future"
                    ? .30
                    : .20
    };
}


/* ============================================================
   DISTRICT REASONING
   ============================================================ */

function buildReasoning(p) {

    const level = p.risk_level;
    const future = p.future_outlook;

    const statements = [];

    if (level === "CRITICAL") {
        statements.push(
            "<strong>Current state:</strong> PRAVAH identifies " +
            "critical conditions from the available evidence."
        );
    }
    else if (level === "WARNING") {
        statements.push(
            "<strong>Current state:</strong> PRAVAH identifies " +
            "warning-level conditions requiring close attention."
        );
    }
    else if (level === "WATCH") {
        statements.push(
            "<strong>Current state:</strong> PRAVAH places this " +
            "district under WATCH based on elevated evidence."
        );
    }
    else {
        statements.push(
            "<strong>Current state:</strong> available evidence " +
            "does not currently indicate elevated deterministic risk."
        );
    }


    if (p.nasa_6h !== null) {

        statements.push(
            "NASA rainfall provides the primary spatial precipitation " +
            "input, with approximately <strong>" +
            p.nasa_6h +
            " mm</strong> accumulated over the available 6-hour window."
        );
    }


    if (p.bipad_1h !== null) {

        statements.push(
            "BIPAD provides a separate local observation signal of " +
            "<strong>" +
            p.bipad_1h +
            " mm</strong> over the latest available hour."
        );
    }


    if (p.runoff !== null) {

        statements.push(
            "The SCS-CN runoff calculation currently indicates " +
            "<strong>" +
            p.runoff +
            " mm</strong> of modeled runoff."
        );
    }


    if (p.river_rising && Number(p.river_rising) > 0) {

        statements.push(
            "<strong>River response:</strong> " +
            p.river_rising +
            " monitored station(s) are currently showing a rising signal."
        );
    }


    if (p.river_warning && Number(p.river_warning) > 0) {

        statements.push(
            "<strong>River warning evidence:</strong> " +
            p.river_warning +
            " station(s) are in warning conditions."
        );
    }


    if (p.geoglows_rise !== null) {

        statements.push(
            "GEOGLOWS provides forward river-flow context with a modeled " +
            "rise of approximately <strong>" +
            p.geoglows_rise +
            " m³/s</strong>."
        );
    }


    if (future === "ELEVATED") {

        statements.push(
            "<strong>Forward outlook:</strong> conditions are " +
            "classified as ELEVATED. This is a forward-looking signal " +
            "and is kept separate from the current deterministic risk state."
        );
    }


    return statements.join(" ");
}


/* ============================================================
   DISTRICT PANEL
   ============================================================ */

function selectDistrict(feature, layer) {

    selectedFeature = feature;
    selectedLayer = layer;

    const p = feature.properties.pravah;

    document.querySelector("#districtCard").innerHTML = `

        <div class="district-name">
            ${escapeHtml(p.district)}
        </div>

        <div class="district-meta">
            District ${safeText(p.district_id)} • Confidence:
            ${escapeHtml(p.confidence)}
        </div>

        <div class="risk-badge"
             style="
                background:${riskBackground(p.risk_level)};
                color:${riskColor(p.risk_level)};
             ">
            ${escapeHtml(p.risk_level)}
        </div>

        <div class="metric-grid">

            <div class="metric">
                <div class="metric-label">Current score</div>
                <div class="metric-value">
                    ${safeText(p.risk_score, "0")}
                </div>
            </div>

            <div class="metric">
                <div class="metric-label">Confidence</div>
                <div class="metric-value">
                    ${safeText(p.confidence)}
                </div>
            </div>

        </div>
    `;


    document.querySelector("#reasoningCard").innerHTML = `

        <div class="card-title">
            PRAVAH assessment
        </div>

        <div class="reasoning">
            ${buildReasoning(p)}
        </div>

    `;


    document.querySelector("#evidenceCard").innerHTML = `

        <div class="card-title">
            Evidence
        </div>

        ${evidenceRow("NASA rainfall — 6h",
                      formatNumber(p.nasa_6h, "mm"))}

        ${evidenceRow("BIPAD rainfall — 1h",
                      formatNumber(p.bipad_1h, "mm"))}

        ${evidenceRow("SCS-CN runoff",
                      formatNumber(p.runoff, "mm"))}

        ${evidenceRow("River response",
                      riverText(p))}

        ${evidenceRow("GEOGLOWS",
                      geoText(p))}

        ${evidenceRow("EO observation",
                      p.eo_available === true
                        ? "Available"
                        : "Not available")}

    `;


    document.querySelector("#futureCard").innerHTML = `

        <div class="card-title">
            Future outlook
        </div>

        <div class="outlook">

            <span class="outlook-dot"
                  style="background:
                    ${p.future_outlook === "ELEVATED"
                        ? "#f2b84b"
                        : "#3fb950"}">
            </span>

            <span>
                ${escapeHtml(p.future_outlook)}
            </span>

        </div>

    `;


    buildML(p);

    layer.bindTooltip(
        escapeHtml(p.district),
        {
            permanent: true,
            direction: "center",
            className: "district-label"
        }
    );

    layer.setStyle(districtStyle(feature));

    map.flyToBounds(
        layer.getBounds(),
        {
            padding: [80, 80],
            maxZoom: 9,
            duration: .8
        }
    );


    agentMessage(
        "Selected " +
        p.district +
        ". Ask PRAVAH why this district is being monitored."
    );
}


/* ============================================================
   EVIDENCE HELPERS
   ============================================================ */

function evidenceRow(name, value) {

    return `
        <div class="evidence-row">
            <span class="evidence-name">
                ${name}
            </span>

            <span class="evidence-value">
                ${value}
            </span>
        </div>
    `;
}


function riverText(p) {

    const parts = [];

    if (p.river_rising)
        parts.push(`${p.river_rising} rising`);

    if (p.river_warning)
        parts.push(`${p.river_warning} warning`);

    if (p.river_danger)
        parts.push(`${p.river_danger} danger`);

    if (!parts.length)
        return "No elevated stations";

    return parts.join(" • ");
}


function geoText(p) {

    if (p.geoglows_current === null &&
        p.geoglows_peak === null)
        return "No forecast signal";

    const peak =
        p.geoglows_peak !== null
            ? `${p.geoglows_peak} m³/s peak`
            : "";

    return peak || "Forecast available";
}


function formatNumber(value, suffix="") {

    if (value === null ||
        value === undefined ||
        value === "")
        return "N/A";

    const n = Number(value);

    if (!Number.isFinite(n))
        return "N/A";

    return `${n.toFixed(1)} ${suffix}`.trim();
}


function safeText(value, fallback="N/A") {

    if (
        value === null ||
        value === undefined ||
        value === ""
    )
        return fallback;

    return escapeHtml(String(value));
}


function escapeHtml(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function riskBackground(level) {

    return {
        LOW: "#3fb95018",
        WATCH: "#f2b84b18",
        WARNING: "#f9731618",
        CRITICAL: "#ef444418"
    }[level] || "#64748b18";
}


/* ============================================================
   ML
   ============================================================ */

function buildML(p) {

    const container =
        document.querySelector("#shapContainer");

    container.innerHTML = `

        <div class="ml-note">
            Historical Random Forest intelligence is treated as
            a parallel evidence layer. It does not replace the
            deterministic PRAVAH risk engine.
        </div>

        <div class="shap-row">

            <div class="shap-top">
                <span>24h rainfall</span>
                <span>highest historical signal</span>
            </div>

            <div class="shap-bar">
                <div class="shap-fill"
                     style="width:100%">
                </div>
            </div>

        </div>

        <div class="shap-row">

            <div class="shap-top">
                <span>12h rainfall</span>
                <span>strong signal</span>
            </div>

            <div class="shap-bar">
                <div class="shap-fill"
                     style="width:60%">
                </div>
            </div>

        </div>

        <div class="shap-row">

            <div class="shap-top">
                <span>6h rainfall</span>
                <span>supporting signal</span>
            </div>

            <div class="shap-bar">
                <div class="shap-fill"
                     style="width:59%">
                </div>
            </div>

        </div>
    `;
}


/* ============================================================
   DISTRICT LAYER
   ============================================================ */

function buildDistrictLayer() {

    layers.district.clearLayers();

    L.geoJSON(DISTRICTS, {

        style: districtStyle,

        onEachFeature: function(feature, layer) {

            layer.on({

                click: function() {

                    selectDistrict(
                        feature,
                        layer
                    );

                },

                mouseover: function() {

                    if (selectedFeature !== feature) {

                        layer.setStyle({
                            weight: 2,
                            fillOpacity:
                                activeMode === "future"
                                    ? .38
                                    : .28
                        });

                    }

                },

                mouseout: function() {

                    if (selectedFeature !== feature) {
                        layer.setStyle(
                            districtStyle(feature)
                        );
                    }

                }

            });

        }

    }).addTo(layers.district);
}


/* ============================================================
   OBSERVATION LAYERS
   ============================================================ */

function addRainLayer() {

    layers.rain.clearLayers();

    DISTRICTS.forEach(feature => {

        const p = feature.properties.pravah;

        if (
            p.nasa_6h === null &&
            p.nasa_1h === null &&
            p.bipad_1h === null
        )
            return;

        const center =
            L.geoJSON(feature).getBounds().getCenter();

        const icon =
            L.divIcon({
                className: "",
                html: `
                    <div class="obs-marker rain">
                        💧
                    </div>
                `,
                iconSize: [30,30],
                iconAnchor: [15,15]
            });

        const marker =
            L.marker(center, {
                icon: icon
            });

        marker.bindTooltip(
            `${escapeHtml(p.district)} • Rainfall evidence`,
            {
                direction: "top"
            }
        );

        marker.on("click", () => {

            const districtLayer =
                findDistrictLayer(feature);

            if (districtLayer)
                selectDistrict(
                    feature,
                    districtLayer
                );

        });

        marker.addTo(layers.rain);

    });
}


function addRiverLayer() {

    layers.river.clearLayers();

    DISTRICTS.forEach(feature => {

        const p = feature.properties.pravah;

        if (
            !p.river_rising &&
            !p.river_warning &&
            !p.river_danger
        )
            return;

        const center =
            L.geoJSON(feature).getBounds().getCenter();

        const icon =
            L.divIcon({
                className: "",
                html: `
                    <div class="obs-marker river">
                        ≋
                    </div>
                `,
                iconSize: [30,30],
                iconAnchor: [15,15]
            });

        const marker =
            L.marker(center, {
                icon: icon
            });

        marker.bindTooltip(
            `${escapeHtml(p.district)} • River evidence`,
            {
                direction: "top"
            }
        );

        marker.on("click", () => {

            const districtLayer =
                findDistrictLayer(feature);

            if (districtLayer)
                selectDistrict(
                    feature,
                    districtLayer
                );

        });

        marker.addTo(layers.river);

    });
}


function addEOLayer() {

    layers.eo.clearLayers();

    DISTRICTS.forEach(feature => {

        const p = feature.properties.pravah;

        if (p.eo_available !== true)
            return;

        const center =
            L.geoJSON(feature).getBounds().getCenter();

        const icon =
            L.divIcon({
                className: "",
                html: `
                    <div class="obs-marker eo">
                        ◇
                    </div>
                `,
                iconSize: [30,30],
                iconAnchor: [15,15]
            });

        L.marker(center, {
            icon: icon
        })
        .bindTooltip(
            `${escapeHtml(p.district)} • EO observation`,
            {
                direction: "top"
            }
        )
        .addTo(layers.eo);

    });
}


/* ============================================================
   DRAINAGE
   ============================================================ */

function addDrainageLayer() {

    layers.drainage.clearLayers();

    /*
       The terrain-derived drainage raster is currently stored
       as a GeoTIFF. It cannot be rendered directly by Leaflet
       without converting it to a browser-readable vector/raster
       representation.

       We deliberately do NOT fabricate drainage lines.

       Instead the UI provides a truthful system state.
    */

    const center =
        map.getCenter();

    const notice =
        L.marker(center, {

            icon: L.divIcon({
                className: "",
                html: `
                    <div style="
                        background:#0b1821;
                        color:#cbd9de;
                        border:1px solid #29404b;
                        border-radius:8px;
                        padding:10px 13px;
                        font-size:12px;
                        box-shadow:0 5px 20px #0008;
                        white-space:nowrap;
                    ">
                        Terrain drainage prepared —
                        browser layer conversion pending
                    </div>
                `,
                iconSize: null
            })

        });

    notice.addTo(layers.drainage);

}


/* ============================================================
   FUTURE
   ============================================================ */

function setFutureStyle() {

    buildDistrictLayer();

}


/* ============================================================
   FIND DISTRICT LAYER
   ============================================================ */

function findDistrictLayer(feature) {

    let found = null;

    layers.district.eachLayer(layer => {

        if (
            layer.feature &&
            layer.feature.properties &&
            layer.feature.properties.pravah &&
            layer.feature.properties.pravah.district ===
                feature.properties.pravah.district
        ) {
            found = layer;
        }

    });

    return found;
}


/* ============================================================
   MODE SWITCHING
   ============================================================ */

function setMode(mode) {

    activeMode = mode;

    Object.values(layers).forEach(layer => {

        if (map.hasLayer(layer))
            map.removeLayer(layer);

    });


    if (mode === "risk") {

        buildDistrictLayer();
        layers.district.addTo(map);

    }


    else if (mode === "future") {

        buildDistrictLayer();
        layers.district.addTo(map);

    }


    else if (mode === "rain") {

        buildDistrictLayer();

        layers.district.setStyle({
            color: "#29444e",
            weight: 1,
            fillColor: "#0d2229",
            fillOpacity: .14
        });

        addRainLayer();
        layers.rain.addTo(map);

    }


    else if (mode === "river") {

        buildDistrictLayer();

        layers.district.setStyle({
            color: "#29444e",
            weight: 1,
            fillColor: "#0d2229",
            fillOpacity: .14
        });

        addRiverLayer();
        layers.river.addTo(map);

    }


    else if (mode === "eo") {

        buildDistrictLayer();

        layers.district.setStyle({
            color: "#29444e",
            weight: 1,
            fillColor: "#0d2229",
            fillOpacity: .14
        });

        addEOLayer();
        layers.eo.addTo(map);

    }


    else if (mode === "drainage") {

        buildDistrictLayer();

        layers.district.setStyle({
            color: "#29444e",
            weight: 1,
            fillColor: "#0d2229",
            fillOpacity: .14
        });

        addDrainageLayer();
        layers.drainage.addTo(map);

    }


    if (selectedFeature) {

        const selected =
            findDistrictLayer(selectedFeature);

        if (selected) {

            selected.setStyle({
                weight: 3,
                fillOpacity: .45
            });

        }

    }

}


/* ============================================================
   AGENT
   ============================================================ */

function agentMessage(message) {

    const response =
        document.querySelector("#agentResponse");

    response.style.display = "block";

    response.innerHTML =
        escapeHtml(message);
}


function answerAgent(question) {

    if (!selectedFeature) {

        agentMessage(
            "Select a district first. PRAVAH needs a geographic context before answering an evidence-grounded question."
        );

        return;

    }


    const p =
        selectedFeature.properties.pravah;

    const q =
        question.toLowerCase();


    if (
        q.includes("why") ||
        q.includes("risk") ||
        q.includes("reason")
    ) {

        agentMessage(
            buildReasoning(p)
        );

        setMode("risk");

        return;
    }


    if (
        q.includes("rain") ||
        q.includes("precip")
    ) {

        agentMessage(
            `${p.district}: NASA provides the primary spatial rainfall input, while BIPAD provides separate local rainfall evidence. ` +
            `The available NASA 6-hour value is ${formatNumber(p.nasa_6h, "mm")}, ` +
            `and the latest BIPAD 1-hour observation is ${formatNumber(p.bipad_1h, "mm")}.`
        );

        setMode("rain");

        return;
    }


    if (
        q.includes("river") ||
        q.includes("water")
    ) {

        agentMessage(
            `${p.district}: river evidence shows ${riverText(p)}. ` +
            `GEOGLOWS is used separately as forward discharge context and should not be directly compared with BIPAD water-level warning thresholds.`
        );

        setMode("river");

        return;
    }


    if (
        q.includes("next") ||
        q.includes("future") ||
        q.includes("forecast")
    ) {

        agentMessage(
            `${p.district}: the current future outlook is ${p.future_outlook}. ` +
            `This outlook is kept separate from the current deterministic risk state so PRAVAH can distinguish what is happening now from what may require attention next.`
        );

        setMode("future");

        return;
    }


    if (
        q.includes("ml") ||
        q.includes("model") ||
        q.includes("shap")
    ) {

        agentMessage(
            `PRAVAH uses historical Random Forest intelligence as a parallel predictive signal. ` +
            `Historical SHAP analysis shows that longer rainfall windows, particularly 24-hour and 12-hour accumulation, are among the strongest learned predictors of documented flood-event days.`
        );

        return;
    }


    agentMessage(
        `For ${p.district}, PRAVAH currently reports ${p.risk_level} risk with a ${p.future_outlook} future outlook. ` +
        `Try asking about rainfall, rivers, future conditions, or ML reasoning.`
    );

}


/* ============================================================
   QUICK BUTTONS
   ============================================================ */

document.querySelectorAll(".quick")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                const type =
                    button.dataset.question;

                if (type === "why")
                    answerAgent("Why is this district at risk?");

                else if (type === "drivers")
                    answerAgent("What is driving risk?");

                else if (type === "next")
                    answerAgent("What happens next?");

            }
        );

    });


document.querySelector("#agentInput")
    .addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                const value =
                    event.target.value.trim();

                if (value) {

                    answerAgent(value);

                    event.target.value = "";

                }

            }

        }
    );


/* ============================================================
   LAYER BUTTONS
   ============================================================ */

document.querySelectorAll(".layer")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(".layer")
                    .forEach(b =>
                        b.classList.remove("active")
                    );

                button.classList.add("active");

                setMode(
                    button.dataset.layer
                );

            }
        );

    });


/* ============================================================
   SEARCH
   ============================================================ */

document.querySelector("#searchInput")
    .addEventListener(
        "input",
        event => {

            const query =
                event.target.value.trim().toLowerCase();

            if (!query)
                return;

            const match =
                DISTRICTS.find(feature => {

                    const p =
                        feature.properties.pravah;

                    return p.district
                        .toLowerCase()
                        .includes(query);

                });

            if (match) {

                const layer =
                    findDistrictLayer(match);

                if (layer)
                    selectDistrict(
                        match,
                        layer
                    );

            }

        }
    );


/* ============================================================
   INITIALIZE
   ============================================================ */

buildDistrictLayer();

addRainLayer();
addRiverLayer();
addEOLayer();

map.fitBounds(
    L.geoJSON(DISTRICTS).getBounds(),
    {
        padding: [20,20]
    }
);


/* ============================================================
   START WITH FIRST DISTRICT
   ============================================================ */

if (DISTRICTS.length) {

    const first =
        DISTRICTS[0];

    const firstLayer =
        findDistrictLayer(first);

    if (firstLayer)
        selectDistrict(
            first,
            firstLayer
        );

}

</script>

</body>
</html>
"""


# ============================================================
# INJECT DATA
# ============================================================

HTML = HTML.replace(
    "__GEOJSON__",
    geojson_json
)

HTML = HTML.replace(
    "__GENERATED__",
    generated
)

HTML = HTML.replace(
    "__WATCH__",
    str(counts["WATCH"])
)

HTML = HTML.replace(
    "__WARNING__",
    str(counts["WARNING"])
)

HTML = HTML.replace(
    "__CRITICAL__",
    str(counts["CRITICAL"])
)


# ============================================================
# WRITE
# ============================================================

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(HTML)


# ============================================================
# TERMINAL SUMMARY
# ============================================================

print("=" * 90)
print("PRAVAH AGENTIC DISASTER INTELLIGENCE MAP")
print("=" * 90)

print()
print("Districts:", len(merged_features))
print("LOW:", counts["LOW"])
print("WATCH:", counts["WATCH"])
print("WARNING:", counts["WARNING"])
print("CRITICAL:", counts["CRITICAL"])
print("Future ELEVATED:", future_elevated)

print()
print("Interface:")
print("  ✓ GIS-first dark interface")
print("  ✓ Large readable typography")
print("  ✓ Current risk layer")
print("  ✓ Future outlook layer")
print("  ✓ Rainfall evidence layer")
print("  ✓ River evidence layer")
print("  ✓ EO evidence layer")
print("  ✓ Terrain drainage status")
print("  ✓ Distinct observation symbols")
print("  ✓ Animated WATCH/WARNING/CRITICAL states")
print("  ✓ Integrated PRAVAH reasoning")
print("  ✓ Evidence panel")
print("  ✓ ML / SHAP explanation")
print("  ✓ Evidence-grounded agent")
print("  ✓ Agent-driven map switching")
print("  ✓ District search")
print("  ✓ No Geoman")
print("  ✓ No drawing/editing")
print("  ✓ No district popups")

print()
print("OUTPUT:")
print(OUTPUT)
print()
print("Open:")
print(f"xdg-open {OUTPUT}")
print("=" * 90)