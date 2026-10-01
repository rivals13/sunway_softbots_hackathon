# PRAVAH 🌊

### AI-Assisted Early Warning System for Flood and River Hazards in Nepal

PRAVAH is an open-source, multi-modal flood intelligence and early-warning system designed to help identify developing flood and river hazards before they become disasters.

It brings together **satellite rainfall, ground observations, river conditions, terrain, hydrological models, and geospatial data** into a unified system for monitoring and assessing flood risk across Nepal.

The goal is simple:

> **Turn fragmented environmental data into timely, location-specific flood intelligence that can support early action.**

---

## 🚀 Why PRAVAH?

Flood risk information is often distributed across different sources and systems.

Rainfall observations, satellite precipitation, river measurements, terrain data, hydrological forecasts, and disaster records may exist independently, making it difficult to obtain a timely and localized understanding of an emerging hazard.

PRAVAH addresses this problem by creating a common geospatial and temporal layer where these sources can be combined and analyzed.

### PRAVAH focuses on:

* 🌧️ Rainfall monitoring
* 🌊 River and flow conditions
* 🛰️ Earth observation data
* 🗺️ Geospatial risk analysis
* ⛰️ Terrain and drainage characteristics
* 📊 Hydrological indicators
* 🤖 AI-assisted interpretation
* 🚨 Continuous flood-risk monitoring

---

## 🧠 How PRAVAH Works

PRAVAH follows a multi-stage data and intelligence pipeline:

```text
┌─────────────────────────────────────────────┐
│              DATA SOURCES                   │
│                                             │
│  Satellite Rainfall     Ground Observations │
│  River Data             Weather Data       │
│  Earth Observation      Terrain / DEM      │
│  Disaster Records       Hydrological Data  │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│        SPATIAL & TEMPORAL ALIGNMENT         │
│                                             │
│  • Geographic normalization                 │
│  • Time alignment                            │
│  • District / watershed mapping              │
│  • Data quality validation                   │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│             MULTI-MODAL FUSION              │
│                                             │
│  Rainfall + River + Terrain + Hydrology    │
│              + EO Indicators                │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│          HYDROLOGICAL ANALYSIS              │
│                                             │
│  Runoff estimation                          │
│  River pressure                             │
│  Rainfall accumulation                      │
│  Antecedent conditions                      │
│  Forecast indicators                        │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│             RISK ASSESSMENT                 │
│                                             │
│       Normal → Warning → Danger             │
│                                             │
│      Continuous spatial monitoring           │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│          PRAVAH INTELLIGENCE LAYER          │
│                                             │
│  Maps • Evidence • Alerts • AI Queries     │
└─────────────────────────────────────────────┘
```

---

## 🛰️ Data Sources

PRAVAH is designed to work with multiple environmental and geospatial data sources.

| Data                      | Purpose                                      |
| ------------------------- | -------------------------------------------- |
| **NASA IMERG**            | Satellite-based precipitation                |
| **BIPAD / disaster data** | Ground observations and disaster information |
| **River observations**    | Monitoring river conditions                  |
| **GEOGLOWS**              | Hydrological flow information                |
| **SRTM DEM**              | Elevation and terrain analysis               |
| **OpenStreetMap**         | Geographic and infrastructure context        |
| **Earth Observation**     | Additional flood and surface indicators      |
| **Weather data**          | Meteorological context                       |

The architecture is designed so additional data providers can be incorporated without redesigning the entire system.

---

## 🧮 Hydrological Intelligence

PRAVAH incorporates hydrological reasoning rather than relying only on a machine-learning prediction.

One component of the current prototype uses the **SCS Curve Number method** to estimate runoff from rainfall.

For rainfall exceeding the initial abstraction:

```text
Q = (P - Ia)² / (P - Ia + S)
```

where:

* `Q` = runoff depth
* `P` = accumulated rainfall
* `Ia` = initial abstraction
* `S` = potential maximum retention

These calculations are combined with rainfall conditions, river behavior, terrain characteristics, and other indicators to derive localized risk states.

---

## 🗺️ Geospatial Intelligence

PRAVAH uses geographic boundaries and spatial processing to associate environmental observations with affected administrative areas.

The system supports analysis across Nepal's administrative hierarchy, including:

```text
Nepal
   ↓
Province
   ↓
District
   ↓
Municipality
   ↓
Ward
```

This allows the system to move from a national overview to a more localized understanding of where risk is developing.

---

## 🤖 AI-Assisted Intelligence

PRAVAH is not intended to replace hydrological or disaster-management expertise.

The AI layer is designed as an **intelligence interface** over the underlying data and analytical pipeline.

It can help users interact with information using natural-language questions such as:

> "Which districts currently show elevated flood risk?"

or:

> "Why is this area classified as high risk?"

The system can connect these questions to the underlying observations and spatial evidence rather than treating the language model as the source of the risk assessment itself.

---

## 🚨 Risk Monitoring

PRAVAH represents developing conditions through continuously updated risk states.

The current prototype uses:

```text
NORMAL
   ↓
WARNING
   ↓
DANGER
```

Risk classification can incorporate multiple signals rather than depending on a single rainfall threshold.

This allows future versions of PRAVAH to incorporate additional evidence such as:

* rainfall accumulation
* rainfall intensity
* antecedent rainfall
* river level / flow
* rate of river rise
* forecast flow
* terrain
* drainage characteristics
* satellite flood observations
* historical hazard information

---

## 🏗️ Architecture

The project is organized into modular components for data acquisition, processing, hydrology, fusion, and visualization.

```text
PRAVAH
│
├── src/
│   ├── config.py
│   │
│   ├── eo/
│   │   └── Earth observation processing
│   │
│   ├── fusion/
│   │   └── Multi-source data fusion
│   │
│   └── hydrology/
│       ├── Rainfall analysis
│       ├── Runoff estimation
│       ├── River analysis
│       └── GEOGLOWS integration
│
├── data/
│   ├── boundaries/
│   └── processed/
│
├── outputs/
│   └── events/
│
├── experiments/
│
├── tests/
│
├── scripts/
│
└── archive/
```

---

## 🛠️ Technology Stack

### Data & Processing

* Python
* NumPy
* Pandas
* Requests
* Shapely
* GeoPandas
* Raster processing tools

### Geospatial

* GeoJSON
* OpenStreetMap
* Folium
* GeoServer
* PostGIS
* Spatial analysis

### Hydrology

* SCS Curve Number
* GEOGLOWS
* Rainfall-runoff analysis
* River-flow indicators
* Terrain and drainage analysis

### AI

* AI-assisted natural-language querying
* Evidence-based interpretation
* Multi-modal data reasoning

---

## 📂 Repository Structure

```text
.
├── archive/
├── experiments/
├── outputs/
├── scripts/
├── src/
│   ├── eo/
│   ├── fusion/
│   └── hydrology/
├── tests/
├── refresh.py
├── terrain_slope.py
├── test_river_drainage_alignment.py
├── update_pravah_agent_ui.py
└── tasks.txt
```

---

## 🌍 Intended Users

PRAVAH is being developed with disaster-risk and emergency-response use cases in mind.

Potential users include:

* Local governments
* Disaster management authorities
* Emergency response teams
* Hydrological and meteorological organizations
* Researchers
* NGOs and humanitarian organizations
* Communities in flood-prone areas

The system is intended to support **early decision-making and situational awareness**, not to replace official warnings or emergency-management procedures.

---

## 🔬 Current Development

PRAVAH began as a prototype developed for the **SOFTBOTS AI Hackathon** and is now being developed further toward a more realistic, deployable disaster-intelligence system.

Current development areas include:

* Improving multi-source data fusion
* Increasing temporal freshness of observations
* Improving river and rainfall alignment
* Integrating additional Earth Observation data
* Improving hydrological modelling
* Incorporating terrain and drainage characteristics
* Building a production-oriented geospatial architecture
* Improving evidence-based AI interaction
* Evaluating the gap between prototype capabilities and real-world disaster-management requirements

The project is intentionally being developed iteratively, with real-world requirements and expert feedback guiding future improvements.

---

## 🧪 Project Status

**Status: Active Development**

PRAVAH is currently a research and development project.

The existing implementation should be considered a **prototype** and should not be used as the sole basis for emergency decisions.

Future development will focus on validation, reliability, data quality, operational deployment, and integration with authoritative disaster-management systems.

---

## 🤝 Contributing

Contributions, ideas, testing, research, and technical feedback are welcome.

If you are interested in:

* hydrology
* GIS
* Earth observation
* disaster risk reduction
* AI/ML
* data engineering
* backend systems
* frontend visualization

feel free to explore the repository and open an issue or pull request.

---

## 📜 Open Source

PRAVAH is developed as an open-source project with the goal of making disaster-monitoring technology more accessible for research, experimentation, and future real-world applications.

---

## 👥 Team 0xNull

PRAVAH is developed by **Team 0xNull**.

The project originated as part of the **SOFTBOTS AI Hackathon** and is being continued as an open-source development effort.

---
