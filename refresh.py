#!/usr/bin/env python3

"""
PRAVAH - MASTER REFRESH RUNNER

Runs the PRAVAH data pipeline in dependency order.

Required pipeline:
    1. Realtime Data Fusion
    2. Rainfall Feature Engine
    3. River Feature Engine
    4. Weather Forecast
    5. Forecast Runoff
    6. GEOGLOWS Integration
    7. Hydrology Feature Fusion
    8. VIIRS NRT Downloader
    9. VIIRS EO Feature Generation
   10. Evidence Fusion
   11. Risk Engine
   12. Hazard Map

Optional:
   13. Flood Event Detector

The runner:
    - executes stages in dependency order
    - stops when a required stage fails
    - validates expected outputs
    - validates JSON outputs
    - checks that outputs were updated during this refresh
    - handles downloader stages separately
    - reports execution time
    - prints a final pipeline summary

This file orchestrates the pipeline only.
It does not change the calculations performed by individual modules.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    LIVE_FUSED_FILE,
    RAINFALL_FILE,
    RIVER_FILE,
    WEATHER_FILE,
    FORECAST_RUNOFF_FILE,
    GEOGLOWS_FILE,
    HYDROLOGY_FILE,
    EVIDENCE_FILE,
    RISK_FILE,
    HAZARD_MAP_FILE,
    FLOOD_EVENTS_FILE,
)


# ---------------------------------------------------------------------
# PROJECT PATH
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

# VIIRS EO output is stored separately from Evidence Fusion output.
EO_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "eo"
    / "prava_eo_features.json"
)


# ---------------------------------------------------------------------
# PIPELINE SETTINGS
# ---------------------------------------------------------------------

# Run the Flood Event Detector after the required pipeline.
RUN_FLOOD_EVENT_DETECTOR = True


# ---------------------------------------------------------------------
# PIPELINE DEFINITION
# ---------------------------------------------------------------------

STAGES = [
    {
        "name": "Realtime Data Fusion",
        "module": "src.fusion.fusion_updated",
        "output": LIVE_FUSED_FILE,
        "type": "json",
    },

    {
        "name": "Rainfall Feature Engine",
        "module": "src.hydrology.rainfall_features",
        "output": RAINFALL_FILE,
        "type": "json",
    },

    {
        "name": "River Feature Engine",
        "module": "src.hydrology.river_features",
        "output": RIVER_FILE,
        "type": "json",
    },

    {
        "name": "Weather Forecast",
        "module": "src.ingestion.weather_meteo",
        "output": WEATHER_FILE,
        "type": "json",
    },

    {
        "name": "Forecast Runoff",
        "module": "src.hydrology.forecast_runoff",
        "output": FORECAST_RUNOFF_FILE,
        "type": "json",
    },

    {
        "name": "GEOGLOWS Integration",
        "module": "src.hydrology.geoglows",
        "output": GEOGLOWS_FILE,
        "type": "json",
    },

    {
        "name": "Hydrology Feature Fusion",
        "module": "src.hydrology.hydrology_fusion",
        "output": HYDROLOGY_FILE,
        "type": "json",
    },

    # -------------------------------------------------------------
    # VIIRS DOWNLOAD MUST HAPPEN BEFORE VIIRS PROCESSING
    # -------------------------------------------------------------

    {
        "name": "VIIRS NRT Downloader",
        "module": "src.eo.viirs_downloader",
        "output": None,
        "type": "downloader",
    },

    {
        "name": "VIIRS EO Feature Generation",
        "module": "src.eo.viirs_eo",
        "output": EO_FILE,
        "type": "json",
    },

    {
        "name": "Evidence Fusion",
        "module": "src.fusion.evidence_fusion",
        "output": EVIDENCE_FILE,
        "type": "json",
    },

    {
        "name": "Risk Engine",
        "module": "src.risk.risk_enginev2",
        "output": RISK_FILE,
        "type": "json",
    },

    {
        "name": "Hazard Map",
        "module": "src.mapping.hazard_map",
        "output": HAZARD_MAP_FILE,
        "type": "html",
    },
]


# ---------------------------------------------------------------------
# OPTIONAL STAGE
# ---------------------------------------------------------------------

OPTIONAL_STAGE = {
    "name": "Flood Event Detector",
    "module": "src.risk.flood_event_detector",
    "output": FLOOD_EVENTS_FILE,
    "type": "json",
}


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def absolute_path(path: Path) -> Path:
    """
    Convert configured relative paths to absolute paths.
    """
    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def validate_json(path: Path) -> tuple[bool, str]:
    """
    Check that a JSON output exists and can be parsed.
    """

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if data is None:
            return False, "JSON file contains null"

        return True, "valid JSON"

    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"

    except OSError as exc:
        return False, f"could not read file: {exc}"


def validate_output(
    stage: dict,
    started_at: float,
) -> tuple[bool, str]:
    """
    Validate the output produced by a normal pipeline stage.

    Checks:
        1. File exists
        2. File was updated during this run
        3. JSON outputs contain valid JSON
        4. HTML outputs are not empty

    Downloader stages are handled separately by run_stage().
    """

    # -------------------------------------------------------------
    # Downloader stages do not use file-output validation.
    # -------------------------------------------------------------

    if stage["type"] == "downloader":
        return True, "downloader completed successfully"

    # -------------------------------------------------------------
    # Resolve output
    # -------------------------------------------------------------

    output = absolute_path(Path(stage["output"]))

    # -------------------------------------------------------------
    # Existence
    # -------------------------------------------------------------

    if not output.exists():
        return False, f"output not found: {output}"

    if not output.is_file():
        return False, f"output path is not a file: {output}"

    # -------------------------------------------------------------
    # Freshness
    # -------------------------------------------------------------

    modified_time = output.stat().st_mtime

    if modified_time < started_at:
        return (
            False,
            "output exists but was not updated during this refresh",
        )

    # -------------------------------------------------------------
    # JSON validation
    # -------------------------------------------------------------

    if stage["type"] == "json":

        valid, message = validate_json(output)

        if not valid:
            return False, message

    # -------------------------------------------------------------
    # HTML validation
    # -------------------------------------------------------------

    if stage["type"] == "html":

        if output.stat().st_size == 0:
            return False, "HTML output is empty"

    return True, "output valid and updated"


# ---------------------------------------------------------------------
# PRINTING
# ---------------------------------------------------------------------

def print_header():
    print("=" * 88)
    print("PRAVAH - MASTER REFRESH")
    print("=" * 88)

    now = datetime.now(timezone.utc)

    print(f"Refresh started UTC : {now.isoformat()}")
    print(f"Project root        : {PROJECT_ROOT}")
    print(f"Python              : {sys.executable}")
    print()

    print("Pipeline:")
    print("  Realtime data → Features → Hydrology → VIIRS Download")
    print("  → VIIRS EO → Evidence → Risk → Event Detection → Hazard Map")

    print("=" * 88)


def print_stage_start(
    number: int,
    total: int,
    stage: dict,
):
    print()
    print("-" * 88)
    print(f"[{number:02d}/{total:02d}] {stage['name']}")
    print("-" * 88)

    print(f"Module : {stage['module']}")

    if stage["output"] is not None:
        print(
            f"Output : "
            f"{absolute_path(Path(stage['output']))}"
        )
    else:
        print("Output : raw VIIRS observation files")


# ---------------------------------------------------------------------
# REQUIRED STAGE RUNNER
# ---------------------------------------------------------------------

def run_stage(
    number: int,
    total: int,
    stage: dict,
) -> dict:
    """
    Run one required pipeline stage.

    Returns a result dictionary used by the final summary.

    Normal stages:
        - execute module
        - validate output file
        - validate freshness

    Downloader stages:
        - execute module
        - rely on exit code
        - no single output file validation
    """

    name = stage["name"]
    module = stage["module"]

    if stage["output"] is not None:
        output = absolute_path(Path(stage["output"]))
    else:
        output = None

    print_stage_start(
        number,
        total,
        stage,
    )

    start_time = time.time()

    # Timestamp used to verify that normal stages
    # really produced a new output file.
    stage_started_at = start_time

    # -------------------------------------------------------------
    # RUN MODULE
    # -------------------------------------------------------------

    try:

        subprocess.run(
            [
                sys.executable,
                "-m",
                module,
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )

    except subprocess.CalledProcessError as exc:

        elapsed = time.time() - start_time

        print()
        print(f"✗ FAILED: {name}")
        print(f"  Exit code : {exc.returncode}")
        print(f"  Time      : {elapsed:.1f}s")

        return {
            "name": name,
            "module": module,
            "output": output,
            "status": "FAILED",
            "elapsed": elapsed,
            "message": (
                f"process exited with code "
                f"{exc.returncode}"
            ),
        }

    except FileNotFoundError:

        elapsed = time.time() - start_time

        print()
        print(f"✗ FAILED: {name}")
        print("  Python executable could not be started.")

        return {
            "name": name,
            "module": module,
            "output": output,
            "status": "FAILED",
            "elapsed": elapsed,
            "message": (
                "Python executable could not be started"
            ),
        }

    # -------------------------------------------------------------
    # PROCESS COMPLETED
    # -------------------------------------------------------------

    elapsed = time.time() - start_time

    # -------------------------------------------------------------
    # DOWNLOADER VALIDATION
    # -------------------------------------------------------------

    if stage["type"] == "downloader":

        print()
        print(f"✓ PASS: {name}")
        print(f"  Time   : {elapsed:.1f}s")
        print(
            "  Check  : "
            "downloader completed successfully"
        )

        return {
            "name": name,
            "module": module,
            "output": None,
            "status": "PASS",
            "elapsed": elapsed,
            "message": (
                "downloader completed successfully"
            ),
        }

    # -------------------------------------------------------------
    # NORMAL OUTPUT VALIDATION
    # -------------------------------------------------------------

    valid, message = validate_output(
        stage,
        stage_started_at,
    )

    if not valid:

        print()
        print(
            f"✗ FAILED OUTPUT CHECK: {name}"
        )
        print(f"  Reason : {message}")
        print(f"  Time   : {elapsed:.1f}s")

        return {
            "name": name,
            "module": module,
            "output": output,
            "status": "FAILED",
            "elapsed": elapsed,
            "message": message,
        }

    # -------------------------------------------------------------
    # SUCCESS
    # -------------------------------------------------------------

    print()
    print(f"✓ PASS: {name}")

    if output is not None:
        print(f"  Output : {output}")

    print(f"  Time   : {elapsed:.1f}s")
    print(f"  Check  : {message}")

    return {
        "name": name,
        "module": module,
        "output": output,
        "status": "PASS",
        "elapsed": elapsed,
        "message": message,
    }


# ---------------------------------------------------------------------
# OPTIONAL STAGE
# ---------------------------------------------------------------------

def run_optional_stage(stage: dict) -> dict:
    """
    Run an optional stage.

    Failure here does not invalidate the required pipeline.
    """

    print()
    print("-" * 88)
    print(f"[OPTIONAL] {stage['name']}")
    print("-" * 88)

    print(f"Module : {stage['module']}")
    print(
        f"Output : "
        f"{absolute_path(Path(stage['output']))}"
    )

    start_time = time.time()

    try:

        subprocess.run(
            [
                sys.executable,
                "-m",
                stage["module"],
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )

    except subprocess.CalledProcessError as exc:

        elapsed = time.time() - start_time

        print()
        print(
            f"⚠ OPTIONAL STAGE FAILED: "
            f"{stage['name']}"
        )
        print(f"  Exit code : {exc.returncode}")
        print(f"  Time      : {elapsed:.1f}s")
        print(
            "  Required pipeline remains valid."
        )

        return {
            "name": stage["name"],
            "module": stage["module"],
            "output": absolute_path(
                Path(stage["output"])
            ),
            "status": "OPTIONAL FAILED",
            "elapsed": elapsed,
            "message": (
                f"exit code {exc.returncode}"
            ),
        }

    elapsed = time.time() - start_time

    valid, message = validate_output(
        stage,
        start_time,
    )

    if valid:

        print()
        print(
            f"✓ OPTIONAL PASS: "
            f"{stage['name']}"
        )
        print(
            f"  Output : "
            f"{absolute_path(Path(stage['output']))}"
        )
        print(f"  Time   : {elapsed:.1f}s")

        return {
            "name": stage["name"],
            "module": stage["module"],
            "output": absolute_path(
                Path(stage["output"])
            ),
            "status": "PASS",
            "elapsed": elapsed,
            "message": message,
        }

    print()
    print(
        f"⚠ OPTIONAL OUTPUT CHECK FAILED: "
        f"{stage['name']}"
    )
    print(f"  Reason : {message}")

    return {
        "name": stage["name"],
        "module": stage["module"],
        "output": absolute_path(
            Path(stage["output"])
        ),
        "status": "OPTIONAL FAILED",
        "elapsed": elapsed,
        "message": message,
    }


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

def print_summary(
    results: list[dict],
    start_time: float,
):
    """
    Print final pipeline summary.
    """

    elapsed = time.time() - start_time
    finished = datetime.now(timezone.utc)

    print()
    print()
    print("=" * 88)
    print("PRAVAH MASTER REFRESH SUMMARY")
    print("=" * 88)

    print(
        f"Finished UTC : "
        f"{finished.isoformat()}"
    )

    print(
        f"Total time   : "
        f"{elapsed:.1f}s"
    )

    print()

    print("STAGES")
    print("-" * 88)

    for result in results:

        status = result["status"]

        if status == "PASS":
            symbol = "✓"

        elif status == "OPTIONAL FAILED":
            symbol = "⚠"

        else:
            symbol = "✗"

        print(
            f"{symbol} "
            f"{result['name']:<35} "
            f"{status:<16} "
            f"{result['elapsed']:.1f}s"
        )

    print()

    # -------------------------------------------------------------
    # Required pipeline result
    # -------------------------------------------------------------

    required_results = [
        result
        for result in results
        if result["status"] != "OPTIONAL FAILED"
    ]

    required_failed = any(
        result["status"] == "FAILED"
        for result in required_results
    )

    if required_failed:

        print("RESULT : FAILED")
        print(
            "The required pipeline did not "
            "complete successfully."
        )

    else:

        print("RESULT : SUCCESS")
        print(
            "All required PRAVAH pipeline "
            "stages completed successfully."
        )

    print("=" * 88)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    pipeline_start = time.time()

    print_header()

    results = []

    total_stages = len(STAGES)

    # -------------------------------------------------------------
    # REQUIRED PIPELINE
    # -------------------------------------------------------------

    for index, stage in enumerate(
        STAGES,
        start=1,
    ):

        result = run_stage(
            index,
            total_stages,
            stage,
        )

        results.append(result)

        # ---------------------------------------------------------
        # STOP REQUIRED PIPELINE ON FAILURE
        # ---------------------------------------------------------

        if result["status"] == "FAILED":

            print()
            print("=" * 88)
            print(
                "PIPELINE STOPPED"
            )
            print("=" * 88)

            print(
                f"Failed stage: "
                f"{stage['name']}"
            )

            print(
                "Downstream stages were not executed."
            )

            break

    # -------------------------------------------------------------
    # CHECK WHETHER REQUIRED PIPELINE COMPLETED
    # -------------------------------------------------------------

    required_pipeline_complete = (
        len(results) == len(STAGES)
        and all(
            result["status"] == "PASS"
            for result in results
        )
    )

    # -------------------------------------------------------------
    # OPTIONAL FLOOD EVENT DETECTOR
    # -------------------------------------------------------------

    if (
        RUN_FLOOD_EVENT_DETECTOR
        and required_pipeline_complete
    ):

        optional_result = run_optional_stage(
            OPTIONAL_STAGE
        )

        results.append(optional_result)

    elif (
        RUN_FLOOD_EVENT_DETECTOR
        and not required_pipeline_complete
    ):

        print()
        print(
            "Flood Event Detector skipped "
            "because the required pipeline failed."
        )

    # -------------------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------------------

    print_summary(
        results,
        pipeline_start,
    )

    # -------------------------------------------------------------
    # PROCESS EXIT CODE
    # -------------------------------------------------------------

    required_failed = any(
        result["status"] == "FAILED"
        for result in results
    )

    if required_failed:
        sys.exit(1)

    sys.exit(0)


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()