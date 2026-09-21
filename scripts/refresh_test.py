import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]


STEPS = [
    ("BIPAD realtime", "src.ingestion.bip_realtime"),
    ("Rainfall features", "src.hydrology.rainfall_features"),
    ("Forecast runoff", "src.hydrology.forecast_runoff"),
]


def run_step(name, module):
    print("\n" + "=" * 80)
    print(f"RUNNING: {name}")
    print("=" * 80)

    start = datetime.now(timezone.utc)

    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_ROOT,
    )

    end = datetime.now(timezone.utc)

    print("\n" + "-" * 80)
    print(f"{name} finished")
    print(f"Exit code : {result.returncode}")
    print(f"Started   : {start.isoformat()}")
    print(f"Finished  : {end.isoformat()}")
    print("-" * 80)

    if result.returncode != 0:
        print(f"\nERROR: {name} failed.")
        return False

    return True


def main():

    print("=" * 80)
    print("PRAVAH REFRESH TEST")
    print("=" * 80)

    print("Project root:")
    print(PROJECT_ROOT)

    print("\nPython:")
    print(sys.executable)

    for name, module in STEPS:

        success = run_step(name, module)

        if not success:
            print("\nPIPELINE STOPPED.")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("PRAVAH REFRESH TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
